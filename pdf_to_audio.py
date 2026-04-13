#!/usr/bin/env python3
"""
pdf_to_audio.py — Convert a PDF file to MP3 audio using Kokoro TTS.

Default voice : af_heart (American English, Grade A female)
Output        : one MP3 per chapter, saved next to the PDF
Quality       : high (192 kbps, default) or low (96 kbps)

Chapter selection (interactive):
  - Auto-detects chapters from the PDF's embedded table of contents
  - Falls back to manual page-range entry if TOC is missing/sparse
  - One MP3 per chapter by default; use --combine for a single file

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
from typing import Optional, Set

import numpy as np

# ---------------------------------------------------------------------------
# PDF helpers — PyMuPDF preferred, pypdf as fallback
# ---------------------------------------------------------------------------

def _bbox_overlaps(a: tuple, b: tuple) -> bool:
    """True when two (x0, y0, x1, y1) rectangles overlap."""
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def _looks_like_footnote_block(text: str) -> bool:
    """Heuristic: numbered/symbol footnote patterns at page bottom."""
    first = text.strip().splitlines()[0] if text.strip() else ""
    return bool(
        re.match(r"^[\[\(]?\d{1,3}[\]\)]?[\s.]\s*\S", first)
        or re.match(r"^[*†‡§¶]\s+\S", first)
    )


try:
    import fitz  # PyMuPDF

    _PYMUPDF = True

    def _pdf_page_count(pdf_path: Path) -> int:
        doc = fitz.open(str(pdf_path))
        n = doc.page_count
        doc.close()
        return n

    def _get_toc_raw(pdf_path: Path):
        doc = fitz.open(str(pdf_path))
        toc = doc.get_toc()   # [[level, title, page(1-indexed)], ...]
        doc.close()
        return toc

    def _extract_pages(
        pdf_path: Path,
        exclude_tables: bool = False,
        exclude_footnotes: bool = False,
        page_range: Optional[tuple[int, int]] = None,   # 0-indexed, inclusive
    ) -> list[str]:
        doc   = fitz.open(str(pdf_path))
        total = doc.page_count

        if page_range is None:
            indices = range(total)
        else:
            lo = max(0, page_range[0])
            hi = min(total - 1, page_range[1])
            indices = range(lo, hi + 1)

        pages: list[str] = []
        for idx in indices:
            page = doc[idx]
            skip_bboxes: list[tuple] = []

            if exclude_tables:
                try:
                    skip_bboxes.extend(t.bbox for t in page.find_tables().tables)
                except Exception:
                    pass

            if skip_bboxes or exclude_footnotes:
                page_h   = page.rect.height
                fn_thresh = page_h * 0.85
                kept: list[str] = []
                for block in page.get_text("blocks"):
                    x0, y0, x1, y1, text, *_ = block
                    bbox = (x0, y0, x1, y1)
                    if any(_bbox_overlaps(bbox, tb) for tb in skip_bboxes):
                        continue
                    if (
                        exclude_footnotes
                        and y0 >= fn_thresh
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

    def _pdf_page_count(pdf_path: Path) -> int:
        from pypdf import PdfReader
        return len(PdfReader(str(pdf_path)).pages)

    def _get_toc_raw(pdf_path: Path):
        return []   # pypdf doesn't expose TOC conveniently

    try:
        from pypdf import PdfReader as _PdfReader

        def _extract_pages(
            pdf_path: Path,
            exclude_tables: bool = False,
            exclude_footnotes: bool = False,
            page_range: Optional[tuple] = None,
        ) -> list[str]:
            reader = _PdfReader(str(pdf_path))
            pages  = reader.pages
            if page_range is not None:
                lo = max(0, page_range[0])
                hi = min(len(pages) - 1, page_range[1])
                pages = pages[lo : hi + 1]
            result: list[str] = []
            for p in pages:
                text = p.extract_text() or ""
                if exclude_tables:
                    text = _strip_table_lines(text)
                result.append(text)
            return result

    except ImportError:
        def _extract_pages(pdf_path: Path, **_) -> list[str]:
            raise ImportError(
                "No PDF library found. Install one:\n"
                "  pip install PyMuPDF      (recommended)\n"
                "  pip install pypdf        (fallback)"
            )


def _strip_table_lines(text: str) -> str:
    """Remove lines that look like table rows (pypdf fallback)."""
    lines = [
        ln for ln in text.splitlines()
        if not (ln.count("\t") >= 2 or ("|" in ln and ln.count("|") >= 2))
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# TOC / chapter detection
# ---------------------------------------------------------------------------

Chapter = dict   # {"title": str, "start": int, "end": int}  — 1-indexed pages


def get_toc(pdf_path: Path) -> list[Chapter]:
    """
    Return top-level chapters from the PDF's embedded TOC.
    Each entry: {"title", "start", "end"}  (1-indexed page numbers).
    Returns [] when the TOC is absent or has fewer than 2 usable entries.
    """
    try:
        raw   = _get_toc_raw(pdf_path)
        total = _pdf_page_count(pdf_path)
    except Exception:
        return []

    if not raw:
        return []

    # Prefer level-1; if that's too sparse, include level-2 as well
    for max_level in (1, 2):
        entries = [(title, page) for level, title, page in raw if level <= max_level]
        if len(entries) >= 2:
            break
    else:
        return []

    chapters: list[Chapter] = []
    for i, (title, start) in enumerate(entries):
        end = entries[i + 1][1] - 1 if i + 1 < len(entries) else total
        start = max(1, start)
        end   = min(total, max(start, end))
        chapters.append({"title": title, "start": start, "end": end})

    return chapters


# ---------------------------------------------------------------------------
# Interactive chapter selection
# ---------------------------------------------------------------------------

def _parse_selection(raw: str, count: int) -> list[int]:
    """
    Parse a selection string like "1,3,5-7" into 0-based indices.
    "all" or empty string selects everything.
    """
    raw = raw.strip().lower()
    if raw in ("all", "", "a"):
        return list(range(count))
    indices: set[int] = set()
    for part in re.split(r"[,\s]+", raw):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            indices.update(range(int(a) - 1, int(b)))
        else:
            indices.add(int(part) - 1)
    return sorted(i for i in indices if 0 <= i < count)


def prompt_chapter_selection(chapters: list[Chapter]) -> list[Chapter]:
    """Display auto-detected chapters and let the user pick."""
    print(f"\n  Found {len(chapters)} chapters:\n")
    for i, ch in enumerate(chapters, 1):
        title_col = ch["title"][:52]
        print(f"    {i:>3}.  {title_col:<52}  p.{ch['start']}–{ch['end']}")
    print()
    while True:
        raw = input("  Which chapters? (e.g. 1,3,5-7  or  'all'  — default: all): ").strip()
        if not raw:
            raw = "all"
        try:
            indices = _parse_selection(raw, len(chapters))
            if indices:
                return [chapters[i] for i in indices]
        except (ValueError, IndexError):
            pass
        print("  Couldn't parse that — try again.\n")


def prompt_manual_chapters(total_pages: int) -> list[Chapter]:
    """Ask the user to enter page ranges when TOC is unavailable."""
    print(f"\n  No chapter list detected (PDF has {total_pages} pages).")
    print("  Enter page ranges manually, one per line.")
    print("  Format:  Title: start-end   (e.g.  Introduction: 1-15)")
    print("  Leave the line blank when done.\n")
    chapters: list[Chapter] = []
    while True:
        label = f"  Chapter {len(chapters) + 1}"
        raw   = input(f"{label}: ").strip()
        if not raw:
            if chapters:
                break
            print("  Enter at least one range.\n")
            continue
        if ":" in raw:
            title, page_part = raw.split(":", 1)
            title = title.strip()
        else:
            title     = f"Part {len(chapters) + 1}"
            page_part = raw
        try:
            start_s, end_s = page_part.strip().split("-")
            start, end = int(start_s.strip()), int(end_s.strip())
            if 1 <= start <= end <= total_pages:
                chapters.append({"title": title, "start": start, "end": end})
                print(f"    Added: {title} (p.{start}–{end})\n")
            else:
                print(f"  Pages must be between 1 and {total_pages}.\n")
        except (ValueError, AttributeError):
            print("  Couldn't parse that — use format  Title: start-end\n")
    return chapters


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

_REFS_HEADING_RE = re.compile(
    r"^\s*(References?|Bibliography|Works\s+Cited|Literature\s+Cited"
    r"|Further\s+Reading|Sources?|Endnotes?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

_FOOTNOTE_LINE_RE = re.compile(
    r"(?m)^[ \t]*(?:[\[\(]?\d{1,3}[\]\)]?[.\s]|[*†‡§¶])\s+\S[^\n]{4,}\n?",
)


# ---------------------------------------------------------------------------
# Text filters
# ---------------------------------------------------------------------------

def strip_references(text: str) -> str:
    matches = list(_REFS_HEADING_RE.finditer(text))
    if not matches:
        return text
    last = matches[-1]
    if last.start() > len(text) * 0.40:
        return text[: last.start()].rstrip()
    return text


def strip_footnotes_text(text: str) -> str:
    return _FOOTNOTE_LINE_RE.sub("", text)


def extract_text(
    pdf_path: Path,
    exclude: Set[str],
    page_range: Optional[tuple[int, int]] = None,   # 0-indexed, inclusive
) -> str:
    pages = _extract_pages(
        pdf_path,
        exclude_tables="tables" in exclude,
        exclude_footnotes="footnotes" in exclude,
        page_range=page_range,
    )
    text = "\n\n".join(p for p in pages if p.strip())

    if "references" in exclude:
        text = strip_references(text)
    if "footnotes" in exclude and not _PYMUPDF:
        text = strip_footnotes_text(text)

    return text


def clean_text(text: str) -> str:
    text = re.sub(r"-\n(\w)", r"\1", text)                    # dehyphenate
    text = re.sub(r"(?<![.!?…])\n(?=[a-z])", " ", text)       # rejoin wrapped lines
    text = re.sub(r"\n{3,}", "\n\n", text)                     # collapse blank lines
    text = re.sub(r"[ \t]{2,}", " ", text)                     # squash spaces
    text = re.sub(r"[^\x20-\x7E\n]", " ", text)               # strip non-ASCII
    lines = [ln for ln in text.splitlines()
             if not re.fullmatch(r"\d{1,4}", ln.strip())]      # remove lone page nums
    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# TTS
# ---------------------------------------------------------------------------

def synthesise(text: str, voice: str, speed: float) -> np.ndarray:
    from kokoro import KPipeline
    pipeline = KPipeline(lang_code="a")
    silence  = np.zeros(int(SAMPLE_RATE * 0.4), dtype=np.float32)
    parts: list[np.ndarray] = []
    for _g, _p, audio in pipeline(text, voice=voice, speed=speed, split_pattern=r"\n\n+"):
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


def _safe_name(s: str, max_len: int = 40) -> str:
    """Convert a chapter title to a safe filename component."""
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s]+", "_", s.strip())
    return s[:max_len].strip("_") or "chapter"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf_to_audio",
        description=(
            "Convert a PDF to MP3 audio using Kokoro TTS.\n"
            "Interactively selects chapters from the PDF's table of contents,\n"
            "or prompts for manual page ranges if no TOC is found."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  pdf_to_audio book.pdf\n"
            "  pdf_to_audio book.pdf --combine\n"
            "  pdf_to_audio book.pdf --exclude tables footnotes references\n"
            "  pdf_to_audio book.pdf --quality low --speed 0.95\n"
        ),
    )
    parser.add_argument("pdf", type=Path, help="Input PDF file.")
    parser.add_argument(
        "--full",
        action="store_true",
        help=(
            "Convert the entire PDF as one MP3 without chapter selection. "
            "Skips the interactive prompt entirely."
        ),
    )
    parser.add_argument(
        "--combine",
        action="store_true",
        help="Merge all selected chapters into a single MP3 instead of one per chapter.",
    )
    parser.add_argument(
        "--exclude",
        nargs="+",
        choices=sorted(VALID_EXCLUSIONS) + ["all"],
        default=[],
        metavar="SECTION",
        help="Exclude: tables  footnotes  references  all",
    )
    parser.add_argument(
        "--quality",
        choices=list(QUALITY_BITRATES),
        default="high",
        metavar="LEVEL",
        help="'high' = 192 kbps (default)  'low' = 96 kbps",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        metavar="RATE",
        help="Speech speed multiplier (default: 1.0)",
    )
    parser.add_argument(
        "--voice",
        default=DEFAULT_VOICE,
        metavar="VOICE",
        help=f"Kokoro voice ID (default: {DEFAULT_VOICE})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Output directory for chapter files (multi-chapter mode), "
            "or output file path (--combine / single chapter). "
            "Defaults to the PDF's own directory."
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

    exclude: Set[str] = VALID_EXCLUSIONS if "all" in args.exclude else set(args.exclude)
    bitrate = QUALITY_BITRATES[args.quality]

    # Determine output directory (for multi-file) or output file (for combined/single)
    if args.output:
        out_arg = args.output.resolve()
    else:
        out_arg = pdf_path.parent   # default: same dir as PDF

    # ---- Full-PDF mode (no chapter selection) ----
    if args.full:
        out_path = out_arg if (args.output and not args.output.is_dir()) \
                   else out_arg / f"{pdf_path.stem}.mp3"
        if args.output:
            out_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"\nConverting entire PDF: {pdf_path.name}")
        if exclude:
            print(f"  Excluding: {', '.join(sorted(exclude))}")
        print(f"  voice={args.voice}  quality={args.quality} ({bitrate})  speed={args.speed}x\n")

        raw_text     = extract_text(pdf_path, exclude)
        cleaned_text = clean_text(raw_text)
        if not cleaned_text:
            print("Error: no readable text found in the PDF.", file=sys.stderr)
            sys.exit(1)

        print(f"  Words : {len(cleaned_text.split()):,}")
        print(f"  Generating audio...")
        audio = synthesise(cleaned_text, voice=args.voice, speed=args.speed)
        duration_min = len(audio) / SAMPLE_RATE / 60
        print(f"  Duration: {duration_min:.1f} min")
        save_mp3(audio, out_path, bitrate)
        print(f"\nDone.  {out_path}")
        return

    # ---- Chapter detection ----
    print(f"\nScanning for chapters in: {pdf_path.name}")
    toc = get_toc(pdf_path)

    if toc:
        print(f"  Auto-detected {len(toc)} chapters from the embedded table of contents.")
        chapters = prompt_chapter_selection(toc)
    else:
        print("  No embedded table of contents found.")
        total_pages = _pdf_page_count(pdf_path)
        chapters = prompt_manual_chapters(total_pages)

    if not chapters:
        print("No chapters selected — nothing to do.", file=sys.stderr)
        sys.exit(1)

    # ---- Confirm selection ----
    print(f"\n  Converting {len(chapters)} chapter(s)  |  "
          f"voice={args.voice}  quality={args.quality} ({bitrate})  speed={args.speed}x")
    if exclude:
        print(f"  Excluding: {', '.join(sorted(exclude))}")
    print()

    # ---- Process chapters ----
    all_audio_parts: list[np.ndarray] = []
    chapter_silence = np.zeros(int(SAMPLE_RATE * 1.5), dtype=np.float32)
    saved_files: list[Path] = []

    for idx, ch in enumerate(chapters, 1):
        title    = ch["title"]
        start_p  = ch["start"]   # 1-indexed
        end_p    = ch["end"]     # 1-indexed
        pr       = (start_p - 1, end_p - 1)   # 0-indexed for extraction

        print(f"  [{idx}/{len(chapters)}] {title}  (p.{start_p}–{end_p})")

        raw_text     = extract_text(pdf_path, exclude, page_range=pr)
        cleaned_text = clean_text(raw_text)

        if not cleaned_text:
            print(f"    ! No readable text on these pages — skipping.\n")
            continue

        word_count = len(cleaned_text.split())
        print(f"    Words : {word_count:,}")
        print(f"    Generating audio...")

        audio        = synthesise(cleaned_text, voice=args.voice, speed=args.speed)
        duration_min = len(audio) / SAMPLE_RATE / 60
        print(f"    Duration: {duration_min:.1f} min")

        if args.combine:
            all_audio_parts.append(audio)
            all_audio_parts.append(chapter_silence)
        else:
            # Determine output path for this chapter
            safe_title = _safe_name(title)
            filename   = f"{pdf_path.stem}_{idx:02d}_{safe_title}.mp3"

            if args.output and not out_arg.is_dir() and len(chapters) == 1:
                # User gave an explicit file path and there's only one chapter
                out_path = out_arg
                out_path.parent.mkdir(parents=True, exist_ok=True)
            else:
                out_dir = out_arg if out_arg.is_dir() else out_arg
                out_dir.mkdir(parents=True, exist_ok=True)
                out_path = out_dir / filename

            save_mp3(audio, out_path, bitrate)
            print(f"    Saved : {out_path.name}\n")
            saved_files.append(out_path)

    # ---- Combined mode: save single file ----
    if args.combine and all_audio_parts:
        combined = np.concatenate(all_audio_parts)
        duration_min = len(combined) / SAMPLE_RATE / 60

        if args.output and not args.output.is_dir():
            combined_path = out_arg
            combined_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            out_dir = out_arg if out_arg.is_dir() else out_arg
            out_dir.mkdir(parents=True, exist_ok=True)
            combined_path = out_dir / f"{pdf_path.stem}_combined.mp3"

        print(f"  Combining {len(chapters)} chapters → {combined_path.name}")
        print(f"  Total duration: {duration_min:.1f} min")
        save_mp3(combined, combined_path, bitrate)
        saved_files.append(combined_path)

    # ---- Summary ----
    if saved_files:
        print(f"\nDone.  {len(saved_files)} file(s) saved to: {saved_files[0].parent}")
        for f in saved_files:
            mins = ""   # could add duration tracking here if needed
            print(f"  {f.name}{mins}")
    else:
        print("\nNo files were saved (all chapters may have been image-only).",
              file=sys.stderr)


if __name__ == "__main__":
    main()
