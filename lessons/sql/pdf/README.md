# Weekly offline packs (PDF + EPUB)

Generated packs for Kindle / print reading. Prefer **EPUB** on a Kindle (reflowable); PDF uses a 5.5×8.5in page for night reading.

| Week | Files |
| --- | --- |
| 1 | [week-01.epub](week-01.epub) · [week-01.pdf](week-01.pdf) · [week-01.md](week-01.md) |

Each pack is days `(week−1)×7+1` … `week×7` (challenge last), plus that week’s section from [SOURCES.md](../SOURCES.md).

## Rebuild

Needs [Pandoc](https://pandoc.org/) on `PATH` (or `PANDOC=/path/to/pandoc`). PDF rendering uses WeasyPrint:

```bash
# from repository root
uv run --with weasyprint python lessons/sql/build_week_pdf.py --week 1
uv run --with weasyprint python lessons/sql/build_week_pdf.py --week 2
```

User-local Pandoc example (no root install):

```bash
# once
mkdir -p ~/.local/opt && cd /tmp
curl -fsSL -o pandoc.tar.gz \
  https://github.com/jgm/pandoc/releases/download/3.6.4/pandoc-3.6.4-linux-amd64.tar.gz
tar -xzf pandoc.tar.gz && mv pandoc-3.6.4 ~/.local/opt/pandoc
export PANDOC=~/.local/opt/pandoc/bin/pandoc
```
