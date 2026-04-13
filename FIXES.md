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
