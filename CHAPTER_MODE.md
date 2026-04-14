# Converting Chapters into Separate MP3s

By default (without `--full`), the script runs in **chapter mode** — it splits the PDF by chapter and saves one MP3 per chapter.

---

## The command

```bash
python3 pdf_to_audio.py '/path/to/your/book.pdf' --exclude all --quality low
```

The only difference from the full-PDF command is the absence of `--full`. Every other option (`--exclude`, `--quality`, `--speed`, `--voice`, `--output`) works exactly the same way.

---

## What happens when you run it

### If the PDF has an embedded table of contents

Most books and some academic PDFs have a table of contents baked into the file itself (separate from the visible pages). The script detects this automatically and shows it to you:

```
Scanning for chapters in: EcoSocialism-DavidPepper-1993.pdf
  Auto-detected 8 chapters from the embedded table of contents.

  Found 8 chapters:

     1.  Introduction                                     p.1–12
     2.  The Roots of Ecosocialism                        p.13–40
     3.  Nature and Society                               p.41–78
     4.  Green Politics                                   p.79–115
     5.  Economy and Ecology                              p.116–150
     6.  Socialism and the Environment                    p.151–190
     7.  Towards Ecosocialism                             p.191–225
     8.  Conclusion                                       p.226–240

  Which chapters? (e.g. 1,3,5-7  or  'all'  — default: all):
```

You then type which chapters you want:

| What you type | What you get |
|---|---|
| *(just press Enter)* | All chapters |
| `all` | All chapters |
| `1,3,5` | Chapters 1, 3, and 5 only |
| `2-5` | Chapters 2 through 5 |
| `1,4-6,8` | Chapters 1, 4, 5, 6, and 8 |

---

### If the PDF has no embedded table of contents

Some PDFs (especially scanned books) don't have a machine-readable TOC. In that case the script asks you to enter page ranges manually:

```
  No embedded table of contents found.
  Enter page ranges manually, one per line.
  Format:  Title: start-end   (e.g.  Introduction: 1-15)

  Chapter 1: Introduction: 1-12
  Chapter 2: The Roots: 13-40
  Chapter 3:                      ← leave blank and press Enter to finish
```

---

## Output files

Each selected chapter is saved as a separate MP3 in the same folder as the PDF (or in `--output` if specified):

```
EcoSocialism-DavidPepper-1993_01_Introduction.mp3
EcoSocialism-DavidPepper-1993_02_The_Roots_of_Ecosocialism.mp3
EcoSocialism-DavidPepper-1993_03_Nature_and_Society.mp3
...
```

---

## Merge all chapters into one file instead

Add `--combine` if you want a single MP3 from all selected chapters:

```bash
python3 pdf_to_audio.py '/path/to/book.pdf' --exclude all --quality low --combine
```

Output: `EcoSocialism-DavidPepper-1993_combined.mp3`

---

## Full example with all options

```bash
python3 pdf_to_audio.py '/Users/narslan/Downloads/EcoSocialism-DavidPepper-1993.pdf' \
  --exclude all \
  --quality low \
  --speed 1.0 \
  --voice af_heart \
  --output ~/Desktop/audiobooks/
```

Then at the prompt, type the chapters you want (e.g. `1-3`) and press Enter.
