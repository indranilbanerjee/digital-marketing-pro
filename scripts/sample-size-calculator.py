#!/usr/bin/env python3
"""
sample-size-calculator.py
=========================
Calculate A/B test sample size requirements using the two-proportion Z-test
formula. Returns per-variant sample sizes, total sample needed, and optional
duration estimates based on daily traffic.

Dependencies: none (stdlib only)

Usage:
    python sample-size-calculator.py --baseline-rate 0.03 --mde 0.005
    python sample-size-calculator.py --baseline-rate 0.03 --mde 0.005 --daily-traffic 5000
    python sample-size-calculator.py --baseline-rate 0.10 --mde 0.02 --significance 0.99 --power 0.90 --variants 3
"""

import argparse
import json
import math
import sys


def inverse_normal_cdf(p):
    """Rational approximation for the inverse standard normal CDF.

    Uses the Abramowitz and Stegun formula 26.2.23.
    Accurate to approximately 4.5e-4.
    """
    if p <= 0 or p >= 1:
        raise ValueError("p must be between 0 and 1 exclusive")
    if p < 0.5:
        return -inverse_normal_cdf(1 - p)
    t = math.sqrt(-2.0 * math.log(1.0 - p))
    c0, c1, c2 = 2.515517, 0.802853, 0.010328
    d1, d2, d3 = 1.432788, 0.189269, 0.001308
    return t - (c0 + c1 * t + c2 * t * t) / (1.0 + d1 * t + d2 * t * t + d3 * t * t * t)


def calculate_sample_size(baseline_rate, mde, significance, power):
    """Calculate required sample size per variant using the two-proportion Z-test.

    Parameters:
        baseline_rate: current conversion rate (0 < x < 1)
        mde: minimum detectable effect as absolute change
        significance: confidence level (e.g. 0.95)
        power: statistical power (e.g. 0.80)

    Returns:
        sample size per variant (integer, rounded up)
    """
    alpha = 1.0 - significance
    z_alpha = inverse_normal_cdf(1.0 - alpha / 2.0)
    z_beta = inverse_normal_cdf(power)

    p1 = baseline_rate
    p2 = baseline_rate + mde

    numerator = (z_alpha + z_beta) ** 2 * (p1 * (1 - p1) + p2 * (1 - p2))
    denominator = (p2 - p1) ** 2

    return math.ceil(numerator / denominator)


def build_recommendations(baseline_rate, mde, sample_per_variant, total_sample, daily_traffic, estimated_days, variants):
    """Generate actionable recommendations based on the calculation."""
    recs = []

    if daily_traffic and estimated_days:
        recs.append(
            f"With {daily_traffic:,} daily visitors split across {variants} variants, "
            f"expect the test to run approximately {estimated_days:,} days."
        )
        if estimated_days > 30:
            recs.append(
                "Test duration exceeds 30 days. Consider increasing the MDE threshold "
                "or focusing on higher-traffic pages to shorten the experiment."
            )
        if estimated_days > 90:
            recs.append(
                "Warning: tests running longer than 90 days risk seasonal bias and "
                "external confounders. Re-evaluate whether this test is feasible."
            )

    relative_lift = mde / baseline_rate * 100
    if relative_lift < 5:
        recs.append(
            f"A {relative_lift:.1f}% relative lift is very small. Detecting such a "
            "subtle change requires a large sample. Consider whether a larger effect "
            "size would be more practical to test."
        )

    if sample_per_variant > 100000:
        recs.append(
            "The required sample size is very large. Consider testing bolder changes "
            "with a higher expected impact to reduce the required sample."
        )

    if baseline_rate < 0.01:
        recs.append(
            "Low baseline conversion rates require significantly more traffic. "
            "Consider micro-conversion metrics (e.g., clicks, scroll depth) as "
            "proxy goals to detect changes faster."
        )

    if not recs:
        recs.append(
            "Sample size requirements look reasonable. Ensure even traffic "
            "splitting and avoid peeking at results before reaching the target."
        )

    return recs


def main():
    parser = argparse.ArgumentParser(
        description="Calculate A/B test sample size requirements"
    )
    parser.add_argument("--baseline-rate", type=float, required=True,
                        help="Current conversion rate (e.g. 0.03 for 3%%)")
    parser.add_argument("--mde", type=float, required=True,
                        help="Minimum detectable effect — absolute change (e.g. 0.005 for +0.5%%)")
    parser.add_argument("--significance", type=float, default=0.95,
                        help="Confidence level (default: 0.95)")
    parser.add_argument("--power", type=float, default=0.80,
                        help="Statistical power (default: 0.80)")
    parser.add_argument("--daily-traffic", type=int, default=None,
                        help="Daily visitors for duration estimate")
    parser.add_argument("--variants", type=int, default=2,
                        help="Number of variants including control (default: 2)")
    args = parser.parse_args()

    # --- Validation ---
    if not (0 < args.baseline_rate < 1):
        json.dump({"error": "baseline-rate must be between 0 and 1 exclusive"}, sys.stdout, indent=2)
        print()
        sys.exit(1)

    if args.mde <= 0:
        json.dump({"error": "mde must be greater than 0"}, sys.stdout, indent=2)
        print()
        sys.exit(1)

    if args.baseline_rate + args.mde >= 1:
        json.dump({"error": "baseline-rate + mde must be less than 1"}, sys.stdout, indent=2)
        print()
        sys.exit(1)

    if not (0.5 < args.significance < 0.999):
        json.dump({"error": "significance must be between 0.5 and 0.999 exclusive"}, sys.stdout, indent=2)
        print()
        sys.exit(1)

    if not (0.5 < args.power < 0.999):
        json.dump({"error": "power must be between 0.5 and 0.999 exclusive"}, sys.stdout, indent=2)
        print()
        sys.exit(1)

    if args.variants < 2:
        json.dump({"error": "variants must be at least 2"}, sys.stdout, indent=2)
        print()
        sys.exit(1)

    if args.daily_traffic is not None and args.daily_traffic <= 0:
        json.dump({"error": "daily-traffic must be a positive integer"}, sys.stdout, indent=2)
        print()
        sys.exit(1)

    # --- Calculation ---
    sample_per_variant = calculate_sample_size(
        args.baseline_rate, args.mde, args.significance, args.power
    )
    total_sample = sample_per_variant * args.variants

    relative_lift = (args.mde / args.baseline_rate) * 100

    estimated_days = None
    if args.daily_traffic:
        visitors_per_variant_per_day = args.daily_traffic / args.variants
        estimated_days = math.ceil(sample_per_variant / visitors_per_variant_per_day)

    recommendations = build_recommendations(
        args.baseline_rate, args.mde, sample_per_variant, total_sample,
        args.daily_traffic, estimated_days, args.variants
    )

    # --- Output ---
    output = {
        "baseline_rate": args.baseline_rate,
        "minimum_detectable_effect": args.mde,
        "target_rate": round(args.baseline_rate + args.mde, 6),
        "relative_lift": f"{relative_lift:.1f}%",
        "significance_level": args.significance,
        "statistical_power": args.power,
        "sample_size_per_variant": sample_per_variant,
        "total_sample_needed": total_sample,
        "variants": args.variants,
        "methodology": "Two-proportion Z-test",
        "recommendations": recommendations,
    }

    if args.daily_traffic:
        output["daily_traffic"] = args.daily_traffic
        output["estimated_days"] = estimated_days

    json.dump(output, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
