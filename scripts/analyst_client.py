#!/usr/bin/env python3
"""Local Open-FDD runner against a remote brickts API (Render or localhost).

Architecture (this is the intended split):

  SERVER (model + timeseries)
    - Brick RDF model, SPARQL, point lookup, timeseries JSON
    - GET /api/equipment/{id}/faults  → which rules have required roles
    - Does NOT run open-fdd math

  YOUR LAPTOP (this script)
    - for each applicable rule: lesson → fetch series → open_fdd.rules.run_rule
    - prints FAULT / hours / intervals

Examples:
  # Summarize applicable rules only
  uv run python scripts/analyst_client.py \\
    --base-url https://sparql-playground.onrender.com --equipment AHU_1 --list-only

  # One rule
  uv run python scripts/analyst_client.py \\
    --base-url https://sparql-playground.onrender.com --equipment AHU_1 --rule FC2

  # For-loop every applicable role-based rule on AHU_1
  uv run python scripts/analyst_client.py \\
    --base-url https://sparql-playground.onrender.com --equipment AHU_1 --all-applicable

  # All AHUs × all applicable rules
  uv run python scripts/analyst_client.py \\
    --base-url https://sparql-playground.onrender.com --all-equipment --all-applicable
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings

import httpx
import pandas as pd
from open_fdd.rules import run_rule

warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    module=r"open_fdd\.rules\.evidence",
)


def find_one(client, equip: str, **params: str):
    r = client.get(f"/api/equipment/{equip}/points", params=params)
    r.raise_for_status()
    pts = r.json()["points"]
    if len(pts) != 1:
        raise SystemExit(f"expected 1 point for {params}, got {len(pts)}")
    return pts[0]


def fetch_series(client: httpx.Client, point_id: str) -> pd.Series:
    r = client.get(f"/api/points/{point_id}/timeseries")
    r.raise_for_status()
    samples = r.json()["samples"]
    idx = pd.to_datetime([s["ts"] for s in samples], unit="s", utc=True)
    return pd.Series([s["value"] for s in samples], index=idx, name=point_id)


def list_ahu_ids(client: httpx.Client) -> list[str]:
    r = client.get("/api/equipment")
    r.raise_for_status()
    ids = []
    for row in r.json().get("equipment", []):
        eid = row.get("equipment_id") or ""
        if eid.startswith("AHU_"):
            ids.append(eid)
    return sorted(set(ids))


def list_applicable(client: httpx.Client, equipment_id: str) -> list[dict]:
    faults = client.get(f"/api/equipment/{equipment_id}/faults", params={"include_generic": False})
    faults.raise_for_status()
    return [f for f in faults.json() if f.get("applicable")]


def run_fc1(client: httpx.Client, equipment_id: str) -> None:
    """Legacy helper used by tests: resolve FC1 roles then run_rule locally."""
    roles = {
        "duct-static-pressure": find_one(
            client, equipment_id, brick_class="Supply_Air_Static_Pressure_Sensor"
        ),
        "duct-static-pressure-sp": find_one(
            client,
            equipment_id,
            tags="Supply,Air,Static,Pressure,Setpoint",
        ),
        "fan-cmd": find_one(
            client,
            equipment_id,
            brick_class="Fan_Speed_Command",
            parent_class="Supply_Fan",
        ),
    }
    series = {role: fetch_series(client, pt["point_id"]) for role, pt in roles.items()}
    df = pd.DataFrame(series).sort_index()
    df.attrs.update(equipment_id=equipment_id, equipment_type="ahu")
    res = run_rule("FC1", df, poll_seconds=300)
    print(res.status, res.fault_hours, res.fault_pct, res.sample_count, res.fault_sample_count)
    evidence = res.to_dict().get("evidence", {})
    confirmed = evidence.get("confirmed_fault", {})
    intervals = confirmed.get("fault_intervals", [])[:5]
    print(intervals)


def fetch_lesson(client: httpx.Client, equipment_id: str, rule_id: str) -> dict:
    lesson = client.get(f"/api/equipment/{equipment_id}/faults/{rule_id}/lesson")
    lesson.raise_for_status()
    return lesson.json()


def run_rule_from_lesson(
    client: httpx.Client,
    equipment_id: str,
    rule_id: str,
    *,
    equipment_type: str = "ahu",
    poll_seconds: int = 300,
    quiet: bool = False,
) -> dict:
    """Lesson bindings from server → timeseries from server → open-fdd on this machine."""
    data = fetch_lesson(client, equipment_id, rule_id)
    if not quiet:
        print(
            json.dumps(
                {
                    "rule_id": data.get("rule_id"),
                    "title": data.get("title"),
                    "roles": [
                        {
                            "role": x.get("role"),
                            "point_id": (x.get("binding") or {}).get("point_id"),
                            "error": x.get("error"),
                        }
                        for x in data.get("lessons", [])
                    ],
                },
                indent=2,
            )
        )
    series: dict[str, pd.Series] = {}
    for item in data.get("lessons", []):
        binding = item.get("binding")
        if not binding:
            raise SystemExit(item.get("error") or f"missing role {item.get('role')}")
        role = item["role"]
        series[role] = fetch_series(client, binding["point_id"])
        if not quiet:
            print(f"  loaded {role}: {binding['point_id']} ({len(series[role])} samples)")
    if not series:
        raise SystemExit(f"no role bindings for {rule_id}")
    df = pd.DataFrame(series).sort_index()
    df.attrs.update(equipment_id=equipment_id, equipment_type=equipment_type)
    res = run_rule(rule_id, df, poll_seconds=poll_seconds)
    summary = {
        "equipment_id": equipment_id,
        "rule_id": rule_id,
        "status": str(getattr(res, "status", "")),
        "fault_hours": getattr(res, "fault_hours", None),
        "fault_pct": getattr(res, "fault_pct", None),
        "sample_count": getattr(res, "sample_count", None),
        "fault_sample_count": getattr(res, "fault_sample_count", None),
    }
    print(
        f"{equipment_id} {rule_id}: {summary['status']} "
        f"hours={summary['fault_hours']} pct={summary['fault_pct']} "
        f"samples={summary['sample_count']} fault_samples={summary['fault_sample_count']}"
    )
    evidence = res.to_dict().get("evidence", {}) if hasattr(res, "to_dict") else {}
    confirmed = evidence.get("confirmed_fault", {})
    intervals = (confirmed.get("fault_intervals") or [])[:3]
    if intervals and not quiet:
        print(f"  intervals: {intervals}")
    return summary


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--base-url",
        default="https://sparql-playground.onrender.com",
        help="brickts API (model + timeseries live here)",
    )
    p.add_argument("--equipment", default=None, help="e.g. AHU_1 (omit with --all-equipment)")
    p.add_argument("--rule", default="FC1", help="open-fdd rule id when not using --all-applicable")
    p.add_argument(
        "--all-applicable",
        action="store_true",
        help="for-loop every applicable role-based rule (local crunch)",
    )
    p.add_argument(
        "--all-equipment",
        action="store_true",
        help="for-loop every AHU_* from GET /api/equipment",
    )
    p.add_argument(
        "--list-only",
        action="store_true",
        help="only print applicable rules from the server (no crunch)",
    )
    p.add_argument(
        "--local-fc1",
        action="store_true",
        help="legacy FC1 point lookup (tests)",
    )
    p.add_argument("--lesson-only", action="store_true", help="print lesson JSON only")
    p.add_argument("--quiet", action="store_true", help="less per-role chatter in loops")
    args = p.parse_args()

    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=300.0) as client:
        if args.all_equipment:
            equipment_ids = list_ahu_ids(client)
        elif args.equipment:
            equipment_ids = [args.equipment]
        else:
            raise SystemExit("pass --equipment AHU_1 or --all-equipment")

        print(f"API: {args.base_url}")
        print("Split: server=model/SPARQL/timeseries · laptop=open-fdd run_rule")
        print(f"Equipment: {', '.join(equipment_ids)}")

        report: list[dict] = []
        for equipment_id in equipment_ids:
            applicable = list_applicable(client, equipment_id)
            print(f"\n=== {equipment_id}: {len(applicable)} applicable role-based rules ===")
            for f in applicable:
                print(f"  {f['rule_id']}: {f['title']}")

            if args.list_only:
                continue

            if args.lesson_only:
                print(json.dumps(fetch_lesson(client, equipment_id, args.rule), indent=2)[:4000])
                continue

            if args.local_fc1:
                if args.rule != "FC1":
                    raise SystemExit("--local-fc1 only supports FC1")
                run_fc1(client, equipment_id)
                continue

            rules = [f["rule_id"] for f in applicable] if args.all_applicable else [args.rule]
            for rule_id in rules:
                print(f"\n--- {equipment_id} / {rule_id} (local crunch) ---")
                try:
                    report.append(
                        run_rule_from_lesson(
                            client,
                            equipment_id,
                            rule_id,
                            quiet=args.quiet or args.all_applicable,
                        )
                    )
                except SystemExit as exc:
                    print(f"  SKIP: {exc}")
                except Exception as exc:  # noqa: BLE001 - keep loop going for reports
                    print(f"  ERROR: {exc}")

        if report:
            print("\n=== report summary (computed locally) ===")
            print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
