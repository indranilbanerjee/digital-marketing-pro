#!/usr/bin/env python3
"""
roi-calculator.py
=================
Campaign ROI calculator. Computes ROI, ROAS, CPA, and contribution metrics
per channel from each channel's raw reported revenue, and generates
optimisation recommendations. Attribution weights (last_touch, first_touch,
linear, time_decay, position_based) are advisory per-channel metadata only —
input order is treated as touch order — and do NOT redistribute revenue in
the computed metrics.

Dependencies: none (stdlib only)

Usage:
    python roi-calculator.py --channels '[{"name":"Google Ads","spend":5000,"conversions":150,"revenue":22500}]'
    python roi-calculator.py --file channels.json --attribution linear --period "Q1 2026"
    python roi-calculator.py --channels '[...]' --attribution time_decay --ltv 1200
"""

import argparse
import json
import sys

for _stream in (sys.stdout, sys.stderr):  # UTF-8 output, even where a Windows pipe defaults to cp1252
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from pathlib import Path

# ---------------------------------------------------------------------------
# Attribution helpers
# ---------------------------------------------------------------------------

VALID_MODELS = {"last_touch", "first_touch", "linear", "time_decay", "position_based"}


def apply_attribution(channels, model):
    """Return a list of attribution weights (same order as channels).

    Each weight is a float between 0 and 1; all weights sum to 1.
    """
    n = len(channels)
    if n == 0:
        return []
    if n == 1:
        return [1.0]

    if model == "last_touch":
        weights = [0.0] * n
        weights[-1] = 1.0

    elif model == "first_touch":
        weights = [0.0] * n
        weights[0] = 1.0

    elif model == "linear":
        weights = [1.0 / n] * n

    elif model == "time_decay":
        decay = 0.7
        raw = [decay ** (n - 1 - i) for i in range(n)]
        total = sum(raw)
        weights = [r / total for r in raw]

    elif model == "position_based":
        if n == 2:
            weights = [0.5, 0.5]
        else:
            weights = [0.0] * n
            weights[0] = 0.4
            weights[-1] = 0.4
            middle_share = 0.2 / (n - 2)
            for i in range(1, n - 1):
                weights[i] = middle_share
    else:
        weights = [1.0 / n] * n

    return weights


# ---------------------------------------------------------------------------
# Metric calculations
# ---------------------------------------------------------------------------

def calculate_channel_metrics(channel, total_revenue, ltv=None):
    """Calculate per-channel metrics. Returns a dict."""
    spend = channel["spend"]
    conversions = channel["conversions"]
    revenue = channel["revenue"]

    roi_percent = ((revenue - spend) / spend * 100) if spend > 0 else None
    roas = (revenue / spend) if spend > 0 else None
    cpa = (spend / conversions) if conversions > 0 else None
    rev_per_conv = (revenue / conversions) if conversions > 0 else None
    contribution = (revenue / total_revenue * 100) if total_revenue > 0 else 0.0

    result = {
        "name": channel["name"],
        "spend": spend,
        "conversions": conversions,
        "revenue": revenue,
        "roi_percent": round(roi_percent, 2) if roi_percent is not None else None,
        "roas": round(roas, 2) if roas is not None else None,
        "cpa": round(cpa, 2) if cpa is not None else None,
        "revenue_per_conversion": round(rev_per_conv, 2) if rev_per_conv is not None else None,
        "contribution_percent": round(contribution, 2),
        "ltv_cac_ratio": None,
    }

    if ltv is not None and cpa is not None and cpa > 0:
        result["ltv_cac_ratio"] = round(ltv / cpa, 2)

    return result


def calculate_summary(channel_metrics):
    """Calculate aggregate summary across all channels."""
    total_spend = sum(c["spend"] for c in channel_metrics)
    total_revenue = sum(c["revenue"] for c in channel_metrics)
    total_conversions = sum(c["conversions"] for c in channel_metrics)

    blended_roi = ((total_revenue - total_spend) / total_spend * 100) if total_spend > 0 else None
    blended_roas = (total_revenue / total_spend) if total_spend > 0 else None
    blended_cpa = (total_spend / total_conversions) if total_conversions > 0 else None

    # Rank by ROI (descending), handle None ROI values
    valid_roi = [c for c in channel_metrics if c["roi_percent"] is not None]
    sorted_by_roi = sorted(valid_roi, key=lambda c: c["roi_percent"], reverse=True)

    best_channel = sorted_by_roi[0]["name"] if sorted_by_roi else None
    worst_channel = sorted_by_roi[-1]["name"] if sorted_by_roi else None

    # Rank by ROAS for budget efficiency
    valid_roas = [c for c in channel_metrics if c["roas"] is not None]
    sorted_by_roas = sorted(valid_roas, key=lambda c: c["roas"], reverse=True)
    efficiency_ranking = [c["name"] for c in sorted_by_roas]

    return {
        "total_spend": round(total_spend, 2),
        "total_revenue": round(total_revenue, 2),
        "total_conversions": total_conversions,
        "blended_roi_percent": round(blended_roi, 2) if blended_roi is not None else None,
        "blended_roas": round(blended_roas, 2) if blended_roas is not None else None,
        "blended_cpa": round(blended_cpa, 2) if blended_cpa is not None else None,
        "best_channel": best_channel,
        "worst_channel": worst_channel,
        "budget_efficiency_ranking": efficiency_ranking,
    }


def generate_recommendations(channel_metrics, summary):
    """Generate actionable budget and performance recommendations."""
    recs = []

    # Sort by ROAS descending for recommendation logic
    valid = [c for c in channel_metrics if c["roas"] is not None]
    sorted_by_roas = sorted(valid, key=lambda c: c["roas"], reverse=True)

    if sorted_by_roas:
        top = sorted_by_roas[0]
        recs.append(
            f"Increase {top['name']} budget \u2014 highest ROAS at {top['roas']}x"
        )

    # Flag negative-ROI channels
    negative = [c for c in channel_metrics if c["roi_percent"] is not None and c["roi_percent"] < 0]
    for ch in negative:
        recs.append(
            f"Reduce {ch['name']} spend \u2014 negative ROI ({ch['roi_percent']}%)"
        )

    # Suggest reallocation from worst to second-best
    if len(sorted_by_roas) >= 2 and negative:
        worst = negative[0]
        runner_up = sorted_by_roas[1]
        recs.append(
            f"Test shifting 20% of {worst['name']} budget to "
            f"{runner_up['name']} (ROAS {runner_up['roas']}x)"
        )

    # High CPA warning
    if summary["blended_cpa"] is not None:
        high_cpa = [
            c for c in channel_metrics
            if c["cpa"] is not None and c["cpa"] > summary["blended_cpa"] * 1.5
        ]
        for ch in high_cpa:
            recs.append(
                f"Investigate {ch['name']} CPA (${ch['cpa']:.2f}) \u2014 "
                f"50%+ above blended average (${summary['blended_cpa']:.2f})"
            )

    # LTV:CAC guidance
    ltv_channels = [c for c in channel_metrics if c["ltv_cac_ratio"] is not None]
    low_ltv = [c for c in ltv_channels if c["ltv_cac_ratio"] < 3.0]
    for ch in low_ltv:
        recs.append(
            f"{ch['name']} LTV:CAC ratio is {ch['ltv_cac_ratio']} \u2014 "
            f"below the 3:1 healthy threshold. Review targeting or reduce spend."
        )

    if not recs:
        recs.append(
            "All channels are performing well. Consider A/B testing creative "
            "or expanding to new channels for growth."
        )

    return recs


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
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Campaign ROI calculator with multi-touch attribution models"
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
        "--attribution", default="last_touch",
        choices=sorted(VALID_MODELS),
        help="Attribution model (default: last_touch)",
    )
    parser.add_argument(
        "--period", default=None,
        help='Time period label (e.g. "Q1 2026")',
    )
    parser.add_argument(
        "--ltv", type=float, default=None,
        help="Average customer lifetime value (enables LTV:CAC ratio)",
    )
    args = parser.parse_args()

    # --- Load and validate ---
    channels, err = load_channels(args)
    if err:
        json.dump({"error": err}, sys.stdout, indent=2)
        print()
        sys.exit(1 if str(err).startswith(("File not found", "Failed to read")) else 2)

    if args.ltv is not None and args.ltv <= 0:
        json.dump({"error": "LTV must be a positive number"}, sys.stdout, indent=2)
        print()
        sys.exit(2)

    # --- Compute per-channel metrics ---
    total_revenue = sum(ch["revenue"] for ch in channels)
    channel_metrics = [
        calculate_channel_metrics(ch, total_revenue, ltv=args.ltv)
        for ch in channels
    ]

    # --- Attribution weights ---
    weights = apply_attribution(channels, args.attribution)
    for i, cm in enumerate(channel_metrics):
        cm["attribution_weight"] = round(weights[i], 4)

    # --- Summary ---
    summary = calculate_summary(channel_metrics)

    # --- Recommendations ---
    recommendations = generate_recommendations(channel_metrics, summary)

    # --- Build output ---
    output = {}
    if args.period:
        output["period"] = args.period
    output["attribution_model"] = args.attribution
    output["channels"] = channel_metrics
    output["summary"] = summary
    output["recommendations"] = recommendations

    json.dump(output, sys.stdout, indent=2)
    print()
    sys.exit(1 if isinstance(output, dict) and "error" in output else 0)  # an error payload never exits 0


if __name__ == "__main__":
    main()
