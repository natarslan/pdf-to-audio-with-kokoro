# pdf-to-audio-with-kokoro

Convert PDF files to MP3 audio using [Kokoro](https://github.com/hexgrad/kokoro), a high-quality open-source text-to-speech engine.

## Requirements

**Python packages**
```bash
pip install -r requirements.txt
```

**ffmpeg** (for MP3 encoding) — must be on your PATH:
```bash
brew install ffmpeg          # macOS
sudo apt install ffmpeg      # Ubuntu / Debian
# Windows: https://ffmpeg.org/download.html
```

## Installation

```bash
git clone https://github.com/natarslan/pdf-to-audio-with-kokoro.git
cd pdf-to-audio-with-kokoro
pip install -r requirements.txt
```

---

## Usage

### 1. Convert an entire PDF to one MP3

The simplest way — no questions asked, no chapter splitting, just the whole PDF as a single file.

```bash
python pdf_to_audio.py book.pdf --full
```

Output: `book.mp3` saved in the same folder as the PDF.

When finished, the script prints a summary:
```
  Converted : book.pdf
  Words     : 7,768
  Options   : voice=af_heart, quality=high, speed=1.0x, excluded=none
  Audio     : 48.3 min
  Time taken: 22.1 min
  Saved to  : /path/to/folder
```

---

### 2. Convert with custom speed, quality, or output location

```bash
python pdf_to_audio.py book.pdf --full --quality low --speed 0.9 --output ~/audiobooks/book.mp3
```

- `--quality low` — smaller file (96 kbps instead of the default 192 kbps)
- `--speed 0.9` — slightly slower narration (1.0 is normal, 1.2 is faster)
- `--output` — where to save the file; defaults to the same folder as the PDF

---

### 3. Skip tables, footnotes, and/or the references section

Useful for academic papers where you don't want the script reading out citation lists or table data.

```bash
# Skip everything at once
python pdf_to_audio.py paper.pdf --full --exclude all

# Or pick specific ones
python pdf_to_audio.py paper.pdf --full --exclude footnotes references
```

Available exclusions: `tables`, `footnotes`, `references`, `parentheses`, `all`

---

### 4. Convert chapter by chapter (interactive)

Run without `--full` and the script will automatically look for a table of contents inside the PDF.

```bash
python pdf_to_audio.py book.pdf
```

**If the PDF has an embedded table of contents**, the script shows the detected chapters and asks which ones to convert:

```
Scanning for chapters in: book.pdf
  Auto-detected 12 chapters from the embedded table of contents.

  Found 12 chapters:

     1.  Introduction                                     p.1–15
     2.  Background                                       p.16–35
     3.  Methods                                          p.36–55
    ...
    12.  Conclusion                                       p.180–195

  Which chapters? (e.g. 1,3,5-7  or  'all'  — default: all): 1,3
```

Press **Enter** to select all chapters, or type numbers like `1,3,5-7` to pick specific ones.

**If no table of contents is found**, the script asks you to enter page ranges manually:

```
  No embedded table of contents found.
  Enter page ranges manually, one per line.
  Format:  Title: start-end   (e.g.  Introduction: 1-15)

  Chapter 1: Introduction: 1-15
  Chapter 2: Methods: 36-55
  Chapter 3:                      ← blank line to finish
```

**Output — by default, one MP3 per chapter:**
```
book_01_Introduction.mp3
book_03_Methods.mp3
```

---

### 5. Convert selected chapters into one combined MP3

Add `--combine` to merge everything into a single file instead of separate chapter files.

```bash
python pdf_to_audio.py book.pdf --combine
```

Output: `book_combined.mp3`

---

## All options

| Option | Default | Description |
|--------|---------|-------------|
| `--full` | off | Convert the entire PDF as one MP3, skipping chapter selection |
| `--combine` | off | Merge all selected chapters into one MP3 (chapter mode only) |
| `--exclude` | none | Skip content: `tables` `footnotes` `references` `parentheses` `all` |
| `--quality` | `high` | `high` = 192 kbps  \|  `low` = 96 kbps |
| `--speed` | `1.0` | Speech speed — `0.9` slower, `1.2` faster |
| `--voice` | `af_heart` | Kokoro voice ID (see below) |
| `--output` | PDF's folder | Output file (single MP3) or folder (chapter mode) |

---

## Voices

The default voice is **`af_heart`** — Kokoro's highest-rated female American English voice.
Other options: `af_bella`, `af_nicole`, `af_sarah`, `af_sky`.

To use a different voice:
```bash
python pdf_to_audio.py book.pdf --full --voice af_bella
```

---

## How content filtering works

| Filter | What it removes |
|--------|----------------|
| `tables` | Detects table regions spatially (PyMuPDF) and skips their text |
| `footnotes` | Skips numbered/symbol text blocks at the bottom of each page |
| `references` | Finds the last "References" or "Bibliography" heading and cuts from there |
| `parentheses` | Removes parenthetical content that contains a number or `n.d` — targets inline citations like `(Smith et al., 2020)` or `(n.d.)` while keeping plain prose like `(see discussion above)` |
