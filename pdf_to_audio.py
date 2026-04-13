#!/usr/bin/env python3
"""
pdf_to_audio.py — Convert a PDF file to an MP3 using Kokoro TTS.

Default voice : af_heart (American English, Grade A female)
Output file   : <input_stem>.mp3 in the same directory as the PDF
Quality       : high (192 k, default) or low (96 k)

Optional exclusions (--exclude):
  tables      — skip table regions (spatial detection via PyMuPDF)
  footnotes   — skip footnote blocks at the bottom of each page
  references  — drop the References / Bibliography section

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
from typing import Set

import numpy as np

# ---------------------------------------------------------------------------
# PDF extraction — PyMuPDF preferred, pypdf as fallback
# ---------------------------------------------------------------------------

def _bbox_overlaps(a: tuple, b: tuple) -> bool:
    """True when two (x0, y0, x1, y1) rectangles overlap."""
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def _looks_like_footnote_block(text: str) -> bool:
    """
    Heuristic: does this text block look like a footnote?

    Matches patterns such as:
      1 Some footnote text here.
      [1] A bracketed footnote.
      * An asterisk footnote.
      † Dagger symbol footnote.
    """
    first_line = text.strip().splitlines()[0] if text.strip() else ""
    return bool(
        re.match(r"^[\[\(]?\d{1,3}[\]\)]?[\s.]\s*\S", first_line)
        or re.match(r"^[*†‡§¶]\s+\S", first_line)
    )


try:
    import fitz  # PyMuPDF — preferred

    _PYMUPDF = True

    def _extract_pages(
        pdf_path: Path,
        exclude_tables: bool = False,
        exclude_footnotes: bool = False,
    ) -> list[str]:
        doc = fitz.open(str(pdf_path))
        pages: list[str] = []

        for page in doc:
            # ---- collect bounding boxes to skip ----
            skip_bboxes: list[tuple] = []

            if exclude_tables:
                try:
                    tab_finder = page.find_tables()
                    skip_bboxes.extend(t.bbox for t in tab_finder.tables)
                except Exception:
                    pass  # find_tables may not be available in older PyMuPDF

            # ---- iterate text blocks ----
            if skip_bboxes or exclude_footnotes:
                page_height = page.rect.height
                # Footnotes live in roughly the bottom 15 % of the page.
                footnote_threshold = page_height * 0.85

                blocks = page.get_text("blocks")  # (x0,y0,x1,y1,text,block_no,type)
                kept: list[str] = []
                for block in blocks:
                    x0, y0, x1, y1, text, *_ = block
                    block_bbox = (x0, y0, x1, y1)

                    # Skip table regions
                    if any(_bbox_overlaps(block_bbox, tb) for tb in skip_bboxes):
                        continue

                    # Skip footnote blocks: must be both in the bottom region
                    # AND match the footnote pattern (reduces false positives)
                    if (
                        exclude_footnotes
                        and y0 >= footnote_threshold
                        and _looks_like_footnote_block(text)
                    ):
                        continue

                    kept.append(text)

                pages.append(" ".join(kept))
            else:
                pages.append(page.get_text())

        doc.close()
        return pages

except ImportError:
    _PYMUPDF = False

    try:
        from pypdf import PdfReader

        def _extract_pages(
            pdf_path: Path,
            exclude_tables: bool = False,
            exclude_footnotes: bool = False,
        ) -> list[str]:
            reader = PdfReader(str(pdf_path))
            pages: list[str] = []
            for p in reader.pages:
                text = p.extract_text() or ""
                if exclude_tables:
                    text = _strip_table_lines(text)
                # pypdf has no spatial info — footnote stripping done later in
                # strip_footnotes() via text-level heuristics
                pages.append(text)
            return pages

    except ImportError:
        def _extract_pages(pdf_path: Path, **_) -> list[str]:
            raise ImportError(
                "No PDF library found. Install one:\n"
                "  pip install PyMuPDF      (recommended)\n"
                "  pip install pypdf        (fallback)"
            )


def _strip_table_lines(text: str) -> str:
    """
    Text-level table heuristic (used when PyMuPDF is unavailable).

    Removes runs of lines that look like table rows:
      - Multiple tab characters (columnar layout)
      - Pipe-delimited cells  |col|col|col|
    """
    lines = text.splitlines()
    result: list[str] = []
    for line in lines:
        if line.count("\t") >= 2 or ("|" in line and line.count("|") >= 2):
            continue
        result.append(line)
    return "\n".join(result)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_VOICE = "af_heart"   # Kokoro Grade A — top female American English voice
SAMPLE_RATE   = 24_000       # Hz — fixed by Kokoro

QUALITY_BITRATES: dict[str, str] = {
    "high": "192k",
    "low":  "96k",
}

VALID_EXCLUSIONS = {"tables", "footnotes", "references"}

# Section headings that signal the start of a references block
_REFS_HEADING_RE = re.compile(
    r"^\s*"
    r"(References?|Bibliography|Works\s+Cited|Literature\s+Cited"
    r"|Further\s+Reading|Sources?|Endnotes?)"
    r"\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Footnote-like lines: "1.", "[1]", "(2)", "* …", "† …"
_FOOTNOTE_LINE_RE = re.compile(
    r"(?m)^[ \t]*(?:[\[\(]?\d{1,3}[\]\)]?[.\s]|[*†‡§¶])\s+\S[^\n]{4,}\n?",
)


# ---------------------------------------------------------------------------
# Post-extraction filters
# ---------------------------------------------------------------------------

def strip_references(text: str) -> str:
    """
    Remove the References / Bibliography section.

    Strategy: find the *last* occurrence of a known section heading and cut
    there, but only if it appears in the final 60 % of the document (to avoid
    cutting legitimate mid-document sections titled "Notes", etc.).
    """
    matches = list(_REFS_HEADING_RE.finditer(text))
    if not matches:
        return text
    last = matches[-1]
    if last.start() > len(text) * 0.40:
        return text[: last.start()].rstrip()
    return text


def strip_footnotes_text(text: str) -> str:
    """
    Text-level footnote removal (fallback when spatial info is unavailable).

    Removes lines matching numbered / symbol footnote patterns.
    Conservative — only fires on clear matches to avoid eating numbered lists.
    """
    return _FOOTNOTE_LINE_RE.sub("", text)


# ---------------------------------------------------------------------------
# Main extraction pipeline
# ---------------------------------------------------------------------------

def extract_text(pdf_path: Path, exclude: Set[str]) -> str:
    """
    Extract text from *pdf_path*, applying structural exclusions.

    *exclude* is a subset of {"tables", "footnotes", "references"}.
    """
    pages = _extract_pages(
        pdf_path,
        exclude_tables="tables" in exclude,
        exclude_footnotes="footnotes" in exclude,
    )
    text = "\n\n".join(p for p in pages if p.strip())

    # Text-level filters — applied regardless of which PDF library was used
    # (PyMuPDF may have already handled tables/footnotes spatially, but these
    #  catch anything that slipped through)
    if "references" in exclude:
        text = strip_references(text)
    if "footnotes" in exclude and not _PYMUPDF:
        # Only needed as fallback; PyMuPDF already filtered spatially
        text = strip_footnotes_text(text)

    return text


def clean_text(text: str) -> str:
    """
    Clean raw PDF text for natural-sounding TTS output.

    - Rejoin words split by soft hyphens at line breaks
    - Merge wrapped lines that continue a sentence
    - Collapse blank lines and squash horizontal whitespace
    - Strip non-printable / non-ASCII characters
    - Remove lone page numbers
    """
    # "hy-\nphen" → "hyphen"
    text = re.sub(r"-\n(\w)", r"\1", text)

    # Mid-sentence line wraps (lowercase continues after bare newline)
    text = re.sub(r"(?<![.!?…])\n(?=[a-z])", " ", text)

    # 3+ blank lines → single paragraph break
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Squash horizontal whitespace
    text = re.sub(r"[ \t]{2,}", " ", text)

    # Drop non-printable / non-ASCII
    text = re.sub(r"[^\x20-\x7E\n]", " ", text)

    # Remove lone page numbers (a line that is only digits)
    lines = [ln for ln in text.splitlines() if not re.fullmatch(r"\d{1,4}", ln.strip())]
    text = "\n".join(lines)

    return text.strip()


# ---------------------------------------------------------------------------
# TTS
# ---------------------------------------------------------------------------

def synthesise(text: str, voice: str, speed: float) -> np.ndarray:
    """
    Synthesise *text* with Kokoro and return a float32 NumPy audio array.

    A 0.4 s silence is inserted between chunks for natural pacing.
    """
    from kokoro import KPipeline

    pipeline = KPipeline(lang_code="a")  # 'a' = American English
    silence  = np.zeros(int(SAMPLE_RATE * 0.4), dtype=np.float32)
    parts: list[np.ndarray] = []

    for _graphemes, _phonemes, audio in pipeline(
        text, voice=voice, speed=speed, split_pattern=r"\n\n+"
    ):
        if audio is not None and audio.size > 0:
            parts.append(audio.astype(np.float32))
            parts.append(silence)

    if not parts:
        raise RuntimeError("Kokoro produced no audio — is the text empty?")

    return np.concatenate(parts)


# ---------------------------------------------------------------------------
# MP3 export
# ---------------------------------------------------------------------------

def save_mp3(audio: np.ndarray, output_path: Path, bitrate: str) -> None:
    """Write *audio* (float32, 24 kHz mono) as an MP3. Requires ffmpeg."""
    import soundfile as sf
    from pydub import AudioSegment

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        sf.write(str(tmp_path), audio, SAMPLE_RATE, subtype="PCM_16")
        AudioSegment.from_wav(str(tmp_path)).export(
            str(output_path), format="mp3", bitrate=bitrate
        )
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
        epilog=(
            "examples:\n"
            "  pdf_to_audio paper.pdf\n"
            "  pdf_to_audio paper.pdf --exclude tables footnotes references\n"
            "  pdf_to_audio paper.pdf --exclude references --quality low\n"
            "  pdf_to_audio paper.pdf --output ~/audio/paper.mp3\n"
        ),
    )
    parser.add_argument(
        "pdf",
        type=Path,
        help="Path to the input PDF file.",
    )
    parser.add_argument(
        "--exclude",
        nargs="+",
        choices=sorted(VALID_EXCLUSIONS) + ["all"],
        default=[],
        metavar="SECTION",
        help=(
            "Sections to exclude from the audio. "
            "Choose any combination of: tables  footnotes  references  all. "
            "Example: --exclude tables footnotes"
        ),
    )
    parser.add_argument(
        "--quality",
        choices=list(QUALITY_BITRATES),
        default="high",
        metavar="LEVEL",
        help="MP3 quality: 'high' = 192 kbps (default), 'low' = 96 kbps.",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        metavar="RATE",
        help="Speech speed multiplier (default: 1.0). E.g. 0.9 = slightly slower.",
    )
    parser.add_argument(
        "--voice",
        default=DEFAULT_VOICE,
        metavar="VOICE",
        help=(
            f"Kokoro voice ID (default: {DEFAULT_VOICE} — Grade A female, "
            "American English)."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Custom output path for the MP3. "
            "Defaults to <pdf_stem>.mp3 in the same directory as the PDF."
        ),
    )
    return parser


def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()

    pdf_path: Path = args.pdf.resolve()

    if not pdf_path.exists():
        parser.error(f"File not found: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        parser.error(f"Expected a .pdf file, got: {pdf_path.name}")

    output_path = args.output.resolve() if args.output else pdf_path.with_suffix(".mp3")
    if args.output:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    # Resolve "all" shorthand
    exclude: Set[str] = (
        VALID_EXCLUSIONS if "all" in args.exclude else set(args.exclude)
    )

    bitrate = QUALITY_BITRATES[args.quality]

    # ---- 1. Extract & filter ----
    exclude_label = ", ".join(sorted(exclude)) if exclude else "none"
    print(f"[1/3] Extracting text from  : {pdf_path.name}")
    print(f"      Excluding              : {exclude_label}")

    raw_text     = extract_text(pdf_path, exclude)
    cleaned_text = clean_text(raw_text)

    if not cleaned_text:
        print("Error: no readable text found in the PDF.", file=sys.stderr)
        sys.exit(1)

    print(f"      Words to synthesise   : {len(cleaned_text.split()):,}")

    # ---- 2. Synthesise ----
    print(
        f"[2/3] Synthesising audio    : voice={args.voice}  "
        f"speed={args.speed}x  quality={args.quality} ({bitrate})"
    )
    audio = synthesise(cleaned_text, voice=args.voice, speed=args.speed)
    duration_min = len(audio) / SAMPLE_RATE / 60
    print(f"      Audio duration         : {duration_min:.1f} min")

    # ---- 3. Save ----
    print(f"[3/3] Saving MP3 to         : {output_path}")
    save_mp3(audio, output_path, bitrate)

    print(f"\nDone.  {output_path}")


if __name__ == "__main__":
    main()
