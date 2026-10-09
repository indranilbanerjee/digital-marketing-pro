#!/usr/bin/env python3
"""Churn Predictor — Score customer segments by churn probability.

Scores customer segments using weighted behavioral signals, tracks churn
trends over time, generates intervention playbooks, and analyzes cohort
risk. All scoring uses deterministic weighted formulas (no ML dependencies).

Dependencies: none (stdlib only)

Storage: ~/.claude-marketing/brands/{slug}/churn/

Usage:
    python churn-predictor.py --action score-segment --segment-name "Enterprise Q4" --signals '{"email_open_rate_trend":[0.12,0.25],"login_frequency_trend":[3,8],"purchase_frequency_trend":[1,3]}'
    python churn-predictor.py --action score-batch --data '[{"segment_name":"Enterprise","signals":{...}},{"segment_name":"SMB","signals":{...}}]'
    python churn-predictor.py --action intervention-plan --tier critical
    python churn-predictor.py --action trend --brand acme --segment-name "Enterprise" --score 72
    python churn-predictor.py --action cohort-risk --data '{"cohorts":[{"name":"Q1-2025","acquisition_date":"2025-01","current_customers":500,"churned_customers":45,"avg_ltv":2400,"engagement_score":65}]}'
    python churn-predictor.py --action summary --brand acme
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

BRANDS_DIR = _common.brands_root()

# Signal weights (must sum to 1.0)
WEIGHTS = {
    "email_engagement": 0.15,
    "login_frequency": 0.20,
    "purchase_frequency": 0.25,
    "support_tickets": 0.10,
    "feature_usage": 0.15,
    "payment_failures": 0.10,
    "recency": 0.05,
}

INTERVENTIONS = {
    "low": {
        "tier": "low",
        "actions": [
            "Send satisfaction survey",
            "Share product tips newsletter",
            "Offer loyalty program enrollment",
        ],
        "timing": "Within 30 days",
        "channels": ["email", "in-app"],
        "expected_save_rate": 0.95,
        "messaging_themes": [
            "Value reinforcement",
            "Feature discovery",
            "Community engagement",
        ],
    },
    "medium": {
        "tier": "medium",
        "actions": [
            "Trigger personalized re-engagement email sequence",
            "Assign CSM check-in call",
            "Offer usage-based incentive or discount",
            "Send case study matching their use case",
        ],
        "timing": "Within 14 days",
        "channels": ["email", "phone", "in-app"],
        "expected_save_rate": 0.75,
        "messaging_themes": [
            "ROI demonstration",
            "Personalized value proposition",
            "Success story alignment",
            "Exclusive offer framing",
        ],
    },
    "high": {
        "tier": "high",
        "actions": [
            "Executive outreach from account manager",
            "Custom QBR or success review meeting",
            "Offer contract adjustment or upgrade incentive",
            "Deploy win-back campaign with urgency",
            "Escalate to retention team",
        ],
        "timing": "Within 7 days",
        "channels": ["phone", "email", "video-call", "in-app"],
        "expected_save_rate": 0.50,
        "messaging_themes": [
            "Partnership commitment",
            "Tailored solution adjustment",
            "Risk of loss framing",
            "Executive sponsorship",
        ],
    },
    "critical": {
        "tier": "critical",
        "actions": [
            "Immediate executive phone call",
            "Emergency retention offer (pricing, contract flex)",
            "Dedicated success plan with weekly check-ins",
            "Escalate internally — flag revenue at risk",
            "Offer concierge migration/setup support",
            "Deploy save offer with deadline",
        ],
        "timing": "Within 48 hours",
        "channels": ["phone", "video-call", "email", "sms"],
        "expected_save_rate": 0.30,
        "messaging_themes": [
            "Urgency and personal attention",
            "We want to make this right",
            "Concrete plan to fix pain points",
            "Last-chance exclusive offer",
        ],
    },
}


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


def _decay_score(recent, baseline):
    """Score a trend signal: 0 (no decay) to 100 (total decay).
    recent/baseline are the metric values; lower recent = higher churn signal."""
    if baseline <= 0:
        return 50.0  # No baseline — neutral
    ratio = recent / baseline
    # ratio 1.0+ = no decay (score 0), ratio 0 = total decay (score 100)
    score = max(0.0, min(100.0, (1.0 - ratio) * 100.0))
    return round(score, 1)


def _score_segment_signals(signals):
    """Calculate churn score (0-100) from behavioral signals."""
    factors = []

    # Email engagement (trend)
    email = signals.get("email_open_rate_trend")
    if email and len(email) == 2:
        s = _decay_score(email[0], email[1])
        factors.append(("email_engagement", s, WEIGHTS["email_engagement"]))
    else:
        factors.append(("email_engagement", 50.0, WEIGHTS["email_engagement"]))

    # Login frequency (trend)
    login = signals.get("login_frequency_trend")
    if login and len(login) == 2:
        s = _decay_score(login[0], login[1])
        factors.append(("login_frequency", s, WEIGHTS["login_frequency"]))
    else:
        factors.append(("login_frequency", 50.0, WEIGHTS["login_frequency"]))

    # Purchase frequency (trend)
    purchase = signals.get("purchase_frequency_trend")
    if purchase and len(purchase) == 2:
        s = _decay_score(purchase[0], purchase[1])
        factors.append(("purchase_frequency", s, WEIGHTS["purchase_frequency"]))
    else:
        factors.append(("purchase_frequency", 50.0, WEIGHTS["purchase_frequency"]))

    # Support tickets (trend — higher recent = higher churn)
    support = signals.get("support_tickets_trend")
    if support and len(support) == 2:
        recent_t, baseline_t = support[0], support[1]
        if baseline_t > 0:
            ratio = recent_t / baseline_t
            s = min(100.0, max(0.0, (ratio - 1.0) * 50.0 + 50.0))
        else:
            s = min(100.0, recent_t * 20.0)  # No baseline — raw count heuristic
        factors.append(("support_tickets", round(s, 1), WEIGHTS["support_tickets"]))
    else:
        factors.append(("support_tickets", 50.0, WEIGHTS["support_tickets"]))

    # Feature usage (trend)
    feature = signals.get("feature_usage_trend")
    if feature and len(feature) == 2:
        s = _decay_score(feature[0], feature[1])
        factors.append(("feature_usage", s, WEIGHTS["feature_usage"]))
    else:
        factors.append(("feature_usage", 50.0, WEIGHTS["feature_usage"]))

    # Payment failures (count — direct risk indicator)
    pf = signals.get("payment_failures", 0)
    pf_score = min(100.0, pf * 33.0)  # 1 failure=33, 2=66, 3+=100
    factors.append(("payment_failures", round(pf_score, 1), WEIGHTS["payment_failures"]))

    # Recency (months since last purchase)
    months_since = signals.get("months_since_last_purchase", 0)
    recency_score = min(100.0, months_since * 15.0)  # 7+ months = max risk
    factors.append(("recency", round(recency_score, 1), WEIGHTS["recency"]))

    # Contract buffer (optional — reduces score if contract has time left)
    contract_months = signals.get("contract_months_remaining")

    # Weighted sum
    churn_score = sum(s * w for _, s, w in factors)

    # Contract buffer: reduce score up to 20% if contract has >6 months
    if contract_months is not None and contract_months > 0:
        buffer = min(contract_months / 12.0 * 20.0, 20.0)
        churn_score = max(0.0, churn_score - buffer)

    churn_score = round(min(100.0, max(0.0, churn_score)), 1)

    # Risk tier
    if churn_score >= 75:
        tier = "critical"
    elif churn_score >= 50:
        tier = "high"
    elif churn_score >= 25:
        tier = "medium"
    else:
        tier = "low"

    # Sort contributing factors by impact (score * weight)
    sorted_factors = sorted(factors, key=lambda f: f[1] * f[2], reverse=True)
    contributing = [
        {"signal": name, "signal_score": score, "weight": weight,
         "impact": round(score * weight, 1)}
        for name, score, weight in sorted_factors
    ]

    # Recommended interventions based on tier
    interventions = INTERVENTIONS.get(tier, INTERVENTIONS["medium"])

    return {
        "churn_score": churn_score,
        "risk_tier": tier,
        "contributing_factors": contributing,
        "recommended_interventions": interventions["actions"][:3],
    }


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def score_segment(segment_name, signals):
    result = _score_segment_signals(signals)
    result["segment_name"] = segment_name
    return result


def score_batch(data):
    results = []
    for item in data:
        seg_name = item.get("segment_name", "Unknown")
        signals = item.get("signals", {})
        entry = _score_segment_signals(signals)
        entry["segment_name"] = seg_name
        results.append(entry)
    results.sort(key=lambda r: r["churn_score"], reverse=True)
    return {"segments": results, "total": len(results)}


def intervention_plan(tier):
    plan = INTERVENTIONS.get(tier)
    if not plan:
        return {"error": f"Invalid tier '{tier}'. Use: low, medium, high, critical"}
    return plan


def trend(brand_slug, segment_name, current_score):
    brand_dir = BRANDS_DIR / brand_slug
    if not brand_dir.exists():
        return {"error": f"Brand '{brand_slug}' not found. Run /digital-marketing-pro:brand-setup first."}

    churn_dir = brand_dir / "churn"
    churn_dir.mkdir(parents=True, exist_ok=True)

    safe_name = segment_name.lower().replace(" ", "-").replace("/", "-")
    history_path = churn_dir / f"{safe_name}.json"
    history = _load_json(history_path, [])

    # Append current score
    entry = {
        "score": current_score,
        "recorded_at": datetime.now().isoformat(),
    }
    history.append(entry)
    _save_json(history_path, history)

    # Calculate trend
    scores = [h["score"] for h in history]
    if len(scores) >= 3:
        recent_avg = sum(scores[-3:]) / 3
        older_avg = sum(scores[:-3]) / max(len(scores) - 3, 1) if len(scores) > 3 else scores[0]
        velocity = round(recent_avg - older_avg, 1)
        if velocity < -3:
            direction = "improving"
        elif velocity > 3:
            direction = "worsening"
        else:
            direction = "stable"
    elif len(scores) == 2:
        velocity = round(scores[-1] - scores[0], 1)
        direction = "improving" if velocity < -3 else "worsening" if velocity > 3 else "stable"
    else:
        velocity = 0
        direction = "insufficient_data"

    return {
        "segment_name": segment_name,
        "current_score": current_score,
        "historical_scores": scores,
        "data_points": len(scores),
        "trend_direction": direction,
        "velocity": velocity,
    }


def cohort_risk(data):
    cohorts = data.get("cohorts", [])
    results = []
    for c in cohorts:
        current = c.get("current_customers", 0)
        churned = c.get("churned_customers", 0)
        total = current + churned
        retention = round(current / total * 100, 1) if total > 0 else 0
        churn_rate = round(churned / total * 100, 1) if total > 0 else 0
        avg_ltv = c.get("avg_ltv", 0)
        ltv_at_risk = round(current * avg_ltv * (churn_rate / 100), 2)
        engagement = c.get("engagement_score", 50)

        # Risk score: blend of churn rate and inverse engagement
        risk = round(churn_rate * 0.6 + (100 - engagement) * 0.4, 1)

        results.append({
            "cohort": c.get("name", "Unknown"),
            "acquisition_date": c.get("acquisition_date", ""),
            "total_customers": total,
            "current_customers": current,
            "churned_customers": churned,
            "retention_rate_pct": retention,
            "churn_rate_pct": churn_rate,
            "avg_ltv": avg_ltv,
            "ltv_at_risk": ltv_at_risk,
            "engagement_score": engagement,
            "risk_score": risk,
        })

    results.sort(key=lambda r: r["risk_score"], reverse=True)
    return {"cohorts": results, "total": len(results)}


def summary(brand_slug):
    brand_dir = BRANDS_DIR / brand_slug
    if not brand_dir.exists():
        return {"error": f"Brand '{brand_slug}' not found. Run /digital-marketing-pro:brand-setup first."}

    churn_dir = brand_dir / "churn"
    if not churn_dir.exists():
        return {
            "total_segments_tracked": 0,
            "average_churn_score": 0,
            "highest_risk_segments": [],
            "trend_direction": "no_data",
            "total_ltv_at_risk": 0,
            "note": "No churn data tracked yet.",
        }

    segments = []
    all_scores = []
    total_ltv_at_risk = 0.0
    for fp in churn_dir.glob("*.json"):
        history = _load_json(fp, [])
        if not history:
            continue
        name = fp.stem.replace("-", " ").title()
        latest = history[-1].get("score", 0)
        total_ltv_at_risk += history[-1].get("ltv_at_risk", 0) or 0
        all_scores.append(latest)
        segments.append({"segment": name, "latest_score": latest, "data_points": len(history)})

    if not segments:
        return {
            "total_segments_tracked": 0,
            "average_churn_score": 0,
            "highest_risk_segments": [],
            "trend_direction": "no_data",
            "total_ltv_at_risk": 0,
        }

    segments.sort(key=lambda s: s["latest_score"], reverse=True)
    avg_score = round(sum(all_scores) / len(all_scores), 1)

    # Overall direction from all latest scores
    if avg_score >= 50:
        overall = "concerning"
    elif avg_score >= 25:
        overall = "moderate"
    else:
        overall = "healthy"

    return {
        "total_segments_tracked": len(segments),
        "average_churn_score": avg_score,
        "highest_risk_segments": segments[:5],
        "trend_direction": overall,
        "total_ltv_at_risk": round(total_ltv_at_risk, 2),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Churn Predictor — score customer segments by churn probability"
    )
    parser.add_argument("--action", required=True,
                        choices=["score-segment", "score-batch", "intervention-plan",
                                 "trend", "cohort-risk", "summary"],
                        help="Action to perform")
    parser.add_argument("--brand", type=_common.path_component, help="Brand slug")
    parser.add_argument("--segment-name", dest="segment_name",
                        help="Segment name (for score-segment, trend)")
    parser.add_argument("--signals", help="JSON behavioral signals (for score-segment)")
    parser.add_argument("--data", help="JSON data (for score-batch, cohort-risk)")
    parser.add_argument("--tier", choices=["low", "medium", "high", "critical"],
                        help="Risk tier (for intervention-plan)")
    parser.add_argument("--score", type=float,
                        help="Current churn score to record (for trend)")
    args = parser.parse_args()

    result = None

    if args.action == "score-segment":
        if not args.segment_name:
            print(json.dumps({"error": "Provide --segment-name"}))
            sys.exit(1)
        if not args.signals:
            print(json.dumps({"error": "Provide --signals JSON"}))
            sys.exit(1)
        try:
            signals = json.loads(args.signals)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --signals"}))
            sys.exit(1)
        result = score_segment(args.segment_name, signals)

    elif args.action == "score-batch":
        if not args.data:
            print(json.dumps({"error": "Provide --data JSON array"}))
            sys.exit(1)
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --data"}))
            sys.exit(1)
        if not isinstance(data, list):
            data = [data]
        result = score_batch(data)

    elif args.action == "intervention-plan":
        if not args.tier:
            print(json.dumps({"error": "Provide --tier (low|medium|high|critical)"}))
            sys.exit(1)
        result = intervention_plan(args.tier)

    elif args.action == "trend":
        if not args.brand:
            print(json.dumps({"error": "Provide --brand for trend tracking"}))
            sys.exit(1)
        if not args.segment_name:
            print(json.dumps({"error": "Provide --segment-name"}))
            sys.exit(1)
        if args.score is None:
            print(json.dumps({"error": "Provide --score (current churn score)"}))
            sys.exit(1)
        result = trend(args.brand, args.segment_name, args.score)

    elif args.action == "cohort-risk":
        if not args.data:
            print(json.dumps({"error": "Provide --data JSON with cohorts"}))
            sys.exit(1)
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --data"}))
            sys.exit(1)
        result = cohort_risk(data)

    elif args.action == "summary":
        if not args.brand:
            print(json.dumps({"error": "Provide --brand for summary"}))
            sys.exit(1)
        result = summary(args.brand)

    if result is not None:
        _common.finish(result)


if __name__ == "__main__":
    main()
