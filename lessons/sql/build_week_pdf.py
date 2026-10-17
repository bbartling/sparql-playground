#!/usr/bin/env python3
"""Build a printable / Kindle pack for one course week.

Concatenates that week's daily lessons (challenge day last), appends the matching
SOURCES.md section, then writes Markdown, PDF, and EPUB under lessons/sql/pdf/.

Requires a ``pandoc`` binary on PATH (or set PANDOC). PDF uses WeasyPrint via
``uv run --with weasyprint`` when pandoc's weasyprint engine is unavailable.

Examples::

    uv run python lessons/sql/build_week_pdf.py --week 1
    uv run python lessons/sql/build_week_pdf.py --week 2
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
SOURCES = HERE / "SOURCES.md"
INDEX = HERE / "INDEX.md"
MAX_WEEK = 12


def _pandoc() -> str:
    env = os.environ.get("PANDOC")
    if env:
        return env
    local = Path.home() / ".local/opt/pandoc/bin/pandoc"
    if local.is_file():
        return str(local)
    found = shutil.which("pandoc")
    if not found:
        raise SystemExit(
            "pandoc not found. Install it, or set PANDOC to the binary path "
            "(e.g. ~/.local/opt/pandoc/bin/pandoc)."
        )
    return found


def week_day_range(week: int) -> range:
    if not 1 <= week <= MAX_WEEK:
        raise ValueError(f"week must be 1..{MAX_WEEK}")
    start = (week - 1) * 7 + 1
    return range(start, start + 7)


def week_title(week: int) -> str:
    text = INDEX.read_text(encoding="utf-8")
    match = re.search(rf"^### Week {week} — (.+)$", text, re.MULTILINE)
    if not match:
        return f"Week {week}"
    return f"Week {week} — {match.group(1).strip()}"


def week_sources_section(week: int) -> str:
    text = SOURCES.read_text(encoding="utf-8")
    match = re.search(
        rf"(^## Week {week}\n.*?)(?=^## Week |\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        raise SystemExit(f"No '## Week {week}' section in {SOURCES.name}")
    body = match.group(1).strip()
    return (
        f"# Primary reading — Week {week}\n\n"
        "Use the lesson first, then these references for precise behavior. "
        "Full list: [SOURCES.md](../SOURCES.md).\n\n"
        f"{body}\n"
    )


def build_combined_markdown(week: int) -> str:
    title = week_title(week)
    days = list(week_day_range(week))
    parts: list[str] = [
        f"% Brickts SQL course — {title}\n"
        f"% sparql-playground / lessons/sql\n"
        f"% Generated for offline / Kindle reading\n\n"
        f"# {title}\n\n"
        "This pack concatenates the six daily lessons and the weekly challenge, "
        "then the Week primary-reading links from SOURCES.md. Work the SQL in "
        "`psql` against `brickts_course`; keep notes under ignored "
        "`student-work/sql/`.\n\n"
        "## Contents\n\n"
    ]
    for day in days:
        path = HERE / f"day{day:02d}.md"
        heading = path.read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip()
        label = " (weekly challenge)" if day == days[-1] else ""
        parts.append(f"- Day {day:02d}{label}: {heading}\n")
    parts.append("\n---\n\n")

    for day in days:
        path = HERE / f"day{day:02d}.md"
        if not path.is_file():
            raise SystemExit(f"missing lesson file: {path.name}")
        body = path.read_text(encoding="utf-8").strip() + "\n"
        # Drop relative nav noise that is useless on a Kindle; keep lesson text.
        body = re.sub(
            r"\[Course index\]\([^)]+\)\s*·\s*\[Lab guide\]\([^)]+\)"
            r"(?:\s*·\s*\[Next:[^\]]+\]\([^)]+\))?\n*",
            "",
            body,
        )
        parts.append(body)
        if day != days[-1]:
            parts.append('\n\n<div style="page-break-before: always;"></div>\n\n---\n\n')
        else:
            parts.append("\n\n---\n\n")

    parts.append(week_sources_section(week))
    return "".join(parts)


def _run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def write_pdf_via_weasyprint(md_path: Path, pdf_path: Path, pandoc_bin: str) -> None:
    css = """
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
    th, td { border: 1px solid #ccc; padding: 0.25em 0.4em; }
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        html_path = tmp_path / "week.html"
        css_path = tmp_path / "kindle.css"
        css_path.write_text(css, encoding="utf-8")
        _run(
            [
                pandoc_bin,
                str(md_path),
                "-f",
                "markdown",
                "-t",
                "html5",
                "--standalone",
                f"--css={css_path}",
                "-o",
                str(html_path),
            ]
        )
        # Import inside function so --help works without the optional dep installed.
        from weasyprint import HTML  # noqa: PLC0415

        HTML(filename=str(html_path), base_url=str(tmp_path)).write_pdf(str(pdf_path))


def build_week(week: int) -> dict[str, Path]:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"week-{week:02d}"
    md_path = PDF_DIR / f"{stem}.md"
    pdf_path = PDF_DIR / f"{stem}.pdf"
    epub_path = PDF_DIR / f"{stem}.epub"

    md_path.write_text(build_combined_markdown(week), encoding="utf-8")
    pandoc_bin = _pandoc()

    _run(
        [
            pandoc_bin,
            str(md_path),
            "-o",
            str(epub_path),
            "--toc",
            "--toc-depth=2",
            f"--metadata=title:Brickts SQL — {week_title(week)}",
        ]
    )
    write_pdf_via_weasyprint(md_path, pdf_path, pandoc_bin)

    return {"md": md_path, "pdf": pdf_path, "epub": epub_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--week",
        type=int,
        required=True,
        help=f"Course week number (1–{MAX_WEEK})",
    )
    args = parser.parse_args(argv)
    outs = build_week(args.week)
    for kind, path in outs.items():
        size = path.stat().st_size
        print(f"wrote {kind}: {path.relative_to(HERE.parent.parent)} ({size} bytes)")
    print("Kindle tip: prefer the .epub (reflowable). PDF is fixed 5.5×8.5in pages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
