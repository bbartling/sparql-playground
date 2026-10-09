from __future__ import annotations

import argparse
import sys
from pathlib import Path

import uvicorn

from brickts.graph.render import render_model, write_turtle
from brickts.graph.service import GraphService
from brickts.graph.validate import run_shacl, run_sparql_checks
from brickts.ingest import bootstrap_all
from brickts.logging import configure_logging
from brickts.settings import Settings


def _settings(root: Path | None = None) -> Settings:
    base = root or Path.cwd()
    return Settings().resolve(base)


def cmd_model_build(args: argparse.Namespace) -> int:
    s = _settings()
    site = s.site_model_path
    mapping = s.points_dir / "BUILDING_50__AHU_1.csv"
    if args.mapping:
        mapping = Path(args.mapping)
    out = s.model_path
    g = render_model(site, mapping)
    write_turtle(g, out)
    print(f"Wrote {out} ({len(g)} triples)")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    s = _settings()
    configure_logging(s.log_level, s.log_json)
    graph = GraphService(s)
    issues = run_sparql_checks(graph.state.model, graph.ontology)
    for issue in issues:
        print(f"{issue.check}: {issue.count} rows")
        if issue.count and issue.check.startswith("missing"):
            return 1
    if args.shacl:
        ok, report = run_shacl(graph.state.model, graph.ontology)
        if not ok:
            print(report[:2000])
            return 1
    return 0


def cmd_bootstrap(args: argparse.Namespace) -> int:
    s = _settings()
    configure_logging(s.log_level, s.log_json)
    results = bootstrap_all(s, force=args.force)
    for r in results:
        print(r)
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    s = _settings()
    uvicorn.run(
        "brickts.api.app:create_app",
        factory=True,
        host=args.host or s.host,
        port=args.port or s.port,
        log_level=s.log_level.lower(),
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="brickts")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_build = sub.add_parser("model", help="model commands")
    build_sub = p_build.add_subparsers(dest="model_cmd", required=True)
    p_mb = build_sub.add_parser("build", help="render building TTL from site + points CSV")
    p_mb.add_argument("--mapping", default=None)
    p_mb.set_defaults(func=cmd_model_build)

    p_val = sub.add_parser("validate", help="SPARQL invariant checks")
    p_val.add_argument("--shacl", action="store_true")
    p_val.set_defaults(func=cmd_validate)

    p_boot = sub.add_parser("bootstrap", help="ingest CSV datasets into SQLite")
    p_boot.add_argument("--force", action="store_true")
    p_boot.set_defaults(func=cmd_bootstrap)

    p_serve = sub.add_parser("serve", help="run HTTP API + UI")
    p_serve.add_argument("--host", default=None)
    p_serve.add_argument("--port", type=int, default=None)
    p_serve.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
