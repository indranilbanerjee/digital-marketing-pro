#!/usr/bin/env python3
"""
audience-simulator.py
=====================
Audience Simulator — Synthetic audience for message and pricing testing.

Creates synthetic audience panels from segment data, runs simulated focus
groups, tests message variants, pricing scenarios, and positioning statements.
Tracks calibration against real-world outcomes for continuous improvement.

Storage: ~/.claude-marketing/brands/{slug}/panels/

Dependencies: none (stdlib only)

Usage:
    python audience-simulator.py --brand acme --action create-panel --panel-name "Q1 Panel" --segments '[{"name":"Enterprise","size_pct":40,...}]'
    python audience-simulator.py --brand acme --action list-panels
    python audience-simulator.py --brand acme --action focus-group --panel-id panel-20260101-120000 --stimulus "New product demo" --questions '["What is your first reaction?"]'
    python audience-simulator.py --brand acme --action test-message --panel-id panel-20260101-120000 --variants '[{"name":"A","headline":"...","body":"...","cta":"..."}]'
    python audience-simulator.py --brand acme --action test-pricing --panel-id panel-20260101-120000 --price-points '[29,49,79,99]' --product-description "SaaS analytics tool"
    python audience-simulator.py --brand acme --action test-positioning --panel-id panel-20260101-120000 --statements '[{"name":"Value","statement":"We deliver 10x ROI"}]'
    python audience-simulator.py --brand acme --action calibrate --panel-id panel-20260101-120000 --test-type message --predicted '{"winning":"A"}' --actual '{"winning":"B"}'
    python audience-simulator.py --brand acme --action panel-stats --panel-id panel-20260101-120000
"""

import argparse
import hashlib
import json
import math
import random
import sys
from datetime import datetime
from pathlib import Path
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

BRANDS_DIR = _common.brands_root()

ENGAGEMENT_WEIGHTS = {"high": 1.3, "medium": 1.0, "low": 0.7}
INCOME_MULTIPLIERS = {"low": 0.6, "medium": 1.0, "high": 1.4, "very-high": 1.8}
SENTIMENTS = ["positive", "neutral", "negative"]
TEST_TYPES = ["message", "pricing", "positioning"]


# ── Helpers ─────────────────────────────────────────────────────────────────

def _load_json(path, default=None):
    if default is None:
        default = {}
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _panels_dir(slug):
    return BRANDS_DIR / slug / "panels"


def _brand_check(slug):
    brand_dir = BRANDS_DIR / slug
    if not brand_dir.exists():
        return {"error": f"Brand '{slug}' not found. Run /digital-marketing-pro:brand-setup first."}
    return None


def _deterministic_seed(panel_id, *args):
    """Create a deterministic seed from panel ID and other factors."""
    raw = f"{panel_id}:{'|'.join(str(a) for a in args)}"
    return int(hashlib.md5(raw.encode()).hexdigest()[:8], 16)


def _score_with_profile(base, segment, factor_key, panel_id, variant_idx=0):
    """Generate a deterministic score influenced by segment profile."""
    seed = _deterministic_seed(panel_id, segment["name"], factor_key, variant_idx)
    rng = random.Random(seed)

    engagement = segment.get("behavior", {}).get("engagement_level", "medium")
    weight = ENGAGEMENT_WEIGHTS.get(engagement, 1.0)

    # Profile influence: psychographic alignment adds up to 2 points
    values = segment.get("psychographics", {}).get("values", [])
    motivations = segment.get("psychographics", {}).get("motivations", [])
    profile_bonus = min(2.0, (len(values) + len(motivations)) * 0.2)

    score = base * weight + profile_bonus + rng.uniform(-1.0, 1.0)
    return round(max(1.0, min(10.0, score)), 1)


def _load_panel(slug, panel_id):
    """Load a panel by ID. Returns (panel_dict, error_dict_or_None)."""
    pdir = _panels_dir(slug)
    panel_path = pdir / panel_id / "panel.json"
    panel = _load_json(panel_path)
    if not panel or "segments" not in panel:
        return None, {"error": f"Panel '{panel_id}' not found. Run create-panel first."}
    return panel, None


# ── Actions ─────────────────────────────────────────────────────────────────

def create_panel(slug, panel_name, segments_str):
    err = _brand_check(slug)
    if err:
        return err

    try:
        segments = json.loads(segments_str) if isinstance(segments_str, str) else segments_str
    except json.JSONDecodeError:
        return {"error": "Invalid JSON in --segments"}

    if not isinstance(segments, list) or not segments:
        return {"error": "Provide a non-empty array of segments"}

    # Validate size_pct sums to 100
    total_pct = sum(s.get("size_pct", 0) for s in segments)
    if abs(total_pct - 100.0) > 0.5:
        return {"error": f"Segment size_pct values sum to {total_pct}, must equal 100."}

    # Validate required fields
    for i, seg in enumerate(segments):
        if not seg.get("name"):
            return {"error": f"Segment {i} missing 'name'"}
        if "size_pct" not in seg:
            return {"error": f"Segment '{seg['name']}' missing 'size_pct'"}

    panel_id = f"panel-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    # Count total characteristics
    total_chars = 0
    for seg in segments:
        total_chars += len(seg.get("demographics", {}))
        psycho = seg.get("psychographics", {})
        total_chars += len(psycho.get("values", [])) + len(psycho.get("motivations", [])) + len(psycho.get("objections", []))
        behavior = seg.get("behavior", {})
        total_chars += len(behavior.get("preferred_channels", [])) + (3 if behavior else 0)
        total_chars += len(seg.get("pain_points", [])) + len(seg.get("goals", []))

    panel = {
        "panel_id": panel_id,
        "panel_name": panel_name,
        "segments": segments,
        "segments_count": len(segments),
        "total_characteristics": total_chars,
        "created_at": datetime.now().isoformat(),
        "tests_run": 0,
        "calibrations": [],
    }

    pdir = _panels_dir(slug) / panel_id
    _save_json(pdir / "panel.json", panel)

    return {"panel_id": panel_id, "segments_count": len(segments),
            "total_characteristics": total_chars}


def list_panels(slug):
    err = _brand_check(slug)
    if err:
        return err

    pdir = _panels_dir(slug)
    if not pdir.exists():
        return {"panels": [], "total": 0}

    panels = []
    for d in sorted(pdir.iterdir()):
        if d.is_dir():
            panel = _load_json(d / "panel.json")
            if panel and "panel_id" in panel:
                panels.append({
                    "panel_id": panel["panel_id"],
                    "panel_name": panel.get("panel_name", ""),
                    "segments_count": panel.get("segments_count", 0),
                    "tests_run": panel.get("tests_run", 0),
                    "created_at": panel.get("created_at"),
                })

    return {"panels": panels, "total": len(panels)}


def focus_group(slug, panel_id, stimulus, questions_str):
    err = _brand_check(slug)
    if err:
        return err

    panel, perr = _load_panel(slug, panel_id)
    if perr:
        return perr

    try:
        questions = json.loads(questions_str) if isinstance(questions_str, str) else questions_str
    except json.JSONDecodeError:
        return {"error": "Invalid JSON in --questions"}

    if not isinstance(questions, list) or not questions:
        return {"error": "Provide a non-empty array of questions"}

    responses_by_segment = []
    all_sentiments = []

    for seg in panel["segments"]:
        seg_responses = []
        for qi, question in enumerate(questions):
            seed = _deterministic_seed(panel_id, seg["name"], question)
            rng = random.Random(seed)

            # Determine sentiment based on segment profile
            pain_points = seg.get("pain_points", [])
            goals = seg.get("goals", [])
            motivations = seg.get("psychographics", {}).get("motivations", [])
            objections = seg.get("psychographics", {}).get("objections", [])

            # Positive bias from goals/motivations, negative from pain_points/objections
            pos_weight = len(goals) + len(motivations)
            neg_weight = len(pain_points) + len(objections)
            total_w = pos_weight + neg_weight + 1
            pos_prob = (pos_weight + 1) / (total_w + 1)

            roll = rng.random()
            if roll < pos_prob * 0.6:
                sentiment = "positive"
            elif roll < pos_prob * 0.6 + 0.3:
                sentiment = "neutral"
            else:
                sentiment = "negative"

            engagement = seg.get("behavior", {}).get("engagement_level", "medium")
            confidence = round(ENGAGEMENT_WEIGHTS.get(engagement, 1.0) * rng.uniform(0.5, 0.85), 2)
            confidence = min(0.95, max(0.3, confidence))

            # Build predicted response based on profile
            values = seg.get("psychographics", {}).get("values", [])
            val_str = f" Their core values ({', '.join(values[:2])}) shape this view." if values else ""
            obj_str = f" Key concern: {objections[0]}." if objections else ""

            predicted = (f"As a {seg['name']} segment member, "
                         f"reaction to '{stimulus}' is {sentiment}.{val_str}{obj_str}")

            seg_responses.append({
                "question": question,
                "predicted_response": predicted,
                "sentiment": sentiment,
                "confidence": confidence,
            })
            all_sentiments.append(sentiment)

        responses_by_segment.append({
            "segment_name": seg["name"],
            "responses": seg_responses,
        })

    # Consensus themes
    pos_count = all_sentiments.count("positive")
    neg_count = all_sentiments.count("negative")
    neu_count = all_sentiments.count("neutral")
    total = len(all_sentiments) or 1

    consensus = []
    if pos_count / total > 0.6:
        consensus.append("Strong positive reception across segments")
    if neg_count / total > 0.4:
        consensus.append("Significant resistance detected")
    if neu_count / total > 0.5:
        consensus.append("Lukewarm response — may need stronger differentiation")

    # Divergence points: questions where segments disagree
    divergence = []
    for qi, question in enumerate(questions):
        q_sentiments = []
        for rbs in responses_by_segment:
            if qi < len(rbs["responses"]):
                q_sentiments.append(rbs["responses"][qi]["sentiment"])
        if len(set(q_sentiments)) > 1:
            divergence.append({"question": question,
                               "sentiments": dict(zip([r["segment_name"] for r in responses_by_segment], q_sentiments))})

    overall = "positive" if pos_count > neg_count else ("negative" if neg_count > pos_count else "neutral")

    # Increment tests_run
    panel["tests_run"] = panel.get("tests_run", 0) + 1
    _save_json(_panels_dir(slug) / panel_id / "panel.json", panel)

    return {
        "responses_by_segment": responses_by_segment,
        "consensus_themes": consensus if consensus else ["Mixed reactions — no clear consensus"],
        "divergence_points": divergence,
        "overall_sentiment": overall,
    }


def test_message(slug, panel_id, variants_str):
    err = _brand_check(slug)
    if err:
        return err

    panel, perr = _load_panel(slug, panel_id)
    if perr:
        return perr

    try:
        variants = json.loads(variants_str) if isinstance(variants_str, str) else variants_str
    except json.JSONDecodeError:
        return {"error": "Invalid JSON in --variants"}

    if not isinstance(variants, list) or not variants:
        return {"error": "Provide a non-empty array of message variants"}

    scoring_dims = ["resonance", "clarity", "credibility", "urgency", "differentiation"]
    variant_scores = []
    per_segment = []
    segment_winners = {}

    for vi, variant in enumerate(variants):
        v_name = variant.get("name", f"Variant {vi + 1}")
        total_score = 0
        seg_scores = []

        for seg in panel["segments"]:
            dim_scores = {}
            for dim in scoring_dims:
                base = 5.5
                # Adjust base by variant properties
                if dim == "clarity" and len(variant.get("headline", "")) < 50:
                    base += 1
                if dim == "urgency" and variant.get("cta", ""):
                    base += 0.5
                if dim == "credibility":
                    objections = seg.get("psychographics", {}).get("objections", [])
                    base -= len(objections) * 0.3
                if dim == "resonance":
                    goals = seg.get("goals", [])
                    base += len(goals) * 0.2
                if dim == "differentiation":
                    base += 0.5  # Slight boost for having a distinct variant

                score = _score_with_profile(base, seg, dim, panel_id, vi)
                dim_scores[dim] = score

            seg_total = sum(dim_scores.values())
            weighted_total = round(seg_total * seg.get("size_pct", 0) / 100, 2)
            total_score += weighted_total

            seg_scores.append({
                "segment_name": seg["name"],
                "scores": dim_scores,
                "segment_total": round(seg_total, 1),
            })

            # Track segment winner
            prev = segment_winners.get(seg["name"], (None, 0))
            if seg_total > prev[1]:
                segment_winners[seg["name"]] = (v_name, seg_total)

        per_segment.append({"variant": v_name, "segment_scores": seg_scores})
        variant_scores.append({"variant": v_name, "total_score": round(total_score, 2),
                                "headline": variant.get("headline", ""),
                                "cta": variant.get("cta", "")})

    variant_scores.sort(key=lambda v: v["total_score"], reverse=True)
    winning = variant_scores[0]["variant"] if variant_scores else None

    seg_win_map = {seg: winner for seg, (winner, _) in segment_winners.items()}

    recs = []
    if winning:
        recs.append(f"Lead with '{winning}' as the primary variant.")
    if len(set(seg_win_map.values())) > 1:
        recs.append("Consider segment-specific messaging — different segments prefer different variants.")
    recs.append("A/B test the top 2 variants with real traffic to validate synthetic predictions.")

    # Increment tests_run
    panel["tests_run"] = panel.get("tests_run", 0) + 1
    _save_json(_panels_dir(slug) / panel_id / "panel.json", panel)

    return {
        "variant_scores": variant_scores,
        "per_segment_breakdown": per_segment,
        "winning_variant": winning,
        "segment_specific_winners": seg_win_map,
        "recommendations": recs,
    }


def test_pricing(slug, panel_id, price_points_str, product_description):
    err = _brand_check(slug)
    if err:
        return err

    panel, perr = _load_panel(slug, panel_id)
    if perr:
        return perr

    try:
        price_points = json.loads(price_points_str) if isinstance(price_points_str, str) else price_points_str
    except json.JSONDecodeError:
        return {"error": "Invalid JSON in --price-points"}

    if not isinstance(price_points, list) or not price_points:
        return {"error": "Provide a non-empty array of price points"}

    price_points = sorted([float(p) for p in price_points])
    mid = price_points[len(price_points) // 2]

    per_segment = []
    all_too_cheap = []
    all_good_deal = []
    all_expensive = []
    all_too_expensive = []

    for seg in panel["segments"]:
        income = seg.get("demographics", {}).get("income_bracket", "medium")
        income_mult = INCOME_MULTIPLIERS.get(income, 1.0)

        aov = seg.get("behavior", {}).get("avg_order_value", mid)
        if isinstance(aov, str):
            try:
                aov = float(aov)
            except ValueError:
                aov = mid

        freq = seg.get("behavior", {}).get("purchase_frequency", "monthly")
        freq_mult = 1.0
        if freq in ("weekly", "daily"):
            freq_mult = 0.8  # Price-sensitive frequent buyers
        elif freq in ("quarterly", "annually"):
            freq_mult = 1.2  # Less price-sensitive infrequent buyers

        base_ref = aov * income_mult * freq_mult
        seed = _deterministic_seed(panel_id, seg["name"], "pricing")
        rng = random.Random(seed)
        noise = rng.uniform(0.9, 1.1)

        too_cheap = round(base_ref * 0.3 * noise, 2)
        good_deal = round(base_ref * 0.6 * noise, 2)
        expensive = round(base_ref * 1.2 * noise, 2)
        too_expensive = round(base_ref * 1.8 * noise, 2)

        all_too_cheap.append(too_cheap)
        all_good_deal.append(good_deal)
        all_expensive.append(expensive)
        all_too_expensive.append(too_expensive)

        per_segment.append({
            "segment_name": seg["name"],
            "size_pct": seg.get("size_pct", 0),
            "too_cheap": too_cheap,
            "good_deal": good_deal,
            "expensive": expensive,
            "too_expensive": too_expensive,
            "income_bracket": income,
        })

    # Weighted averages
    weights = [seg.get("size_pct", 0) / 100 for seg in panel["segments"]]
    w_good = sum(g * w for g, w in zip(all_good_deal, weights))
    w_expensive = sum(e * w for e, w in zip(all_expensive, weights))

    optimal = round((w_good + w_expensive) / 2, 2)
    acceptable_low = round(sum(tc * w for tc, w in zip(all_too_cheap, weights)), 2)
    acceptable_high = round(sum(te * w for te, w in zip(all_too_expensive, weights)), 2)

    # Revenue vs volume: higher price = more revenue per unit, lower price = more volume
    viable = [p for p in price_points if acceptable_low <= p <= acceptable_high]
    revenue_max = max(viable) if viable else price_points[-1]
    volume_max = min(viable) if viable else price_points[0]

    # Increment tests_run
    panel["tests_run"] = panel.get("tests_run", 0) + 1
    _save_json(_panels_dir(slug) / panel_id / "panel.json", panel)

    return {
        "product_description": product_description,
        "price_points_tested": price_points,
        "optimal_price_point": optimal,
        "acceptable_range": {"low": acceptable_low, "high": acceptable_high},
        "per_segment_sensitivity": per_segment,
        "revenue_maximizing_price": revenue_max,
        "volume_maximizing_price": volume_max,
    }


def test_positioning(slug, panel_id, statements_str):
    err = _brand_check(slug)
    if err:
        return err

    panel, perr = _load_panel(slug, panel_id)
    if perr:
        return perr

    try:
        statements = json.loads(statements_str) if isinstance(statements_str, str) else statements_str
    except json.JSONDecodeError:
        return {"error": "Invalid JSON in --statements"}

    if not isinstance(statements, list) or not statements:
        return {"error": "Provide a non-empty array of positioning statements"}

    scoring_dims = ["resonance", "believability", "differentiation",
                    "emotional_appeal", "memorability"]
    statement_scores = []
    per_segment = []
    objection_patterns = []
    segment_winners = {}

    for si, stmt in enumerate(statements):
        s_name = stmt.get("name", f"Statement {si + 1}")
        s_text = stmt.get("statement", "")
        total_score = 0
        seg_scores = []

        for seg in panel["segments"]:
            dim_scores = {}
            for dim in scoring_dims:
                base = 5.0
                if dim == "resonance":
                    goals = seg.get("goals", [])
                    base += min(2, len(goals) * 0.3)
                if dim == "believability":
                    objections = seg.get("psychographics", {}).get("objections", [])
                    base -= len(objections) * 0.4
                if dim == "emotional_appeal":
                    values = seg.get("psychographics", {}).get("values", [])
                    base += min(2, len(values) * 0.3)
                if dim == "memorability":
                    # Shorter statements are more memorable
                    word_count = len(s_text.split())
                    if word_count < 15:
                        base += 1.5
                    elif word_count > 30:
                        base -= 1.0
                if dim == "differentiation":
                    base += 0.5

                score = _score_with_profile(base, seg, dim, panel_id, si)
                dim_scores[dim] = score

            seg_total = sum(dim_scores.values())
            weighted = round(seg_total * seg.get("size_pct", 0) / 100, 2)
            total_score += weighted

            seg_scores.append({
                "segment_name": seg["name"],
                "scores": dim_scores,
                "segment_total": round(seg_total, 1),
            })

            # Collect objection patterns
            if dim_scores.get("believability", 10) < 5:
                objections = seg.get("psychographics", {}).get("objections", [])
                for obj in objections:
                    objection_patterns.append({
                        "segment": seg["name"],
                        "statement": s_name,
                        "objection": obj,
                    })

            prev = segment_winners.get(seg["name"], (None, 0))
            if seg_total > prev[1]:
                segment_winners[seg["name"]] = (s_name, seg_total)

        per_segment.append({"statement": s_name, "segment_scores": seg_scores})
        statement_scores.append({"statement": s_name, "text": s_text,
                                  "total_score": round(total_score, 2)})

    statement_scores.sort(key=lambda s: s["total_score"], reverse=True)
    winning = statement_scores[0]["statement"] if statement_scores else None

    # Deduplicate objection patterns
    seen = set()
    unique_objections = []
    for op in objection_patterns:
        key = f"{op['segment']}:{op['objection']}"
        if key not in seen:
            seen.add(key)
            unique_objections.append(op)

    recs = []
    if winning:
        recs.append(f"Lead with '{winning}' as the primary positioning statement.")
    if unique_objections:
        recs.append(f"Address {len(unique_objections)} objection pattern(s) in supporting content.")
    recs.append("Validate with real customer interviews before full rollout.")

    # Increment tests_run
    panel["tests_run"] = panel.get("tests_run", 0) + 1
    _save_json(_panels_dir(slug) / panel_id / "panel.json", panel)

    return {
        "statement_scores": statement_scores,
        "per_segment_breakdown": per_segment,
        "winning_statement": winning,
        "objection_patterns": unique_objections,
        "recommendation": recs,
    }


def calibrate(slug, panel_id, test_type, predicted_str, actual_str):
    err = _brand_check(slug)
    if err:
        return err

    panel, perr = _load_panel(slug, panel_id)
    if perr:
        return perr

    try:
        predicted = json.loads(predicted_str) if isinstance(predicted_str, str) else predicted_str
        actual = json.loads(actual_str) if isinstance(actual_str, str) else actual_str
    except json.JSONDecodeError:
        return {"error": "Invalid JSON in --predicted or --actual"}

    # Compare predicted vs actual — compute accuracy
    matches = 0
    total_fields = 0
    per_segment_acc = {}

    for key in set(list(predicted.keys()) + list(actual.keys())):
        total_fields += 1
        p_val = predicted.get(key)
        a_val = actual.get(key)

        if isinstance(p_val, (int, float)) and isinstance(a_val, (int, float)):
            # Numeric: accuracy = 1 - (|diff| / max(|p|, |a|, 1))
            diff = abs(p_val - a_val)
            ref = max(abs(p_val), abs(a_val), 1)
            acc = round(1 - diff / ref, 3)
            matches += max(0, acc)
            per_segment_acc[key] = acc
        elif p_val == a_val:
            matches += 1
            per_segment_acc[key] = 1.0
        else:
            per_segment_acc[key] = 0.0

    accuracy = round(matches / total_fields, 3) if total_fields > 0 else 0.0

    if accuracy >= 0.7:
        direction = "well-calibrated"
    else:
        # Signed mean error over numeric fields: positive => over-predicted
        signed_errors = [
            p_v - a_v
            for p_v, a_v in (
                (predicted.get(k), actual.get(k))
                for k in set(list(predicted.keys()) + list(actual.keys()))
            )
            if isinstance(p_v, (int, float)) and isinstance(a_v, (int, float))
        ]
        if not signed_errors:
            direction = "poorly-calibrated"
        elif sum(signed_errors) / len(signed_errors) > 0:
            direction = "over-predicted"
        else:
            direction = "under-predicted"

    calibration_record = {
        "test_type": test_type,
        "predicted": predicted,
        "actual": actual,
        "accuracy_score": accuracy,
        "calibration_direction": direction,
        "per_segment_accuracy": per_segment_acc,
        "calibrated_at": datetime.now().isoformat(),
    }

    # Save calibration to panel
    calibrations = panel.get("calibrations", [])
    calibrations.append(calibration_record)
    panel["calibrations"] = calibrations
    _save_json(_panels_dir(slug) / panel_id / "panel.json", panel)

    return {
        "accuracy_score": accuracy,
        "calibration_direction": direction,
        "per_segment_accuracy": per_segment_acc,
    }


def panel_stats(slug, panel_id):
    err = _brand_check(slug)
    if err:
        return err

    panel, perr = _load_panel(slug, panel_id)
    if perr:
        return perr

    calibrations = panel.get("calibrations", [])
    cal_scores = [c["accuracy_score"] for c in calibrations if "accuracy_score" in c]
    avg_cal = round(sum(cal_scores) / len(cal_scores), 3) if cal_scores else None

    # Per-segment calibration summary
    seg_accuracy = {}
    for cal in calibrations:
        for seg, acc in cal.get("per_segment_accuracy", {}).items():
            seg_accuracy.setdefault(seg, []).append(acc)

    seg_avg = {seg: round(sum(accs) / len(accs), 3) for seg, accs in seg_accuracy.items()}
    best_seg = max(seg_avg, key=seg_avg.get) if seg_avg else None
    worst_seg = min(seg_avg, key=seg_avg.get) if seg_avg else None

    return {
        "panel_id": panel_id,
        "panel_name": panel.get("panel_name", ""),
        "segments_count": panel.get("segments_count", 0),
        "total_tests_run": panel.get("tests_run", 0),
        "calibration_score": avg_cal,
        "calibration_count": len(cal_scores),
        "best_calibrated_segment": best_seg,
        "worst_calibrated_segment": worst_seg,
        "created_at": panel.get("created_at"),
    }


# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Audience Simulator — Synthetic audience for message and pricing testing for Digital Marketing Pro"
    )
    parser.add_argument("--brand", type=_common.path_component, required=True, help="Brand slug")
    parser.add_argument(
        "--action", required=True,
        choices=["create-panel", "list-panels", "focus-group", "test-message",
                 "test-pricing", "test-positioning", "calibrate", "panel-stats"],
        help="Action to perform",
    )
    parser.add_argument("--panel-name", help="Panel name (create-panel)")
    parser.add_argument("--segments", help="JSON array of segment objects (create-panel)")
    parser.add_argument("--panel-id", help="Panel ID")
    parser.add_argument("--stimulus", help="Description of what you are presenting (focus-group)")
    parser.add_argument("--questions", help="JSON array of question strings (focus-group)")
    parser.add_argument("--variants", help="JSON array of message variants (test-message)")
    parser.add_argument("--price-points", help="JSON array of price points (test-pricing)")
    parser.add_argument("--product-description", help="Product description (test-pricing)")
    parser.add_argument("--statements", help="JSON array of positioning statements (test-positioning)")
    parser.add_argument("--test-type", choices=TEST_TYPES,
                        help="Test type for calibration (calibrate)")
    parser.add_argument("--predicted", help="JSON of predicted outcomes (calibrate)")
    parser.add_argument("--actual", help="JSON of actual outcomes (calibrate)")

    args = parser.parse_args()

    if args.action == "create-panel":
        if not args.panel_name or not args.segments:
            print(json.dumps({"error": "Provide --panel-name and --segments"}))
            sys.exit(1)
        result = create_panel(args.brand, args.panel_name, args.segments)

    elif args.action == "list-panels":
        result = list_panels(args.brand)

    elif args.action == "focus-group":
        if not args.panel_id or not args.stimulus or not args.questions:
            print(json.dumps({"error": "Provide --panel-id, --stimulus, and --questions"}))
            sys.exit(1)
        result = focus_group(args.brand, args.panel_id, args.stimulus, args.questions)

    elif args.action == "test-message":
        if not args.panel_id or not args.variants:
            print(json.dumps({"error": "Provide --panel-id and --variants"}))
            sys.exit(1)
        result = test_message(args.brand, args.panel_id, args.variants)

    elif args.action == "test-pricing":
        if not args.panel_id or not args.price_points or not args.product_description:
            print(json.dumps({"error": "Provide --panel-id, --price-points, and --product-description"}))
            sys.exit(1)
        result = test_pricing(args.brand, args.panel_id, args.price_points, args.product_description)

    elif args.action == "test-positioning":
        if not args.panel_id or not args.statements:
            print(json.dumps({"error": "Provide --panel-id and --statements"}))
            sys.exit(1)
        result = test_positioning(args.brand, args.panel_id, args.statements)

    elif args.action == "calibrate":
        if not args.panel_id or not args.test_type or not args.predicted or not args.actual:
            print(json.dumps({"error": "Provide --panel-id, --test-type, --predicted, and --actual"}))
            sys.exit(1)
        result = calibrate(args.brand, args.panel_id, args.test_type, args.predicted, args.actual)

    elif args.action == "panel-stats":
        if not args.panel_id:
            print(json.dumps({"error": "Provide --panel-id"}))
            sys.exit(1)
        result = panel_stats(args.brand, args.panel_id)

    _common.finish(result)


if __name__ == "__main__":
    main()
