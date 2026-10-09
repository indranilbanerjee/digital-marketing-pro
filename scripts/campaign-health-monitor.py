#!/usr/bin/env python3
"""Campaign Health Monitor — Self-healing campaign operations.

Scores campaign health, detects issues, recommends corrective actions, and
manages auto-correction guardrails. Tracks correction history and estimates
savings from automated interventions.

Dependencies: none (stdlib only)

Usage:
    python campaign-health-monitor.py --action health-score --campaign-id camp-123 --campaign-type conversion --metrics '{"spend_actual":8000,"spend_planned":10000,"ctr_current":2.1,"ctr_baseline":2.5,"roas_current":3.2,"roas_target":4.0,"bounce_rate":45,"landing_page_status":"up","frequency":3.5}'
    python campaign-health-monitor.py --action detect-issues --brand acme --campaigns '[...]'
    python campaign-health-monitor.py --action recommend-action --issue-type ctr-decline --severity high --campaign-id camp-123
    python campaign-health-monitor.py --action get-guardrails --brand acme
    python campaign-health-monitor.py --action set-guardrails --brand acme --guardrails '{"max_bid_adjustment_pct":15}'
    python campaign-health-monitor.py --action log-correction --brand acme --campaign-id camp-123 --issue "CTR decline" --correction-applied "Paused underperforming ad set" --was-auto true --expected-impact "CTR +0.3%"
    python campaign-health-monitor.py --action corrections-history --brand acme
    python campaign-health-monitor.py --action savings-report --brand acme
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

BRANDS_DIR = _common.brands_root()

# Default guardrails. allowed_actions is EMPTY: autopilot proposes every
# correction and waits for a typed yes. Actions can be pre-authorised only with
# set-guardrails plus an approved standing approval (kind "autopilot"); configs
# written before 3.35.0 that already list actions keep working as written.
AUTOPILOT_ACTIONS = [
    "pause_ad_set", "adjust_bid", "adjust_budget", "swap_creative",
    "pause_campaign", "enable_backup_landing_page", "reduce_frequency_cap",
]
DEFAULT_GUARDRAILS = {
    "allowed_actions": [],
    # Match the published limits (self-healing-ops-guide.md, PRIVACY.md): bids -15%, budgets -20%.
    "max_bid_adjustment_pct": 15,
    "max_budget_adjustment_pct": 20,
    "pause_on_landing_page_down": True,
    "escalation_thresholds": {
        "spend_overage_pct": 15,
        "ctr_decline_pct": 30,
        "cpa_increase_pct": 40,
        "roas_decline_pct": 25,
    },
}

# Health score weights by campaign type
WEIGHTS = {
    "awareness": {
        "spend_pacing": 15, "ctr": 25, "bounce_rate": 15,
        "landing_page": 10, "frequency": 20, "quality_score": 15,
    },
    "conversion": {
        "spend_pacing": 15, "ctr": 15, "cpa": 20, "roas": 20,
        "bounce_rate": 10, "landing_page": 10, "frequency": 10,
    },
    "retention": {
        "spend_pacing": 10, "deliverability": 20, "open_rate": 20,
        "ctr": 15, "unsubscribe_rate": 20, "bounce_rate": 15,
    },
    "engagement": {
        "spend_pacing": 10, "ctr": 25, "bounce_rate": 15,
        "frequency": 20, "quality_score": 15, "landing_page": 15,
    },
}

# Corrective action recommendations
ACTION_RECOMMENDATIONS = {
    "landing-page-down": {
        "recommended_action": "Redirect traffic to backup landing page or pause campaign immediately",
        "can_auto_correct": True,
        "requires_approval": False,
        "expected_impact": "Prevents 100% bounce rate and wasted spend",
        "rollback_instructions": "Re-enable original landing page URL once it is confirmed back online",
    },
    "bounce-spike": {
        "recommended_action": "Review landing page load time and content relevance; consider A/B test with alternative page",
        "can_auto_correct": False,
        "requires_approval": True,
        "expected_impact": "Bounce rate reduction of 10-25% after fix",
        "rollback_instructions": "Revert landing page changes if bounce rate does not improve within 48 hours",
    },
    "overspend": {
        "recommended_action": "Reduce daily budget cap or pause lowest-performing ad sets to bring spend in line",
        "can_auto_correct": True,
        "requires_approval": False,
        "expected_impact": "Brings spend within planned budget, saves remaining allocation",
        "rollback_instructions": "Restore original budget caps once spend pacing normalizes",
    },
    "deliverability-drop": {
        "recommended_action": "Audit sending domain health, check blacklists, reduce send volume, warm up IP if needed",
        "can_auto_correct": False,
        "requires_approval": True,
        "expected_impact": "Deliverability recovery to baseline within 1-2 weeks",
        "rollback_instructions": "If deliverability continues to drop, switch to backup sending domain",
    },
    "ctr-decline": {
        "recommended_action": "Refresh ad creatives, test new copy variants, review audience targeting for fatigue",
        "can_auto_correct": True,
        "requires_approval": True,
        "expected_impact": "CTR recovery of 15-30% with creative refresh",
        "rollback_instructions": "Revert to previous top-performing creative if new variants underperform",
    },
    "frequency-fatigue": {
        "recommended_action": "Reduce frequency cap, expand audience targeting, or rotate creative assets",
        "can_auto_correct": True,
        "requires_approval": False,
        "expected_impact": "Reduces ad fatigue, improves CTR by 10-20%",
        "rollback_instructions": "Restore original frequency cap if reach drops below acceptable threshold",
    },
    "quality-score-drop": {
        "recommended_action": "Improve ad relevance and landing page experience; align keywords with ad copy more tightly",
        "can_auto_correct": False,
        "requires_approval": True,
        "expected_impact": "Quality score improvement reduces CPC by 10-30%",
        "rollback_instructions": "Monitor for 7 days; if quality score doesn't recover, revert keyword and copy changes",
    },
    "budget-exhaustion": {
        "recommended_action": "Reallocate budget from underperforming campaigns or request additional budget approval",
        "can_auto_correct": True,
        "requires_approval": True,
        "expected_impact": "Extends campaign run time, prevents early end to high-performing campaigns",
        "rollback_instructions": "Restore original budget allocation if reallocated campaign performance drops",
    },
}


def _get_brand_dir(slug):
    brand_dir = BRANDS_DIR / slug
    if not brand_dir.exists():
        return None, f"Brand '{slug}' not found. Run /digital-marketing-pro:brand-setup first."
    return brand_dir, None


def _ops_dir(brand_dir):
    d = brand_dir / "operations"
    d.mkdir(exist_ok=True)
    return d


def _corrections_dir(brand_dir):
    d = _ops_dir(brand_dir) / "corrections"
    d.mkdir(exist_ok=True)
    return d


def _load_guardrails(brand_dir):
    config_dir = brand_dir / "config"
    gp = config_dir / "guardrails.json"
    if gp.exists():
        try:
            return json.loads(gp.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return dict(DEFAULT_GUARDRAILS)


def _score_component(actual, target, higher_is_better=True, max_score=100):
    """Score a single metric component on a 0-100 scale."""
    if target is None or target == 0:
        return max_score  # No target = assume healthy
    if higher_is_better:
        ratio = actual / target
    else:
        ratio = target / actual if actual > 0 else 0
    return round(min(max(ratio * max_score, 0), max_score), 1)


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def health_score(campaign_id, campaign_type, metrics):
    weights = WEIGHTS.get(campaign_type, WEIGHTS["conversion"])
    scores = {}
    issues = []

    # Spend pacing
    spend_actual = metrics.get("spend_actual", 0)
    spend_planned = metrics.get("spend_planned", 1)
    if "spend_pacing" in weights:
        pacing_ratio = spend_actual / spend_planned if spend_planned > 0 else 0
        if pacing_ratio > 1.15:
            scores["spend_pacing"] = max(0, 100 - (pacing_ratio - 1.0) * 200)
            issues.append({"issue": "overspend", "detail": f"Spend at {round(pacing_ratio * 100, 1)}% of plan", "severity": "high" if pacing_ratio > 1.3 else "medium"})
        elif pacing_ratio < 0.7:
            scores["spend_pacing"] = pacing_ratio / 0.7 * 80
            issues.append({"issue": "underspend", "detail": f"Spend at {round(pacing_ratio * 100, 1)}% of plan", "severity": "medium"})
        else:
            scores["spend_pacing"] = 100

    # CTR
    ctr_current = metrics.get("ctr_current", 0)
    ctr_baseline = metrics.get("ctr_baseline", 0)
    if "ctr" in weights and ctr_baseline > 0:
        ctr_score = _score_component(ctr_current, ctr_baseline, higher_is_better=True)
        scores["ctr"] = ctr_score
        if ctr_current < ctr_baseline * 0.7:
            issues.append({"issue": "ctr-decline", "detail": f"CTR {ctr_current}% vs {ctr_baseline}% baseline", "severity": "high"})
        elif ctr_current < ctr_baseline * 0.9:
            issues.append({"issue": "ctr-decline", "detail": f"CTR {ctr_current}% vs {ctr_baseline}% baseline", "severity": "medium"})

    # CPA
    cpa_current = metrics.get("cpa_current")
    cpa_target = metrics.get("cpa_target")
    if "cpa" in weights and cpa_current is not None and cpa_target:
        cpa_score = _score_component(cpa_current, cpa_target, higher_is_better=False)
        scores["cpa"] = cpa_score
        if cpa_current > cpa_target * 1.4:
            issues.append({"issue": "cpa-spike", "detail": f"CPA ${cpa_current} vs ${cpa_target} target", "severity": "critical"})
        elif cpa_current > cpa_target * 1.15:
            issues.append({"issue": "cpa-spike", "detail": f"CPA ${cpa_current} vs ${cpa_target} target", "severity": "medium"})

    # ROAS
    roas_current = metrics.get("roas_current")
    roas_target = metrics.get("roas_target")
    if "roas" in weights and roas_current is not None and roas_target:
        roas_score = _score_component(roas_current, roas_target, higher_is_better=True)
        scores["roas"] = roas_score
        if roas_current < roas_target * 0.6:
            issues.append({"issue": "roas-decline", "detail": f"ROAS {roas_current}x vs {roas_target}x target", "severity": "critical"})
        elif roas_current < roas_target * 0.85:
            issues.append({"issue": "roas-decline", "detail": f"ROAS {roas_current}x vs {roas_target}x target", "severity": "medium"})

    # Bounce rate
    bounce_rate = metrics.get("bounce_rate", 0)
    if "bounce_rate" in weights:
        bounce_score = max(0, 100 - bounce_rate)
        scores["bounce_rate"] = bounce_score
        if bounce_rate > 70:
            issues.append({"issue": "bounce-spike", "detail": f"Bounce rate at {bounce_rate}%", "severity": "high"})
        elif bounce_rate > 55:
            issues.append({"issue": "bounce-spike", "detail": f"Bounce rate at {bounce_rate}%", "severity": "medium"})

    # Landing page status
    lp_status = metrics.get("landing_page_status", "up")
    if "landing_page" in weights:
        if lp_status == "down":
            scores["landing_page"] = 0
            issues.append({"issue": "landing-page-down", "detail": "Landing page is down", "severity": "critical"})
        elif lp_status == "slow":
            scores["landing_page"] = 50
            issues.append({"issue": "landing-page-slow", "detail": "Landing page is slow", "severity": "medium"})
        else:
            scores["landing_page"] = 100

    # Quality score
    quality_score = metrics.get("quality_score")
    if "quality_score" in weights and quality_score is not None:
        qs_score = quality_score / 10 * 100
        scores["quality_score"] = qs_score
        if quality_score < 5:
            issues.append({"issue": "quality-score-drop", "detail": f"Quality score at {quality_score}/10", "severity": "high"})
        elif quality_score < 7:
            issues.append({"issue": "quality-score-drop", "detail": f"Quality score at {quality_score}/10", "severity": "medium"})

    # Frequency
    frequency = metrics.get("frequency", 0)
    if "frequency" in weights:
        if frequency > 8:
            scores["frequency"] = 20
            issues.append({"issue": "frequency-fatigue", "detail": f"Frequency at {frequency}", "severity": "high"})
        elif frequency > 5:
            scores["frequency"] = 60
            issues.append({"issue": "frequency-fatigue", "detail": f"Frequency at {frequency}", "severity": "medium"})
        else:
            scores["frequency"] = 100

    # Deliverability
    deliverability = metrics.get("deliverability_rate")
    if "deliverability" in weights and deliverability is not None:
        scores["deliverability"] = deliverability
        if deliverability < 85:
            issues.append({"issue": "deliverability-drop", "detail": f"Deliverability at {deliverability}%", "severity": "critical"})
        elif deliverability < 95:
            issues.append({"issue": "deliverability-drop", "detail": f"Deliverability at {deliverability}%", "severity": "medium"})

    # Open rate
    open_rate = metrics.get("open_rate")
    if "open_rate" in weights and open_rate is not None:
        scores["open_rate"] = min(open_rate / 25 * 100, 100)  # 25% open rate = perfect

    # Unsubscribe rate
    unsub_rate = metrics.get("unsubscribe_rate")
    if "unsubscribe_rate" in weights and unsub_rate is not None:
        unsub_score = max(0, 100 - unsub_rate * 100)  # 1% unsub = 0 score
        scores["unsubscribe_rate"] = unsub_score
        if unsub_rate > 0.5:
            issues.append({"issue": "high-unsubscribe", "detail": f"Unsubscribe rate at {unsub_rate}%", "severity": "high"})

    # Calculate weighted health score
    total_weight = 0
    weighted_sum = 0
    contributing_factors = []
    for component, weight in weights.items():
        if component in scores:
            weighted_sum += scores[component] * weight
            total_weight += weight
            contributing_factors.append({
                "factor": component,
                "score": round(scores[component], 1),
                "weight": weight,
                "impact": round(scores[component] * weight / 100, 1),
            })

    health = round(weighted_sum / total_weight, 1) if total_weight > 0 else 0

    # Determine risk level
    if health >= 80:
        risk_level = "healthy"
    elif health >= 60:
        risk_level = "watch"
    elif health >= 40:
        risk_level = "warning"
    else:
        risk_level = "critical"

    # Sort contributing factors by impact (ascending = worst first)
    contributing_factors.sort(key=lambda x: x["impact"])

    # Sort issues by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    issues.sort(key=lambda x: severity_order.get(x.get("severity", "low"), 4))

    return {
        "campaign_id": campaign_id,
        "campaign_type": campaign_type,
        "health_score": health,
        "risk_level": risk_level,
        "issues_detected": issues,
        "top_issue": issues[0]["issue"] if issues else None,
        "contributing_factors": contributing_factors,
    }


def detect_issues(slug, campaigns):
    brand_dir, err = _get_brand_dir(slug)
    if err:
        return {"error": err}

    all_issues = []
    healthy = 0
    warning = 0
    critical = 0
    total_wasted = 0.0

    for camp in campaigns:
        cid = camp.get("campaign_id", "unknown")
        ctype = camp.get("campaign_type", "conversion")
        metrics = camp.get("metrics", {})

        result = health_score(cid, ctype, metrics)
        rl = result["risk_level"]

        if rl == "healthy":
            healthy += 1
        elif rl in ("watch", "warning"):
            warning += 1
        else:
            critical += 1

        for issue in result["issues_detected"]:
            issue["campaign_id"] = cid
            all_issues.append(issue)

        # Estimate wasted spend from critical issues
        if rl == "critical":
            total_wasted += metrics.get("spend_actual", 0) * 0.3
        elif rl == "warning":
            total_wasted += metrics.get("spend_actual", 0) * 0.1

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    all_issues.sort(key=lambda x: severity_order.get(x.get("severity", "low"), 4))

    return {
        "total_campaigns": len(campaigns),
        "healthy_count": healthy,
        "warning_count": warning,
        "critical_count": critical,
        "issues": all_issues,
        "estimated_wasted_spend": round(total_wasted, 2),
    }


def recommend_action(issue_type, severity, campaign_id):
    rec = ACTION_RECOMMENDATIONS.get(issue_type)
    if not rec:
        return {
            "campaign_id": campaign_id,
            "issue_type": issue_type,
            "error": f"No recommendation template for issue type '{issue_type}'",
        }

    severity_map = {"low": "low", "medium": "medium", "high": "high", "critical": "high"}
    risk = severity_map.get(severity, "medium")

    return {
        "campaign_id": campaign_id,
        "issue_type": issue_type,
        "severity": severity,
        "recommended_action": rec["recommended_action"],
        "risk_level": risk,
        "can_auto_correct": rec["can_auto_correct"],
        "requires_approval": rec["requires_approval"] or severity == "critical",
        "expected_impact": rec["expected_impact"],
        "rollback_instructions": rec["rollback_instructions"],
    }


def get_guardrails(slug):
    brand_dir, err = _get_brand_dir(slug)
    if err:
        return {"error": err}
    return _load_guardrails(brand_dir)


def set_guardrails(slug, guardrails, approval_id=None):
    brand_dir, err = _get_brand_dir(slug)
    if err:
        return {"error": err}

    config_dir = brand_dir / "config"
    config_dir.mkdir(exist_ok=True)

    # Merge with defaults
    current = _load_guardrails(brand_dir)
    requested = guardrails.get("allowed_actions")
    if requested:
        unknown = sorted(set(requested) - set(AUTOPILOT_ACTIONS))
        if unknown:
            return {"error": f"unknown autopilot actions {unknown}; allowed: {AUTOPILOT_ACTIONS}"}
        standing, why = _standing_for(slug, approval_id, requested)
        if why:
            return {"error": why, "approval_required": True,
                    "next": ("Create the standing approval: approval-manager.py --brand "
                             f"{slug} --action create-standing --data '{{\"kind\": \"autopilot\", "
                             f"\"actions\": {json.dumps(requested)}, \"max_uses_per_day\": 5, \"days\": 30, "
                             "\"summary\": \"...\"}}', show it to the user, approve it only after they type "
                             "yes, then re-run set-guardrails with --approval-id <id>.")}
        guardrails = dict(guardrails, standing_approval={
            "approval_id": standing["approval_id"], "approved_at": standing.get("approved_at"),
            "expires_at": standing.get("expires_at"), "max_uses_per_day": standing.get("max_uses_per_day")})
    current.update(guardrails)

    gp = config_dir / "guardrails.json"
    gp.write_text(json.dumps(current, indent=2), encoding="utf-8")

    return {"status": "saved", "guardrails": current, "path": str(gp)}


def _standing_for(slug, approval_id, actions):
    """(record, None) if approval_id is an approved, unexpired autopilot standing
    approval covering every action, else (None, reason)."""
    if not approval_id:
        return None, ("pre-authorising autopilot actions needs --approval-id of an approved standing "
                      "approval (kind 'autopilot') covering them")
    path, err = _common.child_or_error(_common.approvals_dir(slug), approval_id, ".json")
    if err:
        return None, err
    rec = _common.load_json_safe(path) if path.exists() else None
    if not isinstance(rec, dict) or "error" in rec:
        return None, f"approval '{approval_id}' not found"
    scope = rec.get("scope") or {}
    if rec.get("kind") != "standing" or scope.get("kind") != "autopilot":
        return None, f"approval '{approval_id}' is not an autopilot standing approval"
    if rec.get("status") != "approved":
        return None, f"approval '{approval_id}' is '{rec.get('status')}', not 'approved'"
    if _common._expired(rec.get("expires_at")):
        return None, f"approval '{approval_id}' expired at {rec.get('expires_at')}"
    missing = sorted(set(actions) - set(scope.get("actions") or []))
    if missing:
        return None, f"approval '{approval_id}' does not cover {missing}"
    return rec, None


def log_correction(slug, campaign_id, issue, correction_applied, was_auto, expected_impact):
    brand_dir, err = _get_brand_dir(slug)
    if err:
        return {"error": err}

    # An automatic correction under a standing approval counts against its daily
    # cap; at the cap, autopilot stops and must propose instead.
    standing = (_load_guardrails(brand_dir).get("standing_approval") or {})
    if was_auto and standing.get("approval_id"):
        path, perr = _common.child_or_error(_common.approvals_dir(slug), standing["approval_id"], ".json")
        rec = _common.load_json_safe(path) if (not perr and path.exists()) else None
        if not isinstance(rec, dict) or "error" in rec or rec.get("status") != "approved" \
                or _common._expired(rec.get("expires_at")):
            return {"error": "the standing approval behind this automatic correction is missing, revoked or "
                             "expired; propose the correction and wait for a typed yes", "cap_reached": True}
        today = datetime.now(timezone.utc).date().isoformat()
        used = sum(1 for u in rec.get("uses", []) if str(u.get("at", "")).startswith(today))
        if used >= int(rec.get("max_uses_per_day") or 0):
            return {"error": f"standing approval cap of {rec.get('max_uses_per_day')} automatic corrections "
                             "per day reached; propose this one and wait for a typed yes", "cap_reached": True}
        rec.setdefault("uses", []).append({"at": datetime.now(timezone.utc).isoformat(),
                                           "campaign_id": campaign_id, "correction": correction_applied})
        _common.atomic_write_json(path, rec)

    cdir = _corrections_dir(brand_dir)
    now = datetime.now()
    ts = now.strftime("%Y%m%d-%H%M%S")
    correction_id = hashlib.md5(f"{campaign_id}-{ts}".encode()).hexdigest()[:12]

    correction = {
        "correction_id": correction_id,
        "campaign_id": campaign_id,
        "issue": issue,
        "correction_applied": correction_applied,
        "was_auto": was_auto,
        "expected_impact": expected_impact,
        "timestamp": now.isoformat(),
    }

    fp = cdir / f"{correction_id}.json"
    fp.write_text(json.dumps(correction, indent=2), encoding="utf-8")

    return {"status": "logged", "correction_id": correction_id, "path": str(fp)}


def corrections_history(slug, since=None, campaign_id=None):
    brand_dir, err = _get_brand_dir(slug)
    if err:
        return {"error": err}

    cdir = brand_dir / "operations" / "corrections"
    if not cdir.exists():
        return {"corrections": [], "total": 0, "note": "No corrections logged yet."}

    corrections = []
    for fp in sorted(cdir.glob("*.json")):
        try:
            c = json.loads(fp.read_text(encoding="utf-8"))
            corrections.append(c)
        except json.JSONDecodeError:
            continue

    # Filter by since date
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
            corrections = [c for c in corrections
                           if datetime.fromisoformat(c.get("timestamp", "2000-01-01")) >= since_dt]
        except ValueError:
            pass

    # Filter by campaign
    if campaign_id:
        corrections = [c for c in corrections if c.get("campaign_id") == campaign_id]

    # Most recent first
    corrections.sort(key=lambda c: c.get("timestamp", ""), reverse=True)

    return {"corrections": corrections, "total": len(corrections)}


def savings_report(slug, since=None):
    brand_dir, err = _get_brand_dir(slug)
    if err:
        return {"error": err}

    hist = corrections_history(slug, since)
    if "error" in hist:
        return hist

    corrections = hist.get("corrections", [])
    total = len(corrections)

    # Estimate savings: auto corrections save more because they're faster
    auto_count = sum(1 for c in corrections if c.get("was_auto"))
    manual_count = total - auto_count

    # Heuristic savings estimate per correction type
    savings_per_type = {
        "landing-page-down": 500,
        "overspend": 300,
        "ctr-decline": 200,
        "frequency-fatigue": 150,
        "bounce-spike": 250,
        "quality-score-drop": 200,
        "deliverability-drop": 400,
        "budget-exhaustion": 350,
    }

    corrections_by_type = {}
    total_savings = 0.0
    for c in corrections:
        issue = c.get("issue", "other")
        # Normalize issue to match savings keys
        issue_key = issue.lower().replace(" ", "-").replace("_", "-")
        corrections_by_type[issue] = corrections_by_type.get(issue, 0) + 1

        # Look up savings estimate
        est = 0
        for key, val in savings_per_type.items():
            if key in issue_key:
                est = val
                break
        if est == 0:
            est = 150  # default savings estimate
        if c.get("was_auto"):
            est *= 1.5  # Auto corrections save more (faster response)
        total_savings += est

    # Calculate average response time (placeholder — real implementation would use timestamps)
    avg_response_time = "< 1 minute" if auto_count > manual_count else "< 30 minutes"

    return {
        "total_corrections": total,
        "auto_corrections": auto_count,
        "manual_corrections": manual_count,
        "estimated_savings": round(total_savings, 2),
        "corrections_by_type": corrections_by_type,
        "avg_response_time": avg_response_time,
        "period": f"since {since}" if since else "all time",
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Campaign Health Monitor — Self-healing campaign operations"
    )
    parser.add_argument("--action", required=True,
                        choices=["health-score", "detect-issues", "recommend-action",
                                 "get-guardrails", "set-guardrails", "log-correction",
                                 "corrections-history", "savings-report"],
                        help="Action to perform")
    parser.add_argument("--brand", type=_common.path_component, help="Brand slug")
    parser.add_argument("--campaign-id", dest="campaign_id", help="Campaign identifier")
    parser.add_argument("--campaign-type", dest="campaign_type",
                        choices=["awareness", "conversion", "retention", "engagement"],
                        help="Campaign type (for health-score)")
    parser.add_argument("--metrics", help="JSON campaign metrics (for health-score)")
    parser.add_argument("--campaigns", help="JSON array of campaign objects (for detect-issues)")
    parser.add_argument("--issue-type", dest="issue_type",
                        choices=["landing-page-down", "bounce-spike", "overspend",
                                 "deliverability-drop", "ctr-decline", "frequency-fatigue",
                                 "quality-score-drop", "budget-exhaustion"],
                        help="Issue type (for recommend-action)")
    parser.add_argument("--severity", choices=["low", "medium", "high", "critical"],
                        help="Issue severity (for recommend-action)")
    parser.add_argument("--guardrails", help="JSON guardrail settings (for set-guardrails)")
    parser.add_argument("--approval-id", dest="approval_id",
                        help="Approved autopilot standing approval (required to pre-authorise allowed_actions)")
    parser.add_argument("--issue", help="Issue description (for log-correction)")
    parser.add_argument("--correction-applied", dest="correction_applied",
                        help="Correction applied (for log-correction)")
    parser.add_argument("--was-auto", dest="was_auto",
                        help="Whether auto-corrected: true/false (for log-correction)")
    parser.add_argument("--expected-impact", dest="expected_impact",
                        help="Expected impact (for log-correction)")
    parser.add_argument("--since", help="Filter from date YYYY-MM-DD (for history/savings)")
    args = parser.parse_args()

    result = None

    if args.action == "health-score":
        if not args.campaign_id:
            print(json.dumps({"error": "Provide --campaign-id"}))
            sys.exit(1)
        if not args.campaign_type:
            print(json.dumps({"error": "Provide --campaign-type"}))
            sys.exit(1)
        if not args.metrics:
            print(json.dumps({"error": "Provide --metrics JSON"}))
            sys.exit(1)
        try:
            metrics = json.loads(args.metrics)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --metrics"}))
            sys.exit(1)
        result = health_score(args.campaign_id, args.campaign_type, metrics)

    elif args.action == "detect-issues":
        if not args.brand:
            print(json.dumps({"error": "Provide --brand"}))
            sys.exit(1)
        if not args.campaigns:
            print(json.dumps({"error": "Provide --campaigns JSON array"}))
            sys.exit(1)
        try:
            campaigns = json.loads(args.campaigns)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --campaigns"}))
            sys.exit(1)
        if not isinstance(campaigns, list):
            campaigns = [campaigns]
        result = detect_issues(args.brand, campaigns)

    elif args.action == "recommend-action":
        if not args.issue_type:
            print(json.dumps({"error": "Provide --issue-type"}))
            sys.exit(1)
        if not args.severity:
            print(json.dumps({"error": "Provide --severity"}))
            sys.exit(1)
        if not args.campaign_id:
            print(json.dumps({"error": "Provide --campaign-id"}))
            sys.exit(1)
        result = recommend_action(args.issue_type, args.severity, args.campaign_id)

    elif args.action == "get-guardrails":
        if not args.brand:
            print(json.dumps({"error": "Provide --brand"}))
            sys.exit(1)
        result = get_guardrails(args.brand)

    elif args.action == "set-guardrails":
        if not args.brand:
            print(json.dumps({"error": "Provide --brand"}))
            sys.exit(1)
        if not args.guardrails:
            print(json.dumps({"error": "Provide --guardrails JSON"}))
            sys.exit(1)
        try:
            guardrails = json.loads(args.guardrails)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --guardrails"}))
            sys.exit(1)
        result = set_guardrails(args.brand, guardrails, approval_id=args.approval_id)

    elif args.action == "log-correction":
        if not args.brand:
            print(json.dumps({"error": "Provide --brand"}))
            sys.exit(1)
        if not args.campaign_id:
            print(json.dumps({"error": "Provide --campaign-id"}))
            sys.exit(1)
        if not args.issue:
            print(json.dumps({"error": "Provide --issue"}))
            sys.exit(1)
        if not args.correction_applied:
            print(json.dumps({"error": "Provide --correction-applied"}))
            sys.exit(1)
        was_auto = args.was_auto and args.was_auto.lower() == "true"
        result = log_correction(args.brand, args.campaign_id, args.issue,
                                args.correction_applied, was_auto,
                                args.expected_impact or "")

    elif args.action == "corrections-history":
        if not args.brand:
            print(json.dumps({"error": "Provide --brand"}))
            sys.exit(1)
        result = corrections_history(args.brand, args.since, args.campaign_id)

    elif args.action == "savings-report":
        if not args.brand:
            print(json.dumps({"error": "Provide --brand"}))
            sys.exit(1)
        result = savings_report(args.brand, args.since)

    if result is not None:
        _common.finish(result)


if __name__ == "__main__":
    main()
