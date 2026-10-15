"""Small psql launcher for an isolated course DB; no application database adapter."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STATE = ROOT / "var" / "sql-course"
DATABASE = "brickts_course"


def environment() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PGDATABASE", DATABASE)
    env.setdefault("PGCONNECT_TIMEOUT", "5")
    env.setdefault("PGOPTIONS", "-c statement_timeout=15000 -c lock_timeout=3000")
    if env.get("COURSE_MODE", "docker") not in {"docker", "native"}:
        raise ValueError("COURSE_MODE must be docker or native")
    if env.get("COURSE_MODE", "docker") == "docker" and not env.get("COURSE_PASSWORD"):
        STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
        password_file = STATE / "password"
        if not password_file.exists():
            fd = os.open(password_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as handle:
                handle.write(secrets.token_urlsafe(24))
        env["COURSE_PASSWORD"] = password_file.read_text().strip()
    return env


def compose() -> list[str]:
    return ["docker", "compose", "-p", "brickts-sql-course", "-f", str(HERE / "compose.yaml")]


def psql_command(env: dict[str, str], *, interactive: bool = False) -> list[str]:
    if env.get("COURSE_MODE", "docker") == "native":
        return ["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-P", "pager=off"]
    return compose() + [
        "exec",
        *([] if interactive else ["-T"]),
        "-e",
        "PGOPTIONS=-c statement_timeout=15000 -c lock_timeout=3000",
        "db",
        "psql",
        "-X",
        "-q",
        "-U",
        "learner",
        "-d",
        DATABASE,
        "-v",
        "ON_ERROR_STOP=1",
        "-P",
        "pager=off",
    ]


def query(text: str, env: dict[str, str], *, tuples: bool = False) -> str:
    command = psql_command(env) + (["-A", "-t"] if tuples else []) + ["-f", "-"]
    result = subprocess.run(
        command, input=text, text=True, capture_output=True, env=env, timeout=120, check=True
    )
    return result.stdout


def require_course_database(env: dict[str, str]) -> None:
    observed = query("SELECT current_database();", env, tuples=True).strip()
    if observed != DATABASE:
        raise ValueError(f"Refusing course command: expected {DATABASE}, got {observed}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["up", "down", "doctor", "load", "psql", "run", "check"])
    parser.add_argument("file", nargs="?", type=Path)
    args = parser.parse_args(argv)
    env = environment()
    if args.command in {"up", "down"}:
        if env.get("COURSE_MODE", "docker") != "docker":
            parser.error(
                "up/down control only the isolated course Compose project, never a shared server"
            )
        command = compose() + (
            ["up", "-d", "--wait", "--wait-timeout", "90"] if args.command == "up" else ["down"]
        )
        subprocess.run(command, env=env, check=True, timeout=180)
        return 0
    require_course_database(env)
    if args.command == "doctor":
        print(
            query(
                "SHOW server_version; "
                "SELECT extversion FROM pg_extension WHERE extname='timescaledb';",
                env,
            )
        )
    elif args.command == "psql":
        subprocess.run(psql_command(env, interactive=True), env=env, check=True)
    elif args.command == "load":
        for name in ["00_schema.sql", "01_seed.sql", "03_assertions.sql"]:
            print(query((HERE / "sql" / name).read_text(), env))
    elif args.command == "run":
        if args.file is None or args.file.suffix.lower() != ".sql":
            parser.error("run requires a readable .sql file path")
        print(query(args.file.read_text(), env))
    elif args.command == "check":
        print(query((HERE / "sql" / "03_assertions.sql").read_text(), env))
        runtime_sql = (HERE / "reference" / "runtime.sql").read_text().rstrip().removesuffix(";")
        print(query(runtime_sql + ";", env))
        runtimes = json.loads(
            query("SELECT json_agg(x) FROM (" + runtime_sql + ") x;", env, tuples=True)
        )
        fixture = json.loads((HERE / "fixture.json").read_text())
        expected_hours = [24, 12, 12]
        by_id = {row["equipment_id"]: row for row in runtimes}
        if len(runtimes) != 3:
            raise ValueError("Runtime query must return exactly three equipment identities")
        for equipment, hours in zip(fixture["equipment"], expected_hours, strict=True):
            row = by_id[equipment["equipment_id"]]
            if row["observed_run_hours"] != hours or row["known_status_hours"] != 48:
                raise ValueError("Runtime known-answer or coverage mismatch")
        result = query((HERE / "reference" / "duct_static.sql").read_text(), env)
        print(result)
        # Assert expected numbers, not merely successful SQL execution.
        raw = (HERE / "reference" / "duct_static.sql").read_text().rstrip().removesuffix(";")
        rows = json.loads(query("SELECT json_agg(x) FROM (" + raw + ") x;", env, tuples=True))
        if len(rows) != 3:
            raise ValueError("Fault query must return exactly three equipment identities")
        target = next(
            x for x in rows if x["site_id"] == "SYN-NORTH" and x["equipment_label"] == "Supply A"
        )
        if (target["raw_seconds"], target["confirmed_seconds"], target["unknown_seconds"]) != (
            3000,
            1800,
            600,
        ):
            raise ValueError(f"Teaching fault known-answer failed: {target}")
        for row in rows:
            if row["equipment_id"] != target["equipment_id"] and any(
                row[field] != 0 for field in ("raw_seconds", "confirmed_seconds", "unknown_seconds")
            ):
                raise ValueError("Unrelated equipment received a synthetic fault")
        print("PASS: gap-aware teaching fault has 3000 raw/1800 confirmed/600 unknown seconds")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        # Avoid echoing process arguments or environment (native connections may use secrets).
        raise SystemExit(
            f"Course command failed (exit {exc.returncode}): {exc.stderr or 'see command output'}"
        ) from None
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        raise SystemExit(f"Course lab: {exc}") from None
