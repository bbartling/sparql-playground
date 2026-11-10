# Weekly offline packs (PDF)

Printable packs of the written lessons, 5.5×8.5 in pages. Each has the week's five daily lessons with the answers
unfolded, plus a short reading list. The day's scripts (`dayNN_pandas.py` and `dayNN_sql.py` in Weeks 1–5, one
`dayNN_rdf.py` in Weeks 6–9) are in the repo next to each lesson; run them with
`uv run python lessons/course.py run N`.

| Week | PDF |
| --- | --- |
| 1 — find your way around (read-only) | [week-01.pdf](week-01.pdf) |
| 2 — units, joins and conditions | [week-02.pdf](week-02.pdf) |
| 3 — fault detection in SQL and pandas | [week-03.pdf](week-03.pdf) |
| 4 — FDD at scale: pandas vs SQL vs plain Python | [week-04.pdf](week-04.pdf) |
| 5 — data modeling: Haystack RDF and external timeseries references | [week-05.pdf](week-05.pdf) |
| 6 — RDF basics, by hand (Burger Barn) | [week-06.pdf](week-06.pdf) |
| 7 — your own ontology: RDFS, OWL and SHACL | [week-07.pdf](week-07.pdf) |
| 8 — building an ontology on purpose (Ontology Development 101) | [week-08.pdf](week-08.pdf) |
| 9 — publishing your own ontology | [week-09.pdf](week-09.pdf) |

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
