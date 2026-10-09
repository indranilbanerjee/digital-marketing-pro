#!/usr/bin/env python3
"""Revenue Simulator — Monte Carlo simulation of marketing decisions.

Runs probabilistic revenue simulations across marketing scenarios using
normal distributions for ROI, optional saturation curves, and multi-channel
interaction bonuses. Uses stdlib random module (not numpy) for zero-dep
portability.

Dependencies: none (stdlib only)

Usage:
    python revenue-simulator.py --action simulate --scenarios '[{"name":"Aggressive","channels":[{"name":"Google Ads","budget":10000,"roi_mean":3.2,"roi_std":0.8}],"months":6}]'
    python revenue-simulator.py --action simulate --scenarios '[...]' --target 500000
    python revenue-simulator.py --action what-if --current '{"channels":[{"name":"Google Ads","budget":5000,"roi_mean":3.0}]}' --scenarios '[{"channels":[{"name":"Google Ads","budget":8000,"roi_mean":3.0}]}]'
    python revenue-simulator.py --action sensitivity --base-scenario '{"channels":[{"name":"PPC","budget":10000,"roi_mean":3.0,"roi_std":0.5}],"months":6}' --variable budget --range '[5000,20000,6]'
    python revenue-simulator.py --action channel-interaction --data '{"channels":[{"name":"PPC","solo_performance":100,"combined_performance":120}]}'
    python revenue-simulator.py --action saturation-check --channel "Google Ads" --current-budget 15000 --performance-history '[{"budget":5000,"revenue":15000},{"budget":10000,"revenue":27000},{"budget":15000,"revenue":35000}]'
"""

import argparse
import json
import math
import random
import sys
from pathlib import Path
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

NUM_SIMULATIONS = 10000


def _saturation_curve(budget, saturation_point):
    """Diminishing returns: 1 - e^(-3 * budget / saturation_point).
    Returns a multiplier between 0 and 1."""
    if saturation_point <= 0:
        return 1.0
    return 1.0 - math.exp(-3.0 * budget / saturation_point)


def _percentile(sorted_vals, pct):
    """Return the pct-th percentile from a sorted list."""
    if not sorted_vals:
        return 0.0
    idx = (pct / 100.0) * (len(sorted_vals) - 1)
    lower = int(math.floor(idx))
    upper = min(lower + 1, len(sorted_vals) - 1)
    frac = idx - lower
    return sorted_vals[lower] * (1 - frac) + sorted_vals[upper] * frac


def _run_simulation(channels, months, interaction_bonus, seed):
    """Run NUM_SIMULATIONS Monte Carlo trials and return revenue distribution."""
    rng = random.Random(seed)
    results = []

    for _ in range(NUM_SIMULATIONS):
        total_revenue = 0.0
        for _m in range(months):
            month_revenue = 0.0
            for ch in channels:
                roi = rng.gauss(ch["roi_mean"], ch.get("roi_std", 0.0))
                roi = max(roi, 0.0)  # ROI can't go negative
                raw_revenue = ch["budget"] * roi

                # Apply saturation curve if specified
                sat = ch.get("saturation_point")
                if sat and sat > 0:
                    raw_revenue *= _saturation_curve(ch["budget"], sat)

                month_revenue += raw_revenue

            # Multi-channel interaction bonus
            if len(channels) > 1 and interaction_bonus > 0:
                month_revenue *= (1.0 + interaction_bonus)

            total_revenue += month_revenue
        results.append(round(total_revenue, 2))

    results.sort()
    return results


def _channel_contributions(channels, months, interaction_bonus, seed):
    """Estimate each channel's share of total revenue."""
    rng = random.Random(seed)
    contrib = {ch["name"]: 0.0 for ch in channels}
    runs = 1000  # lighter run for breakdown

    for _ in range(runs):
        for _m in range(months):
            for ch in channels:
                roi = rng.gauss(ch["roi_mean"], ch.get("roi_std", 0.0))
                roi = max(roi, 0.0)
                rev = ch["budget"] * roi
                sat = ch.get("saturation_point")
                if sat and sat > 0:
                    rev *= _saturation_curve(ch["budget"], sat)
                contrib[ch["name"]] += rev

    total = sum(contrib.values())
    if total > 0:
        return [{"channel": name, "share": round(val / total * 100, 1),
                 "estimated_revenue": round(val / runs, 2)}
                for name, val in contrib.items()]
    return [{"channel": name, "share": 0, "estimated_revenue": 0} for name in contrib]


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def simulate(scenarios, target, seed):
    results = []
    for sc in scenarios:
        name = sc.get("name", "Unnamed")
        channels = sc.get("channels", [])
        months = sc.get("months", 1)
        interaction_bonus = sc.get("interaction_bonus", 0.0)

        if not channels:
            results.append({"name": name, "error": "No channels defined."})
            continue

        dist = _run_simulation(channels, months, interaction_bonus, seed)
        entry = {
            "name": name,
            "months": months,
            "total_budget": sum(ch["budget"] for ch in channels) * months,
            "expected_revenue": round(sum(dist) / len(dist), 2),
            "p10": round(_percentile(dist, 10), 2),
            "p25": round(_percentile(dist, 25), 2),
            "p50": round(_percentile(dist, 50), 2),
            "p75": round(_percentile(dist, 75), 2),
            "p90": round(_percentile(dist, 90), 2),
            "channel_contributions": _channel_contributions(
                channels, months, interaction_bonus, seed),
        }
        if target is not None:
            hits = sum(1 for v in dist if v >= target)
            entry["probability_of_target"] = round(hits / len(dist) * 100, 1)
            entry["target"] = target

        results.append(entry)
    return {"scenarios": results, "simulations_per_scenario": NUM_SIMULATIONS, "seed": seed}


def what_if(current, alternatives, seed):
    # Simulate current
    curr_channels = current.get("channels", [])
    curr_months = current.get("months", 1)
    curr_bonus = current.get("interaction_bonus", 0.0)
    curr_dist = _run_simulation(curr_channels, curr_months, curr_bonus, seed)
    curr_mean = sum(curr_dist) / len(curr_dist) if curr_dist else 0

    comparisons = []
    for i, alt in enumerate(alternatives):
        alt_channels = alt.get("channels", curr_channels)
        alt_months = alt.get("months", curr_months)
        alt_bonus = alt.get("interaction_bonus", curr_bonus)
        alt_dist = _run_simulation(alt_channels, alt_months, alt_bonus, seed)
        alt_mean = sum(alt_dist) / len(alt_dist) if alt_dist else 0
        delta = alt_mean - curr_mean
        pct_change = round(delta / curr_mean * 100, 1) if curr_mean else 0

        comparisons.append({
            "scenario": alt.get("name", f"Alternative {i + 1}"),
            "expected_revenue": round(alt_mean, 2),
            "delta_vs_current": round(delta, 2),
            "percent_change": pct_change,
            "total_budget": sum(ch["budget"] for ch in alt_channels) * alt_months,
        })

    return {
        "current_expected_revenue": round(curr_mean, 2),
        "current_total_budget": sum(ch["budget"] for ch in curr_channels) * curr_months,
        "comparisons": comparisons,
    }


def sensitivity(base_scenario, variable, var_range, seed):
    channels = base_scenario.get("channels", [])
    months = base_scenario.get("months", 1)
    bonus = base_scenario.get("interaction_bonus", 0.0)
    min_val, max_val, steps = var_range[0], var_range[1], int(var_range[2])
    step_size = (max_val - min_val) / max(steps - 1, 1)

    data_points = []
    for i in range(steps):
        val = min_val + step_size * i
        modified = [dict(ch) for ch in channels]

        if variable == "budget":
            # Scale all budgets proportionally
            base_total = sum(ch["budget"] for ch in channels)
            scale = val / base_total if base_total > 0 else 1
            for ch in modified:
                ch["budget"] = ch["budget"] * scale
        elif variable == "roi":
            for ch in modified:
                ch["roi_mean"] = val
        elif variable == "saturation":
            for ch in modified:
                ch["saturation_point"] = val

        dist = _run_simulation(modified, months, bonus, seed)
        mean_rev = sum(dist) / len(dist) if dist else 0
        data_points.append({
            "variable_value": round(val, 2),
            "expected_revenue": round(mean_rev, 2),
            "p25": round(_percentile(dist, 25), 2),
            "p75": round(_percentile(dist, 75), 2),
        })

    return {"variable": variable, "range": var_range, "data_points": data_points}


def channel_interaction(data):
    channels = data.get("channels", [])
    if len(channels) < 2:
        return {"error": "Need at least 2 channels for interaction analysis."}

    matrix = []
    for ch in channels:
        solo = ch.get("solo_performance", 0)
        combined = ch.get("combined_performance", 0)
        lift = round((combined - solo) / solo * 100, 1) if solo > 0 else 0
        matrix.append({
            "channel": ch["name"],
            "solo_performance": solo,
            "combined_performance": combined,
            "interaction_lift_pct": lift,
            "complementarity_score": round(min(lift / 50.0, 1.0), 2),
        })

    avg_lift = sum(m["interaction_lift_pct"] for m in matrix) / len(matrix)
    return {
        "interaction_matrix": matrix,
        "average_lift_pct": round(avg_lift, 1),
        "recommended_interaction_bonus": round(min(avg_lift / 100 * 0.5, 0.2), 3),
    }


def saturation_check(channel_name, current_budget, history):
    if len(history) < 2:
        return {"error": "Need at least 2 data points for saturation analysis."}

    history.sort(key=lambda h: h["budget"])
    budgets = [h["budget"] for h in history]
    revenues = [h["revenue"] for h in history]

    # Estimate saturation point using marginal returns
    marginals = []
    for i in range(1, len(budgets)):
        db = budgets[i] - budgets[i - 1]
        dr = revenues[i] - revenues[i - 1]
        if db > 0:
            marginals.append({"budget": budgets[i], "marginal_roi": round(dr / db, 4)})

    # Simple saturation estimate: extrapolate where marginal ROI hits 0.5x of initial
    if marginals and marginals[0]["marginal_roi"] > 0:
        initial_mroi = marginals[0]["marginal_roi"]
        last_mroi = marginals[-1]["marginal_roi"]
        decay_rate = (initial_mroi - last_mroi) / (budgets[-1] - budgets[0]) if budgets[-1] != budgets[0] else 0
        if decay_rate > 0:
            est_saturation = budgets[0] + initial_mroi / decay_rate
        else:
            est_saturation = current_budget * 3  # No decay detected — far from saturation
    else:
        est_saturation = current_budget * 3

    position_pct = round(current_budget / est_saturation * 100, 1) if est_saturation > 0 else 100
    current_mroi = marginals[-1]["marginal_roi"] if marginals else 0

    return {
        "channel": channel_name,
        "current_budget": current_budget,
        "estimated_saturation_point": round(est_saturation, 2),
        "position_on_curve_pct": min(position_pct, 100),
        "marginal_roi_at_current_spend": current_mroi,
        "marginal_history": marginals,
        "recommendation": (
            "Well below saturation — room to scale"
            if position_pct < 50 else
            "Approaching saturation — monitor marginal returns"
            if position_pct < 80 else
            "Near or at saturation — reallocate incremental budget"
        ),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Revenue Simulator — Monte Carlo simulation of marketing decisions"
    )
    parser.add_argument("--action", required=True,
                        choices=["simulate", "what-if", "sensitivity",
                                 "channel-interaction", "saturation-check"],
                        help="Action to perform")
    parser.add_argument("--brand", type=_common.path_component, help="Brand slug (reserved)")
    parser.add_argument("--scenarios", help="JSON array of scenario objects (for simulate)")
    parser.add_argument("--current", help="JSON current allocation (for what-if)")
    parser.add_argument("--base-scenario", dest="base_scenario",
                        help="JSON base scenario (for sensitivity)")
    parser.add_argument("--variable", choices=["budget", "roi", "saturation"],
                        help="Variable to vary (for sensitivity)")
    parser.add_argument("--range", dest="var_range",
                        help="JSON [min, max, steps] (for sensitivity)")
    parser.add_argument("--data", help="JSON data (for channel-interaction)")
    parser.add_argument("--channel", help="Channel name (for saturation-check)")
    parser.add_argument("--current-budget", type=float,
                        help="Current budget (for saturation-check)")
    parser.add_argument("--performance-history", dest="perf_history",
                        help="JSON array of {budget, revenue} (for saturation-check)")
    parser.add_argument("--target", type=float, help="Revenue target (for simulate)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility (default: 42)")
    args = parser.parse_args()

    result = None

    if args.action == "simulate":
        if not args.scenarios:
            print(json.dumps({"error": "Provide --scenarios JSON array"}))
            sys.exit(1)
        try:
            scenarios = json.loads(args.scenarios)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --scenarios"}))
            sys.exit(1)
        if not isinstance(scenarios, list):
            scenarios = [scenarios]
        result = simulate(scenarios, args.target, args.seed)

    elif args.action == "what-if":
        if not args.current:
            print(json.dumps({"error": "Provide --current JSON allocation"}))
            sys.exit(1)
        if not args.scenarios:
            print(json.dumps({"error": "Provide --scenarios JSON alternatives"}))
            sys.exit(1)
        try:
            current = json.loads(args.current)
            alternatives = json.loads(args.scenarios)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --current or --scenarios"}))
            sys.exit(1)
        if not isinstance(alternatives, list):
            alternatives = [alternatives]
        result = what_if(current, alternatives, args.seed)

    elif args.action == "sensitivity":
        if not args.base_scenario:
            print(json.dumps({"error": "Provide --base-scenario JSON"}))
            sys.exit(1)
        if not args.variable:
            print(json.dumps({"error": "Provide --variable (budget|roi|saturation)"}))
            sys.exit(1)
        if not args.var_range:
            print(json.dumps({"error": "Provide --range [min, max, steps]"}))
            sys.exit(1)
        try:
            base = json.loads(args.base_scenario)
            vr = json.loads(args.var_range)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --base-scenario or --range"}))
            sys.exit(1)
        if not isinstance(vr, list) or len(vr) != 3:
            print(json.dumps({"error": "--range must be [min, max, steps]"}))
            sys.exit(1)
        result = sensitivity(base, args.variable, vr, args.seed)

    elif args.action == "channel-interaction":
        if not args.data:
            print(json.dumps({"error": "Provide --data JSON with channels"}))
            sys.exit(1)
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --data"}))
            sys.exit(1)
        result = channel_interaction(data)

    elif args.action == "saturation-check":
        if not args.channel:
            print(json.dumps({"error": "Provide --channel name"}))
            sys.exit(1)
        if args.current_budget is None:
            print(json.dumps({"error": "Provide --current-budget"}))
            sys.exit(1)
        if not args.perf_history:
            print(json.dumps({"error": "Provide --performance-history JSON array"}))
            sys.exit(1)
        try:
            history = json.loads(args.perf_history)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --performance-history"}))
            sys.exit(1)
        result = saturation_check(args.channel, args.current_budget, history)

    if result is not None:
        _common.finish(result)


if __name__ == "__main__":
    main()
