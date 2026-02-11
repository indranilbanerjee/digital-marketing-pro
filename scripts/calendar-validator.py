#!/usr/bin/env python3
"""Validate content calendar structure, frequency, variety, and gap coverage.

Parses a JSON calendar of scheduled posts, checks posting frequency against
platform guidelines, detects content-type imbalance, finds scheduling gaps
and duplicates, and returns a 0-100 quality score with detailed breakdowns.

Usage:
    python calendar-validator.py --calendar '[{"date":"2026-03-01","platform":"instagram","content_type":"reel","topic":"Launch"}]'
    python calendar-validator.py --file calendar.json
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PLATFORM_FREQUENCY = {
    "instagram": {"min_per_week": 3, "max_per_week": 7, "ideal": 5},
    "linkedin": {"min_per_week": 2, "max_per_week": 5, "ideal": 3},
    "twitter": {"min_per_week": 5, "max_per_week": 25, "ideal": 14},
    "tiktok": {"min_per_week": 3, "max_per_week": 7, "ideal": 5},
    "facebook": {"min_per_week": 2, "max_per_week": 5, "ideal": 3},
    "blog": {"min_per_week": 0.5, "max_per_week": 3, "ideal": 1},
    "email": {"min_per_week": 0.5, "max_per_week": 3, "ideal": 1},
    "youtube": {"min_per_week": 1, "max_per_week": 3, "ideal": 2},
    "pinterest": {"min_per_week": 3, "max_per_week": 15, "ideal": 7},
    "threads": {"min_per_week": 3, "max_per_week": 10, "ideal": 5},
}

DATE_FORMAT = "%Y-%m-%d"


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def parse_entries(raw):
    """Parse and validate calendar entries. Returns (entries, date_errors)."""
    entries = []
    date_errors = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            date_errors.append(f"Entry {i}: not a valid object")
            continue
        date_str = entry.get("date", "")
        try:
            parsed_date = datetime.strptime(date_str, DATE_FORMAT)
        except (ValueError, TypeError):
            date_errors.append(f"Entry {i}: invalid date '{date_str}' (expected YYYY-MM-DD)")
            continue
        platform = str(entry.get("platform", "")).lower().strip()
        content_type = str(entry.get("content_type", "post")).lower().strip()
        topic = str(entry.get("topic", "")).strip()
        entries.append({
            "date": parsed_date,
            "date_str": date_str,
            "platform": platform,
            "content_type": content_type,
            "topic": topic,
        })
    # Sort by date
    entries.sort(key=lambda e: e["date"])
    return entries, date_errors


def check_frequency(entries, span_weeks):
    """Check posting frequency per platform. Returns (platform_report, score)."""
    platform_counts = Counter(e["platform"] for e in entries)
    report = {}
    total_score = 0
    platform_count = 0

    for platform, count in platform_counts.items():
        freq = PLATFORM_FREQUENCY.get(platform)
        if not freq:
            per_week = round(count / max(span_weeks, 0.5), 1)
            report[platform] = {
                "count": count,
                "frequency_per_week": per_week,
                "status": "unknown platform",
                "guideline": "N/A",
            }
            continue

        per_week = round(count / max(span_weeks, 0.5), 1)
        if per_week < freq["min_per_week"]:
            status = "below minimum"
        elif per_week > freq["max_per_week"]:
            status = "above maximum"
        else:
            status = "within range"

        report[platform] = {
            "count": count,
            "frequency_per_week": per_week,
            "status": status,
            "guideline": f"{freq['min_per_week']}-{freq['max_per_week']}/week",
        }

        # Score contribution: within range = full, otherwise partial
        platform_count += 1
        if status == "within range":
            total_score += 1.0
        elif status == "below minimum":
            ratio = per_week / freq["min_per_week"] if freq["min_per_week"] > 0 else 0
            total_score += max(0.2, min(0.8, ratio))
        else:
            overshoot = per_week / freq["max_per_week"] if freq["max_per_week"] > 0 else 2
            total_score += max(0.2, 1.0 / overshoot)

    freq_score = int(30 * (total_score / max(platform_count, 1)))
    return report, freq_score


def check_variety(entries):
    """Check content type variety. Returns (type_counts, score)."""
    type_counts = Counter(e["content_type"] for e in entries)
    total = len(entries)
    unique = len(type_counts)

    if total == 0:
        return dict(type_counts), 0

    variety_ratio = unique / total
    # More unique types relative to total = better (but diminishing returns)
    if unique >= 5:
        score = 20
    elif unique >= 3:
        score = 15
    elif unique >= 2:
        score = 10
    else:
        score = 5

    # Penalize if one type dominates >60% of posts
    if type_counts and type_counts.most_common(1)[0][1] / total > 0.6:
        score = max(0, score - 5)

    return dict(type_counts), score


def check_gaps(entries, start_date, end_date):
    """Detect scheduling gaps >3 days. Returns (gap_list, score)."""
    if not entries:
        return [], 0

    dates_with_posts = set(e["date"].date() for e in entries)
    gaps = []
    current = start_date.date()
    end = end_date.date()
    consecutive_empty = 0

    while current <= end:
        if current not in dates_with_posts:
            consecutive_empty += 1
            day_name = current.strftime("%A")
            if consecutive_empty >= 3:
                gaps.append({
                    "date": current.strftime(DATE_FORMAT),
                    "note": f"No posts scheduled ({day_name}) — gap of {consecutive_empty}+ days",
                })
        else:
            consecutive_empty = 0
        current += timedelta(days=1)

    # Deduplicate: keep only the last day of each gap stretch
    span_days = (end_date.date() - start_date.date()).days + 1
    gap_days = span_days - len(dates_with_posts)
    gap_ratio = gap_days / max(span_days, 1)

    score = max(0, int(20 * (1 - gap_ratio)))
    return gaps, score


def check_dates(date_errors, total):
    """Score date validity. Returns score (0-15)."""
    if total == 0:
        return 0
    valid_ratio = 1 - (len(date_errors) / total)
    return int(15 * valid_ratio)


def check_balance(entries):
    """Check content balance across platforms. Returns score (0-15)."""
    if not entries:
        return 0
    platform_counts = Counter(e["platform"] for e in entries)
    if len(platform_counts) <= 1:
        return 8  # Single platform is fine, just less balanced

    counts = list(platform_counts.values())
    avg = sum(counts) / len(counts)
    if avg == 0:
        return 0
    deviations = [abs(c - avg) / avg for c in counts]
    avg_deviation = sum(deviations) / len(deviations)

    # Lower deviation = better balance
    return max(0, int(15 * (1 - min(avg_deviation, 1.0))))


def detect_duplicates(entries):
    """Find same platform + date + topic combos."""
    seen = set()
    dupes = []
    for e in entries:
        key = (e["date_str"], e["platform"], e["topic"].lower())
        if key in seen and e["topic"]:
            dupes.append(f"{e['date_str']} / {e['platform']} / {e['topic']}")
        seen.add(key)
    return dupes


def check_weekend_coverage(entries):
    """Check whether weekends have posts."""
    weekend_posts = [e for e in entries if e["date"].weekday() in (5, 6)]
    total_weekends = len(set(
        (e["date"].isocalendar()[1], e["date"].year) for e in entries
        if e["date"].weekday() in (5, 6)
    ))
    all_weeks = set(
        (e["date"].isocalendar()[1], e["date"].year) for e in entries
    )
    total_weeks = len(all_weeks)
    if total_weeks == 0:
        return 0, "0%"
    pct = round(100 * total_weekends / total_weeks)
    return len(weekend_posts), f"{pct}%"


def generate_suggestions(platform_report, type_counts, gaps, weekend_count, duplicates):
    """Generate actionable suggestions."""
    suggestions = []
    for platform, info in platform_report.items():
        if info["status"] == "below minimum":
            freq = PLATFORM_FREQUENCY.get(platform)
            if freq:
                suggestions.append(f"Increase {platform} posts to at least {freq['min_per_week']}/week")
        elif info["status"] == "above maximum":
            freq = PLATFORM_FREQUENCY.get(platform)
            if freq:
                suggestions.append(f"Reduce {platform} posts to {freq['max_per_week']}/week or fewer")

    if len(type_counts) == 1:
        suggestions.append("Diversify content types — using only one type limits reach")

    if gaps:
        suggestions.append(f"Fill {len(gaps)} scheduling gap(s) to maintain consistent presence")

    if weekend_count == 0:
        suggestions.append("Consider adding 1-2 weekend posts for platforms with consumer audiences")

    if duplicates:
        suggestions.append(f"Review {len(duplicates)} potential duplicate(s) (same platform + date + topic)")

    return suggestions


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def validate_calendar(raw_entries):
    """Run all validation checks and produce the full result."""
    entries, date_errors = parse_entries(raw_entries)

    if not entries and not date_errors:
        return {"error": "No calendar entries to validate"}

    # Date range
    if entries:
        start_date = entries[0]["date"]
        end_date = entries[-1]["date"]
        span_days = (end_date - start_date).days + 1
        span_weeks = max(span_days / 7, 0.5)
    else:
        start_date = end_date = None
        span_days = 0
        span_weeks = 0

    # Run checks
    platform_report, freq_score = check_frequency(entries, span_weeks)
    type_counts, variety_score = check_variety(entries)
    gaps, gap_score = check_gaps(entries, start_date, end_date) if entries else ([], 0)
    date_score = check_dates(date_errors, len(raw_entries))
    balance_score = check_balance(entries)
    duplicates = detect_duplicates(entries)
    weekend_count, weekend_pct = check_weekend_coverage(entries) if entries else (0, "0%")

    total_score = max(0, min(100, freq_score + variety_score + gap_score + date_score + balance_score))

    # Warnings
    warnings = []
    if date_errors:
        warnings.extend(date_errors)
    if duplicates:
        for d in duplicates[:5]:
            warnings.append(f"Potential duplicate: {d}")
    for platform, info in platform_report.items():
        if info["status"] == "below minimum":
            warnings.append(f"{platform} is below minimum posting frequency ({info['frequency_per_week']}/week)")
        elif info["status"] == "above maximum":
            warnings.append(f"{platform} exceeds maximum posting frequency ({info['frequency_per_week']}/week)")
    if weekend_count == 0 and entries:
        warnings.append("No weekend posts scheduled")

    suggestions = generate_suggestions(platform_report, type_counts, gaps, weekend_count, duplicates)

    result = {
        "valid": len(date_errors) == 0,
        "score": total_score,
        "total_entries": len(raw_entries),
        "date_range": {
            "start": entries[0]["date_str"] if entries else None,
            "end": entries[-1]["date_str"] if entries else None,
            "span_days": span_days,
        },
        "breakdown": {
            "frequency_score": freq_score,
            "variety_score": variety_score,
            "gap_score": gap_score,
            "date_score": date_score,
            "balance_score": balance_score,
        },
        "platforms": platform_report,
        "content_types": type_counts,
        "gaps": gaps[:10],  # Limit to 10 most notable gaps
        "warnings": warnings,
        "suggestions": suggestions,
        "statistics": {
            "posts_per_day_avg": round(len(entries) / max(span_days, 1), 1),
            "unique_content_types": len(type_counts),
            "weekend_coverage": weekend_pct,
        },
    }

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Validate content calendar structure and identify issues"
    )
    parser.add_argument(
        "--calendar",
        help="JSON array of calendar entries",
    )
    parser.add_argument(
        "--file",
        help="Path to JSON file with calendar entries",
    )
    args = parser.parse_args()

    if not args.calendar and not args.file:
        parser.error("Provide either --calendar or --file")

    # Load entries
    if args.file:
        path = Path(args.file)
        if not path.exists():
            json.dump({"error": f"File not found: {args.file}"}, sys.stdout, indent=2)
            print()
            sys.exit(1)
        try:
            raw_entries = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            json.dump({"error": f"Invalid JSON in file: {exc}"}, sys.stdout, indent=2)
            print()
            sys.exit(1)
    else:
        try:
            raw_entries = json.loads(args.calendar)
        except json.JSONDecodeError as exc:
            json.dump({"error": f"Invalid JSON: {exc}"}, sys.stdout, indent=2)
            print()
            sys.exit(1)

    if not isinstance(raw_entries, list):
        json.dump({"error": "Calendar must be a JSON array of entries"}, sys.stdout, indent=2)
        print()
        sys.exit(1)

    if not raw_entries:
        json.dump({"error": "Calendar is empty — no entries to validate"}, sys.stdout, indent=2)
        print()
        sys.exit(1)

    result = validate_calendar(raw_entries)
    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
