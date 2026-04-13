# pdf-to-audio-with-kokoro

Convert PDF files to MP3 audio using the [Kokoro TTS](https://github.com/hexgrad/kokoro) engine.

## Features

- High-quality neural text-to-speech via Kokoro
- Optional exclusion of tables, footnotes, and references/bibliography
- Adjustable speech speed and MP3 quality
- Works on desktop (Linux/macOS/Windows) and **Android via Termux**

## Desktop Installation

```bash
pip install kokoro soundfile pydub PyMuPDF
# system dependency:
# Ubuntu/Debian: sudo apt install ffmpeg espeak-ng
# macOS:         brew install ffmpeg
```

## Usage

```bash
# Basic conversion
python pdf_to_audio.py paper.pdf

# Skip tables, footnotes, and references
python pdf_to_audio.py paper.pdf --exclude tables footnotes references

# Custom output path, lower quality (smaller file)
python pdf_to_audio.py paper.pdf --output ~/audio/paper.mp3 --quality low

# Slightly faster speech
python pdf_to_audio.py paper.pdf --speed 1.2

# Different voice
python pdf_to_audio.py paper.pdf --voice am_adam
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--exclude SECTION [...]` | none | Skip `tables`, `footnotes`, `references`, or `all` |
| `--quality {high,low}` | `high` | MP3 bitrate: high = 192 kbps, low = 96 kbps |
| `--speed RATE` | `1.0` | Speech speed multiplier (e.g. `0.9` = slower) |
| `--voice VOICE` | `af_heart` | Kokoro voice ID |
| `--output PATH` | next to PDF | Custom output path for the MP3 |

---

## Android (Termux) Installation

The script works on Android through [Termux](https://termux.dev). It uses
`kokoro-onnx` instead of the full `kokoro` package, which means **no PyTorch
is required** — lighter and faster to set up on mobile.

### Step 1 — Install Termux

Download **Termux from F-Droid** (not the Play Store version, which is outdated):
https://f-droid.org/packages/com.termux/

### Step 2 — Clone the repository

Open Termux and run:

```bash
pkg install git
git clone https://github.com/natarslan/pdf-to-audio-with-kokoro
cd pdf-to-audio-with-kokoro
```

### Step 3 — Run the setup script

```bash
bash termux_setup.sh
```

This will:
1. Install `python`, `ffmpeg`, and `libsndfile` via `pkg`
2. Install Python packages (`kokoro-onnx`, `pydub`, `PyMuPDF`, etc.) via `pip`
3. Request storage permission so your `/sdcard/` PDF files are accessible
4. Download the Kokoro-ONNX model files (~115 MB) to `~/.cache/kokoro-onnx/`

### Step 4 — Convert a PDF

```bash
# PDF files on your phone are under ~/storage/shared/ (same as /sdcard/)
python pdf_to_audio.py ~/storage/shared/document.pdf

# With options
python pdf_to_audio.py ~/storage/shared/paper.pdf --exclude references --quality low
```

The output MP3 is saved next to the source PDF.

### Manual setup (alternative to the script)

If you prefer to install manually:

```bash
# System packages
pkg update && pkg install python ffmpeg libsndfile

# Storage access
termux-setup-storage

# Python packages
pip install kokoro-onnx soundfile pydub PyMuPDF pypdf numpy

# Download model files
mkdir -p ~/.cache/kokoro-onnx
cd ~/.cache/kokoro-onnx
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices-v1_0.bin
```

### Android notes

- Conversion is slower than on desktop but fully functional.
- For long PDFs, `--quality low` reduces processing time and output file size.
- PDF files on Android are accessible via `~/storage/shared/` after running
  `termux-setup-storage`.
- Downloads are large (~115 MB for model files). Use Wi-Fi.

---

## License

MIT
