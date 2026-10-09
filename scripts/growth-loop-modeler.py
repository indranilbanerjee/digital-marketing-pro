#!/usr/bin/env python3
"""Growth Loop Modeler — Identify and model compounding growth loops.

Models viral, content, data, paid, ecosystem, and community growth loops with
compound projections, break-even analysis, and investment prioritization.
Pure calculation tool with optional brand storage.

Dependencies: none (stdlib only)

Usage:
    python growth-loop-modeler.py --action model-loop --name "Referral Loop" --type viral --input-metric users --amplification-factor 1.3 --cycle-time-days 14 --decay-factor 0.15 --initial-input 100
    python growth-loop-modeler.py --action compare-loops --loops '[{"name":"Referral","type":"viral","input_metric":"users","amplification_factor":1.3,"cycle_time_days":14,"decay_factor":0.15,"initial_input":100}]'
    python growth-loop-modeler.py --action detect-loops --data '{"metrics":[{"name":"organic_traffic","current_value":50000,"growth_rate":0.08,"description":"Monthly organic visits"}],"business_model":"saas"}'
    python growth-loop-modeler.py --action bottleneck-analysis --name "Content Loop" --stages '[{"name":"Publish","conversion_rate":1.0,"volume":20},{"name":"Index","conversion_rate":0.85,"volume":17}]'
    python growth-loop-modeler.py --action investment-plan --loops '[{"name":"Referral","type":"viral","current_amplification":1.1,"cost_to_improve":5000,"estimated_new_amplification":1.4}]'
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

BRANDS_DIR = _common.brands_root()
MONTHS_PROJECTION = 12

# Loop type metadata for detection heuristics
LOOP_TEMPLATES = {
    "saas": [
        {"type": "viral", "description": "Users invite other users via sharing, referral programs, or collaboration features", "signals": ["user_invites", "referral_signups", "viral_coefficient"]},
        {"type": "content", "description": "Content attracts traffic which generates data for more content", "signals": ["organic_traffic", "blog_posts", "seo_rankings"]},
        {"type": "data", "description": "More users generate more data, improving the product, attracting more users", "signals": ["user_data_volume", "model_accuracy", "feature_usage"]},
        {"type": "community", "description": "Community members create content and attract new members", "signals": ["community_members", "forum_posts", "user_generated_content"]},
    ],
    "ecommerce": [
        {"type": "content", "description": "Reviews and UGC drive SEO traffic and conversion", "signals": ["product_reviews", "organic_traffic", "ugc_volume"]},
        {"type": "viral", "description": "Customers share purchases and refer friends", "signals": ["social_shares", "referral_orders", "word_of_mouth"]},
        {"type": "data", "description": "Purchase data improves recommendations, increasing AOV", "signals": ["recommendation_ctr", "aov", "repeat_purchase_rate"]},
        {"type": "paid", "description": "Revenue funds ads that drive more revenue", "signals": ["roas", "ad_spend", "revenue"]},
    ],
    "marketplace": [
        {"type": "ecosystem", "description": "More sellers attract more buyers and vice versa (network effects)", "signals": ["seller_count", "buyer_count", "gmv"]},
        {"type": "content", "description": "Listings create SEO content that attracts more participants", "signals": ["listings", "organic_traffic", "search_impressions"]},
        {"type": "data", "description": "Transaction data improves matching and trust scores", "signals": ["match_rate", "transaction_volume", "trust_score"]},
        {"type": "viral", "description": "Users invite counterparts to complete transactions", "signals": ["invite_rate", "cross_side_conversion"]},
    ],
    "media": [
        {"type": "content", "description": "Content attracts audience, audience data guides better content", "signals": ["pageviews", "content_pieces", "time_on_site"]},
        {"type": "community", "description": "Engaged audience creates and shares content", "signals": ["comments", "shares", "user_submissions"]},
        {"type": "viral", "description": "Shareable content spreads to new audiences", "signals": ["social_shares", "referral_traffic", "viral_coefficient"]},
        {"type": "paid", "description": "Ad revenue funds content production", "signals": ["ad_revenue", "content_budget", "cpm"]},
    ],
    "b2b": [
        {"type": "content", "description": "Thought leadership drives inbound leads", "signals": ["organic_traffic", "lead_magnet_downloads", "webinar_signups"]},
        {"type": "data", "description": "Client data and case studies improve sales effectiveness", "signals": ["case_studies", "win_rate", "sales_cycle_days"]},
        {"type": "ecosystem", "description": "Partner integrations expand reach and stickiness", "signals": ["partner_count", "integration_usage", "co_marketing_leads"]},
        {"type": "community", "description": "Customer community drives advocacy and referrals", "signals": ["nps_score", "referral_leads", "community_members"]},
    ],
}


def _model_single_loop(name, loop_type, input_metric, amplification, cycle_days, decay, initial):
    """Model a single growth loop over 12 months, returning monthly projections."""
    cycles_per_month = 30.0 / max(cycle_days, 1)
    monthly_projections = []
    cumulative_output = 0.0
    current_input = initial

    # Recurrence: input *= (1 + amplification - decay) each cycle, so input
    # grows without bound whenever amplification > decay and decays toward
    # zero otherwise — there is no finite non-zero fixed point.
    is_sustainable = amplification > decay
    net_growth = amplification - decay
    if is_sustainable:
        projected_note = (
            "Input compounds without bound (amplification > decay); "
            "external limits will cap real-world growth."
        )
    else:
        projected_note = (
            "Input decays toward zero (amplification <= decay); "
            "loop is not self-sustaining."
        )

    break_even_month = None

    for month in range(1, MONTHS_PROJECTION + 1):
        input_start = current_input
        month_output = 0.0
        for _ in range(int(cycles_per_month)):
            new_generated = current_input * amplification
            lost = current_input * decay
            month_output += new_generated
            current_input = current_input + new_generated - lost
            current_input = max(current_input, 0)

        # Handle fractional cycle
        frac = cycles_per_month - int(cycles_per_month)
        if frac > 0:
            partial_new = current_input * amplification * frac
            partial_lost = current_input * decay * frac
            month_output += partial_new
            current_input = current_input + partial_new - partial_lost
            current_input = max(current_input, 0)

        cumulative_output += month_output

        # Break-even: when monthly output exceeds initial input (self-sustaining)
        if break_even_month is None and month_output > initial:
            break_even_month = month

        monthly_projections.append({
            "month": month,
            "input_start": round(input_start, 1),
            "output": round(month_output, 1),
            "cumulative_output": round(cumulative_output, 1),
        })

    return {
        "name": name,
        "type": loop_type,
        "input_metric": input_metric,
        "amplification_factor": amplification,
        "cycle_time_days": cycle_days,
        "decay_factor": decay,
        "initial_input": initial,
        "monthly_projections": monthly_projections,
        "is_sustainable": is_sustainable,
        "break_even_month": break_even_month,
        "net_growth_per_cycle": round(net_growth, 4),
        "projected_note": projected_note,
        "total_output_12_months": round(cumulative_output, 1),
    }


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def model_loop(name, loop_type, input_metric, amplification, cycle_days, decay, initial):
    return _model_single_loop(name, loop_type, input_metric, amplification,
                              cycle_days, decay, initial)


def compare_loops(loops):
    results = []
    for lp in loops:
        r = _model_single_loop(
            name=lp.get("name", "Unnamed"),
            loop_type=lp.get("type", "unknown"),
            input_metric=lp.get("input_metric", "units"),
            amplification=lp.get("amplification_factor", 1.0),
            cycle_days=lp.get("cycle_time_days", 30),
            decay=lp.get("decay_factor", 0.1),
            initial=lp.get("initial_input", 100),
        )
        results.append(r)

    # Rank by 12-month output
    ranked = sorted(results, key=lambda x: x["total_output_12_months"], reverse=True)

    comparison_table = []
    for i, r in enumerate(ranked):
        comparison_table.append({
            "rank": i + 1,
            "name": r["name"],
            "type": r["type"],
            "total_output_12_months": r["total_output_12_months"],
            "is_sustainable": r["is_sustainable"],
            "break_even_month": r["break_even_month"],
        })

    # Investment priority: sustainable loops first, then by output
    priority = [r["name"] for r in ranked if r["is_sustainable"]]
    priority += [r["name"] for r in ranked if not r["is_sustainable"]]

    return {
        "loops": ranked,
        "comparison_table": comparison_table,
        "recommended_investment_priority": priority,
    }


def detect_loops(data):
    metrics = data.get("metrics", [])
    business_model = data.get("business_model", "saas")
    templates = LOOP_TEMPLATES.get(business_model, LOOP_TEMPLATES["saas"])

    metric_names = {m["name"].lower().replace(" ", "_") for m in metrics}
    metric_map = {m["name"].lower().replace(" ", "_"): m for m in metrics}

    detected = []
    for tmpl in templates:
        # Check signal overlap
        matching_signals = [s for s in tmpl["signals"] if s in metric_names]
        signal_coverage = len(matching_signals) / len(tmpl["signals"]) if tmpl["signals"] else 0

        # Estimate health from growth rates of matching metrics
        growth_rates = []
        for sig in matching_signals:
            m = metric_map.get(sig)
            if m and "growth_rate" in m:
                growth_rates.append(m["growth_rate"])

        avg_growth = sum(growth_rates) / len(growth_rates) if growth_rates else 0

        if avg_growth > 0.15:
            health = "strong"
            est_amp = round(1.0 + avg_growth * 3, 2)
        elif avg_growth > 0.05:
            health = "moderate"
            est_amp = round(1.0 + avg_growth * 2, 2)
        elif signal_coverage > 0.3:
            health = "weak"
            est_amp = round(1.0 + avg_growth, 2)
        else:
            health = "potential"
            est_amp = 1.0

        # Identify bottleneck (weakest signal)
        weakest_signal = None
        weakest_growth = float("inf")
        for sig in matching_signals:
            m = metric_map.get(sig)
            if m and m.get("growth_rate", 0) < weakest_growth:
                weakest_growth = m.get("growth_rate", 0)
                weakest_signal = sig

        # Recommendations
        if health == "strong":
            rec = "Invest heavily — this loop is compounding. Focus on reducing cycle time."
        elif health == "moderate":
            rec = "Promising loop. Improve the weakest stage to accelerate compounding."
        elif health == "weak":
            rec = "Loop exists but needs activation. Address the bottleneck metric first."
        else:
            rec = "Potential loop detected but not yet active. Test with small investment."

        detected.append({
            "type": tmpl["type"],
            "description": tmpl["description"],
            "matching_signals": matching_signals,
            "signal_coverage": round(signal_coverage * 100, 1),
            "estimated_amplification": est_amp,
            "health": health,
            "bottleneck": weakest_signal,
            "recommendation": rec,
        })

    # Sort by health strength
    health_order = {"strong": 0, "moderate": 1, "weak": 2, "potential": 3}
    detected.sort(key=lambda x: health_order.get(x["health"], 4))

    return {
        "business_model": business_model,
        "metrics_analyzed": len(metrics),
        "detected_loops": detected,
    }


def bottleneck_analysis(name, stages):
    if not stages:
        return {"error": "Provide at least one stage."}

    # Find the stage with lowest conversion rate
    bottleneck = min(stages, key=lambda s: s.get("conversion_rate", 1.0))
    bottleneck_name = bottleneck.get("name", "Unknown")
    bottleneck_rate = bottleneck.get("conversion_rate", 1.0)

    # Calculate total loop throughput
    total_throughput = stages[0].get("volume", 0)
    for s in stages:
        total_throughput *= s.get("conversion_rate", 1.0)
    total_throughput = round(total_throughput, 2)

    # Calculate impact of 10% improvement at bottleneck
    improved_throughput = stages[0].get("volume", 0)
    for s in stages:
        rate = s.get("conversion_rate", 1.0)
        if s.get("name") == bottleneck_name:
            rate = min(rate * 1.10, 1.0)  # 10% improvement, capped at 100%
        improved_throughput *= rate
    improved_throughput = round(improved_throughput, 2)

    improvement_impact = round(improved_throughput - total_throughput, 2)
    pct_improvement = round((improvement_impact / total_throughput * 100), 1) if total_throughput > 0 else 0

    return {
        "loop_name": name,
        "stages": stages,
        "bottleneck_stage": bottleneck_name,
        "current_rate": bottleneck_rate,
        "current_throughput": total_throughput,
        "improved_throughput": improved_throughput,
        "improvement_impact": improvement_impact,
        "improvement_pct": pct_improvement,
        "recommendation": f"Improving '{bottleneck_name}' conversion by 10% would increase loop output by {pct_improvement}%",
    }


def investment_plan(loops):
    if not loops:
        return {"error": "Provide at least one loop."}

    evaluated = []
    for lp in loops:
        name = lp.get("name", "Unnamed")
        current_amp = lp.get("current_amplification", 1.0)
        cost = lp.get("cost_to_improve", 1)
        new_amp = lp.get("estimated_new_amplification", current_amp)

        # Model current and improved loops for 12 months
        current_result = _model_single_loop(
            name=name, loop_type=lp.get("type", "unknown"),
            input_metric="units", amplification=current_amp,
            cycle_days=lp.get("cycle_time_days", 30),
            decay=lp.get("decay_factor", 0.1),
            initial=lp.get("initial_input", 100),
        )
        improved_result = _model_single_loop(
            name=name, loop_type=lp.get("type", "unknown"),
            input_metric="units", amplification=new_amp,
            cycle_days=lp.get("cycle_time_days", 30),
            decay=lp.get("decay_factor", 0.1),
            initial=lp.get("initial_input", 100),
        )

        incremental = improved_result["total_output_12_months"] - current_result["total_output_12_months"]
        roi = round(incremental / max(cost, 1), 2)

        evaluated.append({
            "name": name,
            "type": lp.get("type", "unknown"),
            "current_amplification": current_amp,
            "estimated_new_amplification": new_amp,
            "cost_to_improve": cost,
            "current_12m_output": current_result["total_output_12_months"],
            "improved_12m_output": improved_result["total_output_12_months"],
            "expected_incremental_output": round(incremental, 1),
            "roi_per_dollar": roi,
        })

    # Sort by ROI
    evaluated.sort(key=lambda x: x["roi_per_dollar"], reverse=True)

    return {
        "investment_plan": evaluated,
        "top_priority": evaluated[0]["name"] if evaluated else None,
        "total_investment": sum(e["cost_to_improve"] for e in evaluated),
        "total_incremental_output": round(sum(e["expected_incremental_output"] for e in evaluated), 1),
    }


def _save_to_brand(slug, data, filename):
    """Optional: save results to brand's growth/ directory."""
    brand_dir = BRANDS_DIR / slug
    if not brand_dir.exists():
        return  # silently skip if brand doesn't exist
    growth_dir = brand_dir / "growth"
    growth_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    fp = growth_dir / f"{filename}-{ts}.json"
    fp.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Growth Loop Modeler — Identify and model compounding growth loops"
    )
    parser.add_argument("--action", required=True,
                        choices=["model-loop", "compare-loops", "detect-loops",
                                 "bottleneck-analysis", "investment-plan"],
                        help="Action to perform")
    parser.add_argument("--brand", type=_common.path_component, help="Brand slug (optional, for saving results)")
    parser.add_argument("--name", help="Loop name (for model-loop, bottleneck-analysis)")
    parser.add_argument("--type", dest="loop_type",
                        choices=["viral", "content", "data", "paid", "ecosystem", "community"],
                        help="Growth loop type (for model-loop)")
    parser.add_argument("--input-metric", dest="input_metric",
                        help="Name of the input metric (for model-loop)")
    parser.add_argument("--amplification-factor", dest="amplification_factor", type=float,
                        help="How many new inputs per cycle (for model-loop)")
    parser.add_argument("--cycle-time-days", dest="cycle_time_days", type=int,
                        help="Days per cycle (for model-loop)")
    parser.add_argument("--decay-factor", dest="decay_factor", type=float,
                        help="Portion lost each cycle, 0-1 (for model-loop)")
    parser.add_argument("--initial-input", dest="initial_input", type=float,
                        help="Starting value (for model-loop)")
    parser.add_argument("--loops", help="JSON array of loop definitions (for compare-loops, investment-plan)")
    parser.add_argument("--data", help="JSON business data (for detect-loops)")
    parser.add_argument("--stages", help="JSON array of stage objects (for bottleneck-analysis)")
    args = parser.parse_args()

    result = None

    if args.action == "model-loop":
        missing = []
        if not args.name:
            missing.append("--name")
        if not args.loop_type:
            missing.append("--type")
        if not args.input_metric:
            missing.append("--input-metric")
        if args.amplification_factor is None:
            missing.append("--amplification-factor")
        if args.cycle_time_days is None:
            missing.append("--cycle-time-days")
        if args.decay_factor is None:
            missing.append("--decay-factor")
        if args.initial_input is None:
            missing.append("--initial-input")
        if missing:
            print(json.dumps({"error": f"Missing required arguments: {', '.join(missing)}"}))
            sys.exit(1)
        result = model_loop(args.name, args.loop_type, args.input_metric,
                            args.amplification_factor, args.cycle_time_days,
                            args.decay_factor, args.initial_input)

    elif args.action == "compare-loops":
        if not args.loops:
            print(json.dumps({"error": "Provide --loops JSON array"}))
            sys.exit(1)
        try:
            loops = json.loads(args.loops)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --loops"}))
            sys.exit(1)
        if not isinstance(loops, list):
            loops = [loops]
        result = compare_loops(loops)

    elif args.action == "detect-loops":
        if not args.data:
            print(json.dumps({"error": "Provide --data JSON with metrics and business_model"}))
            sys.exit(1)
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --data"}))
            sys.exit(1)
        result = detect_loops(data)

    elif args.action == "bottleneck-analysis":
        if not args.name:
            print(json.dumps({"error": "Provide --name for the loop"}))
            sys.exit(1)
        if not args.stages:
            print(json.dumps({"error": "Provide --stages JSON array"}))
            sys.exit(1)
        try:
            stages = json.loads(args.stages)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --stages"}))
            sys.exit(1)
        result = bottleneck_analysis(args.name, stages)

    elif args.action == "investment-plan":
        if not args.loops:
            print(json.dumps({"error": "Provide --loops JSON array"}))
            sys.exit(1)
        try:
            loops = json.loads(args.loops)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --loops"}))
            sys.exit(1)
        if not isinstance(loops, list):
            loops = [loops]
        result = investment_plan(loops)

    if result is not None:
        # Optionally save to brand
        if args.brand:
            _save_to_brand(args.brand, result, args.action)
        _common.finish(result)


if __name__ == "__main__":
    main()
