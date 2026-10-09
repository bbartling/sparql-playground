#!/usr/bin/env python3
"""Analyst demo: list faults, SPARQL-resolve roles, run open-fdd rules via API."""

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


def run_via_api(client: httpx.Client, equipment_id: str, rule_id: str) -> None:
    lesson = client.get(f"/api/equipment/{equipment_id}/faults/{rule_id}/lesson")
    lesson.raise_for_status()
    print(json.dumps(lesson.json(), indent=2)[:2000])
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
        help="resolve FC1 roles via points API and run open-fdd locally (legacy)",
    )
    args = p.parse_args()
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
        if args.local_fc1:
            run_fc1(client, args.equipment)
        else:
            run_via_api(client, args.equipment, args.rule)
    return 0


if __name__ == "__main__":
    sys.exit(main())
