# Usage Examples

Practical examples showing every option the script supports, with plain-language explanations of what each one does.

---

## The basic pattern

```bash
python pdf_to_audio.py <path-to-pdf> [options]
```

The PDF path is the only required argument. Everything else is optional.

---

## Examples

### 1. Simplest possible command

```bash
python pdf_to_audio.py paper.pdf --full
```

**What it does:**
- Converts the entire PDF to one MP3 file
- Uses default settings: best-quality voice, 192 kbps, normal speed
- Saves `paper.mp3` in the same folder as `paper.pdf`

---

### 2. Use a full absolute path (recommended for long paths)

```bash
python pdf_to_audio.py '/Users/narslan/Desktop/starbase/library/zotero-pdfs/paper.pdf' --full
```

**What it does:**
- Same as above, just using the full path to the file
- Wrap the path in quotes if it contains spaces

---

### 3. Skip content you don't want read aloud

```bash
python pdf_to_audio.py paper.pdf --full --exclude all
```

**What `--exclude all` does:**
- `footnotes` — skips numbered footnote blocks at the bottom of pages (e.g. `¹ See also Smith et al.`)
- `references` — drops everything from the "References" or "Bibliography" heading to the end
- `tables` — skips table regions detected on each page

You can also exclude specific parts instead of everything:

```bash
python pdf_to_audio.py paper.pdf --full --exclude footnotes references
python pdf_to_audio.py paper.pdf --full --exclude tables
```

---

### 4. Adjust audio quality

```bash
# Smaller file, faster to export (96 kbps)
python pdf_to_audio.py paper.pdf --full --quality low

# Best quality, larger file (192 kbps) — this is the default
python pdf_to_audio.py paper.pdf --full --quality high
```

**What `--quality` controls:**
- This only affects the final MP3 file size, not the voice quality during generation
- `high` (192 kbps) ≈ 10 MB per hour of audio
- `low` (96 kbps) ≈ 5 MB per hour of audio
- For listening on a phone or laptop, `low` is indistinguishable from `high`

---

### 5. Change the narration speed

```bash
# Slightly slower — good for dense academic text
python pdf_to_audio.py paper.pdf --full --speed 0.85

# Normal speed (default)
python pdf_to_audio.py paper.pdf --full --speed 1.0

# Faster — good for familiar material
python pdf_to_audio.py paper.pdf --full --speed 1.2
```

**What `--speed` controls:**
- `1.0` is the voice's natural pace
- Values below `1.0` slow it down (e.g. `0.85` = 15% slower)
- Values above `1.0` speed it up (e.g. `1.2` = 20% faster)
- Recommended range: `0.75` to `1.3` — outside this range quality degrades

---

### 6. Change the voice

```bash
python pdf_to_audio.py paper.pdf --full --voice af_bella
```

**What `--voice` controls:**
- Selects which Kokoro voice is used for narration
- The voice file is downloaded automatically the first time you use it
- Default is `af_heart` — Kokoro's highest-rated voice

Available American English female voices:

| Voice ID | Character |
|----------|-----------|
| `af_heart` | Warm, clear (default) |
| `af_bella` | Expressive |
| `af_nicole` | Soft |
| `af_sarah` | Natural |
| `af_sky` | Bright |

---

### 7. Save the output to a specific location

```bash
# Save to a specific folder
python pdf_to_audio.py paper.pdf --full --output ~/Desktop/audiobooks/

# Save as a specific filename
python pdf_to_audio.py paper.pdf --full --output ~/Desktop/audiobooks/my-paper.mp3
```

**What `--output` controls:**
- If you give a folder path, the file is saved there with an auto-generated name
- If you give a file path (ending in `.mp3`), it saves with exactly that name
- If omitted, the MP3 is saved in the same folder as the PDF

---

### 8. Everything at once — the "kitchen sink" command

This is the command used during development and testing:

```bash
python pdf_to_audio.py '/Users/narslan/Desktop/starbase/library/zotero-pdfs/paper.pdf' \
  --full \
  --exclude all \
  --quality low \
  --speed 1.0 \
  --voice af_heart \
  --output ~/Desktop/audiobooks/
```

**What each flag does, in plain terms:**

| Flag | Value | Meaning |
|------|-------|---------|
| `--full` | — | Don't ask about chapters, just convert everything |
| `--exclude all` | `all` | Skip footnotes, references, and tables |
| `--quality` | `low` | Smaller MP3 file (96 kbps) |
| `--speed` | `1.0` | Normal narration speed |
| `--voice` | `af_heart` | Default voice |
| `--output` | `~/Desktop/audiobooks/` | Save there instead of next to the PDF |

---

### 9. Chapter-by-chapter mode (interactive)

```bash
python pdf_to_audio.py book.pdf
```

**What happens:**
- The script looks for a table of contents embedded in the PDF
- If found, it shows the chapter list and asks which ones to convert
- If not found, it asks you to type page ranges manually
- Produces one MP3 per chapter by default

```bash
# Merge selected chapters into one file instead
python pdf_to_audio.py book.pdf --combine
```

---

## What the script prints when it finishes

```
  Converted : paper.pdf
  Words     : 7,768
  Options   : voice=af_heart, quality=low, speed=1.0x, excluded=footnotes, references, tables
  Audio     : 48.3 min
  Time taken: 22.1 min
  Saved to  : /Users/narslan/Desktop/audiobooks
```

- **Words** — how many words were extracted from the PDF after filtering
- **Audio** — the total duration of the resulting MP3
- **Time taken** — how long the conversion took (CPU-only is slow; expect 20–40% of audio duration)
- **Saved to** — the folder where the MP3 was written
