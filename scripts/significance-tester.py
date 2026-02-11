#!/usr/bin/env python3
"""
significance-tester.py
======================
Test A/B experiment results for statistical significance using both a
two-proportion Z-test and a Chi-squared test. Returns p-values, confidence
intervals, and an actionable recommendation.

Dependencies: none (stdlib only)

Usage:
    python significance-tester.py --control-visitors 10000 --control-conversions 300 \\
                                  --variant-visitors 10000 --variant-conversions 350
    python significance-tester.py --control-visitors 5000 --control-conversions 150 \\
                                  --variant-visitors 5000 --variant-conversions 190 --confidence 0.99
"""

import argparse
import json
import math
import sys


# ---------------------------------------------------------------------------
# Statistical helper functions (stdlib only, no scipy)
# ---------------------------------------------------------------------------

def normal_cdf(x):
    """Standard normal CDF approximation (Abramowitz & Stegun 26.2.17)."""
    if x < 0:
        return 1.0 - normal_cdf(-x)
    t = 1.0 / (1.0 + 0.2316419 * x)
    coeffs = [0.319381530, -0.356563782, 1.781477937, -1.821255978, 1.330274429]
    poly = sum(c * t ** (i + 1) for i, c in enumerate(coeffs))
    return 1.0 - poly * math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def inverse_normal_cdf(p):
    """Rational approximation for the inverse standard normal CDF.

    Abramowitz and Stegun formula 26.2.23. Accurate to ~4.5e-4.
    """
    if p <= 0 or p >= 1:
        raise ValueError("p must be between 0 and 1 exclusive")
    if p < 0.5:
        return -inverse_normal_cdf(1 - p)
    t = math.sqrt(-2.0 * math.log(1.0 - p))
    c0, c1, c2 = 2.515517, 0.802853, 0.010328
    d1, d2, d3 = 1.432788, 0.189269, 0.001308
    return t - (c0 + c1 * t + c2 * t * t) / (1.0 + d1 * t + d2 * t * t + d3 * t * t * t)


def chi2_cdf_df1(x):
    """CDF of chi-squared distribution with 1 degree of freedom.

    Uses the relationship: chi2(1) CDF = 2 * Phi(sqrt(x)) - 1
    where Phi is the standard normal CDF.
    """
    if x <= 0:
        return 0.0
    return 2 * normal_cdf(math.sqrt(x)) - 1


# ---------------------------------------------------------------------------
# Core test functions
# ---------------------------------------------------------------------------

def z_test_two_proportions(c_vis, c_conv, v_vis, v_conv):
    """Two-proportion Z-test for comparing conversion rates.

    Returns:
        dict with z_statistic, p_value (two-tailed)
    """
    c_rate = c_conv / c_vis
    v_rate = v_conv / v_vis
    pooled_p = (c_conv + v_conv) / (c_vis + v_vis)
    se = math.sqrt(pooled_p * (1 - pooled_p) * (1.0 / c_vis + 1.0 / v_vis))

    if se == 0:
        return {"z_statistic": 0.0, "p_value": 1.0}

    z = (v_rate - c_rate) / se
    p_value = 2 * (1 - normal_cdf(abs(z)))

    return {
        "z_statistic": round(z, 4),
        "p_value": round(p_value, 6),
    }


def chi_squared_test(c_vis, c_conv, v_vis, v_conv):
    """Chi-squared test for 2x2 contingency table.

    Observed:
        [[c_conv, c_vis - c_conv],
         [v_conv, v_vis - v_conv]]

    Returns:
        dict with chi2_statistic, p_value
    """
    observed = [
        [c_conv, c_vis - c_conv],
        [v_conv, v_vis - v_conv],
    ]
    n = c_vis + v_vis
    row_totals = [c_vis, v_vis]
    col_totals = [c_conv + v_conv, (c_vis - c_conv) + (v_vis - v_conv)]

    chi2 = 0.0
    for i in range(2):
        for j in range(2):
            expected = row_totals[i] * col_totals[j] / n
            if expected == 0:
                continue
            chi2 += (observed[i][j] - expected) ** 2 / expected

    p_value = 1.0 - chi2_cdf_df1(chi2)

    return {
        "chi2_statistic": round(chi2, 4),
        "p_value": round(p_value, 6),
    }


def confidence_interval_for_diff(c_vis, c_conv, v_vis, v_conv, confidence):
    """Compute confidence interval for the difference in proportions.

    Uses the Wald method: (p2 - p1) +/- z * SE
    where SE = sqrt(p1*(1-p1)/n1 + p2*(1-p2)/n2).
    """
    c_rate = c_conv / c_vis
    v_rate = v_conv / v_vis
    diff = v_rate - c_rate

    se = math.sqrt(c_rate * (1 - c_rate) / c_vis + v_rate * (1 - v_rate) / v_vis)
    z = inverse_normal_cdf(1.0 - (1.0 - confidence) / 2.0)

    lower = diff - z * se
    upper = diff + z * se

    return round(lower, 6), round(upper, 6)


def build_recommendation(c_rate, v_rate, z_significant, chi2_significant, confidence):
    """Generate a human-readable recommendation."""
    lift_abs = v_rate - c_rate
    lift_rel = (lift_abs / c_rate) * 100 if c_rate > 0 else 0

    if z_significant and chi2_significant:
        if lift_abs > 0:
            return (
                f"The variant shows a statistically significant improvement of "
                f"{lift_rel:.2f}% relative lift at the {confidence:.0%} confidence level. "
                f"Both the Z-test and Chi-squared test agree. Consider deploying the "
                f"variant, but monitor post-launch metrics to confirm sustained performance."
            )
        else:
            return (
                f"The variant shows a statistically significant decrease of "
                f"{abs(lift_rel):.2f}% relative to the control. Both tests agree. "
                f"Do not deploy this variant."
            )
    else:
        return (
            f"The difference between control ({c_rate:.2%}) and variant ({v_rate:.2%}) "
            f"is not statistically significant at the {confidence:.0%} confidence level. "
            f"Continue running the test to accumulate more data, or consider testing "
            f"a bolder change with a larger expected effect."
        )


def main():
    parser = argparse.ArgumentParser(
        description="Test A/B experiment results for statistical significance"
    )
    parser.add_argument("--control-visitors", type=int, required=True,
                        help="Control group total visitors")
    parser.add_argument("--control-conversions", type=int, required=True,
                        help="Control group conversions")
    parser.add_argument("--variant-visitors", type=int, required=True,
                        help="Variant group total visitors")
    parser.add_argument("--variant-conversions", type=int, required=True,
                        help="Variant group conversions")
    parser.add_argument("--confidence", type=float, default=0.95,
                        help="Desired confidence level (default: 0.95)")
    args = parser.parse_args()

    # --- Validation ---
    errors = []
    if args.control_visitors <= 0:
        errors.append("control-visitors must be a positive integer")
    if args.control_conversions < 0:
        errors.append("control-conversions must be non-negative")
    if args.variant_visitors <= 0:
        errors.append("variant-visitors must be a positive integer")
    if args.variant_conversions < 0:
        errors.append("variant-conversions must be non-negative")

    if errors:
        json.dump({"error": "; ".join(errors)}, sys.stdout, indent=2)
        print()
        sys.exit(1)

    if args.control_conversions > args.control_visitors:
        json.dump({"error": "control-conversions cannot exceed control-visitors"}, sys.stdout, indent=2)
        print()
        sys.exit(1)

    if args.variant_conversions > args.variant_visitors:
        json.dump({"error": "variant-conversions cannot exceed variant-visitors"}, sys.stdout, indent=2)
        print()
        sys.exit(1)

    if args.control_conversions < 1 or args.variant_conversions < 1:
        json.dump({"error": "Need at least 1 conversion in each group for a meaningful test"}, sys.stdout, indent=2)
        print()
        sys.exit(1)

    if not (0.5 < args.confidence < 0.999):
        json.dump({"error": "confidence must be between 0.5 and 0.999 exclusive"}, sys.stdout, indent=2)
        print()
        sys.exit(1)

    # --- Calculations ---
    c_vis = args.control_visitors
    c_conv = args.control_conversions
    v_vis = args.variant_visitors
    v_conv = args.variant_conversions

    c_rate = c_conv / c_vis
    v_rate = v_conv / v_vis
    lift_abs = v_rate - c_rate
    lift_rel = (lift_abs / c_rate) * 100 if c_rate > 0 else 0

    z_result = z_test_two_proportions(c_vis, c_conv, v_vis, v_conv)
    chi2_result = chi_squared_test(c_vis, c_conv, v_vis, v_conv)

    alpha = 1.0 - args.confidence
    z_significant = z_result["p_value"] < alpha
    chi2_significant = chi2_result["p_value"] < alpha

    ci_lower, ci_upper = confidence_interval_for_diff(c_vis, c_conv, v_vis, v_conv, args.confidence)

    recommendation = build_recommendation(c_rate, v_rate, z_significant, chi2_significant, args.confidence)

    # --- Warnings ---
    warnings = []
    if c_vis < 100 or v_vis < 100:
        warnings.append("Very small sample size; results may be unreliable.")
    if c_rate < 0.005 or v_rate < 0.005:
        warnings.append("Very low conversion rates may reduce test reliability.")
    if abs(c_vis - v_vis) / max(c_vis, v_vis) > 0.2:
        warnings.append("Unbalanced group sizes detected (>20%% difference). Results are valid but power may be reduced.")
    if z_significant != chi2_significant:
        warnings.append("Z-test and Chi-squared test disagree on significance. The result is borderline; collect more data.")

    # --- Output ---
    output = {
        "control": {
            "visitors": c_vis,
            "conversions": c_conv,
            "rate": f"{c_rate:.2%}",
        },
        "variant": {
            "visitors": v_vis,
            "conversions": v_conv,
            "rate": f"{v_rate:.2%}",
        },
        "lift": {
            "absolute": f"{lift_abs:.2%}",
            "relative": f"{lift_rel:.2f}%",
        },
        "z_test": {
            "z_statistic": z_result["z_statistic"],
            "p_value": z_result["p_value"],
            "significant": z_significant,
        },
        "chi_squared_test": {
            "chi2_statistic": chi2_result["chi2_statistic"],
            "p_value": chi2_result["p_value"],
            "significant": chi2_significant,
        },
        "confidence_level": args.confidence,
        "confidence_interval": {
            "lower": f"{ci_lower:.2%}",
            "upper": f"{ci_upper:.2%}",
        },
        "recommendation": recommendation,
        "warnings": warnings,
    }

    json.dump(output, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
