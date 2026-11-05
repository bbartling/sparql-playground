# Weekly offline packs (PDF)

Printable packs of the written lessons, 5.5×8.5 in pages. Each has the week's five daily lessons with the answers
unfolded, plus a short reading list.

| Week | PDF |
| --- | --- |
| 1 — find your way around (read-only) | [week-01.pdf](week-01.pdf) |
| 2 — lookups, joins and conditions | [week-02.pdf](week-02.pdf) |
| 3 — fault detection in SQL | [week-03.pdf](week-03.pdf) |

## Rebuild

Needs [Pandoc](https://pandoc.org/) on `PATH` (or `PANDOC=/path/to/pandoc`). PDF uses WeasyPrint when it's
installed, otherwise headless Chrome/Edge.

```bash
# from the repository root: every written week
uv run python lessons/build_week_pdf.py --all

# one week
uv run python lessons/build_week_pdf.py --week 2
```

Rebuild after editing a lesson, so the PDF matches the Markdown.
