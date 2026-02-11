#!/usr/bin/env python3
"""
adaptive-scorer.py
==================
Dynamic content scoring that adapts based on brand profile, industry benchmarks,
and past performance data. Wraps content-scorer.py with intelligence.

Usage:
    python adaptive-scorer.py --brand acme --text "Content..." --type blog --keyword "AI"
    python adaptive-scorer.py --brand acme --file article.md --type email
"""

import argparse
import json
import sys
from pathlib import Path

BRANDS_DIR = Path.home() / ".claude-marketing" / "brands"

# Industry-specific weight adjustments
# These modify the base content-scorer weights based on what matters most per industry
INDUSTRY_WEIGHT_MODS = {
    "healthcare": {"spam_filler": 0.25, "readability": 0.25, "cta": 0.10},
    "finance": {"spam_filler": 0.25, "readability": 0.20, "seo": 0.15},
    "technology": {"seo": 0.30, "structure": 0.20, "readability": 0.15},
    "ecommerce": {"cta": 0.30, "seo": 0.25, "length": 0.10},
    "education": {"readability": 0.30, "structure": 0.25, "seo": 0.15},
    "real_estate": {"seo": 0.25, "cta": 0.25, "readability": 0.15},
    "legal": {"readability": 0.15, "spam_filler": 0.25, "structure": 0.20},
    "saas": {"seo": 0.25, "cta": 0.25, "structure": 0.20},
    "agency": {"readability": 0.20, "seo": 0.20, "cta": 0.20},
    "nonprofit": {"readability": 0.25, "cta": 0.25, "spam_filler": 0.15},
}

# Business model scoring priorities
MODEL_WEIGHT_MODS = {
    "B2B_SaaS": {"seo": 0.25, "cta": 0.20, "structure": 0.20},
    "B2C_eCommerce": {"cta": 0.30, "seo": 0.25, "spam_filler": 0.15},
    "B2C_DTC": {"cta": 0.25, "readability": 0.20, "spam_filler": 0.15},
    "B2B_Services": {"readability": 0.20, "seo": 0.20, "structure": 0.25},
    "Local_Business": {"seo": 0.30, "cta": 0.20, "readability": 0.20},
    "Creator": {"readability": 0.25, "cta": 0.20, "spam_filler": 0.15},
    "Enterprise": {"structure": 0.25, "readability": 0.20, "seo": 0.20},
    "Non_Profit": {"readability": 0.25, "cta": 0.25, "spam_filler": 0.15},
}

# Goal-based adjustments
GOAL_WEIGHT_MODS = {
    "lead_generation": {"cta": +0.10, "seo": +0.05},
    "brand_awareness": {"readability": +0.10, "seo": +0.05},
    "conversion": {"cta": +0.15, "spam_filler": +0.05},
    "thought_leadership": {"readability": +0.10, "structure": +0.10},
    "traffic": {"seo": +0.15, "readability": +0.05},
    "engagement": {"readability": +0.10, "cta": +0.05},
    "retention": {"readability": +0.10, "cta": +0.05},
}


def load_brand_context(slug):
    """Load brand profile and past insights for adaptive scoring."""
    brand_dir = BRANDS_DIR / slug
    if not brand_dir.exists():
        return None, f"Brand '{slug}' not found."

    profile_path = brand_dir / "profile.json"
    if not profile_path.exists():
        return None, f"Brand profile not found for '{slug}'."

    try:
        profile = json.loads(profile_path.read_text())
    except json.JSONDecodeError:
        return None, f"Brand profile corrupted for '{slug}'."

    # Load past insights if available
    insights = []
    insights_path = brand_dir / "insights.json"
    if insights_path.exists():
        try:
            insights = json.loads(insights_path.read_text())
        except json.JSONDecodeError:
            pass

    return {"profile": profile, "insights": insights}, None


def compute_adaptive_weights(brand_context, content_type):
    """Compute scoring weights adapted to brand context."""
    # Start with base weights per content type
    base_weights = {
        "blog": {"readability": 0.20, "seo": 0.25, "structure": 0.20, "cta": 0.10, "spam_filler": 0.10, "length": 0.15},
        "email": {"readability": 0.25, "seo": 0.05, "structure": 0.15, "cta": 0.30, "spam_filler": 0.15, "length": 0.10},
        "ad": {"readability": 0.20, "seo": 0.10, "structure": 0.10, "cta": 0.35, "spam_filler": 0.15, "length": 0.10},
        "landing_page": {"readability": 0.15, "seo": 0.25, "structure": 0.20, "cta": 0.25, "spam_filler": 0.05, "length": 0.10},
        "social": {"readability": 0.25, "seo": 0.05, "structure": 0.10, "cta": 0.25, "spam_filler": 0.20, "length": 0.15},
    }

    weights = dict(base_weights.get(content_type, base_weights["blog"]))
    adjustments_applied = []

    profile = brand_context.get("profile", {})

    # Apply industry adjustments
    industry = profile.get("industry", {}).get("primary", "").lower().replace(" ", "_")
    if industry in INDUSTRY_WEIGHT_MODS:
        mods = INDUSTRY_WEIGHT_MODS[industry]
        for dim, val in mods.items():
            if dim in weights:
                weights[dim] = val
        adjustments_applied.append(f"industry:{industry}")

    # Apply business model adjustments
    biz_model = profile.get("business_model", {}).get("type", "")
    if biz_model in MODEL_WEIGHT_MODS:
        mods = MODEL_WEIGHT_MODS[biz_model]
        # Blend: 60% industry-adjusted + 40% model-based
        for dim, val in mods.items():
            if dim in weights:
                weights[dim] = weights[dim] * 0.6 + val * 0.4
        adjustments_applied.append(f"model:{biz_model}")

    # Apply goal adjustments
    goal = profile.get("goals", {}).get("primary_objective", "").lower().replace(" ", "_")
    if goal in GOAL_WEIGHT_MODS:
        mods = GOAL_WEIGHT_MODS[goal]
        for dim, delta in mods.items():
            if dim in weights:
                weights[dim] = min(weights[dim] + delta, 0.50)
        adjustments_applied.append(f"goal:{goal}")

    # Regulated industry boost: increase spam_filler weight for compliance
    if profile.get("industry", {}).get("regulated", False):
        weights["spam_filler"] = min(weights.get("spam_filler", 0.10) + 0.10, 0.35)
        adjustments_applied.append("regulated:+spam_check")

    # Normalize weights to sum to 1.0
    total = sum(weights.values())
    if total > 0:
        weights = {k: round(v / total, 4) for k, v in weights.items()}

    return weights, adjustments_applied


def main():
    parser = argparse.ArgumentParser(description="Adaptive content scoring for Digital Marketing Pro")
    parser.add_argument("--brand", required=True, help="Brand slug")
    parser.add_argument("--type", dest="content_type", required=True,
                        choices=["blog", "email", "ad", "landing_page", "social"],
                        help="Content type")
    parser.add_argument("--text", help="Content text (inline)")
    parser.add_argument("--file", help="Path to content file")
    parser.add_argument("--keyword", help="Primary SEO keyword")
    parser.add_argument("--weights-only", action="store_true",
                        help="Only output the computed adaptive weights")
    args = parser.parse_args()

    # Load brand context
    brand_context, err = load_brand_context(args.brand)
    if err:
        print(json.dumps({"error": err}))
        sys.exit(1)

    # Compute adaptive weights
    weights, adjustments = compute_adaptive_weights(brand_context, args.content_type)

    if args.weights_only:
        json.dump({
            "brand": args.brand,
            "content_type": args.content_type,
            "adaptive_weights": weights,
            "adjustments_applied": adjustments,
        }, sys.stdout, indent=2)
        print()
        return

    # For full scoring, delegate to content-scorer with adaptive weights
    # Output the weights for the caller (Claude) to use when interpreting scores
    if not args.text and not args.file:
        print(json.dumps({"error": "Provide --text or --file"}))
        sys.exit(1)

    text = args.text or ""
    if args.file:
        fpath = Path(args.file)
        if not fpath.exists():
            print(json.dumps({"error": f"File not found: {args.file}"}))
            sys.exit(1)
        text = fpath.read_text(encoding="utf-8")

    json.dump({
        "brand": args.brand,
        "content_type": args.content_type,
        "adaptive_weights": weights,
        "adjustments_applied": adjustments,
        "text_length": len(text),
        "word_count": len(text.split()),
        "note": "Use these weights with content-scorer.py results for brand-adaptive scoring. Multiply each dimension score by the adaptive weight instead of the default weight.",
    }, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
