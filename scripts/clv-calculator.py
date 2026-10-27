#!/usr/bin/env python3
"""
clv-calculator.py
=================
Customer lifetime value calculator supporting simple, cohort, and contractual
models. Computes CLV, net-present-value-adjusted CLV, LTV:CAC analysis with
health assessments, and segment-level breakdowns.

Dependencies: none (stdlib only)

Usage:
    python clv-calculator.py --model simple --avg-purchase-value 80 --purchase-frequency 12 --customer-lifespan 5
    python clv-calculator.py --model simple --avg-purchase-value 80 --purchase-frequency 12 --customer-lifespan 5 --cac 200 --margin 60
    python clv-calculator.py --model contractual --monthly-revenue 99 --churn-rate 0.05 --margin 70 --cac 500
    python clv-calculator.py --model cohort --segments '[{"name":"Enterprise","avg_purchase_value":200,"purchase_frequency":24,"customer_lifespan":7,"weight":0.3},{"name":"SMB","avg_purchase_value":50,"purchase_frequency":12,"customer_lifespan":3,"weight":0.7}]'
"""

import argparse
import json
import sys

for _stream in (sys.stdout, sys.stderr):  # UTF-8 output, even where a Windows pipe defaults to cp1252
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# CLV models
# ---------------------------------------------------------------------------

def simple_clv(avg_purchase_value, purchase_frequency, customer_lifespan, margin_pct):
    """Simple CLV = APV x F x L x margin."""
    margin = margin_pct / 100.0
    return avg_purchase_value * purchase_frequency * customer_lifespan * margin


def contractual_clv(monthly_revenue, churn_rate, margin_pct):
    """Contractual CLV = (MRR x margin) / churn_rate."""
    if churn_rate <= 0:
        return 0.0
    margin = margin_pct / 100.0
    return (monthly_revenue * margin) / churn_rate


def npv_adjust(clv, customer_lifespan_years, discount_rate_pct):
    """Discount CLV to net present value using annual discount rate.

    Approximation: NPV = sum over years of (annual_value / (1 + r)^t).
    """
    if customer_lifespan_years <= 0:
        return 0.0
    r = discount_rate_pct / 100.0
    annual_value = clv / customer_lifespan_years
    npv = 0.0
    for t in range(1, int(customer_lifespan_years) + 1):
        npv += annual_value / ((1 + r) ** t)
    # Handle fractional year
    frac = customer_lifespan_years - int(customer_lifespan_years)
    if frac > 0:
        t = int(customer_lifespan_years) + 1
        npv += (annual_value * frac) / ((1 + r) ** t)
    return npv


def npv_adjust_contractual(monthly_revenue, churn_rate, margin_pct, discount_rate_pct, horizon_months=120):
    """NPV for contractual model: discount monthly cash flows with survival probability.

    Sums expected monthly cash flows up to horizon_months (default 10 years).
    """
    margin = margin_pct / 100.0
    monthly_cf = monthly_revenue * margin
    r_monthly = (1 + discount_rate_pct / 100.0) ** (1 / 12) - 1
    npv = 0.0
    survival = 1.0
    for m in range(1, horizon_months + 1):
        survival *= (1 - churn_rate)
        npv += (monthly_cf * survival) / ((1 + r_monthly) ** m)
        if survival < 0.001:
            break
    return npv


def assess_ltv_cac(ratio):
    """Return health assessment string for LTV:CAC ratio."""
    if ratio >= 5.0:
        return "excellent"
    elif ratio >= 3.0:
        return "healthy"
    elif ratio >= 1.0:
        return "needs_improvement"
    else:
        return "unsustainable"


# ---------------------------------------------------------------------------
# Model runners
# ---------------------------------------------------------------------------

def run_simple(args):
    """Execute simple CLV model."""
    required = ["avg_purchase_value", "purchase_frequency", "customer_lifespan"]
    missing = [f for f in required if getattr(args, f) is None]
    if missing:
        return {"error": f"Simple model requires: {', '.join('--' + m.replace('_', '-') for m in missing)}"}

    apv = args.avg_purchase_value
    freq = args.purchase_frequency
    lifespan = args.customer_lifespan
    margin = args.margin
    discount = args.discount_rate

    clv = simple_clv(apv, freq, lifespan, margin)
    clv_npv = npv_adjust(clv, lifespan, discount)
    annual_value = apv * freq * (margin / 100.0)
    monthly_value = annual_value / 12.0

    output = {
        "model": "simple",
        "clv": round(clv, 2),
        "clv_npv": round(clv_npv, 2),
        "inputs": {
            "avg_purchase_value": apv,
            "purchase_frequency": freq,
            "customer_lifespan": lifespan,
            "margin_percent": margin,
            "discount_rate_percent": discount,
        },
        "derived_metrics": {
            "annual_customer_value": round(annual_value, 2),
            "monthly_customer_value": round(monthly_value, 2),
            "payback_period_months": None,
        },
        "cac_analysis": None,
        "benchmarks": {
            "ltv_cac_healthy_minimum": 3.0,
            "ltv_cac_excellent_threshold": 5.0,
            "payback_healthy_maximum_months": 12,
        },
    }

    if args.cac is not None and args.cac > 0:
        ratio = clv / args.cac
        payback = args.cac / monthly_value if monthly_value > 0 else None
        output["cac_analysis"] = {
            "cac": args.cac,
            "ltv_cac_ratio": round(ratio, 2),
            "payback_period_months": round(payback, 1) if payback is not None else None,
            "assessment": assess_ltv_cac(ratio),
        }
        output["derived_metrics"]["payback_period_months"] = (
            round(payback, 1) if payback is not None else None
        )

    return output


def run_contractual(args):
    """Execute contractual (subscription) CLV model."""
    if args.monthly_revenue is None:
        return {"error": "Contractual model requires --monthly-revenue"}
    if args.churn_rate is None:
        return {"error": "Contractual model requires --churn-rate"}

    mr = args.monthly_revenue
    churn = args.churn_rate
    margin = args.margin
    discount = args.discount_rate

    if churn <= 0 or churn >= 1:
        return {"error": "churn-rate must be between 0 and 1 exclusive"}

    clv = contractual_clv(mr, churn, margin)
    clv_npv = npv_adjust_contractual(mr, churn, margin, discount)
    avg_lifespan_months = 1.0 / churn
    annual_value = mr * 12 * (margin / 100.0)
    monthly_value = mr * (margin / 100.0)

    output = {
        "model": "contractual",
        "clv": round(clv, 2),
        "clv_npv": round(clv_npv, 2),
        "inputs": {
            "monthly_revenue": mr,
            "churn_rate": churn,
            "margin_percent": margin,
            "discount_rate_percent": discount,
        },
        "derived_metrics": {
            "average_lifespan_months": round(avg_lifespan_months, 1),
            "average_lifespan_years": round(avg_lifespan_months / 12, 1),
            "annual_customer_value": round(annual_value, 2),
            "monthly_customer_value": round(monthly_value, 2),
            "monthly_churn_percent": round(churn * 100, 2),
            "annual_retention_rate": round((1 - churn) ** 12 * 100, 1),
            "payback_period_months": None,
        },
        "cac_analysis": None,
        "benchmarks": {
            "ltv_cac_healthy_minimum": 3.0,
            "ltv_cac_excellent_threshold": 5.0,
            "payback_healthy_maximum_months": 12,
            "healthy_monthly_churn_max": 0.05,
        },
    }

    if args.cac is not None and args.cac > 0:
        ratio = clv / args.cac
        payback = args.cac / monthly_value if monthly_value > 0 else None
        output["cac_analysis"] = {
            "cac": args.cac,
            "ltv_cac_ratio": round(ratio, 2),
            "payback_period_months": round(payback, 1) if payback is not None else None,
            "assessment": assess_ltv_cac(ratio),
        }
        output["derived_metrics"]["payback_period_months"] = (
            round(payback, 1) if payback is not None else None
        )

    return output


def run_cohort(args):
    """Execute cohort model with segment-level analysis."""
    if args.segments is None:
        return {"error": "Cohort model requires --segments JSON array"}

    try:
        segments = json.loads(args.segments)
    except json.JSONDecodeError as exc:
        return {"error": f"Invalid JSON in --segments: {exc}"}

    if not isinstance(segments, list) or len(segments) == 0:
        return {"error": "Segments must be a non-empty JSON array"}

    required_keys = {"name", "avg_purchase_value", "purchase_frequency", "customer_lifespan", "weight"}
    margin = args.margin
    discount = args.discount_rate

    segment_results = []
    weighted_clv = 0.0
    weighted_npv = 0.0
    total_weight = 0.0

    for i, seg in enumerate(segments):
        if not isinstance(seg, dict):
            return {"error": f"Segment entry {i} is not an object"}
        missing = required_keys - set(seg.keys())
        if missing:
            return {"error": f"Segment '{seg.get('name', i)}' missing keys: {', '.join(sorted(missing))}"}

        clv = simple_clv(
            seg["avg_purchase_value"], seg["purchase_frequency"],
            seg["customer_lifespan"], margin
        )
        clv_npv = npv_adjust(clv, seg["customer_lifespan"], discount)
        annual = seg["avg_purchase_value"] * seg["purchase_frequency"] * (margin / 100.0)

        seg_result = {
            "name": seg["name"],
            "clv": round(clv, 2),
            "clv_npv": round(clv_npv, 2),
            "weight": seg["weight"],
            "weighted_clv_contribution": round(clv * seg["weight"], 2),
            "annual_customer_value": round(annual, 2),
            "inputs": {
                "avg_purchase_value": seg["avg_purchase_value"],
                "purchase_frequency": seg["purchase_frequency"],
                "customer_lifespan": seg["customer_lifespan"],
            },
        }

        if args.cac is not None and args.cac > 0:
            ratio = clv / args.cac
            monthly = annual / 12
            payback = args.cac / monthly if monthly > 0 else None
            seg_result["cac_analysis"] = {
                "ltv_cac_ratio": round(ratio, 2),
                "payback_period_months": round(payback, 1) if payback is not None else None,
                "assessment": assess_ltv_cac(ratio),
            }

        segment_results.append(seg_result)
        weighted_clv += clv * seg["weight"]
        weighted_npv += clv_npv * seg["weight"]
        total_weight += seg["weight"]

    # Normalise if weights don't sum to 1
    if total_weight > 0 and abs(total_weight - 1.0) > 0.001:
        weighted_clv /= total_weight
        weighted_npv /= total_weight

    output = {
        "model": "cohort",
        "weighted_clv": round(weighted_clv, 2),
        "weighted_clv_npv": round(weighted_npv, 2),
        "inputs": {
            "margin_percent": margin,
            "discount_rate_percent": discount,
            "total_segments": len(segments),
            "total_weight": round(total_weight, 4),
        },
        "segments": segment_results,
        "cac_analysis": None,
        "benchmarks": {
            "ltv_cac_healthy_minimum": 3.0,
            "ltv_cac_excellent_threshold": 5.0,
            "payback_healthy_maximum_months": 12,
        },
    }

    if args.cac is not None and args.cac > 0:
        ratio = weighted_clv / args.cac
        output["cac_analysis"] = {
            "cac": args.cac,
            "ltv_cac_ratio": round(ratio, 2),
            "assessment": assess_ltv_cac(ratio),
        }

    return output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Customer lifetime value calculator with multiple models"
    )
    parser.add_argument(
        "--model", default="simple", choices=["simple", "cohort", "contractual"],
        help="Calculation model (default: simple)",
    )
    parser.add_argument(
        "--avg-purchase-value", type=float, default=None,
        help="Average purchase/order value",
    )
    parser.add_argument(
        "--purchase-frequency", type=float, default=None,
        help="Average purchases per year",
    )
    parser.add_argument(
        "--customer-lifespan", type=float, default=None,
        help="Average customer lifespan in years",
    )
    parser.add_argument(
        "--margin", type=float, default=100,
        help="Gross margin percentage (default: 100 = use revenue directly)",
    )
    parser.add_argument(
        "--discount-rate", type=float, default=10,
        help="Annual discount rate for NPV (default: 10)",
    )
    parser.add_argument(
        "--monthly-revenue", type=float, default=None,
        help="Monthly subscription revenue (contractual model)",
    )
    parser.add_argument(
        "--churn-rate", type=float, default=None,
        help="Monthly churn rate, e.g. 0.05 for 5%% (contractual model)",
    )
    parser.add_argument(
        "--cac", type=float, default=None,
        help="Customer acquisition cost (for LTV:CAC ratio)",
    )
    parser.add_argument(
        "--segments", default=None,
        help="JSON array of segment objects (cohort model)",
    )
    args = parser.parse_args()

    # --- Validation ---
    if args.margin <= 0 or args.margin > 100:
        json.dump({"error": "margin must be between 0 (exclusive) and 100 (inclusive)"}, sys.stdout, indent=2)
        print()
        sys.exit(2)

    if args.discount_rate < 0:
        json.dump({"error": "discount-rate must be non-negative"}, sys.stdout, indent=2)
        print()
        sys.exit(2)

    if args.cac is not None and args.cac < 0:
        json.dump({"error": "cac must be non-negative"}, sys.stdout, indent=2)
        print()
        sys.exit(2)

    # --- Run selected model ---
    if args.model == "simple":
        output = run_simple(args)
    elif args.model == "contractual":
        output = run_contractual(args)
    elif args.model == "cohort":
        output = run_cohort(args)
    else:
        output = {"error": f"Unknown model: {args.model}"}

    json.dump(output, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
