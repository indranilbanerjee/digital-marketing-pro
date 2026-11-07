#!/usr/bin/env python3
"""Marketing revenue/pipeline forecasting using historical trends.

Takes historical monthly revenue (and optional spend) data and produces
multi-month forecasts using linear regression and growth-rate models.
Supports seasonal multipliers and custom growth-rate overrides. Returns
blended forecasts with confidence ranges, projected ROAS, and assumptions.

Dependencies: none (stdlib only)

Usage:
    python revenue-forecaster.py --historical '[{"month":"2025-01","revenue":50000,"spend":15000}]'
    python revenue-forecaster.py --file history.json --forecast-months 6
    python revenue-forecaster.py --file history.json --growth-assumption 0.05
    python revenue-forecaster.py --file history.json --seasonality '{"1":0.85,"11":1.3,"12":1.5}'
"""

import argparse
import json
import sys
from pathlib import Path
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

# ---------------------------------------------------------------------------
# Linear regression (least squares)
# ---------------------------------------------------------------------------

def linear_regression(x, y):
    """Compute slope and intercept using ordinary least squares.

    Parameters:
        x: list of float (independent variable)
        y: list of float (dependent variable)

    Returns:
        (slope, intercept) tuple
    """
    n = len(x)
    if n < 2:
        return 0.0, y[0] if y else 0.0

    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))
    sum_x2 = sum(xi ** 2 for xi in x)

    denom = n * sum_x2 - sum_x ** 2
    if denom == 0:
        return 0.0, sum_y / n

    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n
    return slope, intercept


# ---------------------------------------------------------------------------
# Growth rate calculations
# ---------------------------------------------------------------------------

def compute_growth_rates(revenues):
    """Compute month-over-month growth rates."""
    rates = []
    for i in range(1, len(revenues)):
        if revenues[i - 1] > 0:
            rate = (revenues[i] - revenues[i - 1]) / revenues[i - 1]
            rates.append(rate)
        else:
            rates.append(0.0)
    return rates


def average_growth(rates, window=None):
    """Average growth rate over the last `window` periods (or all)."""
    if not rates:
        return 0.0
    if window is not None:
        rates = rates[-window:]
    return sum(rates) / len(rates) if rates else 0.0


# ---------------------------------------------------------------------------
# Month arithmetic
# ---------------------------------------------------------------------------

def next_month(month_str):
    """Given 'YYYY-MM', return the next month string."""
    year, month = int(month_str[:4]), int(month_str[5:7])
    month += 1
    if month > 12:
        month = 1
        year += 1
    return f"{year:04d}-{month:02d}"


def month_index(month_str):
    """Return 1-12 month index from 'YYYY-MM'."""
    return int(month_str[5:7])


# ---------------------------------------------------------------------------
# Trend classification
# ---------------------------------------------------------------------------

def classify_trend(growth_rates):
    """Classify the overall trend direction."""
    if not growth_rates:
        return "insufficient_data"

    recent = growth_rates[-3:] if len(growth_rates) >= 3 else growth_rates
    avg_recent = sum(recent) / len(recent)

    if avg_recent > 0.02:
        return "growing"
    elif avg_recent < -0.02:
        return "declining"
    else:
        return "stable"


# ---------------------------------------------------------------------------
# Forecasting
# ---------------------------------------------------------------------------

def forecast_revenue(historical, forecast_months, growth_assumption, seasonality):
    """Generate revenue forecasts from historical data."""
    n = len(historical)
    months = [h["month"] for h in historical]
    revenues = [h["revenue"] for h in historical]
    spends = [h.get("spend") for h in historical]
    has_spend = any(s is not None and s > 0 for s in spends)

    # --- Historical analysis ---
    growth_rates = compute_growth_rates(revenues)
    avg_growth_all = average_growth(growth_rates)
    avg_growth_3mo = average_growth(growth_rates, window=3)
    avg_growth_6mo = average_growth(growth_rates, window=6)
    trend_direction = classify_trend(growth_rates)

    avg_monthly_revenue = sum(revenues) / n if n > 0 else 0
    avg_roas = None
    if has_spend:
        valid_spend = [(r, s) for r, s in zip(revenues, spends) if s and s > 0]
        if valid_spend:
            total_rev = sum(r for r, _ in valid_spend)
            total_sp = sum(s for _, s in valid_spend)
            avg_roas = round(total_rev / total_sp, 2) if total_sp > 0 else None

    historical_analysis = {
        "months_analyzed": n,
        "average_monthly_revenue": round(avg_monthly_revenue, 2),
        "average_monthly_growth_rate": round(avg_growth_all, 4),
        "recent_3mo_growth_rate": round(avg_growth_3mo, 4),
        "trend_direction": trend_direction,
    }
    if avg_roas is not None:
        historical_analysis["average_roas"] = avg_roas

    # --- Forecasting ---
    # Linear regression: x = period index (0..n-1), y = revenue
    x_vals = list(range(n))
    slope, intercept = linear_regression(x_vals, revenues)

    # Determine effective growth rate
    if growth_assumption is not None:
        effective_growth = growth_assumption
    else:
        effective_growth = avg_growth_3mo if len(growth_rates) >= 3 else avg_growth_all

    # Parse seasonality multipliers
    seasonal = {}
    if seasonality:
        for k, v in seasonality.items():
            seasonal[int(k)] = float(v)

    # Average spend growth rate for spend projection
    avg_spend = None
    if has_spend:
        valid_spends = [s for s in spends if s is not None and s > 0]
        avg_spend = sum(valid_spends) / len(valid_spends) if valid_spends else None

    # Generate forecasts
    forecasts = []
    last_month = months[-1]
    last_revenue = revenues[-1]
    current_month = last_month

    for i in range(forecast_months):
        current_month = next_month(current_month)
        period_idx = n + i  # continuing the x-axis

        # Linear forecast
        linear_val = slope * period_idx + intercept

        # Growth rate forecast
        growth_val = last_revenue * ((1 + effective_growth) ** (i + 1))

        # Blended (50/50)
        blended = (linear_val + growth_val) / 2

        # Apply seasonal multiplier if available
        m_idx = month_index(current_month)
        if m_idx in seasonal:
            multiplier = seasonal[m_idx]
            linear_val *= multiplier
            growth_val *= multiplier
            blended *= multiplier

        # Confidence range: +-15% base, widening by 3% per additional month
        confidence_margin = 0.15 + (i * 0.03)
        conf_low = blended * (1 - confidence_margin)
        conf_high = blended * (1 + confidence_margin)

        forecast_entry = {
            "month": current_month,
            "linear_forecast": round(max(0, linear_val), 2),
            "growth_forecast": round(max(0, growth_val), 2),
            "blended_forecast": round(max(0, blended), 2),
            "confidence_low": round(max(0, conf_low), 2),
            "confidence_high": round(conf_high, 2),
        }

        # Projected spend and ROAS
        if avg_spend is not None and avg_roas is not None:
            proj_spend = round(blended / avg_roas, 2) if avg_roas > 0 else round(avg_spend, 2)
            forecast_entry["projected_spend"] = proj_spend
            forecast_entry["projected_roas"] = avg_roas

        forecasts.append(forecast_entry)

    # --- Summary ---
    total_forecasted_rev = sum(f["blended_forecast"] for f in forecasts)
    total_forecasted_spend = sum(f.get("projected_spend", 0) for f in forecasts) if has_spend else None

    first_forecast_month = forecasts[0]["month"] if forecasts else ""
    last_forecast_month = forecasts[-1]["month"] if forecasts else ""

    # Projected growth rate over forecast period
    if forecasts and forecasts[0]["blended_forecast"] > 0:
        proj_growth = (forecasts[-1]["blended_forecast"] - forecasts[0]["blended_forecast"]) / forecasts[0]["blended_forecast"]
        if forecast_months > 1:
            proj_growth = proj_growth / (forecast_months - 1) if forecast_months > 1 else proj_growth
    else:
        proj_growth = effective_growth

    # Confidence level based on data quality
    if n >= 12:
        confidence_level = "high"
    elif n >= 6:
        confidence_level = "moderate"
    elif n >= 3:
        confidence_level = "low"
    else:
        confidence_level = "very_low"

    summary = {
        "forecast_period": f"{first_forecast_month} to {last_forecast_month}",
        "total_forecasted_revenue": round(total_forecasted_rev, 2),
        "projected_growth_rate": round(proj_growth, 4),
        "confidence_level": confidence_level,
    }
    if total_forecasted_spend is not None:
        summary["total_forecasted_spend"] = round(total_forecasted_spend, 2)

    # --- Assumptions ---
    assumptions = [
        "Linear and growth rate models given equal weight (50/50 blend)",
    ]
    if growth_assumption is not None:
        assumptions.append(f"Growth rate overridden to {growth_assumption * 100:.1f}% monthly")
    else:
        assumptions.append(f"Growth rate derived from recent {min(3, len(growth_rates))}-month average ({effective_growth * 100:.2f}%)")

    if has_spend:
        assumptions.append("Spend assumed to grow proportionally with revenue")
    else:
        assumptions.append("No spend data provided -- ROAS projections unavailable")

    if seasonality:
        assumptions.append(f"Seasonal multipliers applied for months: {', '.join(str(k) for k in sorted(seasonal.keys()))}")

    base_margin = 15
    max_margin = base_margin + (forecast_months - 1) * 3
    assumptions.append(f"Confidence range: +/-{base_margin}% to +/-{max_margin}% (widening for longer forecasts)")

    # --- Compile output ---
    output = {
        "historical_analysis": historical_analysis,
        "forecast": forecasts,
        "summary": summary,
        "assumptions": assumptions,
    }

    return output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Marketing revenue/pipeline forecasting using historical trends"
    )
    parser.add_argument(
        "--historical", default=None,
        help='JSON array of monthly data: [{"month":"2025-01","revenue":50000,"spend":15000}]',
    )
    parser.add_argument(
        "--file", default=None,
        help="Path to JSON file containing historical data (alternative to --historical)",
    )
    parser.add_argument(
        "--forecast-months", type=int, default=3,
        help="Number of months to forecast (default: 3)",
    )
    parser.add_argument(
        "--growth-assumption", type=float, default=None,
        help="Override growth rate (e.g., 0.05 for 5%% monthly)",
    )
    parser.add_argument(
        "--seasonality", default=None,
        help='JSON object with month indices and multipliers: {"11":1.3,"12":1.5}',
    )
    args = parser.parse_args()

    # --- Input loading ---
    if not args.historical and not args.file:
        json.dump(
            {"error": "Provide either --historical (JSON array) or --file (path to JSON file)"},
            sys.stdout, indent=2,
        )
        print()
        sys.exit(1)

    historical = None
    if args.file:
        path = Path(args.file)
        if not path.exists():
            json.dump({"error": f"File not found: {args.file}"}, sys.stdout, indent=2)
            print()
            sys.exit(1)
        try:
            content = path.read_text(encoding="utf-8-sig")
            historical = json.loads(content)
        except json.JSONDecodeError as exc:
            json.dump({"error": f"Invalid JSON in file: {exc}"}, sys.stdout, indent=2)
            print()
            sys.exit(1)
        except Exception as exc:
            json.dump({"error": f"Could not read file: {exc}"}, sys.stdout, indent=2)
            print()
            sys.exit(1)
    else:
        try:
            historical = _common.json_text(args.historical, "--historical")
        except json.JSONDecodeError as exc:
            json.dump({"error": f"Invalid JSON in --historical: {exc}"}, sys.stdout, indent=2)
            print()
            sys.exit(1)

    if not isinstance(historical, list):
        json.dump({"error": "Historical data must be a JSON array"}, sys.stdout, indent=2)
        print()
        sys.exit(1)

    if len(historical) < 2:
        json.dump({"error": "At least 2 months of historical data are required for forecasting"}, sys.stdout, indent=2)
        print()
        sys.exit(1)

    # Validate each entry
    for i, entry in enumerate(historical):
        if not isinstance(entry, dict):
            json.dump({"error": f"Entry {i} is not a JSON object"}, sys.stdout, indent=2)
            print()
            sys.exit(1)
        if "month" not in entry:
            json.dump({"error": f"Entry {i} missing 'month' field"}, sys.stdout, indent=2)
            print()
            sys.exit(1)
        if "revenue" not in entry:
            json.dump({"error": f"Entry {i} missing 'revenue' field"}, sys.stdout, indent=2)
            print()
            sys.exit(1)
        try:
            entry["revenue"] = float(entry["revenue"])
        except (ValueError, TypeError):
            json.dump({"error": f"Entry {i} has invalid revenue value"}, sys.stdout, indent=2)
            print()
            sys.exit(1)
        if entry["revenue"] < 0:
            json.dump({"error": f"Entry {i} has negative revenue"}, sys.stdout, indent=2)
            print()
            sys.exit(1)
        if "spend" in entry and entry["spend"] is not None:
            try:
                entry["spend"] = float(entry["spend"])
            except (ValueError, TypeError):
                entry["spend"] = None

    # Validate forecast months
    if args.forecast_months < 1:
        json.dump({"error": "forecast-months must be at least 1"}, sys.stdout, indent=2)
        print()
        sys.exit(1)
    if args.forecast_months > 24:
        json.dump({"error": "forecast-months cannot exceed 24"}, sys.stdout, indent=2)
        print()
        sys.exit(1)

    # Parse seasonality
    seasonality = None
    if args.seasonality:
        try:
            seasonality = _common.json_text(args.seasonality, "--seasonality")
            if not isinstance(seasonality, dict):
                json.dump({"error": "Seasonality must be a JSON object"}, sys.stdout, indent=2)
                print()
                sys.exit(1)
            # Validate keys are 1-12
            for k, v in seasonality.items():
                ki = int(k)
                if ki < 1 or ki > 12:
                    json.dump({"error": f"Seasonality month index {k} must be 1-12"}, sys.stdout, indent=2)
                    print()
                    sys.exit(1)
                float(v)  # validate multiplier is numeric
        except json.JSONDecodeError as exc:
            json.dump({"error": f"Invalid seasonality JSON: {exc}"}, sys.stdout, indent=2)
            print()
            sys.exit(1)
        except (ValueError, TypeError) as exc:
            json.dump({"error": f"Invalid seasonality values: {exc}"}, sys.stdout, indent=2)
            print()
            sys.exit(1)

    # Validate growth assumption
    if args.growth_assumption is not None:
        if args.growth_assumption < -0.5 or args.growth_assumption > 2.0:
            json.dump(
                {"error": "growth-assumption should be between -0.5 (-50%) and 2.0 (200%)"},
                sys.stdout, indent=2,
            )
            print()
            sys.exit(1)

    # Sort historical data by month
    historical.sort(key=lambda h: h["month"])

    # --- Run forecast ---
    try:
        result = forecast_revenue(
            historical=historical,
            forecast_months=args.forecast_months,
            growth_assumption=args.growth_assumption,
            seasonality=seasonality,
        )
        _common.finish(result)
    except Exception as exc:
        json.dump({"error": f"Forecasting failed: {exc}"}, sys.stdout, indent=2)
        print()
        sys.exit(1)


if __name__ == "__main__":
    main()
