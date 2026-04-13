# Bug Fixes & Changes

A log of errors encountered when running the code locally, why they happened, and how they were fixed. Written for beginners.

---

## Fix 1 — `TypeError: '>' not supported between instances of 'builtin_function_or_method' and 'int'`

**Date:** 2026-04-14  
**File:** `pdf_to_audio.py`, line 375 (in the `synthesise` function)

### What the error said

```
TypeError: '>' not supported between instances of 'builtin_function_or_method' and 'int'
```

### What was happening

The `synthesise` function calls the Kokoro text-to-speech pipeline, which processes the text and yields audio chunks. After getting each audio chunk, the code was checking whether the chunk was non-empty before saving it:

```python
if audio is not None and audio.size > 0:
```

The problem: `.size` behaves differently depending on what kind of object `audio` is.

- In **NumPy** (a popular math/array library), `.size` is a **property** — it just gives you a number, like `1024`.
- In **PyTorch** (the deep learning library Kokoro uses under the hood), `.size` is a **method** — it's a function you have to *call*, like `.size()`. Without the parentheses, you just get the function object itself, not a number.

So `audio.size` was returning something like `<built-in method size of Tensor>` instead of a number. Python then tried to compare that with `> 0`, which makes no sense, and crashed.

This is a subtle incompatibility: the code was written assuming NumPy arrays, but the version of Kokoro installed returns PyTorch tensors instead.

### The fix

Convert the audio chunk to a NumPy array first, before doing the size check:

```python
# Before (broken):
if audio is not None and audio.size > 0:
    parts.append(audio.astype(np.float32))

# After (fixed):
if audio is not None:
    audio_np = audio.numpy() if hasattr(audio, "numpy") else np.asarray(audio)
    if audio_np.size > 0:
        parts.append(audio_np.astype(np.float32))
```

- `hasattr(audio, "numpy")` checks whether the object is a PyTorch tensor (tensors have a `.numpy()` method for converting to NumPy).
- If it is a tensor, we call `.numpy()` to convert it.
- If it's already a NumPy array (or something else), we use `np.asarray()` as a safe fallback.
- Once it's a NumPy array, `.size` works correctly as a plain number.

---

## Fix 2 — Three warnings printed during audio generation

**Date:** 2026-04-14  
**File:** `pdf_to_audio.py` (imports section + `synthesise` function)

### What the warnings said

```
WARNING: Defaulting repo_id to hexgrad/Kokoro-82M. Pass repo_id='hexgrad/Kokoro-82M' to suppress this warning.

UserWarning: dropout option adds dropout after all but last recurrent layer,
so non-zero dropout expects num_layers greater than 1, but got dropout=0.2 and num_layers=1

FutureWarning: `torch.nn.utils.weight_norm` is deprecated in favor of
`torch.nn.utils.parametrizations.weight_norm`.
```

### What each one meant and where it came from

**Warning 1 — `repo_id` not specified**

This came from our code. When initializing the Kokoro pipeline, we wrote:

```python
pipeline = KPipeline(lang_code="a")
```

Kokoro needs to know which model to download from Hugging Face (an online model repository). We didn't tell it, so it fell back to a default and printed a reminder to be explicit. Not harmful, but noisy and easy to fix.

**Warning 2 — dropout / num_layers**

This comes from deep inside PyTorch (the machine learning library), triggered when Kokoro loads its neural network model. It's a design choice in Kokoro's model architecture that PyTorch is flagging as unusual. We have no control over this — it would need to be fixed by the Kokoro developers.

**Warning 3 — weight_norm deprecated**

Also comes from inside PyTorch during model loading. It means PyTorch is notifying that an internal function Kokoro uses (`weight_norm`) is old and will eventually be removed. Again, this needs to be fixed by the Kokoro developers, not us.

### The fixes

**Warning 1** — pass the model name explicitly so Kokoro stops guessing:

```python
# Before:
pipeline = KPipeline(lang_code="a")

# After:
pipeline = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
```

**Warnings 2 & 3** — suppress them using Python's built-in `warnings` module. This tells Python: "I know about these warnings, they're not from my code, don't show them." Added near the top of the file:

```python
import warnings

warnings.filterwarnings(
    "ignore",
    message="dropout option adds dropout after all but last recurrent layer",
    category=UserWarning,
)
warnings.filterwarnings(
    "ignore",
    message="`torch.nn.utils.weight_norm` is deprecated",
    category=FutureWarning,
)
```

This is targeted suppression — it only silences these specific messages, not all warnings globally.

---

## Fix 3 — Code appears frozen during audio generation

**Date:** 2026-04-14  
**File:** `pdf_to_audio.py`, `synthesise` function

### What was happening

After printing the model-loading messages, the terminal went silent and nothing appeared to happen. The program looked completely stuck.

It wasn't actually frozen — it was working. Kokoro was processing the text paragraph by paragraph on the CPU, which is slow. A 7,768-word document can take 10–30 minutes to convert. But the code had no progress output inside the processing loop, so there was no way to tell if it was running or hung.

### Why no output?

Python buffers terminal output. Even if you write something with `print()`, it may not appear on screen immediately — Python holds it in a buffer and flushes it in batches. This makes progress messages invisible mid-loop unless you explicitly flush after each one.

### The fix

Add a live progress line inside the `synthesise` loop that updates after each paragraph (chunk) is converted:

```python
# Before (silent):
for _g, _p, audio in pipeline(text, ...):
    if audio is not None:
        ...

# After (shows progress):
chunk_count = 0
seconds_done = 0.0
print("  Processing chunks: 0 done", end="", flush=True)
for _g, _p, audio in pipeline(text, ...):
    if audio is not None:
        audio_np = ...
        if audio_np.size > 0:
            ...
            chunk_count += 1
            seconds_done += audio_np.size / SAMPLE_RATE
            print(f"\r  Processing chunks: {chunk_count} done  (~{seconds_done:.0f}s of audio so far)", end="", flush=True)
print()
```

Key details:
- `end=""` prevents a newline so the line can be overwritten in place.
- `\r` (carriage return) moves the cursor back to the start of the line, so each update overwrites the previous one instead of flooding the terminal.
- `flush=True` forces Python to display the output immediately instead of buffering it.

---
