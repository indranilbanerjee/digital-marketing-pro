#!/usr/bin/env python3
"""Recommend optimal social media posting times by platform, industry, and audience.

Combines platform-specific engagement benchmarks with industry modifiers and
audience type filters to produce ranked posting-time recommendations with
confidence levels, rationale, and avoidance windows.

Usage:
    python posting-time-analyzer.py --platform instagram
    python posting-time-analyzer.py --platform linkedin --industry saas --audience-type b2b
    python posting-time-analyzer.py --platform tiktok --industry ecommerce --audience-type b2c
"""

import argparse
import json
import sys

# ---------------------------------------------------------------------------
# Benchmark data: platform -> audience_type -> ranked time slots
# ---------------------------------------------------------------------------

PLATFORM_BENCHMARKS = {
    "instagram": {
        "b2b": [
            {"day": "Tuesday", "time": "10:00-12:00", "rationale": "Professional browsing during work breaks", "confidence": "high"},
            {"day": "Wednesday", "time": "11:00-13:00", "rationale": "Mid-week engagement peak", "confidence": "high"},
            {"day": "Thursday", "time": "14:00-16:00", "rationale": "Afternoon scroll sessions", "confidence": "medium"},
        ],
        "b2c": [
            {"day": "Saturday", "time": "10:00-12:00", "rationale": "Weekend leisure browsing", "confidence": "high"},
            {"day": "Wednesday", "time": "11:00-13:00", "rationale": "Mid-week break engagement", "confidence": "high"},
            {"day": "Friday", "time": "11:00-13:00", "rationale": "Pre-weekend scrolling", "confidence": "medium"},
        ],
        "mixed": [
            {"day": "Wednesday", "time": "11:00-13:00", "rationale": "Peak engagement across all audiences", "confidence": "high"},
            {"day": "Tuesday", "time": "10:00-12:00", "rationale": "Strong weekday reach", "confidence": "high"},
            {"day": "Saturday", "time": "10:00-12:00", "rationale": "Weekend discovery window", "confidence": "medium"},
        ],
    },
    "linkedin": {
        "b2b": [
            {"day": "Tuesday", "time": "08:00-10:00", "rationale": "Morning professional check-in", "confidence": "high"},
            {"day": "Wednesday", "time": "09:00-11:00", "rationale": "Mid-week business hours peak", "confidence": "high"},
            {"day": "Thursday", "time": "10:00-12:00", "rationale": "Late-week thought leadership window", "confidence": "medium"},
        ],
        "b2c": [
            {"day": "Tuesday", "time": "10:00-12:00", "rationale": "Professionals exploring non-work content", "confidence": "medium"},
            {"day": "Wednesday", "time": "12:00-14:00", "rationale": "Lunch-break scrolling", "confidence": "medium"},
            {"day": "Thursday", "time": "09:00-11:00", "rationale": "Pre-weekend professional browsing", "confidence": "medium"},
        ],
        "mixed": [
            {"day": "Tuesday", "time": "09:00-11:00", "rationale": "Broad professional engagement window", "confidence": "high"},
            {"day": "Wednesday", "time": "10:00-12:00", "rationale": "Mid-week high-activity hours", "confidence": "high"},
            {"day": "Thursday", "time": "08:00-10:00", "rationale": "Early morning decision-maker window", "confidence": "medium"},
        ],
    },
    "twitter": {
        "b2b": [
            {"day": "Monday", "time": "09:00-11:00", "rationale": "Week kickoff news and updates", "confidence": "high"},
            {"day": "Wednesday", "time": "12:00-14:00", "rationale": "Lunch-hour engagement spike", "confidence": "high"},
            {"day": "Thursday", "time": "09:00-11:00", "rationale": "Active industry conversation window", "confidence": "medium"},
        ],
        "b2c": [
            {"day": "Friday", "time": "12:00-15:00", "rationale": "Pre-weekend casual browsing", "confidence": "high"},
            {"day": "Saturday", "time": "09:00-12:00", "rationale": "Weekend morning engagement", "confidence": "high"},
            {"day": "Wednesday", "time": "12:00-14:00", "rationale": "Mid-week break scrolling", "confidence": "medium"},
        ],
        "mixed": [
            {"day": "Wednesday", "time": "12:00-14:00", "rationale": "Consistent mid-week engagement", "confidence": "high"},
            {"day": "Monday", "time": "09:00-11:00", "rationale": "Start-of-week catch-up", "confidence": "high"},
            {"day": "Friday", "time": "12:00-15:00", "rationale": "Pre-weekend wind-down browsing", "confidence": "medium"},
        ],
    },
    "tiktok": {
        "b2b": [
            {"day": "Tuesday", "time": "10:00-12:00", "rationale": "Professional content discovery window", "confidence": "medium"},
            {"day": "Thursday", "time": "12:00-15:00", "rationale": "Afternoon creative browsing", "confidence": "medium"},
            {"day": "Wednesday", "time": "14:00-17:00", "rationale": "Mid-week engagement for educational content", "confidence": "medium"},
        ],
        "b2c": [
            {"day": "Thursday", "time": "19:00-21:00", "rationale": "Prime evening scroll time", "confidence": "high"},
            {"day": "Friday", "time": "17:00-19:00", "rationale": "After-work entertainment browsing", "confidence": "high"},
            {"day": "Saturday", "time": "11:00-14:00", "rationale": "Weekend binge-scroll window", "confidence": "high"},
        ],
        "mixed": [
            {"day": "Thursday", "time": "18:00-21:00", "rationale": "Evening peak across all demographics", "confidence": "high"},
            {"day": "Friday", "time": "17:00-19:00", "rationale": "Start-of-weekend entertainment window", "confidence": "high"},
            {"day": "Tuesday", "time": "10:00-12:00", "rationale": "Daytime discovery for diverse content", "confidence": "medium"},
        ],
    },
    "facebook": {
        "b2b": [
            {"day": "Wednesday", "time": "09:00-11:00", "rationale": "Mid-week business page engagement", "confidence": "high"},
            {"day": "Tuesday", "time": "10:00-12:00", "rationale": "Professional networking window", "confidence": "high"},
            {"day": "Thursday", "time": "13:00-15:00", "rationale": "Afternoon content consumption", "confidence": "medium"},
        ],
        "b2c": [
            {"day": "Friday", "time": "12:00-15:00", "rationale": "Pre-weekend casual engagement", "confidence": "high"},
            {"day": "Saturday", "time": "10:00-13:00", "rationale": "Weekend morning browsing", "confidence": "high"},
            {"day": "Wednesday", "time": "11:00-13:00", "rationale": "Mid-week social break", "confidence": "medium"},
        ],
        "mixed": [
            {"day": "Wednesday", "time": "11:00-13:00", "rationale": "Broad mid-week engagement", "confidence": "high"},
            {"day": "Friday", "time": "12:00-15:00", "rationale": "End-of-week content discovery", "confidence": "high"},
            {"day": "Tuesday", "time": "10:00-12:00", "rationale": "Steady weekday reach", "confidence": "medium"},
        ],
    },
    "pinterest": {
        "b2b": [
            {"day": "Tuesday", "time": "14:00-16:00", "rationale": "Afternoon inspiration browsing", "confidence": "medium"},
            {"day": "Wednesday", "time": "13:00-15:00", "rationale": "Mid-week planning and pinning", "confidence": "medium"},
            {"day": "Thursday", "time": "15:00-17:00", "rationale": "Pre-weekend project planning", "confidence": "medium"},
        ],
        "b2c": [
            {"day": "Saturday", "time": "20:00-23:00", "rationale": "Evening inspiration and planning", "confidence": "high"},
            {"day": "Sunday", "time": "14:00-17:00", "rationale": "Weekend project planning sessions", "confidence": "high"},
            {"day": "Friday", "time": "15:00-18:00", "rationale": "Pre-weekend discovery browsing", "confidence": "high"},
        ],
        "mixed": [
            {"day": "Saturday", "time": "20:00-23:00", "rationale": "Peak evening pinning activity", "confidence": "high"},
            {"day": "Friday", "time": "15:00-18:00", "rationale": "End-of-week inspiration window", "confidence": "high"},
            {"day": "Sunday", "time": "14:00-17:00", "rationale": "Weekend project and idea curation", "confidence": "medium"},
        ],
    },
    "youtube": {
        "b2b": [
            {"day": "Tuesday", "time": "09:00-11:00", "rationale": "Morning professional learning window", "confidence": "high"},
            {"day": "Wednesday", "time": "14:00-16:00", "rationale": "Afternoon educational content consumption", "confidence": "high"},
            {"day": "Thursday", "time": "10:00-12:00", "rationale": "Mid-week how-to and tutorial viewing", "confidence": "medium"},
        ],
        "b2c": [
            {"day": "Friday", "time": "15:00-18:00", "rationale": "Pre-weekend entertainment ramp-up", "confidence": "high"},
            {"day": "Saturday", "time": "09:00-12:00", "rationale": "Weekend morning viewing sessions", "confidence": "high"},
            {"day": "Sunday", "time": "17:00-20:00", "rationale": "Sunday evening entertainment peak", "confidence": "high"},
        ],
        "mixed": [
            {"day": "Friday", "time": "15:00-18:00", "rationale": "Broad audience pre-weekend peak", "confidence": "high"},
            {"day": "Wednesday", "time": "14:00-16:00", "rationale": "Mid-week content consumption", "confidence": "high"},
            {"day": "Saturday", "time": "09:00-12:00", "rationale": "Weekend morning viewing", "confidence": "medium"},
        ],
    },
    "threads": {
        "b2b": [
            {"day": "Tuesday", "time": "09:00-11:00", "rationale": "Morning professional conversation window", "confidence": "medium"},
            {"day": "Wednesday", "time": "12:00-14:00", "rationale": "Lunch-break engagement", "confidence": "medium"},
            {"day": "Thursday", "time": "10:00-12:00", "rationale": "Late-week discussion peak", "confidence": "medium"},
        ],
        "b2c": [
            {"day": "Wednesday", "time": "12:00-14:00", "rationale": "Mid-week casual conversation", "confidence": "high"},
            {"day": "Friday", "time": "11:00-14:00", "rationale": "Pre-weekend social engagement", "confidence": "high"},
            {"day": "Saturday", "time": "10:00-12:00", "rationale": "Weekend morning scrolling", "confidence": "medium"},
        ],
        "mixed": [
            {"day": "Wednesday", "time": "12:00-14:00", "rationale": "Consistent mid-week activity", "confidence": "high"},
            {"day": "Friday", "time": "11:00-14:00", "rationale": "End-of-week social wind-down", "confidence": "high"},
            {"day": "Tuesday", "time": "09:00-11:00", "rationale": "Early-week catch-up browsing", "confidence": "medium"},
        ],
    },
}

# ---------------------------------------------------------------------------
# Industry modifiers
# ---------------------------------------------------------------------------

INDUSTRY_MODIFIERS = {
    "saas": {
        "peak_days": ["Tuesday", "Wednesday", "Thursday"],
        "avoid": ["Saturday", "Sunday"],
        "note": "SaaS audiences are most active on weekdays during business hours. Decision-makers engage heavily Tuesday through Thursday.",
    },
    "ecommerce": {
        "peak_days": ["Friday", "Saturday", "Sunday"],
        "avoid": [],
        "note": "E-commerce peaks around weekends and paydays. Friday evening through Sunday drives the most purchase-intent engagement.",
    },
    "healthcare": {
        "peak_days": ["Tuesday", "Wednesday"],
        "avoid": ["Friday", "Saturday"],
        "note": "Healthcare audiences prefer mid-week educational content. Avoid weekend posts unless targeting patients directly.",
    },
    "finance": {
        "peak_days": ["Monday", "Tuesday", "Wednesday"],
        "avoid": ["Saturday", "Sunday"],
        "note": "Finance content performs best early in the week when markets are active and professionals are planning.",
    },
    "education": {
        "peak_days": ["Monday", "Tuesday", "Wednesday"],
        "avoid": ["Friday", "Saturday"],
        "note": "Educators and students engage most at the start of the week. Avoid late-week posts when attention shifts to weekend plans.",
    },
    "technology": {
        "peak_days": ["Tuesday", "Wednesday", "Thursday"],
        "avoid": ["Sunday"],
        "note": "Tech professionals are most active mid-week. Developer communities peak on Tuesday and Wednesday.",
    },
    "real_estate": {
        "peak_days": ["Thursday", "Friday", "Saturday"],
        "avoid": ["Monday"],
        "note": "Real estate engagement peaks late in the week as buyers plan weekend viewings.",
    },
    "professional_services": {
        "peak_days": ["Tuesday", "Wednesday", "Thursday"],
        "avoid": ["Saturday", "Sunday"],
        "note": "Professional services audiences mirror standard business hours with mid-week peaks.",
    },
    "nonprofit": {
        "peak_days": ["Tuesday", "Thursday"],
        "avoid": [],
        "note": "Nonprofit engagement is strong on Tuesdays (Giving Tuesday effect) and Thursdays. Weekend posts can work for awareness campaigns.",
    },
    "general": {
        "peak_days": [],
        "avoid": [],
        "note": "No industry-specific adjustments applied. Recommendations are based on general platform engagement data.",
    },
}


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def build_recommendations(platform, audience_type, industry):
    """Build ranked posting-time recommendations with industry adjustments."""
    slots = PLATFORM_BENCHMARKS[platform][audience_type]
    modifier = INDUSTRY_MODIFIERS[industry]

    ranked = []
    for i, slot in enumerate(slots):
        entry = {
            "rank": i + 1,
            "day": slot["day"],
            "time_window": slot["time"],
            "rationale": slot["rationale"],
            "confidence": slot["confidence"],
        }
        # Boost or lower confidence based on industry peak days
        if modifier["peak_days"] and slot["day"] in modifier["peak_days"]:
            entry["industry_boost"] = True
            if slot["confidence"] == "medium":
                entry["confidence"] = "high"
        if modifier["avoid"] and slot["day"] in modifier["avoid"]:
            entry["industry_warning"] = f"{industry} audiences are typically less active on {slot['day']}s"
        ranked.append(entry)

    # Re-sort: industry-boosted slots rise in rank
    ranked.sort(key=lambda r: (
        0 if r.get("industry_boost") and not r.get("industry_warning") else 1,
        r["rank"],
    ))
    for i, entry in enumerate(ranked):
        entry["rank"] = i + 1

    return ranked


def build_avoid_times(platform, industry):
    """Compile times and days to avoid."""
    modifier = INDUSTRY_MODIFIERS[industry]
    avoid = []
    if modifier["avoid"]:
        for day in modifier["avoid"]:
            avoid.append(f"{day} (low {industry} engagement)")
    # Universal low-engagement windows
    avoid.append("Late evenings (after 22:00)")
    avoid.append("Early mornings (before 06:00)")
    return avoid


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    platforms = list(PLATFORM_BENCHMARKS.keys())
    industries = list(INDUSTRY_MODIFIERS.keys())

    parser = argparse.ArgumentParser(
        description="Recommend optimal social media posting times"
    )
    parser.add_argument(
        "--platform", required=True, choices=platforms,
        help="Target social media platform",
    )
    parser.add_argument(
        "--industry", default="general", choices=industries,
        help="Industry vertical (default: general)",
    )
    parser.add_argument(
        "--audience-type", default="mixed", choices=["b2b", "b2c", "mixed"],
        dest="audience_type",
        help="Audience type (default: mixed)",
    )
    args = parser.parse_args()

    recommendations = build_recommendations(args.platform, args.audience_type, args.industry)
    avoid_times = build_avoid_times(args.platform, args.industry)
    industry_note = INDUSTRY_MODIFIERS[args.industry]["note"]

    output = {
        "platform": args.platform,
        "industry": args.industry,
        "audience_type": args.audience_type,
        "recommendations": recommendations,
        "industry_notes": industry_note,
        "avoid_times": avoid_times,
        "methodology_note": "Based on aggregated engagement data from industry benchmarks",
        "data_last_updated": "2026-Q1",
    }

    json.dump(output, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
