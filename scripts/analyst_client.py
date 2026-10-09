#!/usr/bin/env python3
"""Local Open-FDD runner: resolve Brick roles via the API, crunch faults with pandas.

The hosted UI is SPARQL-only. Use this script on your machine (against local or Render).

  uv run python scripts/analyst_client.py --equipment AHU_1 --rule FC1 --local-fc1
  uv run python scripts/analyst_client.py --base-url https://sparql-playground.onrender.com \\
      --equipment AHU_2 --rule FC1 --local-fc1
"""

from __future__ import annotations

import argparse
import json
import sys

import httpx
import pandas as pd
from open_fdd.rules import RULES, run_rule


def find_one(client, equip: str, **params: str):
    r = client.get(f"/api/equipment/{equip}/points", params=params)
    r.raise_for_status()
    pts = r.json()["points"]
    if len(pts) != 1:
        raise SystemExit(f"expected 1 point for {params}, got {len(pts)}")
    return pts[0]


def fetch_series(client: httpx.Client, point: dict) -> pd.Series:
    pid = point["point_id"]
    r = client.get(f"/api/points/{pid}/timeseries")
    r.raise_for_status()
    payload = r.json()
    samples = payload["samples"]
    idx = pd.to_datetime([s["ts"] for s in samples], unit="s", utc=True)
    vals = [s["value"] for s in samples]
    return pd.Series(vals, index=idx, name=pid)


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
    series = {role: fetch_series(client, pt) for role, pt in roles.items()}
    df = pd.DataFrame(series).sort_index()
    df.attrs.update(equipment_id=equipment_id, equipment_type="ahu")
    res = run_rule("FC1", df, poll_seconds=300)
    print(res.status, res.fault_hours, res.fault_pct, res.sample_count, res.fault_sample_count)
    evidence = res.to_dict().get("evidence", {})
    confirmed = evidence.get("confirmed_fault", {})
    intervals = confirmed.get("fault_intervals", [])[:5]
    print(intervals)


def show_lesson(client: httpx.Client, equipment_id: str, rule_id: str) -> None:
    lesson = client.get(f"/api/equipment/{equipment_id}/faults/{rule_id}/lesson")
    lesson.raise_for_status()
    data = lesson.json()
    print(
        json.dumps(
            {
                "rule_id": data.get("rule_id"),
                "title": data.get("title"),
                "roles": [
                    {
                        "role": x.get("role"),
                        "point_id": (x.get("binding") or {}).get("point_id"),
                        "query_preview": (x.get("query") or "")[:120],
                    }
                    for x in data.get("lessons", [])
                ],
            },
            indent=2,
        )
    )


def run_rule_via_api(client: httpx.Client, equipment_id: str, rule_id: str) -> None:
    """Optional: server-side run endpoint (not used by the tutorial UI)."""
    r = client.post(f"/api/equipment/{equipment_id}/faults/{rule_id}/run")
    r.raise_for_status()
    body = r.json()
    print(
        body["status"],
        body.get("fault_hours"),
        body.get("fault_pct"),
        body.get("sample_count"),
        body.get("fault_sample_count"),
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://127.0.0.1:8000")
    p.add_argument("--equipment", required=True)
    p.add_argument("--rule", default="FC1", help="open-fdd rule id (default FC1)")
    p.add_argument(
        "--local-fc1",
        action="store_true",
        help="resolve FC1 roles via points API and run open-fdd locally (recommended)",
    )
    p.add_argument(
        "--via-api",
        action="store_true",
        help="use POST …/faults/{rule}/run on the server (not the UI path)",
    )
    p.add_argument("--lesson-only", action="store_true", help="print SPARQL lesson JSON only")
    args = p.parse_args()

    if args.rule != "FC1" and args.local_fc1:
        print("note: --local-fc1 currently implements FC1 role wiring only", file=sys.stderr)

    with httpx.Client(base_url=args.base_url, timeout=300.0) as client:
        faults = client.get(
            f"/api/equipment/{args.equipment}/faults", params={"include_generic": True}
        )
        faults.raise_for_status()
        applicable = [f for f in faults.json() if f["applicable"]]
        print(f"Applicable faults ({len(applicable)}):")
        for f in applicable:
            print(f"  {f['rule_id']}: {f['title']}")
        print(f"--- {args.rule} ---")
        show_lesson(client, args.equipment, args.rule)
        if args.lesson_only:
            return 0
        if args.via_api:
            run_rule_via_api(client, args.equipment, args.rule)
        else:
            # Default: local crunch for FC1; otherwise require --via-api
            if args.local_fc1 or args.rule == "FC1":
                if args.rule != "FC1":
                    raise SystemExit(
                        "local runner currently supports FC1; use --via-api for others"
                    )
                run_fc1(client, args.equipment)
            else:
                known = {r.id for r in RULES}
                if args.rule not in known:
                    raise SystemExit(f"unknown rule {args.rule}")
                raise SystemExit("pass --local-fc1 for FC1 or --via-api for server-side run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
