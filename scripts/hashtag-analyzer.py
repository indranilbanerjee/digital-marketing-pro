#!/usr/bin/env python3
"""Analyze hashtags for social post effectiveness across platforms.

Scores hashtag sets on count, length, broad/niche mix, spam detection,
duplicates, variety, and platform-specific guidelines. Returns a 0-100
score with detailed per-hashtag analysis and actionable recommendations.

Usage:
    python hashtag-analyzer.py --hashtags '["marketing", "digitalmarketing", "seo"]' --platform instagram
    python hashtag-analyzer.py --hashtags "marketing, digital marketing, seo" --platform linkedin
    python hashtag-analyzer.py --hashtags "#marketing,#seo,#growth" --platform twitter
"""

import argparse
import json
import re
import sys

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PLATFORM_LIMITS = {
    "instagram": {"optimal_min": 5, "optimal_max": 15, "absolute_max": 30, "placement": "caption or first comment"},
    "linkedin": {"optimal_min": 3, "optimal_max": 5, "absolute_max": 5, "placement": "end of post"},
    "twitter": {"optimal_min": 1, "optimal_max": 3, "absolute_max": 5, "placement": "within text or end"},
    "tiktok": {"optimal_min": 3, "optimal_max": 5, "absolute_max": 5, "placement": "caption"},
    "threads": {"optimal_min": 1, "optimal_max": 3, "absolute_max": 5, "placement": "within text"},
    "facebook": {"optimal_min": 1, "optimal_max": 3, "absolute_max": 10, "placement": "end of post"},
}

BANNED_HASHTAGS = {
    "followforfollow", "f4f", "follow4follow", "likeforlike", "l4l",
    "followback", "like4like", "instagood", "spam4spam", "followme",
    "like4follow", "follow4like", "gainwithxvicky", "gaintrick",
    "gaintrain", "teamfollowback", "ifb", "sfs", "s4s", "follow",
    "likes", "instalike", "instadaily", "photooftheday", "picoftheday",
    "likeforlikes", "followforfollowback", "likesforlike", "pleasefollow",
    "gainpost",
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def parse_hashtags(raw):
    """Accept JSON array or comma-separated string, return list of clean tags."""
    raw = raw.strip()
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, str):
            parsed = [parsed]
        elif not isinstance(parsed, list):
            return []
        tags = [str(t).strip() for t in parsed]
    except json.JSONDecodeError:
        tags = [t.strip() for t in raw.split(",")]

    # Normalize: strip leading # and whitespace, lowercase
    cleaned = []
    for tag in tags:
        tag = tag.strip().lstrip("#").strip()
        tag = re.sub(r"\s+", "", tag)  # remove inner spaces
        if tag:
            cleaned.append(tag.lower())
    return cleaned


def categorize_tag(tag):
    """Categorize hashtag by length heuristic: broad, medium, or niche."""
    length = len(tag)
    if length <= 10:
        return "broad"
    elif length <= 20:
        return "medium"
    else:
        return "niche"


def score_count(count, limits):
    """Score hashtag count vs platform optimal range (0-25)."""
    if count > limits["absolute_max"]:
        return 0
    if count == 0:
        return 0
    opt_min = limits["optimal_min"]
    opt_max = limits["optimal_max"]
    if opt_min <= count <= opt_max:
        return 25
    elif count < opt_min:
        ratio = count / max(opt_min, 1)
        return max(5, int(25 * ratio))
    else:
        # Between optimal_max and absolute_max
        overshoot = count - opt_max
        max_overshoot = limits["absolute_max"] - opt_max
        if max_overshoot == 0:
            return 25
        penalty_ratio = overshoot / max_overshoot
        return max(5, int(25 * (1 - penalty_ratio * 0.6)))


def score_lengths(tags):
    """Score individual hashtag lengths (0-20). Optimal: 5-25 chars each."""
    if not tags:
        return 0
    good = sum(1 for t in tags if 5 <= len(t) <= 25)
    return int(20 * (good / len(tags)))


def score_mix(categories):
    """Score broad/medium/niche mix (0-20). Ideal ~30% broad, 40% medium, 30% niche."""
    total = sum(categories.values())
    if total == 0:
        return 0
    broad_pct = categories.get("broad", 0) / total
    medium_pct = categories.get("medium", 0) / total
    niche_pct = categories.get("niche", 0) / total

    # Ideal: 0.3 broad, 0.4 medium, 0.3 niche
    broad_diff = abs(broad_pct - 0.3)
    medium_diff = abs(medium_pct - 0.4)
    niche_diff = abs(niche_pct - 0.3)
    avg_diff = (broad_diff + medium_diff + niche_diff) / 3

    # Perfect mix = 0 diff = 20 pts; worst = 0 pts
    return max(0, int(20 * (1 - avg_diff * 2.5)))


def score_variety(tags):
    """Score character variety (0-10). Penalize if all start with same prefix."""
    if len(tags) < 2:
        return 5
    # Check first 3 chars of each tag
    prefixes = [t[:3] for t in tags if len(t) >= 3]
    if not prefixes:
        return 5
    unique_prefixes = len(set(prefixes))
    ratio = unique_prefixes / len(prefixes)
    return max(0, int(10 * ratio))


def assess_mix(categories):
    """Return a human-readable mix assessment."""
    total = sum(categories.values())
    if total == 0:
        return "No hashtags to assess"
    broad_pct = categories.get("broad", 0) / total
    niche_pct = categories.get("niche", 0) / total
    if broad_pct > 0.6:
        return "Too many broad hashtags — add niche tags for better targeting"
    if niche_pct > 0.6:
        return "Heavily niche — add some broader tags for discoverability"
    if categories.get("medium", 0) == total:
        return "All medium-length — diversify with broad and niche tags"
    return "Good mix of broad, medium, and niche hashtags"


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def analyze_hashtags(tags, platform):
    """Analyze a list of hashtags for a given platform. Returns full result dict."""
    limits = PLATFORM_LIMITS[platform]

    # Per-tag analysis
    hashtag_analysis = []
    banned_count = 0
    categories = {"broad": 0, "medium": 0, "niche": 0}

    for tag in tags:
        cat = categorize_tag(tag)
        categories[cat] += 1
        is_banned = tag in BANNED_HASHTAGS
        if is_banned:
            banned_count += 1
        notes = []
        if len(tag) < 3:
            notes.append("Very short — may be too generic")
        if len(tag) > 30:
            notes.append("Very long — may reduce readability")
        if is_banned:
            notes.append("Known spam/engagement-bait hashtag")
        hashtag_analysis.append({
            "hashtag": f"#{tag}",
            "length": len(tag),
            "category": cat,
            "is_banned": is_banned,
            "notes": notes,
        })

    # Duplicate detection
    seen = set()
    duplicates = []
    for tag in tags:
        if tag in seen:
            duplicates.append(tag)
        seen.add(tag)
    unique_tags = list(dict.fromkeys(tags))  # preserve order, dedupe

    # Scoring components
    count_sc = score_count(len(tags), limits)
    length_sc = score_lengths(tags)
    mix_sc = score_mix(categories)
    spam_pen = banned_count * -15
    dup_pen = len(duplicates) * -10
    variety_sc = score_variety(unique_tags)
    platform_bonus = 10 if limits["optimal_min"] <= len(tags) <= limits["optimal_max"] else 3

    raw_score = count_sc + length_sc + mix_sc + spam_pen + dup_pen + variety_sc + platform_bonus
    total_score = max(0, min(100, raw_score))

    # Recommendations
    recommendations = []
    if len(tags) < limits["optimal_min"]:
        recommendations.append(f"Add more hashtags — {platform} performs best with {limits['optimal_min']}-{limits['optimal_max']}")
    if len(tags) > limits["optimal_max"]:
        recommendations.append(f"Reduce to {limits['optimal_max']} or fewer hashtags for {platform}")
    if categories.get("niche", 0) == 0 and len(tags) >= 3:
        recommendations.append("Add more niche hashtags specific to your content")
    if categories.get("broad", 0) == 0 and len(tags) >= 3:
        recommendations.append("Add 1-2 broad hashtags for wider discoverability")
    if limits["optimal_min"] <= len(tags) <= limits["optimal_max"]:
        recommendations.append(f"Good count for {platform}")

    # Warnings
    warnings = []
    if banned_count > 0:
        warnings.append(f"{banned_count} spam/banned hashtag(s) detected — remove to avoid shadowbanning")
    if len(duplicates) > 0:
        warnings.append(f"{len(duplicates)} duplicate hashtag(s): {', '.join('#' + d for d in duplicates)}")
    if len(tags) > limits["absolute_max"]:
        warnings.append(f"Exceeds {platform} maximum of {limits['absolute_max']} hashtags")

    return {
        "platform": platform,
        "hashtag_count": len(tags),
        "score": total_score,
        "breakdown": {
            "count_score": count_sc,
            "length_score": length_sc,
            "mix_score": mix_sc,
            "spam_penalty": spam_pen,
            "duplicate_penalty": dup_pen,
            "variety_score": variety_sc,
            "platform_bonus": platform_bonus,
        },
        "hashtag_analysis": hashtag_analysis,
        "mix": {
            "broad": categories["broad"],
            "medium": categories["medium"],
            "niche": categories["niche"],
            "assessment": assess_mix(categories),
        },
        "platform_guidelines": {
            "optimal_range": f"{limits['optimal_min']}-{limits['optimal_max']}",
            "max": limits["absolute_max"],
            "placement": limits["placement"],
        },
        "recommendations": recommendations,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Analyze hashtags for social post effectiveness"
    )
    parser.add_argument(
        "--hashtags", required=True,
        help='JSON array of hashtags OR comma-separated string (with or without #)',
    )
    parser.add_argument(
        "--platform", required=True,
        choices=list(PLATFORM_LIMITS.keys()),
        help="Target social media platform",
    )
    args = parser.parse_args()

    tags = parse_hashtags(args.hashtags)
    if not tags:
        json.dump({"error": "No valid hashtags provided"}, sys.stdout, indent=2)
        print()
        sys.exit(1)

    result = analyze_hashtags(tags, args.platform)
    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
