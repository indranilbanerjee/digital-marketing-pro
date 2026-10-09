#!/usr/bin/env python3
"""
quality-tracker.py
==================
Persistent content quality evaluation tracker for Digital Marketing Pro.

Logs eval scores over time, computes weekly trends, detects quality
regression across scoring dimensions, and surfaces best/worst content.

Storage:
    ~/.claude-marketing/brands/{slug}/quality/evals/eval-{timestamp}.json
    ~/.claude-marketing/brands/{slug}/quality/_summary.json

Actions:
    log-eval          Log a new content evaluation
    get-trends        Weekly trend analysis across scoring dimensions
    get-summary       Overall quality stats and averages
    check-regression  Detect drops in quality vs. rolling baseline
    get-best          Top N evals by composite score
    get-worst         Bottom N evals by composite score

Usage:
    python quality-tracker.py --action log-eval --data '{"content_type":"blog_post","title":"Q1 Recap","scores":{"content_quality":82,"brand_voice":78,"hallucination":95,"readability":75,"composite":82},"grade":"B+"}'
    python quality-tracker.py --action get-trends --days 30
    python quality-tracker.py --action get-trends --content-type blog_post --days 60
    python quality-tracker.py --action get-summary
    python quality-tracker.py --action check-regression
    python quality-tracker.py --action get-best --limit 5
    python quality-tracker.py --action get-worst --limit 5 --content-type email
    python quality-tracker.py --brand acme --action get-summary
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

BRANDS_DIR = _common.brands_root()
ACTIVE_BRAND_FILE = BRANDS_DIR / "_active-brand.json"

SCORE_DIMENSIONS = [
    "content_quality", "brand_voice", "hallucination",
    "readability", "composite",
]


# ---------------------------------------------------------------------------
# Brand resolution
# ---------------------------------------------------------------------------

def resolve_brand(slug):
    """Resolve brand slug — use provided value or fall back to active brand."""
    if slug:
        return slug

    if ACTIVE_BRAND_FILE.exists():
        try:
            active = json.loads(ACTIVE_BRAND_FILE.read_text(encoding="utf-8"))
            return active.get("active_slug")
        except (json.JSONDecodeError, OSError):
            pass

    return None


def get_quality_dir(slug):
    """Return the quality tracking directory for a brand, creating if needed."""
    brand_dir = BRANDS_DIR / slug
    if not brand_dir.exists():
        return None, f"Brand '{slug}' not found. Run /digital-marketing-pro:brand-setup first."

    quality_dir = brand_dir / "quality"
    quality_dir.mkdir(exist_ok=True)

    evals_dir = quality_dir / "evals"
    evals_dir.mkdir(exist_ok=True)

    return quality_dir, None


# ---------------------------------------------------------------------------
# Eval file I/O
# ---------------------------------------------------------------------------

def load_evals(quality_dir, days=None, content_type=None):
    """Load eval files, optionally filtered by age and content type."""
    evals_dir = quality_dir / "evals"
    if not evals_dir.exists():
        return []

    cutoff = None
    if days:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    evals = []
    for fp in sorted(evals_dir.glob("eval-*.json")):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        # Age filter
        if cutoff and data.get("timestamp", "") < cutoff:
            continue

        # Content-type filter
        if content_type and data.get("content_type") != content_type:
            continue

        evals.append(data)

    return evals


def load_summary(quality_dir):
    """Load the rolling summary file."""
    summary_path = quality_dir / "_summary.json"
    if summary_path.exists():
        try:
            return json.loads(summary_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_summary(quality_dir, summary):
    """Write the rolling summary file."""
    summary_path = quality_dir / "_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def action_log_eval(slug, data):
    """Persist a new content evaluation and update the running summary."""
    quality_dir, err = get_quality_dir(slug)
    if err:
        return {"error": err}

    # Validate required fields
    scores = data.get("scores")
    if not scores or not isinstance(scores, dict):
        return {"error": "Missing or invalid 'scores' object in --data."}
    if "composite" not in scores:
        return {"error": "'scores.composite' is required."}

    # Stamp the eval (include milliseconds to avoid collisions)
    now = datetime.now()
    timestamp = now.strftime("%Y%m%dT%H%M%S") + f"-{now.microsecond // 1000:03d}"
    eval_id = f"eval-{timestamp}"

    record = {
        "eval_id": eval_id,
        "content_type": data.get("content_type", "unknown"),
        "title": data.get("title", ""),
        "scores": scores,
        "grade": data.get("grade", ""),
        "timestamp": data.get("timestamp", now.isoformat()),
    }

    # Save individual eval file
    evals_dir = quality_dir / "evals"
    filepath = evals_dir / f"{eval_id}.json"
    filepath.write_text(json.dumps(record, indent=2))

    # Update running summary
    summary = load_summary(quality_dir)
    count = summary.get("total_evals", 0) + 1
    summary["total_evals"] = count
    summary["last_eval_id"] = eval_id
    summary["last_updated"] = now.isoformat()

    # Running averages per dimension
    dim_avgs = summary.get("dimension_averages", {})
    for dim in SCORE_DIMENSIONS:
        if dim in scores:
            prev_avg = dim_avgs.get(dim, 0)
            # Incremental mean: new_avg = prev_avg + (val - prev_avg) / n
            dim_avgs[dim] = round(prev_avg + (scores[dim] - prev_avg) / count, 2)
    summary["dimension_averages"] = dim_avgs

    # Track counts per content type
    type_counts = summary.get("content_type_counts", {})
    ct = record["content_type"]
    type_counts[ct] = type_counts.get(ct, 0) + 1
    summary["content_type_counts"] = type_counts

    save_summary(quality_dir, summary)

    return {
        "status": "logged",
        "eval_id": eval_id,
        "content_type": record["content_type"],
        "composite": scores["composite"],
        "grade": record["grade"],
        "total_evals": count,
    }


def action_get_trends(slug, days, content_type):
    """Compute per-dimension weekly trend buckets."""
    quality_dir, err = get_quality_dir(slug)
    if err:
        return {"error": err}

    evals = load_evals(quality_dir, days=days, content_type=content_type)
    if not evals:
        return {
            "period": f"last_{days}_days",
            "total_evals": 0,
            "weekly_trends": [],
            "dimension_trends": {},
            "note": "No evals found for this period.",
        }

    # Group evals into ISO-week buckets
    weekly = defaultdict(list)
    for ev in evals:
        try:
            ts = datetime.fromisoformat(ev["timestamp"])
        except (ValueError, KeyError):
            continue
        week_label = ts.strftime("%G-W%V")
        weekly[week_label].append(ev)

    # Build weekly trend rows
    weekly_trends = []
    for week in sorted(weekly.keys()):
        bucket = weekly[week]
        composites = [e["scores"].get("composite", 0) for e in bucket]
        weekly_trends.append({
            "week": week,
            "evals": len(bucket),
            "composite_avg": round(mean(composites), 1) if composites else 0,
        })

    # Per-dimension current vs. previous half comparison
    mid = len(evals) // 2
    first_half = evals[:mid] if mid > 0 else []
    second_half = evals[mid:] if mid > 0 else evals

    dimension_trends = {}
    for dim in SCORE_DIMENSIONS:
        prev_vals = [e["scores"].get(dim) for e in first_half if dim in e.get("scores", {})]
        curr_vals = [e["scores"].get(dim) for e in second_half if dim in e.get("scores", {})]

        prev_avg = round(mean(prev_vals), 1) if prev_vals else None
        curr_avg = round(mean(curr_vals), 1) if curr_vals else None

        if prev_avg is not None and curr_avg is not None:
            diff = round(curr_avg - prev_avg, 1)
            if diff > 2:
                trend = "improving"
            elif diff < -2:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"
            diff = 0

        dimension_trends[dim] = {
            "current_avg": curr_avg,
            "previous_avg": prev_avg,
            "change": diff,
            "trend": trend,
        }

    return {
        "period": f"last_{days}_days",
        "content_type": content_type or "all",
        "total_evals": len(evals),
        "weekly_trends": weekly_trends,
        "dimension_trends": dimension_trends,
    }


def action_get_summary(slug):
    """Return the stored summary with overall stats."""
    quality_dir, err = get_quality_dir(slug)
    if err:
        return {"error": err}

    summary = load_summary(quality_dir)
    if not summary:
        return {"total_evals": 0, "note": "No evals logged yet."}

    # Enrich with best/worst content type by average composite
    evals = load_evals(quality_dir)
    type_composites = defaultdict(list)
    for ev in evals:
        ct = ev.get("content_type", "unknown")
        comp = ev.get("scores", {}).get("composite")
        if comp is not None:
            type_composites[ct].append(comp)

    type_averages = {
        ct: round(mean(vals), 1) for ct, vals in type_composites.items() if vals
    }

    best_type = max(type_averages, key=type_averages.get) if type_averages else None
    worst_type = min(type_averages, key=type_averages.get) if type_averages else None

    summary["content_type_averages"] = type_averages
    summary["best_content_type"] = best_type
    summary["worst_content_type"] = worst_type

    return summary


def action_check_regression(slug, days):
    """Detect quality regression by comparing recent evals to baseline."""
    quality_dir, err = get_quality_dir(slug)
    if err:
        return {"error": err}

    evals = load_evals(quality_dir, days=days)
    if len(evals) < 6:
        return {
            "regression_detected": False,
            "alerts": [],
            "baselines": {},
            "note": f"Need at least 6 evals in the last {days} days for regression detection (found {len(evals)}).",
        }

    # Compute baseline: mean of all evals in the window
    baseline = {}
    for dim in SCORE_DIMENSIONS:
        vals = [e["scores"].get(dim) for e in evals if dim in e.get("scores", {})]
        baseline[dim] = round(mean(vals), 1) if vals else None

    # Last 5 evals
    recent = evals[-5:]
    recent_avgs = {}
    for dim in SCORE_DIMENSIONS:
        vals = [e["scores"].get(dim) for e in recent if dim in e.get("scores", {})]
        recent_avgs[dim] = round(mean(vals), 1) if vals else None

    # Detect regression
    alerts = []

    # Check composite: last-5 average drops >10 below baseline
    if baseline.get("composite") and recent_avgs.get("composite"):
        drop = round(baseline["composite"] - recent_avgs["composite"], 1)
        if drop > 10:
            severity = "critical" if drop > 20 else "warning"
            alerts.append({
                "type": "composite_regression",
                "dimension": "composite",
                "baseline": baseline["composite"],
                "current": recent_avgs["composite"],
                "drop": drop,
                "severity": severity,
            })

    # Check individual dimensions: any single drop >15
    for dim in SCORE_DIMENSIONS:
        if dim == "composite":
            continue
        if baseline.get(dim) is not None and recent_avgs.get(dim) is not None:
            drop = round(baseline[dim] - recent_avgs[dim], 1)
            if drop > 15:
                severity = "critical" if drop > 25 else "warning"
                alerts.append({
                    "type": "dimension_regression",
                    "dimension": dim,
                    "baseline": baseline[dim],
                    "current": recent_avgs[dim],
                    "drop": drop,
                    "severity": severity,
                })

    return {
        "regression_detected": len(alerts) > 0,
        "alerts": alerts,
        "alert_count": len(alerts),
        "baselines": baseline,
        "recent_averages": recent_avgs,
        "evals_in_window": len(evals),
        "recent_evals_checked": len(recent),
    }


def action_get_best(slug, limit, content_type, days):
    """Return top N evals by composite score."""
    quality_dir, err = get_quality_dir(slug)
    if err:
        return {"error": err}

    evals = load_evals(quality_dir, days=days, content_type=content_type)
    if not evals:
        return {"evals": [], "total": 0, "note": "No evals found."}

    # Sort descending by composite
    evals.sort(key=lambda e: e.get("scores", {}).get("composite", 0), reverse=True)

    top = evals[:limit]
    return {
        "action": "get-best",
        "content_type": content_type or "all",
        "returned": len(top),
        "total_in_window": len(evals),
        "evals": top,
    }


def action_get_worst(slug, limit, content_type, days):
    """Return bottom N evals by composite score."""
    quality_dir, err = get_quality_dir(slug)
    if err:
        return {"error": err}

    evals = load_evals(quality_dir, days=days, content_type=content_type)
    if not evals:
        return {"evals": [], "total": 0, "note": "No evals found."}

    # Sort ascending by composite
    evals.sort(key=lambda e: e.get("scores", {}).get("composite", 0))

    bottom = evals[:limit]
    return {
        "action": "get-worst",
        "content_type": content_type or "all",
        "returned": len(bottom),
        "total_in_window": len(evals),
        "evals": bottom,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        description="Quality evaluation tracker for Digital Marketing Pro.",
        epilog=(
            "Actions:\n"
            "  log-eval          Log a new content evaluation\n"
            "  get-trends        Weekly trend analysis across scoring dimensions\n"
            "  get-summary       Overall quality stats and averages\n"
            "  check-regression  Detect quality drops vs. rolling baseline\n"
            "  get-best          Top N evals by composite score\n"
            "  get-worst         Bottom N evals by composite score\n"
            "\n"
            "Examples:\n"
            "  python quality-tracker.py --action log-eval --data "
            "'{\"content_type\":\"blog_post\",\"title\":\"Q1 Recap\","
            "\"scores\":{\"composite\":82},\"grade\":\"B+\"}'\n"
            "  python quality-tracker.py --action get-trends --days 60\n"
            "  python quality-tracker.py --action check-regression\n"
            "  python quality-tracker.py --action get-best --limit 10 --content-type email\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--action", required=True,
        choices=["log-eval", "get-trends", "get-summary",
                 "check-regression", "get-best", "get-worst"],
        help="Action to perform.",
    )
    parser.add_argument(
        "--brand", type=_common.path_component, default=None,
        help="Brand slug (defaults to active brand).",
    )
    parser.add_argument(
        "--data", default=None,
        help="JSON eval data (for log-eval).",
    )
    parser.add_argument(
        "--content-type", default=None,
        help="Filter by content type (e.g. blog_post, email, ad, social).",
    )
    parser.add_argument(
        "--days", type=int, default=30,
        help="Time window in days (default: 30).",
    )
    parser.add_argument(
        "--limit", type=int, default=5,
        help="Number of results to return (default: 5).",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    # Resolve brand
    slug = resolve_brand(args.brand)
    if not slug:
        print(json.dumps({
            "error": "No brand specified and no active brand set. "
                     "Use --brand <slug> or run /digital-marketing-pro:brand-setup first."
        }))
        sys.exit(1)

    # Dispatch
    if args.action == "log-eval":
        if not args.data:
            print(json.dumps({"error": "Provide --data with eval JSON."}))
            sys.exit(1)
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --data."}))
            sys.exit(1)
        result = action_log_eval(slug, data)

    elif args.action == "get-trends":
        result = action_get_trends(slug, args.days, args.content_type)

    elif args.action == "get-summary":
        result = action_get_summary(slug)

    elif args.action == "check-regression":
        result = action_check_regression(slug, args.days)

    elif args.action == "get-best":
        result = action_get_best(slug, args.limit, args.content_type, args.days)

    elif args.action == "get-worst":
        result = action_get_worst(slug, args.limit, args.content_type, args.days)

    _common.finish(result)


if __name__ == "__main__":
    main()
