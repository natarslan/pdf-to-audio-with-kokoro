#!/usr/bin/env python3
"""
pdf_to_audio.py — Convert a PDF file to an MP3 using Kokoro TTS.

Default voice : af_heart (American English, Grade A female)
Output file   : <input_stem>.mp3 in the same directory as the PDF
Quality       : high (192 k, default) or low (96 k)

Dependencies:
    pip install kokoro soundfile pydub PyMuPDF
    # system: ffmpeg  (required by pydub for MP3 export)
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# PDF extraction — try PyMuPDF first, fall back to pypdf
# ---------------------------------------------------------------------------
try:
    import fitz  # PyMuPDF

    def _extract_pages(pdf_path: Path) -> list[str]:
        doc = fitz.open(str(pdf_path))
        pages = [page.get_text() for page in doc]
        doc.close()
        return pages

except ImportError:
    try:
        from pypdf import PdfReader

        def _extract_pages(pdf_path: Path) -> list[str]:
            reader = PdfReader(str(pdf_path))
            return [p.extract_text() or "" for p in reader.pages]

    except ImportError:
        def _extract_pages(pdf_path: Path) -> list[str]:
            raise ImportError(
                "No PDF library found. Install one:\n"
                "  pip install PyMuPDF      (recommended)\n"
                "  pip install pypdf        (fallback)"
            )

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_VOICE = "af_heart"   # Kokoro Grade A — best female American English voice
SAMPLE_RATE   = 24_000       # Hz — fixed by Kokoro

QUALITY_BITRATES: dict[str, str] = {
    "high": "192k",
    "low":  "96k",
}


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def extract_text(pdf_path: Path) -> str:
    """Return raw text extracted from every page of *pdf_path*."""
    pages = _extract_pages(pdf_path)
    return "\n\n".join(p for p in pages if p.strip())


def clean_text(text: str) -> str:
    """
    Clean raw PDF text for natural-sounding TTS output.

    Steps:
    - Rejoin words split by soft hyphens at line breaks
    - Merge wrapped lines that continue a sentence (no end-punctuation before newline)
    - Collapse runs of whitespace / blank lines
    - Drop non-ASCII / non-printable characters that confuse the TTS
    """
    # Soft-hyphen line-break: "hy-\nphen" → "hyphen"
    text = re.sub(r"-\n(\w)", r"\1", text)

    # Mid-sentence line wraps: lowercase letter after newline without sentence-end
    text = re.sub(r"(?<![.!?…])\n(?=[a-z])", " ", text)

    # Collapse 3+ consecutive blank lines to a paragraph break
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Squash horizontal whitespace runs
    text = re.sub(r"[ \t]{2,}", " ", text)

    # Strip control characters and non-printable bytes
    text = re.sub(r"[^\x20-\x7E\n]", " ", text)

    # Remove lines that look like page headers/footers (short lines that are
    # only numbers, or very short all-caps lines)
    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        # Skip lone page numbers
        if re.fullmatch(r"\d{1,4}", stripped):
            continue
        cleaned_lines.append(line)
    text = "\n".join(cleaned_lines)

    return text.strip()


# ---------------------------------------------------------------------------
# TTS
# ---------------------------------------------------------------------------

def synthesise(text: str, voice: str, speed: float) -> np.ndarray:
    """
    Run Kokoro TTS on *text* and return a single float32 NumPy audio array.

    The KPipeline is a generator; each chunk yields (graphemes, phonemes, audio).
    A brief silence (0.4 s) is inserted between paragraph-sized chunks so the
    final recording has natural pacing.
    """
    from kokoro import KPipeline  # imported here so the rest of the module is
                                  # importable even when kokoro isn't installed

    pipeline  = KPipeline(lang_code="a")  # 'a' = American English
    silence   = np.zeros(int(SAMPLE_RATE * 0.4), dtype=np.float32)
    parts: list[np.ndarray] = []

    generator = pipeline(text, voice=voice, speed=speed, split_pattern=r"\n\n+")
    for _graphemes, _phonemes, audio in generator:
        if audio is not None and audio.size > 0:
            parts.append(audio.astype(np.float32))
            parts.append(silence)

    if not parts:
        raise RuntimeError("Kokoro produced no audio. Is the text empty?")

    return np.concatenate(parts)


# ---------------------------------------------------------------------------
# MP3 export
# ---------------------------------------------------------------------------

def save_mp3(audio: np.ndarray, output_path: Path, bitrate: str) -> None:
    """
    Write *audio* (float32, 24 kHz mono) to *output_path* as an MP3 file.

    Uses a temporary WAV file as an intermediate because pydub reads from disk.
    Requires ffmpeg on PATH.
    """
    import soundfile as sf
    from pydub import AudioSegment

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        sf.write(str(tmp_path), audio, SAMPLE_RATE, subtype="PCM_16")
        segment = AudioSegment.from_wav(str(tmp_path))
        segment.export(str(output_path), format="mp3", bitrate=bitrate)
    finally:
        tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf_to_audio",
        description=(
            "Convert a PDF to an MP3 using Kokoro TTS.\n"
            "Output is saved next to the PDF by default."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "pdf",
        type=Path,
        help="Path to the input PDF file.",
    )
    parser.add_argument(
        "--quality",
        choices=list(QUALITY_BITRATES),
        default="high",
        metavar="LEVEL",
        help=(
            "MP3 output quality. "
            "'high' = 192 kbps (default), 'low' = 96 kbps."
        ),
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        metavar="RATE",
        help="Speech speed multiplier, e.g. 0.9 for slightly slower (default: 1.0).",
    )
    parser.add_argument(
        "--voice",
        default=DEFAULT_VOICE,
        metavar="VOICE",
        help=(
            f"Kokoro voice ID (default: {DEFAULT_VOICE} — Grade A female, "
            "American English). Override only if needed."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Custom output path for the MP3 file. "
            "Defaults to <pdf_stem>.mp3 in the same directory as the PDF."
        ),
    )
    return parser


def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()

    pdf_path: Path = args.pdf.resolve()

    # --- validate input ---
    if not pdf_path.exists():
        parser.error(f"File not found: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        parser.error(f"Expected a .pdf file, got: {pdf_path.name}")

    # --- determine output path ---
    if args.output:
        output_path = args.output.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        output_path = pdf_path.with_suffix(".mp3")  # same dir as PDF

    bitrate = QUALITY_BITRATES[args.quality]

    # --- extract & clean ---
    print(f"[1/3] Extracting text from  : {pdf_path.name}")
    raw_text     = extract_text(pdf_path)
    cleaned_text = clean_text(raw_text)

    if not cleaned_text:
        print("Error: no readable text found in the PDF.", file=sys.stderr)
        sys.exit(1)

    word_count = len(cleaned_text.split())
    print(f"      Words extracted        : {word_count:,}")

    # --- synthesise ---
    print(
        f"[2/3] Synthesising audio    : voice={args.voice}  "
        f"speed={args.speed}x  quality={args.quality} ({bitrate})"
    )
    audio = synthesise(cleaned_text, voice=args.voice, speed=args.speed)

    duration_s   = len(audio) / SAMPLE_RATE
    duration_min = duration_s / 60
    print(f"      Audio duration         : {duration_min:.1f} min")

    # --- save ---
    print(f"[3/3] Saving MP3 to         : {output_path}")
    save_mp3(audio, output_path, bitrate)

    print(f"\nDone.  {output_path}")


if __name__ == "__main__":
    main()
