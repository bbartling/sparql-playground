#!/usr/bin/env python3
"""Build a printable pack (PDF, 5.5x8.5in) for one course week.

Concatenates that week's five daily lessons, unfolds the hidden answers, appends a short
reference list, and writes lessons/pdf/week-NN.pdf. Same look as the old SQL course packs.

Needs a ``pandoc`` binary on PATH (or set PANDOC). PDF uses WeasyPrint when it's installed,
otherwise headless Chrome/Edge.

    uv run python lessons/build_week_pdf.py --week 1
    uv run python lessons/build_week_pdf.py --all
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PDF_DIR = HERE / "pdf"
README = HERE / "README.md"
DAYS_PER_WEEK = 5

# Weeks that have written lessons, and where they live.
UNIT_DIRS = {
    1: "unit1-sqlite",
    2: "unit1-sqlite",
    3: "unit1-sqlite",
    4: "unit2-python",
    5: "unit3-modeling",
    6: "unit4-rdf-by-hand",
    7: "unit4-rdf-by-hand",
    8: "unit4-rdf-by-hand",
    9: "unit4-rdf-by-hand",
}

REFERENCES = {
    6: [
        ("W3C: RDF 1.1 Primer", "https://www.w3.org/TR/rdf11-primer/"),
        ("W3C: RDF 1.1 Turtle", "https://www.w3.org/TR/turtle/"),
        ("W3C: SPARQL 1.1 Query Language", "https://www.w3.org/TR/sparql11-query/"),
        ("W3C: XML Schema datatypes", "https://www.w3.org/TR/xmlschema11-2/"),
        ("rdflib documentation", "https://rdflib.readthedocs.io/"),
        ("Brick: relationships", "https://docs.brickschema.org/brick/relationships.html"),
    ],
    7: [
        ("W3C: RDF Schema 1.1", "https://www.w3.org/TR/rdf-schema/"),
        ("W3C: OWL 2 Web Ontology Language Primer", "https://www.w3.org/TR/owl2-primer/"),
        ("W3C: Shapes Constraint Language (SHACL)", "https://www.w3.org/TR/shacl/"),
        ("W3C: SPARQL 1.1 property paths", "https://www.w3.org/TR/sparql11-query/#propertypaths"),
        ("owlrl (OWL 2 RL reasoner for rdflib)", "https://github.com/RDFLib/OWL-RL"),
        ("pySHACL", "https://github.com/RDFLib/pySHACL"),
        ("Brick: relationships", "https://docs.brickschema.org/brick/relationships.html"),
        ("ASHRAE 223P (open223.info)", "https://open223.info/"),
        ("Project Haystack: RDF", "https://project-haystack.org/doc/docHaystack/Rdf"),
    ],
    8: [
        (
            "Noy & McGuinness: Ontology Development 101",
            "https://protege.stanford.edu/publications/ontology_development/ontology101.pdf",
        ),
        ("W3C: OWL 2 Web Ontology Language Primer", "https://www.w3.org/TR/owl2-primer/"),
        ("W3C: Shapes Constraint Language (SHACL)", "https://www.w3.org/TR/shacl/"),
        ("W3C: SPARQL 1.1 Query Language", "https://www.w3.org/TR/sparql11-query/"),
        (
            "W3C: SKOS reference (definitions, exactMatch, closeMatch)",
            "https://www.w3.org/TR/skos-reference/",
        ),
        ("Brick: extending Brick", "https://docs.brickschema.org/extra/extending.html"),
    ],
    9: [
        ("w3id.org: creating an identifier", "https://docs.w3id.org/guides/create-an-id"),
        ("w3id.org: content negotiation", "https://docs.w3id.org/guides/content-negotiation"),
        (
            "W3C: Best Practice Recipes for Publishing RDF Vocabularies",
            "https://www.w3.org/TR/swbp-vocab-pub/",
        ),
        (
            "W3C: OWL 2 ontology IRIs and version IRIs",
            "https://www.w3.org/TR/owl2-syntax/#Ontology_IRI_and_Version_IRI",
        ),
        ("W3C: SPARQL 1.1 Update", "https://www.w3.org/TR/sparql11-update/"),
        ("Semantic Versioning", "https://semver.org/"),
        ("Brick: extending Brick", "https://docs.brickschema.org/extra/extending.html"),
    ],
    1: [
        ("Python sqlite3 module", "https://docs.python.org/3/library/sqlite3.html"),
        (
            "pandas: comparison with SQL",
            "https://pandas.pydata.org/docs/getting_started/comparison/comparison_with_sql.html",
        ),
        ("DB Browser for SQLite", "https://sqlitebrowser.org/"),
        ("SQLite SELECT", "https://sqlite.org/lang_select.html"),
        ("SQLite date and time functions", "https://sqlite.org/lang_datefunc.html"),
        ("SQLite aggregate functions", "https://sqlite.org/lang_aggfunc.html"),
        ("RFC 9562: UUIDs (version 5 = name-based)", "https://www.rfc-editor.org/rfc/rfc9562"),
    ],
    2: [
        (
            "SQLite joins (SELECT, the FROM clause)",
            "https://sqlite.org/lang_select.html#fromclause",
        ),
        ("SQLite CASE expressions", "https://sqlite.org/lang_expr.html#case"),
        ("SQLite CREATE VIEW", "https://sqlite.org/lang_createview.html"),
        ("DB Browser: importing CSV", "https://github.com/sqlitebrowser/sqlitebrowser/wiki"),
        (
            "TimescaleDB time_bucket",
            "https://docs.timescale.com/api/latest/hyperfunctions/time_bucket/",
        ),
    ],
    3: [
        ("SQLite window functions", "https://sqlite.org/windowfunctions.html"),
        ("pandas: windowing operations", "https://pandas.pydata.org/docs/user_guide/window.html"),
        ("SQLite query planner", "https://sqlite.org/queryplanner.html"),
        ("SQLite EXPLAIN QUERY PLAN", "https://sqlite.org/eqp.html"),
        (
            "Open-FDD SQL cookbook",
            "https://bbartling.github.io/open-fdd/rules/cookbook/sql-cookbook.html",
        ),
        ("TimescaleDB hypertables", "https://docs.timescale.com/use-timescale/latest/hypertables/"),
        (
            "TimescaleDB continuous aggregates",
            "https://docs.timescale.com/use-timescale/latest/continuous-aggregates/",
        ),
    ],
    5: [
        (
            "Brick: timeseries storage (ref schema)",
            "https://docs.brickschema.org/metadata/timeseries-storage.html",
        ),
        ("Project Haystack: defs", "https://project-haystack.org/doc/docHaystack/Defs"),
        ("Project Haystack: RDF", "https://project-haystack.org/doc/docHaystack/Rdf"),
        ("RFC 9562: UUIDs (version 5 = name-based)", "https://www.rfc-editor.org/rfc/rfc9562"),
        ("rdflib documentation", "https://rdflib.readthedocs.io/"),
        ("FastAPI testing (TestClient)", "https://fastapi.tiangolo.com/tutorial/testing/"),
    ],
    4: [
        ("Python timeit", "https://docs.python.org/3/library/timeit.html"),
        ("Python tracemalloc", "https://docs.python.org/3/library/tracemalloc.html"),
        (
            "pandas: scaling to large datasets",
            "https://pandas.pydata.org/docs/user_guide/scale.html",
        ),
        (
            "pandas.merge_asof",
            "https://pandas.pydata.org/docs/reference/api/pandas.merge_asof.html",
        ),
        ("SQLite query optimizer overview", "https://sqlite.org/optoverview.html"),
        (
            "Open-FDD SQL cookbook",
            "https://bbartling.github.io/open-fdd/rules/cookbook/sql-cookbook.html",
        ),
    ],
}

CSS = """
    @page { size: 5.5in 8.5in; margin: 0.6in; }
    body {
      font-family: Georgia, "Times New Roman", serif;
      font-size: 11.5pt;
      line-height: 1.45;
      color: #111;
    }
    h1, h2, h3 { font-family: Helvetica, Arial, sans-serif; page-break-after: avoid; }
    h1 { font-size: 18pt; margin-top: 1.2em; }
    h2 { font-size: 14pt; }
    h3 { font-size: 12pt; }
    code, pre { font-family: "DejaVu Sans Mono", Consolas, monospace; font-size: 9.5pt; }
    pre {
      background: #f4f4f4;
      padding: 0.6em 0.8em;
      white-space: pre-wrap;
      page-break-inside: avoid;
    }
    a { color: #0645ad; text-decoration: none; }
    table { border-collapse: collapse; width: 100%; font-size: 10pt; }
    /* pandoc's default CSS makes tables scroll sideways, which clips them on paper */
    table { display: table; overflow-x: visible; table-layout: fixed; }
    th, td { border: 1px solid #ccc; padding: 0.25em 0.4em; overflow-wrap: anywhere; }
    td code, th code { overflow-wrap: anywhere; word-break: break-word; }
    """


RDF_WEEKS = {6, 7, 8, 9}
INTRO_PANDAS_SQL = (
    "Five daily lessons. Each day has two scripts that compute the same thing: "
    "`dayNN_pandas.py` reads the CSV export into pandas, `dayNN_sql.py` runs SQLite "
    "queries on the same rows (`uv run python lessons/course.py setup` loads them "
    "once). Run both with `uv run python lessons/course.py run N` and compare the "
    "printouts. The scripts are in the repo next to each lesson. Keep notes under the "
    "ignored `student-work/` folder."
)
INTRO_RDF = (
    "Five daily lessons on Burger Barn, a made-up burger restaurant. Each day has one "
    "short script, `dayNN_rdf.py`, that reads small hand-written Turtle files next to it "
    "in `lessons/unit4-rdf-by-hand/`. Run it with `uv run python lessons/course.py run N`. "
    "Every day ends with a box on how it maps to buildings (Brick, ASHRAE 223P, Project "
    "Haystack) and a burger mini challenge; its answer is in the Try it section. Keep notes "
    "under the ignored `student-work/` folder."
)


def pandoc() -> str:
    env = os.environ.get("PANDOC")
    if env:
        return env
    found = shutil.which("pandoc")
    if not found:
        raise SystemExit("pandoc not found. Install it, or set PANDOC to the binary path.")
    return found


def week_days(week: int) -> list[Path]:
    if week not in UNIT_DIRS:
        raise SystemExit(f"week {week} has no written lessons yet (weeks: {sorted(UNIT_DIRS)})")
    start = (week - 1) * DAYS_PER_WEEK + 1
    days = [HERE / UNIT_DIRS[week] / f"day{d:02d}.md" for d in range(start, start + DAYS_PER_WEEK)]
    for path in days:
        if not path.is_file():
            raise SystemExit(f"missing lesson file: {path.relative_to(HERE)}")
    return days


def week_title(week: int) -> str:
    match = re.search(rf"^\*\*Week {week}: (.+?)\*\*$", README.read_text(encoding="utf-8"), re.M)
    return f"Week {week} — {match.group(1)}" if match else f"Week {week}"


def printable(body: str) -> str:
    """Make a lesson read well on paper: answers unfolded, links to other lessons as text."""
    body = re.sub(r"<details><summary>(.*?)</summary>", r"**\1**", body)
    body = body.replace("</details>", "")
    # links to sibling lessons and repo files don't work in a PDF; keep the text
    body = re.sub(r"\[([^\]]+)\]\((?!https?://)[^)]+\)", r"\1", body)
    return body.strip() + "\n"


def build_markdown(week: int) -> str:
    title = week_title(week)
    days = week_days(week)
    parts = [
        f"% Building data course — {title}\n"
        "% sparql-playground / lessons\n"
        "% Generated for print and offline reading\n\n"
        f"# {title}\n\n"
        f"{INTRO_RDF if week in RDF_WEEKS else INTRO_PANDAS_SQL}\n\n"
        "## Contents\n\n"
    ]
    for path in days:
        heading = path.read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip()
        parts.append(f"- {heading}\n")
    parts.append("\n---\n\n")
    for path in days:
        parts.append(printable(path.read_text(encoding="utf-8")))
        parts.append('\n\n<div style="page-break-before: always;"></div>\n\n')
    heading = "Further reading" if week in RDF_WEEKS else "Reading"
    parts.append(
        f"# {heading} — Week {week}\n\nThe lessons first, then these for exact behavior.\n\n"
    )
    for name, url in REFERENCES.get(week, []):
        parts.append(f"- [{name}]({url})\n")
    return "".join(parts)


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def to_html(md_path: Path, html_path: Path) -> None:
    header = html_path.parent / "header.html"
    header.write_text(f"<style>{CSS}</style>\n", encoding="utf-8")
    run(
        [
            pandoc(),
            str(md_path),
            "-f",
            "markdown",
            "-t",
            "html5",
            "--standalone",
            f"--include-in-header={header}",
            "-o",
            str(html_path),
        ]
    )


def browser() -> str | None:
    for base in (os.environ.get("PROGRAMFILES", ""), os.environ.get("PROGRAMFILES(X86)", "")):
        for rel in (
            "Google/Chrome/Application/chrome.exe",
            "Microsoft/Edge/Application/msedge.exe",
        ):
            if base and (Path(base) / rel).is_file():
                return str(Path(base) / rel)
    for name in ("google-chrome", "chromium", "chromium-browser", "microsoft-edge"):
        if shutil.which(name):
            return shutil.which(name)
    return None


def write_pdf(md_path: Path, pdf_path: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        html_path = Path(tmp) / "week.html"
        to_html(md_path, html_path)
        try:
            from weasyprint import HTML  # noqa: PLC0415  (optional)

            HTML(filename=str(html_path), base_url=tmp).write_pdf(str(pdf_path))
            return
        except (ImportError, OSError):
            pass
        exe = browser()
        if not exe:
            raise SystemExit("No PDF engine: install weasyprint, or Chrome/Edge.")
        pdf_path.unlink(missing_ok=True)
        proc = subprocess.run(
            [
                exe,
                "--headless=new",
                "--disable-gpu",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-extensions",
                f"--user-data-dir={Path(tmp) / 'profile'}",
                "--no-pdf-header-footer",
                f"--print-to-pdf={pdf_path.resolve()}",
                html_path.as_uri(),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0 or not pdf_path.is_file() or pdf_path.stat().st_size < 1000:
            raise SystemExit(f"headless PDF failed (rc={proc.returncode}): {proc.stderr[-1500:]}")


def build_week(week: int) -> Path:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = PDF_DIR / f"week-{week:02d}.pdf"
    with tempfile.TemporaryDirectory() as tmp:
        md_path = Path(tmp) / f"week-{week:02d}.md"
        md_path.write_text(build_markdown(week), encoding="utf-8")
        write_pdf(md_path, pdf_path)
    return pdf_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--week", type=int, help=f"course week ({min(UNIT_DIRS)}-{max(UNIT_DIRS)})")
    group.add_argument("--all", action="store_true", help="every week that has written lessons")
    args = parser.parse_args(argv)
    for week in sorted(UNIT_DIRS) if args.all else [args.week]:
        path = build_week(week)
        print(f"wrote {path.relative_to(HERE.parent)} ({path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
