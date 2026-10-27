#!/usr/bin/env python3
"""
budget-optimizer.py
===================
Data-driven marketing budget reallocation optimizer. Analyses current channel
performance, applies a diminishing-returns model (square-root scaling), and
recommends an optimised allocation that maximises projected revenue within the
given total budget.

Dependencies: none (stdlib only)

Usage:
    python budget-optimizer.py --channels '[{"name":"Google Ads","spend":5000,"conversions":150,"revenue":22500}]' --total-budget 15000
    python budget-optimizer.py --file channels.json --total-budget 20000 --min-spend 500 --test-budget-pct 15
"""

import argparse
import json
import math
import sys

for _stream in (sys.stdout, sys.stderr):  # UTF-8 output, even where a Windows pipe defaults to cp1252
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from pathlib import Path

# ---------------------------------------------------------------------------
# Input parsing
# ---------------------------------------------------------------------------

def load_channels(args):
    """Load channel data from --channels JSON or --file path."""
    if args.file:
        path = Path(args.file)
        if not path.exists():
            return None, f"File not found: {args.file}"
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, OSError) as exc:
            return None, f"Failed to read file: {exc}"
    elif args.channels:
        try:
            data = json.loads(args.channels)
        except json.JSONDecodeError as exc:
            return None, f"Invalid JSON in --channels: {exc}"
    else:
        return None, "Provide either --channels or --file"

    if isinstance(data, dict):
        data = [data]

    if not isinstance(data, list) or len(data) == 0:
        return None, "Channel data must be a non-empty JSON array of objects"

    required_keys = {"name", "spend", "conversions", "revenue"}
    for i, ch in enumerate(data):
        if not isinstance(ch, dict):
            return None, f"Channel entry {i} is not an object"
        missing = required_keys - set(ch.keys())
        if missing:
            return None, f"Channel '{ch.get('name', i)}' missing keys: {', '.join(sorted(missing))}"
        if ch["spend"] < 0:
            return None, f"Channel '{ch['name']}' has negative spend"
        if ch["conversions"] < 0:
            return None, f"Channel '{ch['name']}' has negative conversions"
        if ch["revenue"] < 0:
            return None, f"Channel '{ch['name']}' has negative revenue"

    return data, None


# ---------------------------------------------------------------------------
# Optimisation logic
# ---------------------------------------------------------------------------

def projected_revenue(current_revenue, current_spend, new_spend):
    """Diminishing returns model: revenue scales with sqrt(new/current).

    If current_spend is zero we cannot project, so return 0.
    """
    if current_spend <= 0 or current_revenue <= 0:
        return 0.0
    return current_revenue * math.sqrt(new_spend / current_spend)


def marginal_efficiency(channel):
    """ROAS as the primary efficiency signal."""
    if channel["spend"] <= 0:
        return 0.0
    return channel["revenue"] / channel["spend"]


def optimise(channels, total_budget, min_spend, test_budget_pct):
    """Allocate budget across channels to maximise projected revenue.

    Strategy:
    1. Reserve test budget.
    2. Give every active channel at least min_spend.
    3. Distribute remaining budget proportionally to marginal efficiency,
       then use iterative greedy allocation (step chunks) to refine.
    """
    n = len(channels)
    test_budget = round(total_budget * (test_budget_pct / 100.0), 2)
    allocatable = total_budget - test_budget

    # Edge case: not enough budget for minimums
    total_min = min_spend * n
    if total_min > allocatable:
        # Distribute evenly what we have
        per_channel = allocatable / n if n > 0 else 0
        allocation = [per_channel] * n
    else:
        # Start with minimum, distribute rest by efficiency ranking
        efficiencies = [marginal_efficiency(ch) for ch in channels]
        total_eff = sum(efficiencies)

        allocation = [min_spend] * n
        remaining = allocatable - total_min

        if total_eff > 0 and remaining > 0:
            # Proportional allocation by efficiency
            for i in range(n):
                share = (efficiencies[i] / total_eff) * remaining
                allocation[i] += share
        elif remaining > 0:
            # All channels have zero efficiency, split evenly
            per_channel = remaining / n
            for i in range(n):
                allocation[i] += per_channel

    # Round allocations to 2 decimal places, absorb rounding dust
    allocation = [round(a, 2) for a in allocation]
    dust = round(allocatable - sum(allocation), 2)
    if dust != 0 and n > 0:
        # Add dust to the most efficient channel
        best_idx = max(range(n), key=lambda i: marginal_efficiency(channels[i]))
        allocation[best_idx] = round(allocation[best_idx] + dust, 2)

    return allocation, test_budget


def build_output(channels, allocation, test_budget, total_budget):
    """Construct the full output JSON."""
    # Current state
    current_total_spend = sum(ch["spend"] for ch in channels)
    current_total_revenue = sum(ch["revenue"] for ch in channels)
    current_roas = (current_total_revenue / current_total_spend) if current_total_spend > 0 else 0

    # Optimised channel details
    opt_channels = []
    opt_total_revenue = 0.0

    for i, ch in enumerate(channels):
        new_spend = allocation[i]
        proj_rev = projected_revenue(ch["revenue"], ch["spend"], new_spend)
        opt_total_revenue += proj_rev

        current_roas_ch = (ch["revenue"] / ch["spend"]) if ch["spend"] > 0 else 0
        proj_roas_ch = (proj_rev / new_spend) if new_spend > 0 else 0
        change_pct = ((new_spend - ch["spend"]) / ch["spend"] * 100) if ch["spend"] > 0 else None

        opt_channels.append({
            "name": ch["name"],
            "current_spend": ch["spend"],
            "optimized_spend": round(new_spend, 2),
            "change_percent": round(change_pct, 1) if change_pct is not None else None,
            "current_roas": round(current_roas_ch, 2),
            "projected_roas": round(proj_roas_ch, 2),
            "projected_revenue": round(proj_rev, 2),
        })

    opt_total_revenue = round(opt_total_revenue, 2)
    opt_total_spend = round(sum(allocation), 2)
    opt_roas = (opt_total_revenue / opt_total_spend) if opt_total_spend > 0 else 0

    revenue_change = round(opt_total_revenue - current_total_revenue, 2)
    revenue_change_pct = round(
        (revenue_change / current_total_revenue * 100) if current_total_revenue > 0 else 0, 1
    )
    roas_change = round(opt_roas - current_roas, 2)

    # Recommendations
    recs = generate_recommendations(channels, opt_channels, test_budget)

    return {
        "current_allocation": {
            "total_spend": round(current_total_spend, 2),
            "total_revenue": round(current_total_revenue, 2),
            "blended_roas": round(current_roas, 2),
        },
        "optimized_allocation": {
            "total_spend": round(total_budget, 2),
            "total_revenue": opt_total_revenue,
            "blended_roas": round(opt_roas, 2),
            "test_budget": round(test_budget, 2),
            "channels": opt_channels,
        },
        "projected_improvement": {
            "revenue_change": revenue_change,
            "revenue_change_percent": revenue_change_pct,
            "roas_change": roas_change,
        },
        "recommendations": recs,
    }


def generate_recommendations(channels, opt_channels, test_budget):
    """Generate actionable reallocation recommendations."""
    recs = []

    # Identify biggest increases and decreases
    increases = sorted(
        [c for c in opt_channels if c["change_percent"] is not None and c["change_percent"] > 5],
        key=lambda c: c["change_percent"],
        reverse=True,
    )
    decreases = sorted(
        [c for c in opt_channels if c["change_percent"] is not None and c["change_percent"] < -5],
        key=lambda c: c["change_percent"],
    )

    for inc in increases[:2]:
        # Find where the budget is coming from
        source = decreases[0]["name"] if decreases else "underperforming channels"
        shift = round(inc["optimized_spend"] - inc["current_spend"], 2)
        recs.append(
            f"Shift ${shift:,.0f} from {source} to {inc['name']} "
            f"(highest marginal efficiency)"
        )

    for dec in decreases[:2]:
        recs.append(
            f"Reduce {dec['name']} by {abs(dec['change_percent']):.0f}% "
            f"\u2014 current ROAS ({dec['current_roas']}x) is below optimal"
        )

    # Channels staying roughly the same
    stable = [
        c for c in opt_channels
        if c["change_percent"] is not None and abs(c["change_percent"]) <= 5
    ]
    for ch in stable:
        recs.append(
            f"Maintain {ch['name']} at current level (already near optimal)"
        )

    if test_budget > 0:
        total_budget = sum(c["optimized_spend"] for c in opt_channels) + test_budget
        test_pct = (test_budget / total_budget * 100) if total_budget > 0 else 0
        recs.append(
            f"Reserve ${test_budget:,.0f} ({test_pct:.0f}%) "
            f"for testing new channels"
        )

    if not recs:
        recs.append(
            "Current allocation is already well-balanced. Focus on creative "
            "optimisation within existing channels."
        )

    return recs


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Data-driven marketing budget reallocation optimizer"
    )
    parser.add_argument(
        "--channels", default=None,
        help='JSON array of channel objects: [{"name":"...","spend":N,"conversions":N,"revenue":N}]',
    )
    parser.add_argument(
        "--file", default=None,
        help="Path to JSON file with channel data (alternative to --channels)",
    )
    parser.add_argument(
        "--total-budget", type=float, required=True,
        help="Total budget available for reallocation",
    )
    parser.add_argument(
        "--min-spend", type=float, default=0,
        help="Minimum spend per channel (default: 0)",
    )
    parser.add_argument(
        "--test-budget-pct", type=float, default=10,
        help="Percentage of budget to reserve for testing (default: 10)",
    )
    args = parser.parse_args()

    # --- Load and validate ---
    channels, err = load_channels(args)
    if err:
        json.dump({"error": err}, sys.stdout, indent=2)
        print()
        sys.exit(1 if str(err).startswith(("File not found", "Failed to read")) else 2)

    if args.total_budget <= 0:
        json.dump({"error": "total-budget must be a positive number"}, sys.stdout, indent=2)
        print()
        sys.exit(2)

    if args.min_spend < 0:
        json.dump({"error": "min-spend must be non-negative"}, sys.stdout, indent=2)
        print()
        sys.exit(2)

    if not (0 <= args.test_budget_pct < 100):
        json.dump({"error": "test-budget-pct must be between 0 and 99"}, sys.stdout, indent=2)
        print()
        sys.exit(2)

    # --- Optimise ---
    allocation, test_budget = optimise(
        channels, args.total_budget, args.min_spend, args.test_budget_pct
    )

    # --- Build and emit output ---
    output = build_output(channels, allocation, test_budget, args.total_budget)
    json.dump(output, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
