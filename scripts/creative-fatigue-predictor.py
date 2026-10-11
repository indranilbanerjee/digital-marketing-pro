#!/usr/bin/env python3
"""
creative-fatigue-predictor.py
=============================
Predict ad creative fatigue and track content decay.

Scores creative health from performance metrics, predicts fatigue dates using
trend analysis, generates refresh briefs, scans content libraries for decay,
and prioritizes refresh work by business impact.

Dependencies: none (stdlib only)

Usage:
    python creative-fatigue-predictor.py --action score-health --creative-id ad_001 --data '{"impressions":50000,"frequency":4.2,"ctr_current":0.018,"ctr_baseline":0.025,"cpm_current":12.5,"cpm_baseline":9.0,"engagement_rate_current":0.03,"engagement_rate_baseline":0.05,"days_running":28,"audience_size":200000}'
    python creative-fatigue-predictor.py --action predict-fatigue --creative-id ad_001 --performance-history '[{"date":"2026-01-01","impressions":5000,"ctr":0.025,"cpm":9.0,"engagement_rate":0.05}]'
    python creative-fatigue-predictor.py --action generate-refresh-brief --creative-id ad_001 --data '{"format":"image","channel":"facebook","target_audience":"25-34 professionals","current_headline":"Try it free","current_cta":"Start now","current_visual_description":"Product screenshot","performing_elements":["headline"],"fatiguing_elements":["visual"]}'
    python creative-fatigue-predictor.py --action decay-scan --data '[{"content_id":"blog_01","url":"/blog/seo-guide","title":"SEO Guide","monthly_traffic_current":1200,"monthly_traffic_previous":1800,"monthly_traffic_6mo_ago":2500,"keyword_positions_current":{"seo tips":12},"keyword_positions_previous":{"seo tips":7},"publish_date":"2024-06-15","last_updated":"2025-01-10","backlinks":45}]'
    python creative-fatigue-predictor.py --action priority-refresh --data '[{"content_id":"blog_01","monthly_traffic_current":1200,"monthly_traffic_previous":2500,"conversion_rate":0.03,"revenue_per_conversion":50}]'
    python creative-fatigue-predictor.py --action batch-health --data '[...]'
"""

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402


def _clamp(val, lo=0.0, hi=100.0):
    return max(lo, min(hi, val))


# ── Linear regression (stdlib) ──────────────────────────────────────────────

def _linear_regression(x, y):
    """OLS slope and intercept."""
    n = len(x)
    if n < 2:
        return 0.0, y[0] if y else 0.0
    sx = sum(x)
    sy = sum(y)
    sxy = sum(a * b for a, b in zip(x, y))
    sx2 = sum(a * a for a in x)
    denom = n * sx2 - sx * sx
    if denom == 0:
        return 0.0, sy / n
    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    return slope, intercept


# ── Score Health ─────────────────────────────────────────────────────────────

def score_health(creative_id, data):
    ctr_cur = data.get("ctr_current", 0)
    ctr_base = data.get("ctr_baseline", 1)
    cpm_cur = data.get("cpm_current", 0)
    cpm_base = data.get("cpm_baseline", 1)
    eng_cur = data.get("engagement_rate_current", 0)
    eng_base = data.get("engagement_rate_baseline", 1)
    frequency = data.get("frequency", 1)
    days = data.get("days_running", 0)
    audience = data.get("audience_size", 100000)

    factors = []

    # CTR ratio (30%) — higher is healthier
    ctr_ratio = (ctr_cur / ctr_base) if ctr_base > 0 else 0
    ctr_score = _clamp(ctr_ratio * 100)
    factors.append({"factor": "ctr_ratio", "score": round(ctr_score, 1), "weight": 0.30, "detail": f"{ctr_ratio:.2f}x baseline"})

    # CPM ratio (20%) — lower is healthier (invert)
    cpm_ratio = (cpm_base / cpm_cur) if cpm_cur > 0 else 1
    cpm_score = _clamp(cpm_ratio * 100)
    factors.append({"factor": "cpm_ratio", "score": round(cpm_score, 1), "weight": 0.20, "detail": f"baseline/current = {cpm_ratio:.2f}"})

    # Engagement ratio (20%)
    eng_ratio = (eng_cur / eng_base) if eng_base > 0 else 0
    eng_score = _clamp(eng_ratio * 100)
    factors.append({"factor": "engagement_ratio", "score": round(eng_score, 1), "weight": 0.20, "detail": f"{eng_ratio:.2f}x baseline"})

    # Frequency fatigue (20%) — threshold scales with audience size
    fatigue_threshold = max(3.0, math.log10(audience) - 1)
    freq_ratio = frequency / fatigue_threshold if fatigue_threshold > 0 else 1
    freq_score = _clamp((1 - max(0, freq_ratio - 1)) * 100) if freq_ratio > 1 else 100.0
    factors.append({"factor": "frequency_fatigue", "score": round(freq_score, 1), "weight": 0.20, "detail": f"freq {frequency:.1f} vs threshold {fatigue_threshold:.1f}"})

    # Days running decay (10%) — gradual decay after 14 days
    if days <= 14:
        days_score = 100.0
    else:
        days_score = _clamp(100 - (days - 14) * 2)
    factors.append({"factor": "days_running", "score": round(days_score, 1), "weight": 0.10, "detail": f"{days} days"})

    # Weighted total
    health = sum(f["score"] * f["weight"] for f in factors)
    health = round(_clamp(health), 1)

    if health >= 75:
        risk = "healthy"
    elif health >= 50:
        risk = "watch"
    elif health >= 25:
        risk = "fatiguing"
    else:
        risk = "critical"

    # Estimate days to fatigue (simple linear extrapolation from CTR decay rate)
    if ctr_ratio < 1 and ctr_ratio > 0 and days > 0:
        daily_decay = (1 - ctr_ratio) / days
        remaining_ratio = ctr_ratio - 0.7  # fatigue at 70% of baseline
        days_to_fatigue = max(0, int(remaining_ratio / daily_decay)) if daily_decay > 0 else 999
    else:
        days_to_fatigue = None

    return {
        "creative_id": creative_id,
        "health_score": health,
        "risk_level": risk,
        "days_to_fatigue_estimate": days_to_fatigue,
        "contributing_factors": factors,
    }


# ── Predict Fatigue ──────────────────────────────────────────────────────────

def predict_fatigue(creative_id, history):
    if not isinstance(history, list) or len(history) < 3:
        return {"creative_id": creative_id, "error": "Need at least 3 data points for prediction"}

    try:
        dates = [datetime.strptime(h["date"], "%Y-%m-%d") for h in history]
        ctrs = [h["ctr"] for h in history]
        cpms = [h["cpm"] for h in history]
        if any(b <= a for a, b in zip(dates, dates[1:])):
            raise ValueError("Dates must be strictly increasing")
        if any(isinstance(v, bool) or not isinstance(v, (int, float))
               or not math.isfinite(v) or v < 0 for v in ctrs + cpms):
            raise ValueError("CTR and CPM must be finite nonnegative numbers")
        if ctrs[0] <= 0 or cpms[0] <= 0:
            raise ValueError("Baseline CTR and CPM must be positive")
    except (KeyError, TypeError, ValueError) as exc:
        return {"creative_id": creative_id, "error": f"Invalid performance history: {exc}"}
    x = [(date - dates[0]).days for date in dates]

    ctr_slope, ctr_intercept = _linear_regression(x, ctrs)
    cpm_slope, cpm_intercept = _linear_regression(x, cpms)

    baseline_ctr = ctrs[0]
    baseline_cpm = cpms[0]
    fatigue_ctr = baseline_ctr * 0.70
    fatigue_cpm = baseline_cpm * 1.30

    # Find crossover points
    ctr_days = 0 if ctrs[-1] <= fatigue_ctr else None
    if ctr_days is None and ctr_slope < 0:
        # Solve: ctr_slope * x + ctr_intercept = fatigue_ctr
        ctr_x = (fatigue_ctr - ctr_intercept) / ctr_slope
        ctr_days = max(0, math.ceil(round(ctr_x - x[-1], 10)))

    cpm_days = 0 if cpms[-1] >= fatigue_cpm else None
    if cpm_days is None and cpm_slope > 0:
        cpm_x = (fatigue_cpm - cpm_intercept) / cpm_slope
        cpm_days = max(0, math.ceil(round(cpm_x - x[-1], 10)))

    # Take the sooner of the two
    candidates = [d for d in [ctr_days, cpm_days] if d is not None]
    days_remaining = min(candidates) if candidates else None

    # Legacy confidence labels describe sample count, not calibrated uncertainty.
    n = len(history)
    if n >= 14:
        confidence = "high"
    elif n >= 7:
        confidence = "medium"
    else:
        confidence = "low"

    # Predicted fatigue date
    predicted_date = None
    if days_remaining is not None:
        try:
            last_date = datetime.strptime(history[-1]["date"], "%Y-%m-%d")
            from datetime import timedelta
            predicted_date = (last_date + timedelta(days=days_remaining)).strftime("%Y-%m-%d")
        except (KeyError, ValueError):
            pass

    # Recommendation
    if days_remaining is None:
        rec = "No threshold crossing projected by the linear model; review other fatigue signals."
    elif days_remaining == 0:
        rec = "URGENT: Fatigue threshold reached or projected at the latest observation. Review replacement creative now."
    elif days_remaining <= 7:
        rec = "URGENT: Creative fatigue imminent. Prepare replacement creative immediately."
    elif days_remaining <= 14:
        rec = "Creative approaching fatigue. Begin developing refresh variants now."
    elif days_remaining <= 30:
        rec = "Creative has runway but plan refresh within next sprint."
    else:
        rec = "Creative is healthy. Schedule routine review in 2-4 weeks."

    return {
        "creative_id": creative_id,
        "predicted_fatigue_date": predicted_date,
        "days_remaining": days_remaining,
        "confidence": confidence,
        "confidence_basis": "Heuristic sample-count label; not a statistical confidence interval",
        "trend_time_unit": "calendar_day",
        "ctr_trend_slope": round(ctr_slope, 6),
        "cpm_trend_slope": round(cpm_slope, 4),
        "recommendation": rec,
    }


# ── Generate Refresh Brief ───────────────────────────────────────────────────

def generate_refresh_brief(creative_id, data):
    fmt = data.get("format", "image")
    channel = data.get("channel", "unknown")
    audience = data.get("target_audience", "")
    performing = data.get("performing_elements", [])
    fatiguing = data.get("fatiguing_elements", [])

    keep = [f"Keep: {e} (performing well)" for e in performing]
    if not keep:
        keep = ["No strong performing elements identified — consider full creative overhaul"]

    change = [f"Refresh: {e} (showing fatigue signals)" for e in fatiguing]
    if not change:
        change = ["Test incremental visual changes first"]

    # Format-specific test suggestions
    test_map = {
        "image": ["New hero image with different color palette", "Alternative product angle or lifestyle shot", "User-generated content variant"],
        "video": ["New opening hook (first 3 seconds)", "Different thumbnail frame", "Shorter cut-down variant"],
        "text": ["New headline angle", "Different value proposition lead", "Question-based vs statement-based copy"],
        "carousel": ["Reorder card sequence", "Replace weakest-performing card", "New first card with different hook"],
    }
    tests = test_map.get(fmt, ["A/B test primary visual", "Test alternative headline", "Try different CTA"])

    angle_map = {
        "image": ["Social proof / testimonial overlay", "Before/after comparison", "Bold typography-led design"],
        "video": ["Customer story format", "Problem-agitation-solution structure", "Behind-the-scenes angle"],
        "text": ["Data-driven claim", "Emotional benefit lead", "Urgency/scarcity framing"],
        "carousel": ["Story arc across cards", "Comparison/listicle format", "Interactive quiz-style"],
    }
    angles = angle_map.get(fmt, ["New creative angle recommended"])

    urgency = "high" if len(fatiguing) > len(performing) else ("medium" if fatiguing else "low")

    return {
        "creative_id": creative_id,
        "refresh_brief": {
            "format": fmt,
            "channel": channel,
            "target_audience": audience,
            "what_to_keep": keep,
            "what_to_change": change,
            "what_to_test": tests,
            "suggested_angles": angles,
            "urgency": urgency,
        },
    }


# ── Decay Scan ───────────────────────────────────────────────────────────────

def decay_scan(items):
    results = []
    for item in items:
        cid = item.get("content_id", "unknown")
        traffic_cur = item.get("monthly_traffic_current", 0)
        traffic_prev = item.get("monthly_traffic_previous", 0)
        traffic_6mo = item.get("monthly_traffic_6mo_ago", 0)
        kw_cur = item.get("keyword_positions_current", {})
        kw_prev = item.get("keyword_positions_previous", {})
        publish_date = item.get("publish_date", "")
        last_updated = item.get("last_updated", "")

        signals = []
        decay_score = 0

        # Traffic decline
        if traffic_prev > 0:
            traffic_drop = (traffic_prev - traffic_cur) / traffic_prev
            if traffic_drop > 0.3:
                signals.append(f"Traffic dropped {traffic_drop:.0%} vs previous month")
                decay_score += 30
            elif traffic_drop > 0.1:
                signals.append(f"Traffic declined {traffic_drop:.0%} vs previous month")
                decay_score += 15

        if traffic_6mo > 0:
            long_drop = (traffic_6mo - traffic_cur) / traffic_6mo
            if long_drop > 0.5:
                signals.append(f"Traffic down {long_drop:.0%} vs 6 months ago")
                decay_score += 25

        # Keyword position drops
        pos_drops = 0
        for kw in kw_cur:
            cur_pos = kw_cur[kw]
            prev_pos = kw_prev.get(kw)
            if prev_pos is not None and cur_pos > prev_pos + 3:
                pos_drops += 1
        if pos_drops > 0:
            signals.append(f"{pos_drops} keyword(s) dropped 3+ positions")
            decay_score += min(25, pos_drops * 10)

        # Content age
        if last_updated:
            try:
                upd = datetime.strptime(last_updated[:10], "%Y-%m-%d")
                months_stale = (datetime.now() - upd).days / 30
                if months_stale > 12:
                    signals.append(f"Not updated in {int(months_stale)} months")
                    decay_score += 20
                elif months_stale > 6:
                    signals.append(f"Last updated {int(months_stale)} months ago")
                    decay_score += 10
            except ValueError:
                pass

        decay_score = min(100, decay_score)

        if decay_score >= 60:
            action = "rewrite"
        elif decay_score >= 40:
            action = "major-refresh"
        elif decay_score >= 20:
            action = "minor-refresh"
        elif decay_score >= 10:
            action = "consolidate"
        else:
            action = "no-action"

        if not signals:
            signals.append("No decay signals detected")

        # Priority: traffic impact x decay severity
        priority = round(traffic_cur * (decay_score / 100), 1)

        results.append({
            "content_id": cid,
            "title": item.get("title", ""),
            "decay_score": decay_score,
            "signals_detected": signals,
            "recommended_action": action,
            "priority_score": priority,
        })

    results.sort(key=lambda r: -r["priority_score"])
    return results


# ── Priority Refresh ─────────────────────────────────────────────────────────

def priority_refresh(items):
    results = []
    for item in items:
        cid = item.get("content_id", "unknown")
        traffic = item.get("monthly_traffic_current", 0)
        traffic_prev = item.get("monthly_traffic_previous", 0)
        cr = item.get("conversion_rate", 0)
        rev = item.get("revenue_per_conversion", 0)

        decay_sev = 0
        if traffic_prev > 0:
            decay_sev = max(0, (traffic_prev - traffic) / traffic_prev)

        priority = round(traffic * cr * rev * max(0.1, decay_sev), 2)
        results.append({
            "content_id": cid,
            "monthly_traffic": traffic,
            "decay_severity": round(decay_sev, 3),
            "conversion_rate": cr,
            "revenue_per_conversion": rev,
            "priority_score": priority,
            "monthly_revenue_at_risk": round(traffic * cr * rev * decay_sev, 2),
        })

    results.sort(key=lambda r: -r["priority_score"])
    return results


# ── Batch Health ─────────────────────────────────────────────────────────────

def batch_health(items):
    results = []
    for item in items:
        cid = item.pop("creative_id", item.pop("id", "unknown"))
        result = score_health(cid, item)
        results.append(result)
    results.sort(key=lambda r: r["health_score"])
    return results


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Creative Fatigue Predictor — Predict ad fatigue and track content decay for Digital Marketing Pro"
    )
    parser.add_argument("--action", required=True,
                        choices=["score-health", "predict-fatigue",
                                 "generate-refresh-brief", "decay-scan",
                                 "priority-refresh", "batch-health"],
                        help="Action to perform")
    parser.add_argument("--creative-id", help="Creative/ad identifier")
    parser.add_argument("--data", help="JSON data object or array")
    parser.add_argument("--performance-history",
                        help="JSON array of daily performance data (for predict-fatigue)")

    args = parser.parse_args()

    def _parse_json(raw, label="--data"):
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            print(json.dumps({"error": f"Invalid JSON in {label}: {e}"}))
            sys.exit(1)

    if args.action == "score-health":
        if not args.creative_id or not args.data:
            print(json.dumps({"error": "--creative-id and --data required for score-health"}))
            sys.exit(1)
        result = score_health(args.creative_id, _parse_json(args.data))

    elif args.action == "predict-fatigue":
        if not args.creative_id or not args.performance_history:
            print(json.dumps({"error": "--creative-id and --performance-history required for predict-fatigue"}))
            sys.exit(1)
        result = predict_fatigue(args.creative_id, _parse_json(args.performance_history, "--performance-history"))

    elif args.action == "generate-refresh-brief":
        if not args.creative_id or not args.data:
            print(json.dumps({"error": "--creative-id and --data required for generate-refresh-brief"}))
            sys.exit(1)
        result = generate_refresh_brief(args.creative_id, _parse_json(args.data))

    elif args.action == "decay-scan":
        if not args.data:
            print(json.dumps({"error": "--data required for decay-scan (JSON array)"}))
            sys.exit(1)
        data = _parse_json(args.data)
        if not isinstance(data, list):
            print(json.dumps({"error": "--data must be a JSON array for decay-scan"}))
            sys.exit(1)
        result = decay_scan(data)

    elif args.action == "priority-refresh":
        if not args.data:
            print(json.dumps({"error": "--data required for priority-refresh (JSON array)"}))
            sys.exit(1)
        data = _parse_json(args.data)
        if not isinstance(data, list):
            print(json.dumps({"error": "--data must be a JSON array for priority-refresh"}))
            sys.exit(1)
        result = priority_refresh(data)

    elif args.action == "batch-health":
        if not args.data:
            print(json.dumps({"error": "--data required for batch-health (JSON array)"}))
            sys.exit(1)
        data = _parse_json(args.data)
        if not isinstance(data, list):
            print(json.dumps({"error": "--data must be a JSON array for batch-health"}))
            sys.exit(1)
        result = batch_health(data)

    _common.finish(result)


if __name__ == "__main__":
    main()
