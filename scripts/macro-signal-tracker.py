#!/usr/bin/env python3
"""
macro-signal-tracker.py
=======================
Track macro environmental signals that impact marketing decisions.

Monitors economic, cultural, industry, platform, and regulatory signals.
Generates "Marketing Weather Reports" scoring overall conditions, surfaces
high-severity alerts, and tracks signal trends over time.

Storage: ~/.claude-marketing/brands/{slug}/signals/

Dependencies: none (stdlib only)

Usage:
    python macro-signal-tracker.py --brand acme --action record-signal --category economic --signal "Fed rate hike 25bps" --source "WSJ" --impact negative --severity high
    python macro-signal-tracker.py --brand acme --action weather-report
    python macro-signal-tracker.py --brand acme --action list-signals --category economic --since 2026-01-01
    python macro-signal-tracker.py --brand acme --action trend --category platform
    python macro-signal-tracker.py --brand acme --action alert-check
    python macro-signal-tracker.py --brand acme --action acknowledge --signal-id sig_abc123 --action-taken "Paused PPC spend"
    python macro-signal-tracker.py --brand acme --action summary
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

BRANDS_DIR = _common.brands_root()

VALID_CATEGORIES = ["economic", "cultural", "industry", "platform", "regulatory"]
VALID_IMPACTS = ["positive", "negative", "neutral"]
VALID_SEVERITIES = ["low", "medium", "high"]
SEVERITY_WEIGHTS = {"low": 1, "medium": 2, "high": 3}


def _load_json(path, default=None):
    if default is None:
        default = []
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _signals_dir(slug):
    return BRANDS_DIR / slug / "signals"


def _load_all_signals(slug):
    sdir = _signals_dir(slug)
    if not sdir.exists():
        return []
    signals = []
    for f in sorted(sdir.glob("sig_*.json")):
        s = _load_json(f, None)
        if s and isinstance(s, dict):
            signals.append(s)
    return signals


def _days_ago(n):
    return (datetime.now() - timedelta(days=n)).isoformat()


# ── Actions ──────────────────────────────────────────────────────────────────

def record_signal(slug, args):
    brand_dir = BRANDS_DIR / slug
    if not brand_dir.exists():
        return {"error": f"Brand '{slug}' not found. Run /digital-marketing-pro:brand-setup first."}

    ts = datetime.now().isoformat()
    raw = f"{slug}:{args.signal}:{ts}"
    signal_id = "sig_" + hashlib.sha256(raw.encode()).hexdigest()[:12]

    record = {
        "signal_id": signal_id,
        "brand": slug,
        "category": args.category,
        "signal": args.signal,
        "source": args.source,
        "impact": args.impact,
        "severity": args.severity,
        "affected_channels": [c.strip() for c in args.affected_channels.split(",")] if args.affected_channels else [],
        "recorded_at": ts,
        "acknowledged": False,
        "action_taken": None,
    }

    sdir = _signals_dir(slug)
    sdir.mkdir(parents=True, exist_ok=True)
    _save_json(sdir / f"{signal_id}.json", record)
    return {"status": "recorded", "signal_id": signal_id, "recorded_at": ts}


def weather_report(slug):
    brand_dir = BRANDS_DIR / slug
    if not brand_dir.exists():
        return {"error": f"Brand '{slug}' not found. Run /digital-marketing-pro:brand-setup first."}

    signals = _load_all_signals(slug)
    cutoff = _days_ago(30)
    recent = [s for s in signals if s.get("recorded_at", "") >= cutoff]

    if not recent:
        return {"overall_condition": "green", "category_conditions": {}, "top_signals": [], "recommendations": ["No recent signals recorded. Consider adding macro observations."], "signals_analyzed": 0}

    # Score by category
    cat_scores = {}
    for cat in VALID_CATEGORIES:
        cat_signals = [s for s in recent if s.get("category") == cat]
        if not cat_signals:
            cat_scores[cat] = {"condition": "green", "positive": 0, "negative": 0, "neutral": 0}
            continue
        pos = sum(SEVERITY_WEIGHTS.get(s["severity"], 1) for s in cat_signals if s.get("impact") == "positive")
        neg = sum(SEVERITY_WEIGHTS.get(s["severity"], 1) for s in cat_signals if s.get("impact") == "negative")
        neu = len([s for s in cat_signals if s.get("impact") == "neutral"])
        net = pos - neg
        condition = "green" if net > 0 else ("red" if net < -2 else ("yellow" if net < 0 else "green"))
        cat_scores[cat] = {"condition": condition, "positive": pos, "negative": neg, "neutral": neu}

    # Overall condition
    total_pos = sum(SEVERITY_WEIGHTS.get(s["severity"], 1) for s in recent if s.get("impact") == "positive")
    total_neg = sum(SEVERITY_WEIGHTS.get(s["severity"], 1) for s in recent if s.get("impact") == "negative")
    net_score = total_pos - total_neg
    overall = "green" if net_score > 0 else ("red" if net_score < -3 else "yellow")

    # Top signals (sorted by severity desc, then recorded_at)
    top = sorted(recent, key=lambda s: (-SEVERITY_WEIGHTS.get(s.get("severity", "low"), 1), s.get("recorded_at", "")))[:5]
    top_out = [{"signal_id": s["signal_id"], "category": s["category"], "signal": s["signal"], "impact": s["impact"], "severity": s["severity"]} for s in top]

    # Recommendations
    recs = []
    red_cats = [c for c, v in cat_scores.items() if v["condition"] == "red"]
    if red_cats:
        recs.append(f"High-alert categories: {', '.join(red_cats)}. Review strategies for these areas.")
    high_neg = [s for s in recent if s.get("impact") == "negative" and s.get("severity") == "high"]
    if high_neg:
        recs.append(f"{len(high_neg)} high-severity negative signal(s) detected. Prioritize risk mitigation.")
    if overall == "green":
        recs.append("Conditions are favorable. Consider accelerating planned initiatives.")
    if not recs:
        recs.append("Mixed conditions. Monitor closely and maintain flexible budgets.")

    return {"overall_condition": overall, "category_conditions": cat_scores, "top_signals": top_out, "recommendations": recs, "signals_analyzed": len(recent), "period": "last_30_days"}


def list_signals(slug, category=None, since=None, impact=None):
    brand_dir = BRANDS_DIR / slug
    if not brand_dir.exists():
        return {"error": f"Brand '{slug}' not found. Run /digital-marketing-pro:brand-setup first."}

    signals = _load_all_signals(slug)
    if category:
        signals = [s for s in signals if s.get("category") == category]
    if since:
        signals = [s for s in signals if s.get("recorded_at", "") >= since]
    if impact:
        signals = [s for s in signals if s.get("impact") == impact]
    return {"signals": list(reversed(signals)), "total": len(signals)}


def trend(slug, category=None):
    brand_dir = BRANDS_DIR / slug
    if not brand_dir.exists():
        return {"error": f"Brand '{slug}' not found. Run /digital-marketing-pro:brand-setup first."}

    signals = _load_all_signals(slug)
    if category:
        signals = [s for s in signals if s.get("category") == category]
    if not signals:
        return {"weeks": [], "trend_direction": "no_data", "total_signals": 0}

    # Group by ISO week
    weeks = {}
    for s in signals:
        try:
            dt = datetime.fromisoformat(s["recorded_at"])
            wk = dt.strftime("%G-W%V")
        except (KeyError, ValueError):
            continue
        weeks.setdefault(wk, []).append(s)

    weekly = []
    for wk in sorted(weeks.keys()):
        ws = weeks[wk]
        pos = len([s for s in ws if s.get("impact") == "positive"])
        neg = len([s for s in ws if s.get("impact") == "negative"])
        weekly.append({"week": wk, "total": len(ws), "positive": pos, "negative": neg, "neutral": len(ws) - pos - neg, "sentiment": round((pos - neg) / len(ws), 2) if ws else 0})

    # Trend direction from last 4 weeks
    recent = weekly[-4:] if len(weekly) >= 4 else weekly
    sentiments = [w["sentiment"] for w in recent]
    if len(sentiments) >= 2:
        diff = sentiments[-1] - sentiments[0]
        direction = "improving" if diff > 0.1 else ("declining" if diff < -0.1 else "stable")
    else:
        direction = "insufficient_data"

    return {"weeks": weekly, "trend_direction": direction, "total_signals": len(signals), "category_filter": category}


def alert_check(slug):
    brand_dir = BRANDS_DIR / slug
    if not brand_dir.exists():
        return {"error": f"Brand '{slug}' not found. Run /digital-marketing-pro:brand-setup first."}

    signals = _load_all_signals(slug)
    cutoff = _days_ago(7)
    alerts = [s for s in signals if s.get("severity") == "high" and s.get("recorded_at", "") >= cutoff and not s.get("acknowledged", False)]
    return {"alerts": alerts, "total": len(alerts), "period": "last_7_days"}


def acknowledge(slug, signal_id, action_taken):
    brand_dir = BRANDS_DIR / slug
    if not brand_dir.exists():
        return {"error": f"Brand '{slug}' not found. Run /digital-marketing-pro:brand-setup first."}

    sdir = _signals_dir(slug)
    fpath = sdir / f"{signal_id}.json"
    if not fpath.exists():
        return {"error": f"Signal '{signal_id}' not found."}

    record = _load_json(fpath, {})
    record["acknowledged"] = True
    record["action_taken"] = action_taken
    record["acknowledged_at"] = datetime.now().isoformat()
    _save_json(fpath, record)
    return {"status": "acknowledged", "signal_id": signal_id, "action_taken": action_taken}


def summary(slug):
    brand_dir = BRANDS_DIR / slug
    if not brand_dir.exists():
        return {"error": f"Brand '{slug}' not found. Run /digital-marketing-pro:brand-setup first."}

    signals = _load_all_signals(slug)
    if not signals:
        return {"total_active_signals": 0, "by_category": {}, "overall_sentiment_score": 0, "highest_priority_signals": [], "days_since_last_update": None}

    by_cat = {}
    for s in signals:
        cat = s.get("category", "unknown")
        by_cat[cat] = by_cat.get(cat, 0) + 1

    pos = sum(SEVERITY_WEIGHTS.get(s["severity"], 1) for s in signals if s.get("impact") == "positive")
    neg = sum(SEVERITY_WEIGHTS.get(s["severity"], 1) for s in signals if s.get("impact") == "negative")
    total_w = pos + neg
    sentiment = round((pos - neg) / total_w, 2) if total_w > 0 else 0.0

    high_pri = sorted(signals, key=lambda s: (-SEVERITY_WEIGHTS.get(s.get("severity", "low"), 1), s.get("recorded_at", "")))[:3]
    high_out = [{"signal_id": s["signal_id"], "signal": s["signal"], "severity": s["severity"], "impact": s["impact"]} for s in high_pri]

    dates = [s.get("recorded_at", "") for s in signals if s.get("recorded_at")]
    days_since = None
    if dates:
        try:
            latest = datetime.fromisoformat(max(dates))
            days_since = (datetime.now() - latest).days
        except ValueError:
            pass

    return {"total_active_signals": len(signals), "by_category": by_cat, "overall_sentiment_score": sentiment, "highest_priority_signals": high_out, "days_since_last_update": days_since}


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Macro Signal Tracker — Monitor economic, cultural, and industry signals for Digital Marketing Pro"
    )
    parser.add_argument("--brand", type=_common.path_component, required=True, help="Brand slug")
    parser.add_argument("--action", required=True,
                        choices=["record-signal", "weather-report", "list-signals",
                                 "trend", "alert-check", "acknowledge", "summary"],
                        help="Action to perform")
    parser.add_argument("--category", choices=VALID_CATEGORIES,
                        help="Signal category")
    parser.add_argument("--signal", help="Signal description (for record-signal)")
    parser.add_argument("--source", help="Where the signal was observed")
    parser.add_argument("--impact", choices=VALID_IMPACTS,
                        help="Impact on marketing (positive/negative/neutral)")
    parser.add_argument("--severity", choices=VALID_SEVERITIES,
                        help="Signal severity (low/medium/high)")
    parser.add_argument("--affected-channels",
                        help="Comma-separated list of affected channels")
    parser.add_argument("--since", help="Filter signals since date (YYYY-MM-DD)")
    parser.add_argument("--signal-id", help="Signal ID (for acknowledge)")
    parser.add_argument("--action-taken",
                        help="Description of action taken (for acknowledge)")

    args = parser.parse_args()

    if args.action == "record-signal":
        for field in ["category", "signal", "source", "impact", "severity"]:
            if not getattr(args, field):
                print(json.dumps({"error": f"--{field} is required for record-signal"}))
                sys.exit(1)
        result = record_signal(args.brand, args)

    elif args.action == "weather-report":
        result = weather_report(args.brand)

    elif args.action == "list-signals":
        result = list_signals(args.brand, args.category, args.since, args.impact)

    elif args.action == "trend":
        result = trend(args.brand, args.category)

    elif args.action == "alert-check":
        result = alert_check(args.brand)

    elif args.action == "acknowledge":
        if not args.signal_id or not args.action_taken:
            print(json.dumps({"error": "--signal-id and --action-taken are required for acknowledge"}))
            sys.exit(1)
        result = acknowledge(args.brand, args.signal_id, args.action_taken)

    elif args.action == "summary":
        result = summary(args.brand)

    _common.finish(result)


if __name__ == "__main__":
    main()
