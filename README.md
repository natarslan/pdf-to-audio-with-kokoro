# pdf-to-audio-with-kokoro

Convert PDF files to MP3 audio using [Kokoro](https://github.com/hexgrad/kokoro), a high-quality open-source TTS engine. Supports interactive chapter selection, automatic table-of-contents detection, and content filtering.

## Features

- **Chapter selection** — auto-detects chapters from the PDF's embedded table of contents; falls back to manual page-range entry if none is found
- **One MP3 per chapter** by default; `--combine` merges everything into a single file
- **Content filtering** — optionally skip tables, footnotes, and/or the references section
- **High-quality voice** — defaults to `af_heart` (Kokoro Grade A, female, American English)
- **PDF extraction** — uses PyMuPDF for accurate spatial text extraction (pypdf as fallback)

## Requirements

**Python packages**
```bash
pip install -r requirements.txt
```

**System dependency** — [ffmpeg](https://ffmpeg.org/download.html) must be on your PATH (used for MP3 encoding):
```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg

# Windows — download from https://ffmpeg.org/download.html
```

## Installation

```bash
git clone https://github.com/natarslan/pdf-to-audio-with-kokoro.git
cd pdf-to-audio-with-kokoro
pip install -r requirements.txt
```

## Usage

```bash
python pdf_to_audio.py <path/to/file.pdf> [options]
```

Running the script is interactive — it will guide you through chapter selection before generating any audio.

### Basic example

```bash
python pdf_to_audio.py book.pdf
```

**If the PDF has an embedded table of contents:**
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

  [1/2] Introduction  (p.1–15)
        Words : 3,421  |  Duration: 12.3 min
        Saved : book_01_Introduction.mp3

  [2/2] Methods  (p.36–55)
        Words : 5,102  |  Duration: 18.7 min
        Saved : book_03_Methods.mp3

Done.  2 file(s) saved to: /path/to/book/
```

**If no table of contents is found**, the script asks for page ranges manually:
```
  No embedded table of contents found.
  Enter page ranges manually, one per line.
  Format:  Title: start-end   (e.g.  Introduction: 1-15)

  Chapter 1: Introduction: 1-15
  Chapter 2: Methods: 36-55
  Chapter 3:                      ← blank line to finish
```

### Combine chapters into one file

```bash
python pdf_to_audio.py book.pdf --combine
# → book_combined.mp3
```

### Skip tables, footnotes, and references

```bash
# All at once
python pdf_to_audio.py paper.pdf --exclude all

# Or pick specific ones
python pdf_to_audio.py paper.pdf --exclude footnotes references
```

### Lower quality for smaller file size

```bash
python pdf_to_audio.py book.pdf --quality low
```

### Custom output location

```bash
# Multi-chapter: treated as an output directory
python pdf_to_audio.py book.pdf --output ~/audiobooks/

# Combined: treated as the output file
python pdf_to_audio.py book.pdf --combine --output ~/audiobooks/book.mp3
```

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--combine` | off | Merge all selected chapters into one MP3 |
| `--exclude` | none | Skip content: `tables` `footnotes` `references` `all` |
| `--quality` | `high` | MP3 bitrate: `high` = 192 kbps, `low` = 96 kbps |
| `--speed` | `1.0` | Speech speed multiplier (e.g. `0.9` = slightly slower) |
| `--voice` | `af_heart` | Kokoro voice ID |
| `--output` | PDF's directory | Output directory (multi-chapter) or file path (`--combine`) |

## Output file naming

| Mode | Filename |
|------|----------|
| One file per chapter | `<pdf_stem>_01_<Title>.mp3`, `<pdf_stem>_02_<Title>.mp3`, … |
| Combined | `<pdf_stem>_combined.mp3` |

## How content filtering works

| Filter | Method |
|--------|--------|
| `tables` | PyMuPDF detects table bounding boxes and skips overlapping text blocks; tab/pipe heuristics when using pypdf |
| `footnotes` | Skips text blocks in the bottom 15 % of each page that match numbered/symbol footnote patterns |
| `references` | Finds the last "References" / "Bibliography" heading and truncates the document there |

## Voices

The default voice is `af_heart` — Kokoro's highest-rated female American English voice (Grade A). Other available female voices include `af_bella` (Grade A−), `af_nicole`, `af_sarah`, and `af_sky`. Pass any voice ID with `--voice`.

## Dependencies

| Package | Purpose |
|---------|---------|
| `kokoro` | TTS engine |
| `PyMuPDF` | PDF text extraction and table/footnote detection |
| `pypdf` | Fallback PDF extraction |
| `soundfile` | WAV intermediate file |
| `pydub` | WAV → MP3 conversion |
| `numpy` | Audio array handling |
| `ffmpeg` *(system)* | MP3 encoding (required by pydub) |
