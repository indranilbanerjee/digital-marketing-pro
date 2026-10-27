#!/usr/bin/env python3
"""Ad spend pacing tracker and forecaster.

Tracks ad budget pacing against a linear spend schedule. Calculates pace
status (under/on/over), remaining budget requirements, projected end-of-period
spend, and trend analysis when daily spend data is provided. Generates
actionable recommendations for budget reallocation.

Usage:
    python ad-budget-pacer.py --budget 30000 --period-days 30 --days-elapsed 15 --spend-to-date 12000
    python ad-budget-pacer.py --budget 10000 --period-days 14 --days-elapsed 7 --spend-to-date 6000 \
        --daily-spend '[500,600,700,800,900,1000,1100]'
    python ad-budget-pacer.py --budget 50000 --period-days 30 --days-elapsed 10 --spend-to-date 15000 \
        --channels '[{"name":"google","budget":30000,"spend":9000},{"name":"meta","budget":20000,"spend":6000}]'
"""

import argparse
import json
import sys

for _stream in (sys.stdout, sys.stderr):  # UTF-8 output, even where a Windows pipe defaults to cp1252
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

# ---------------------------------------------------------------------------
# Pacing calculations
# ---------------------------------------------------------------------------

def classify_pace(pace_percent):
    """Classify pacing status and severity."""
    if pace_percent < 75:
        return "under_pacing", "severe"
    elif pace_percent < 90:
        return "under_pacing", "moderate"
    elif pace_percent <= 110:
        return "on_pace", "none"
    elif pace_percent <= 125:
        return "over_pacing", "moderate"
    else:
        return "over_pacing", "severe"


def compute_pacing(budget, period_days, days_elapsed, spend_to_date):
    """Core pacing calculations."""
    expected_spend = budget * (days_elapsed / period_days)
    remaining_budget = budget - spend_to_date
    remaining_days = period_days - days_elapsed

    pace_percent = (spend_to_date / expected_spend * 100) if expected_spend > 0 else 0.0
    status, severity = classify_pace(pace_percent)

    current_daily_avg = spend_to_date / days_elapsed if days_elapsed > 0 else 0.0
    required_daily = remaining_budget / remaining_days if remaining_days > 0 else 0.0

    adjustment_pct = 0.0
    if current_daily_avg > 0:
        adjustment_pct = ((required_daily - current_daily_avg) / current_daily_avg) * 100

    projected_total = current_daily_avg * period_days if days_elapsed > 0 else 0.0
    projected_variance = projected_total - budget
    projected_utilization = (projected_total / budget * 100) if budget > 0 else 0.0

    return {
        "pacing": {
            "expected_spend": round(expected_spend, 2),
            "actual_spend": round(spend_to_date, 2),
            "pace_percent": round(pace_percent, 1),
            "status": status,
            "severity": severity,
        },
        "remaining": {
            "budget": round(remaining_budget, 2),
            "days": remaining_days,
            "required_daily_spend": round(required_daily, 2),
            "current_daily_average": round(current_daily_avg, 2),
            "adjustment_needed_percent": round(adjustment_pct, 1),
        },
        "projection": {
            "projected_total_spend": round(projected_total, 2),
            "projected_variance": round(projected_variance, 2),
            "projected_utilization_percent": round(projected_utilization, 1),
        },
    }


# ---------------------------------------------------------------------------
# Trend analysis
# ---------------------------------------------------------------------------

def analyze_trend(daily_spend, period_days, budget):
    """Analyze daily spend trend when historical data is provided."""
    n = len(daily_spend)
    if n < 2:
        return None

    # 7-day moving average (or full window if fewer than 7 days)
    window = min(7, n)
    recent = daily_spend[-window:]
    moving_avg = sum(recent) / len(recent)

    # Trend direction: compare first half average to second half average
    mid = n // 2
    first_half_avg = sum(daily_spend[:mid]) / mid if mid > 0 else 0
    second_half_avg = sum(daily_spend[mid:]) / (n - mid) if (n - mid) > 0 else 0

    if second_half_avg > first_half_avg * 1.10:
        direction = "increasing"
    elif second_half_avg < first_half_avg * 0.90:
        direction = "decreasing"
    else:
        direction = "stable"

    # Weekend vs weekday pattern (if at least 7 days)
    weekday_weeknd = None
    if n >= 7:
        # Assume day 0 = Monday for pattern detection
        weekday_vals = [daily_spend[i] for i in range(n) if i % 7 < 5]
        weekend_vals = [daily_spend[i] for i in range(n) if i % 7 >= 5]
        if weekday_vals and weekend_vals:
            wd_avg = sum(weekday_vals) / len(weekday_vals)
            we_avg = sum(weekend_vals) / len(weekend_vals)
            weekday_weeknd = {
                "weekday_average": round(wd_avg, 2),
                "weekend_average": round(we_avg, 2),
                "pattern": (
                    "higher weekdays" if wd_avg > we_avg * 1.15
                    else "higher weekends" if we_avg > wd_avg * 1.15
                    else "uniform"
                ),
            }

    # Trend-based projection
    total_spent = sum(daily_spend)
    remaining_days = period_days - n
    if remaining_days > 0:
        # Use moving average as the projected daily rate
        trend_projected_total = total_spent + moving_avg * remaining_days
    else:
        trend_projected_total = total_spent

    trend = {
        "direction": direction,
        "7_day_average": round(moving_avg, 2),
        "trend_projected_total": round(trend_projected_total, 2),
        "data_points": n,
    }

    if weekday_weeknd:
        trend["weekday_weekend_pattern"] = weekday_weeknd

    return trend


# ---------------------------------------------------------------------------
# Channel pacing
# ---------------------------------------------------------------------------

def analyze_channels(channels, period_days, days_elapsed):
    """Per-channel pacing analysis."""
    results = []
    for ch in channels:
        name = ch.get("name", "unknown")
        ch_budget = ch.get("budget", 0)
        ch_spend = ch.get("spend", 0)

        if ch_budget <= 0:
            results.append({"name": name, "error": "Invalid budget"})
            continue

        ch_result = compute_pacing(ch_budget, period_days, days_elapsed, ch_spend)
        ch_result["name"] = name
        ch_result["budget"] = ch_budget
        results.append(ch_result)

    return results


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

def generate_recommendations(pacing, remaining, projection, trend, channels):
    """Generate actionable budget pacing recommendations."""
    recs = []
    status = pacing["status"]
    severity = pacing["severity"]
    adj = remaining["adjustment_needed_percent"]
    utilization = projection["projected_utilization_percent"]

    if status == "under_pacing":
        if severity == "severe":
            recs.append(
                f"Severely under-pacing at {pacing['pace_percent']:.0f}% of expected spend. "
                f"Increase daily spend by {adj:.0f}% (${remaining['current_daily_average']:,.0f} -> "
                f"${remaining['required_daily_spend']:,.0f}) to fully utilize budget."
            )
            recs.append(
                f"Current pace will leave ${abs(projection['projected_variance']):,.0f} unspent "
                f"-- reallocate to high-performing channels or expand targeting."
            )
        else:
            recs.append(
                f"Increase daily spend by {adj:.0f}% "
                f"(${remaining['current_daily_average']:,.0f} -> ${remaining['required_daily_spend']:,.0f}) "
                f"to fully utilize budget."
            )
            recs.append(
                f"Current pace will leave ${abs(projection['projected_variance']):,.0f} unspent "
                f"-- reallocate to high-performing channels."
            )
        recs.append(
            "Consider increasing bids or expanding targeting to deploy remaining budget."
        )

    elif status == "over_pacing":
        if severity == "severe":
            recs.append(
                f"Severely over-pacing at {pacing['pace_percent']:.0f}% of expected spend. "
                f"Reduce daily spend by {abs(adj):.0f}% to avoid exhausting budget early."
            )
            recs.append(
                "Consider pausing lower-performing campaigns or reducing bids immediately."
            )
        else:
            recs.append(
                f"Slightly over-pacing. Reduce daily spend by {abs(adj):.0f}% to stay on track."
            )
        current_daily_avg = remaining["current_daily_average"]
        days_to_exhaustion = (
            remaining["budget"] / current_daily_avg if current_daily_avg > 0 else remaining["days"]
        )
        days_early = max(0, round(remaining["days"] - days_to_exhaustion))
        recs.append(
            f"At current rate, budget will be exhausted "
            f"{days_early} days before period ends. Apply daily budget caps."
        )

    else:
        recs.append(
            f"Budget pacing is on track at {pacing['pace_percent']:.0f}%. "
            f"Maintain current spend levels."
        )
        if utilization < 95:
            recs.append(
                "Slight room to increase spend. Consider testing new ad variations "
                "or expanding to additional audiences."
            )

    if trend:
        if trend["direction"] == "decreasing" and status != "over_pacing":
            recs.append(
                f"Spend trend is decreasing (7-day avg: ${trend['7_day_average']:,.0f}). "
                f"Investigate delivery issues or audience saturation."
            )
        elif trend["direction"] == "increasing" and status == "over_pacing":
            recs.append(
                "Spend trend is accelerating while already over-pacing. "
                "Apply tighter daily caps to prevent early budget exhaustion."
            )

    if channels:
        over_channels = [c["name"] for c in channels if c.get("pacing", {}).get("status") == "over_pacing"]
        under_channels = [c["name"] for c in channels if c.get("pacing", {}).get("status") == "under_pacing"]
        if over_channels and under_channels:
            recs.append(
                f"Rebalance budget: {', '.join(over_channels)} over-pacing while "
                f"{', '.join(under_channels)} under-pacing. Shift funds accordingly."
            )

    return recs


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Ad spend pacing tracker and forecaster"
    )
    parser.add_argument(
        "--budget", required=True, type=float,
        help="Total budget for the period",
    )
    parser.add_argument(
        "--period-days", required=True, type=int,
        help="Total days in the budget period",
    )
    parser.add_argument(
        "--days-elapsed", required=True, type=int,
        help="Days elapsed so far",
    )
    parser.add_argument(
        "--spend-to-date", required=True, type=float,
        help="Amount spent so far",
    )
    parser.add_argument(
        "--daily-spend", default=None,
        help="JSON array of daily spend values for trend analysis",
    )
    parser.add_argument(
        "--channels", default=None,
        help='JSON array of channel objects: [{"name":"google","budget":10000,"spend":5000}]',
    )
    args = parser.parse_args()

    # --- Validation ---
    if args.budget <= 0:
        json.dump({"error": "Budget must be a positive number"}, sys.stdout, indent=2)
        print()
        sys.exit(2)

    if args.period_days <= 0:
        json.dump({"error": "Period days must be a positive integer"}, sys.stdout, indent=2)
        print()
        sys.exit(2)

    if args.days_elapsed < 0:
        json.dump({"error": "Days elapsed cannot be negative"}, sys.stdout, indent=2)
        print()
        sys.exit(2)

    if args.days_elapsed > args.period_days:
        json.dump({"error": "Days elapsed cannot exceed period days"}, sys.stdout, indent=2)
        print()
        sys.exit(2)

    if args.days_elapsed == 0:
        json.dump({"error": "Days elapsed must be at least 1 for pacing analysis"}, sys.stdout, indent=2)
        print()
        sys.exit(2)

    if args.spend_to_date < 0:
        json.dump({"error": "Spend to date cannot be negative"}, sys.stdout, indent=2)
        print()
        sys.exit(2)

    # Parse optional daily spend
    daily_spend = None
    if args.daily_spend:
        try:
            daily_spend = _common.json_arg(args.daily_spend, "--daily-spend", list, (int, float))
            if not isinstance(daily_spend, list):
                json.dump({"error": "daily-spend must be a JSON array of numbers"}, sys.stdout, indent=2)
                print()
                sys.exit(2)
            daily_spend = [float(v) for v in daily_spend]
        except (json.JSONDecodeError, ValueError) as exc:
            json.dump({"error": f"Invalid daily-spend JSON: {exc}"}, sys.stdout, indent=2)
            print()
            sys.exit(2)

    # Parse optional channels
    channels_data = None
    if args.channels:
        try:
            channels_data = _common.json_arg(args.channels, "--channels", list, dict)
            if not isinstance(channels_data, list):
                json.dump({"error": "channels must be a JSON array"}, sys.stdout, indent=2)
                print()
                sys.exit(2)
        except json.JSONDecodeError as exc:
            json.dump({"error": f"Invalid channels JSON: {exc}"}, sys.stdout, indent=2)
            print()
            sys.exit(2)

    # --- Core calculations ---
    try:
        result = compute_pacing(args.budget, args.period_days, args.days_elapsed, args.spend_to_date)

        output = {
            "budget": args.budget,
            "period_days": args.period_days,
            "days_elapsed": args.days_elapsed,
        }
        output.update(result)

        # Trend analysis
        trend = None
        if daily_spend:
            trend = analyze_trend(daily_spend, args.period_days, args.budget)
            if trend:
                output["trend"] = trend

        # Channel pacing
        channel_results = None
        if channels_data:
            channel_results = analyze_channels(channels_data, args.period_days, args.days_elapsed)
            output["channels"] = channel_results

        # Recommendations
        output["recommendations"] = generate_recommendations(
            result["pacing"], result["remaining"], result["projection"],
            trend, channel_results,
        )

        json.dump(output, sys.stdout, indent=2)
        print()

    except Exception as exc:
        json.dump({"error": f"Pacing calculation failed: {exc}"}, sys.stdout, indent=2)
        print()
        sys.exit(1)


if __name__ == "__main__":
    main()
