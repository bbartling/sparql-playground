#!/usr/bin/env python3
"""Local Open-FDD runner: Brick role SPARQL lessons → timeseries → run_rule.

The hosted UI is SPARQL-only. Use this on your machine against local or Render:

  uv run python scripts/analyst_client.py --equipment AHU_1 --rule FC1
  uv run python scripts/analyst_client.py --base-url https://sparql-playground.onrender.com \\
      --equipment AHU_2 --rule FC2
"""

from __future__ import annotations

import argparse
import json
import sys

import httpx
import pandas as pd
from open_fdd.rules import run_rule


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
) -> None:
    """Use /faults/{rule}/lesson bindings, pull timeseries, run open-fdd locally."""
    data = fetch_lesson(client, equipment_id, rule_id)
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
        print(f"  loaded {role}: {binding['point_id']} ({len(series[role])} samples)")
    if not series:
        raise SystemExit(f"no role bindings for {rule_id}")
    df = pd.DataFrame(series).sort_index()
    df.attrs.update(equipment_id=equipment_id, equipment_type=equipment_type)
    res = run_rule(rule_id, df, poll_seconds=poll_seconds)
    print(res.status, res.fault_hours, res.fault_pct, res.sample_count, res.fault_sample_count)
    evidence = res.to_dict().get("evidence", {}) if hasattr(res, "to_dict") else {}
    confirmed = evidence.get("confirmed_fault", {})
    print((confirmed.get("fault_intervals") or [])[:5])


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://127.0.0.1:8000")
    p.add_argument("--equipment", required=True)
    p.add_argument("--rule", default="FC1", help="open-fdd rule id (FC1, FC2, …)")
    p.add_argument(
        "--local-fc1",
        action="store_true",
        help="legacy FC1 point lookup (tests); default path uses lesson API for any rule",
    )
    p.add_argument("--lesson-only", action="store_true", help="print lesson JSON only")
    args = p.parse_args()

    with httpx.Client(base_url=args.base_url, timeout=300.0) as client:
        faults = client.get(
            f"/api/equipment/{args.equipment}/faults", params={"include_generic": False}
        )
        faults.raise_for_status()
        applicable = [f for f in faults.json() if f["applicable"]]
        print(f"Applicable role-based faults ({len(applicable)}):")
        for f in applicable:
            print(f"  {f['rule_id']}: {f['title']}")
        print(f"--- {args.rule} ---")
        if args.lesson_only:
            print(json.dumps(fetch_lesson(client, args.equipment, args.rule), indent=2)[:4000])
            return 0
        if args.local_fc1:
            if args.rule != "FC1":
                raise SystemExit("--local-fc1 only supports FC1")
            run_fc1(client, args.equipment)
        else:
            run_rule_from_lesson(client, args.equipment, args.rule)
    return 0


if __name__ == "__main__":
    sys.exit(main())
