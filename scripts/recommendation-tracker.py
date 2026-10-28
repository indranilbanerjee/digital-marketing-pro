#!/usr/bin/env python3
"""recommendation-tracker.py: how you'll know an audit recommendation worked.

Every recommendation from seo-audit, aeo-audit, landing-page-audit and campaign-audit is recorded
with the metric it should move, the expected direction and a check-by date. The
continuous-improvement loop lists the ones due and records what happened, so a recommendation is
judged by its metric, not forgotten.

Usage:
    python recommendation-tracker.py --brand acme --action add --source seo-audit --data '[{"recommendation": "Fix the 12 broken internal links", "metric": "crawl errors (GSC)", "direction": "down", "check_by": "2027-01-15"}]'
    python recommendation-tracker.py --brand acme --action due [--as-of 2027-01-31]
    python recommendation-tracker.py --brand acme --action close --id rec-1a2b3c4d --observed "4 errors" --outcome worked
    python recommendation-tracker.py --brand acme --action list

Each recommendation needs: recommendation, metric, direction (up or down), check_by (YYYY-MM-DD,
not in the past). Optional: baseline. Rows live in ~/.claude-marketing/brands/{brand}/recommendations.json.
Exit codes: 0 done, 1 error (brand not found), 2 bad input.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

FIELDS = ("recommendation", "metric", "direction", "check_by")
DIRECTIONS = ("up", "down")
OUTCOMES = ("worked", "did-not-work", "unclear")
SOURCES = ("seo-audit", "aeo-audit", "landing-page-audit", "campaign-audit", "other")


def _input_error(message: str):
    print(json.dumps({"error": message}, indent=2, ensure_ascii=False))
    sys.exit(2)


def _rows_path(brand: str):
    brand_dir, err = _common.get_brand_dir(brand)
    if err:
        _common.finish({"error": err})
    return brand_dir / "recommendations.json"


def _load(path) -> list:
    data = _common.load_json_safe(path)
    if isinstance(data, dict) and data.get("missing"):
        return []
    if not isinstance(data, list):
        _common.finish({"error": f"{path.name} is not a list of recommendations: {data.get('error', '') if isinstance(data, dict) else ''}"})
    return data


def validate(items, today: date) -> list:
    """The recommendations as rows, or an input error naming the first item and field that's wrong."""
    if not isinstance(items, list) or not items:
        _input_error("--data must be a non-empty JSON array of recommendations")
    rows = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            _input_error(f"item {i} must be an object")
        missing = [f for f in FIELDS if not str(item.get(f) or "").strip()]
        if missing:
            _input_error(f"item {i} is missing {', '.join(missing)}: every recommendation needs a metric, "
                         f"an expected direction (up or down) and a check_by date")
        if item["direction"] not in DIRECTIONS:
            _input_error(f"item {i}: direction must be up or down, not {item['direction']!r}")
        try:
            check_by = date.fromisoformat(str(item["check_by"]))
        except ValueError:
            _input_error(f"item {i}: check_by must be YYYY-MM-DD, not {item['check_by']!r}")
        if check_by < today:
            _input_error(f"item {i}: check_by {check_by} is in the past")
        rows.append({k: item[k] for k in FIELDS} | ({"baseline": item["baseline"]} if "baseline" in item else {}))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Record audit recommendations with a metric, a direction and a check-by date")
    parser.add_argument("--brand", type=_common.path_component, required=True)
    parser.add_argument("--action", required=True, choices=["add", "due", "close", "list"])
    parser.add_argument("--source", choices=SOURCES, default="other", help="The audit the recommendations came from")
    parser.add_argument("--data", help="JSON array of recommendations (add)")
    parser.add_argument("--id", type=_common.path_component, help="Recommendation id (close)")
    parser.add_argument("--observed", help="What the metric showed at the check (close)")
    parser.add_argument("--outcome", choices=OUTCOMES, help="close")
    parser.add_argument("--as-of", help="Date for due (default today), YYYY-MM-DD")
    args = parser.parse_args()

    path = _rows_path(args.brand)
    rows = _load(path)
    today = date.today()

    if args.action == "add":
        new = validate(_common.json_arg(args.data, "--data", list), today)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for row in new:
            key = f"{args.source}|{row['recommendation']}|{row['metric']}|{stamp}"
            row.update({"id": "rec-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], "source": args.source,
                        "created_at": stamp, "status": "open"})
        _common.atomic_write_json(path, rows + new)
        _common.finish({"status": "recorded", "count": len(new), "ids": [r["id"] for r in new], "path": str(path)})

    if args.action == "due":
        try:
            as_of = date.fromisoformat(args.as_of) if args.as_of else today
        except ValueError:
            _input_error(f"--as-of must be YYYY-MM-DD, not {args.as_of!r}")
        due = [r for r in rows if r.get("status") == "open" and date.fromisoformat(r["check_by"]) <= as_of]
        _common.finish({"as_of": as_of.isoformat(), "due": due, "count": len(due),
                        "next": "Check each metric, then record it: --action close --id <id> --observed ... --outcome ..."})

    if args.action == "close":
        if not (args.id and args.outcome and args.observed):
            _input_error("close needs --id, --observed and --outcome")
        for row in rows:
            if row.get("id") == args.id:
                row.update({"status": "closed", "observed": args.observed, "outcome": args.outcome,
                            "closed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
                _common.atomic_write_json(path, rows)
                _common.finish({"status": "closed", "recommendation": row})
        _common.finish({"error": f"no recommendation with id {args.id}"})

    _common.finish({"recommendations": rows, "open": sum(r.get("status") == "open" for r in rows),
                    "closed": sum(r.get("status") == "closed" for r in rows)})


if __name__ == "__main__":
    main()
