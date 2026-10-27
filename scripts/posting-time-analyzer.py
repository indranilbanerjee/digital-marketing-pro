#!/usr/bin/env python3
"""Recommend social posting times — the brand's own data first, dated population
baselines second, never a timeless table.

THE LADDER
----------
1. FIRST-PARTY (--history): the brand's own posts with timestamps and
   engagement. Population averages describe everyone's audience, which is no
   one's audience; only the brand's history can earn "high" confidence. The
   aggregation is honest statistics: minimum sample sizes per bucket, sample
   counts in the output, and a refusal to rank buckets it cannot support.
2. SHIPPED BASELINE: curated population windows, stamped with BASELINE_AS_OF
   and capped at MEDIUM confidence (a population average can never be high-
   confidence for a specific audience). The stamp AGES: past 180 days every
   output carries a re-verify warning; past 540 days the baseline REFUSES
   (exit 3) and instructs a live refresh or --history. A timing table that
   cannot expire is a 2024 opinion wearing a 2026 date.

WHY TIMING STILL MATTERS (2026): every major feed uses recency as a ranking
signal — engagement in the first 30-60 minutes seeds wider distribution — but
interest-ranked feeds (TikTok especially) have made WHAT you post dominate
WHEN you post it. Baseline windows are test starting points, not answers.

Usage:
    python posting-time-analyzer.py --platform instagram
    python posting-time-analyzer.py --platform linkedin --industry saas --audience-type b2b
    python posting-time-analyzer.py --platform instagram --history posts.json
      history format: [{"posted_at": "2026-07-03T11:20:00", "engagement": 412}, ...]
      (engagement = likes+comments+shares+saves, or any consistent metric)
"""

import argparse
import json
import sys

for _stream in (sys.stdout, sys.stderr):  # UTF-8 output, even where a Windows pipe defaults to cp1252
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

# Population baselines below were last re-verified against current published
# platform-engagement studies on this date. The suite fails when it ages out.
BASELINE_AS_OF = "2026-08-12"
BASELINE_WARN_DAYS = 180
BASELINE_STALE_DAYS = 540

# First-party statistical floors — below these the script says so rather than
# dressing noise up as insight.
MIN_TOTAL_POSTS = 30
MIN_BUCKET_POSTS = 5

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
            {"day": "Wednesday", "time": "07:00-09:00", "rationale": "Early-morning velocity window — engagement in the first hour seeds distribution (2026 published data)", "confidence": "high"},
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
            {"day": "Thursday", "time": "14:00-18:00", "rationale": "Weekday afternoon peak in 2026 published data", "confidence": "high"},
            {"day": "Friday", "time": "15:00-18:00", "rationale": "Pre-weekend afternoon scroll window", "confidence": "high"},
            {"day": "Saturday", "time": "11:00-14:00", "rationale": "Weekend binge-scroll window", "confidence": "medium"},
        ],
        "mixed": [
            {"day": "Thursday", "time": "14:00-18:00", "rationale": "Afternoon peak across demographics (2026 published data)", "confidence": "high"},
            {"day": "Friday", "time": "15:00-18:00", "rationale": "Start-of-weekend afternoon window", "confidence": "high"},
            {"day": "Tuesday", "time": "14:00-16:00", "rationale": "Weekday afternoon discovery", "confidence": "medium"},
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
# 2026 platform timing mechanics — WHY a window works, so the advice survives
# the next algorithm shift better than a bare table would.
# ---------------------------------------------------------------------------

ALGORITHM_NOTES = {
    "tiktok": "Least time-sensitive major platform: the For You feed is interest-ranked and distributes content over days. Timing affects the initial velocity push only — content strength dominates.",
    "instagram": "Ranking rewards engagement velocity in the first 30-60 minutes; posting when your audience is active seeds that velocity. Reels distribute over multiple days.",
    "facebook": "Interest-ranked feed with multi-day distribution; timing mainly affects the initial engagement seed.",
    "youtube": "Recommendation-driven; upload time matters mostly for subscriber-notification velocity in the first hours.",
    "linkedin": "Recency carries more weight than on entertainment feeds; professional-hours posting retains genuine timing leverage.",
    "twitter": "The most chronological major surface; timing retains the most leverage here.",
    "pinterest": "Search-and-save driven; pins surface for months, making posting time the weakest lever of any platform.",
    "threads": "Interest-ranked feed similar to Instagram; early velocity matters, exact hour less so.",
}

GLOBAL_TIMING_NOTE = (
    "Population windows are TEST STARTING POINTS, not answers. Every feed uses "
    "recency to seed early distribution, but your audience's rhythm is learnable "
    "only from your own history — run 4-6 weeks of varied-time posting, then "
    "re-run this script with --history.")

BASELINE_CONFIDENCE_CEILING = (
    "medium — a population average can never be high-confidence for a specific "
    "audience; 'high' is reachable only via --history (first-party data).")


def baseline_age_days(as_of=None):
    d = datetime.strptime(as_of or BASELINE_AS_OF, "%Y-%m-%d").date()
    return (date.today() - d).days


def baseline_status(as_of=None):
    """fresh | aging | stale for the shipped baseline tables."""
    age = baseline_age_days(as_of)
    if age > BASELINE_STALE_DAYS:
        return "stale", age
    if age > BASELINE_WARN_DAYS:
        return "aging", age
    return "fresh", age


# ---------------------------------------------------------------------------
# First-party analysis — the only path to "high" confidence
# ---------------------------------------------------------------------------

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
             "Saturday", "Sunday"]


def _hour_block(hour):
    start = (hour // 3) * 3
    return f"{start:02d}:00-{start + 3:02d}:00"


def analyze_history(entries):
    """Aggregate the brand's own posts into ranked day x 3-hour windows.

    Refuses to rank what it cannot support: needs MIN_TOTAL_POSTS overall and
    MIN_BUCKET_POSTS per bucket before a bucket may appear in the ranking.
    Returns (payload, ok). ok=False payloads explain the shortfall instead of
    dressing noise up as insight."""
    parsed = []
    for e in entries:
        try:
            ts = datetime.fromisoformat(str(e["posted_at"]).replace("Z", "+00:00"))
            parsed.append((ts, float(e["engagement"])))
        except (KeyError, ValueError, TypeError):
            continue
    if len(parsed) < MIN_TOTAL_POSTS:
        return ({"first_party_insufficient":
                 f"{len(parsed)} usable posts < {MIN_TOTAL_POSTS} minimum — "
                 "keep posting at varied times and re-run; falling back to the "
                 "population baseline."}, False)

    buckets = defaultdict(list)
    for ts, eng in parsed:
        buckets[(ts.weekday(), _hour_block(ts.hour))].append(eng)

    ranked = []
    thin = 0
    for (weekday, block), values in buckets.items():
        if len(values) < MIN_BUCKET_POSTS:
            thin += 1
            continue
        n = len(values)
        confidence = "high" if n >= 15 else ("medium" if n >= 8 else "low")
        ranked.append({
            "day": DAY_NAMES[weekday],
            "time_window": block,
            "avg_engagement": round(sum(values) / n, 2),
            "sample_size": n,
            "confidence": confidence,
        })
    if not ranked:
        return ({"first_party_insufficient":
                 f"no day/time bucket reaches {MIN_BUCKET_POSTS} posts — "
                 "history is too scattered to rank; falling back to the "
                 "population baseline."}, False)

    ranked.sort(key=lambda r: -r["avg_engagement"])
    for i, r in enumerate(ranked):
        r["rank"] = i + 1
    return ({
        "recommendations": ranked[:5],
        "total_posts_analyzed": len(parsed),
        "buckets_below_minimum": thin,
        "note": "Ranked from THIS brand's engagement history — re-run monthly; "
                "audience rhythms drift with platform changes and follower growth.",
    }, True)


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
    parser.add_argument(
        "--history",
        help="Path to a JSON file of the brand's own posts "
             '([{"posted_at": ISO-8601, "engagement": number}, ...]) — '
             "first-party data outranks every population baseline",
    )
    args = parser.parse_args()

    output = {
        "platform": args.platform,
        "industry": args.industry,
        "audience_type": args.audience_type,
        "algorithm_note": ALGORITHM_NOTES.get(args.platform, ""),
        "timing_note": GLOBAL_TIMING_NOTE,
    }

    # ── Rung 1: the brand's own data ────────────────────────────────
    if args.history:
        path = Path(args.history)
        if not path.exists():
            print(json.dumps({"error": f"history file not found: {args.history}"}))
            return 1
        try:
            entries = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            print(json.dumps({"error": f"history file is not valid JSON: {exc}"}))
            return 1
        fp, ok = analyze_history(entries)
        if ok:
            output.update(fp)
            output["basis"] = "first-party"
            json.dump(output, sys.stdout, indent=2)
            print()
            return 0
        output.update(fp)  # carries first_party_insufficient explanation

    # ── Rung 2: dated population baseline ───────────────────────────
    status, age = baseline_status()
    if status == "stale":
        output.update({
            "basis": "refused",
            "error": (
                f"Population baseline is {age} days old (as of {BASELINE_AS_OF}) "
                "— refusing to recommend from it. Refresh the tables against "
                "current published platform-engagement studies, or pass the "
                "brand's own data via --history (which never goes stale)."),
        })
        json.dump(output, sys.stdout, indent=2)
        print()
        return 3

    recommendations = build_recommendations(args.platform, args.audience_type, args.industry)
    for rec in recommendations:
        # Table values keep their RELATIVE ordering signal; absolute confidence
        # is capped — population data cannot be "high" for a specific audience.
        rec["relative_strength"] = rec.pop("confidence")

    output.update({
        "basis": "population-baseline",
        "baseline_as_of": BASELINE_AS_OF,
        "baseline_age_days": age,
        "confidence_ceiling": BASELINE_CONFIDENCE_CEILING,
        "recommendations": recommendations,
        "industry_notes": INDUSTRY_MODIFIERS[args.industry]["note"],
        "avoid_times": build_avoid_times(args.platform, args.industry),
    })
    if status == "aging":
        output["warning"] = (
            f"Baseline is {age} days old — re-verify against current published "
            "platform data before building a posting schedule on it.")

    json.dump(output, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
