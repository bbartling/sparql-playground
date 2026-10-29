# Weekly offline packs (PDF)

Generated packs for print or offline reading. Page size is 5.5×8.5in.

| Week | PDF |
| --- | --- |
| 1 | [week-01.pdf](week-01.pdf) |
| 2 | [week-02.pdf](week-02.pdf) |
| 3 | [week-03.pdf](week-03.pdf) |
| 4 | [week-04.pdf](week-04.pdf) |
| 5 | [week-05.pdf](week-05.pdf) |
| 6 | [week-06.pdf](week-06.pdf) |
| 7 | [week-07.pdf](week-07.pdf) |
| 8 | [week-08.pdf](week-08.pdf) |
| 9 | [week-09.pdf](week-09.pdf) |
| 10 | [week-10.pdf](week-10.pdf) |
| 11 | [week-11.pdf](week-11.pdf) |
| 12 | [week-12.pdf](week-12.pdf) |

Each pack is days `(week−1)×7+1` … `week×7` (challenge last), plus that week’s section from [SOURCES.md](../SOURCES.md).

## Rebuild

Needs [Pandoc](https://pandoc.org/) on `PATH` (or `PANDOC=/path/to/pandoc`). PDF uses WeasyPrint when available; on Windows, headless Chrome/Edge is used automatically.

```bash
# from repository root — all weeks, PDF only
uv run python lessons/sql/build_week_pdf.py --all --pdf-only

# one week
uv run python lessons/sql/build_week_pdf.py --week 3 --pdf-only
```

Optional Kindle EPUB + intermediate Markdown (not kept in git by default):

```bash
uv run python lessons/sql/build_week_pdf.py --week 1
```
