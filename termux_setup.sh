#!/data/data/com.termux/files/usr/bin/bash
# termux_setup.sh — Set up pdf-to-audio-with-kokoro on Android (Termux)
#
# Run once after cloning the repository:
#   bash termux_setup.sh
#
# What this script does:
#   1. Installs required Termux system packages (python, ffmpeg, libsndfile)
#   2. Installs Python packages using kokoro-onnx (no PyTorch needed)
#   3. Requests storage permission so /sdcard/ PDFs are accessible
#   4. Downloads Kokoro-ONNX model files (~115 MB total) to ~/.cache/kokoro-onnx/

set -e

echo "========================================"
echo "  pdf-to-audio Termux Setup"
echo "========================================"
echo ""

# ---- 1. System packages ----
echo "[1/4] Installing system packages..."
pkg update -y
pkg install -y python ffmpeg libsndfile
echo "      Done."
echo ""

# ---- 2. Python packages ----
echo "[2/4] Installing Python packages..."
pip install --upgrade pip --quiet
pip install kokoro-onnx soundfile pydub PyMuPDF pypdf numpy
echo "      Done."
echo ""

# ---- 3. Storage access ----
echo "[3/4] Setting up storage access..."
if [ ! -d "$HOME/storage/shared" ]; then
    echo "      Requesting storage permission — tap 'Allow' when prompted..."
    termux-setup-storage
    # Give the user a moment to respond to the permission dialog
    sleep 5
else
    echo "      Storage already set up."
fi
echo ""

# ---- 4. Download model files ----
echo "[4/4] Downloading Kokoro-ONNX model files (~115 MB total)..."
CACHE_DIR="$HOME/.cache/kokoro-onnx"
mkdir -p "$CACHE_DIR"

BASE_URL="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files"

for FNAME in "kokoro-v0_19.onnx" "voices-v1_0.bin"; do
    DEST="$CACHE_DIR/$FNAME"
    if [ -f "$DEST" ]; then
        echo "      $FNAME already exists, skipping."
    else
        echo "      Downloading $FNAME..."
        curl -L --progress-bar "$BASE_URL/$FNAME" -o "$DEST"
        echo "      Saved to $DEST"
    fi
done
echo ""

# ---- Done ----
echo "========================================"
echo "  Setup complete!"
echo "========================================"
echo ""
echo "Your PDF files can be found in:"
echo "  ~/storage/shared/   (same as /sdcard/)"
echo ""
echo "Usage examples:"
echo "  python pdf_to_audio.py ~/storage/shared/document.pdf"
echo "  python pdf_to_audio.py ~/storage/shared/paper.pdf --exclude references"
echo "  python pdf_to_audio.py ~/storage/shared/book.pdf --speed 1.2 --quality low"
echo ""
echo "The output MP3 is saved next to the source PDF."
