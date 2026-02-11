#!/usr/bin/env python3
"""Recommend optimal email send times based on industry benchmarks.

Uses built-in lookup tables covering 10 industries and 3 audience types
(B2B, B2C, mixed) to recommend the top 3 send windows. Supports timezone
offset adjustment from the EST base. Each recommendation includes the day,
time window, rationale, and confidence level.

Usage:
    python send-time-optimizer.py --industry saas --audience-type b2b
    python send-time-optimizer.py --industry ecommerce --audience-type b2c --timezone "+0"
    python send-time-optimizer.py --industry healthcare --audience-type mixed --timezone "-5"
"""

import argparse
import json
import sys

# ---------------------------------------------------------------------------
# Benchmark data: industry -> audience_type -> top 3 send windows
# All times are in EST (UTC-5) base. Day names are full English.
# ---------------------------------------------------------------------------

SEND_BENCHMARKS = {
    "saas": {
        "b2b": [
            {"day": "Tuesday", "time_window": "10:00-11:00 AM", "hour": 10, "rationale": "Mid-morning on Tuesday sees peak B2B engagement when professionals are settling into their workday", "confidence": "high"},
            {"day": "Wednesday", "time_window": "9:00-10:00 AM", "hour": 9, "rationale": "Wednesday morning catches decision-makers before meetings fill their calendar", "confidence": "high"},
            {"day": "Thursday", "time_window": "2:00-3:00 PM", "hour": 14, "rationale": "Post-lunch on Thursday is a secondary peak as professionals clear their inbox before end of week", "confidence": "medium"},
        ],
        "b2c": [
            {"day": "Tuesday", "time_window": "8:00-9:00 PM", "hour": 20, "rationale": "Evening sends reach SaaS consumers during personal browsing time", "confidence": "medium"},
            {"day": "Thursday", "time_window": "12:00-1:00 PM", "hour": 12, "rationale": "Lunch break browsing drives clicks for consumer SaaS products", "confidence": "medium"},
            {"day": "Sunday", "time_window": "10:00-11:00 AM", "hour": 10, "rationale": "Weekend morning is strong for consumer SaaS trial signups", "confidence": "medium"},
        ],
        "mixed": [
            {"day": "Tuesday", "time_window": "10:00-11:00 AM", "hour": 10, "rationale": "Tuesday mid-morning balances B2B and B2C engagement windows", "confidence": "high"},
            {"day": "Wednesday", "time_window": "2:00-3:00 PM", "hour": 14, "rationale": "Midweek afternoon captures both professional and personal email checks", "confidence": "medium"},
            {"day": "Thursday", "time_window": "9:00-10:00 AM", "hour": 9, "rationale": "Thursday morning maintains strong open rates across audience segments", "confidence": "medium"},
        ],
    },
    "ecommerce": {
        "b2b": [
            {"day": "Tuesday", "time_window": "10:00-11:00 AM", "hour": 10, "rationale": "B2B procurement teams review supplier emails mid-morning Tuesday", "confidence": "medium"},
            {"day": "Wednesday", "time_window": "2:00-3:00 PM", "hour": 14, "rationale": "Afternoon on Wednesday aligns with purchase approval cycles", "confidence": "medium"},
            {"day": "Thursday", "time_window": "9:00-10:00 AM", "hour": 9, "rationale": "End-of-week ordering before Friday cutoffs drives B2B ecommerce opens", "confidence": "medium"},
        ],
        "b2c": [
            {"day": "Saturday", "time_window": "10:00-11:00 AM", "hour": 10, "rationale": "Weekend morning shopping browsing drives highest ecommerce click-through rates", "confidence": "high"},
            {"day": "Tuesday", "time_window": "8:00-9:00 PM", "hour": 20, "rationale": "Evening browsing on Tuesday is a secondary peak for online shopping", "confidence": "high"},
            {"day": "Thursday", "time_window": "7:00-8:00 PM", "hour": 19, "rationale": "Pre-weekend evening shopping spikes as consumers plan weekend purchases", "confidence": "medium"},
        ],
        "mixed": [
            {"day": "Tuesday", "time_window": "10:00-11:00 AM", "hour": 10, "rationale": "Tuesday mid-morning captures both B2B buyers and early consumer shoppers", "confidence": "high"},
            {"day": "Saturday", "time_window": "10:00-11:00 AM", "hour": 10, "rationale": "Weekend morning shopping is the top B2C window and still reaches some B2B", "confidence": "medium"},
            {"day": "Thursday", "time_window": "2:00-3:00 PM", "hour": 14, "rationale": "Thursday afternoon balances professional procurement and consumer browsing", "confidence": "medium"},
        ],
    },
    "healthcare": {
        "b2b": [
            {"day": "Wednesday", "time_window": "10:00-11:00 AM", "hour": 10, "rationale": "Healthcare professionals check non-clinical email mid-morning midweek", "confidence": "high"},
            {"day": "Tuesday", "time_window": "2:00-3:00 PM", "hour": 14, "rationale": "Post-lunch Tuesday is a reliable window for medical office decision-makers", "confidence": "medium"},
            {"day": "Thursday", "time_window": "9:00-10:00 AM", "hour": 9, "rationale": "Thursday morning catches healthcare administrators before clinic hours intensify", "confidence": "medium"},
        ],
        "b2c": [
            {"day": "Monday", "time_window": "7:00-8:00 AM", "hour": 7, "rationale": "Early Monday patients check health-related emails as part of weekly wellness planning", "confidence": "medium"},
            {"day": "Wednesday", "time_window": "6:00-7:00 PM", "hour": 18, "rationale": "Evening sends reach health-conscious consumers after work", "confidence": "medium"},
            {"day": "Saturday", "time_window": "9:00-10:00 AM", "hour": 9, "rationale": "Weekend morning wellness content has strong open rates for consumer health", "confidence": "medium"},
        ],
        "mixed": [
            {"day": "Wednesday", "time_window": "10:00-11:00 AM", "hour": 10, "rationale": "Midweek mid-morning is the safest window across healthcare audiences", "confidence": "high"},
            {"day": "Tuesday", "time_window": "2:00-3:00 PM", "hour": 14, "rationale": "Tuesday afternoon works for both clinical admin and patient engagement", "confidence": "medium"},
            {"day": "Thursday", "time_window": "9:00-10:00 AM", "hour": 9, "rationale": "Thursday morning captures decision-makers and early-bird patients alike", "confidence": "medium"},
        ],
    },
    "finance": {
        "b2b": [
            {"day": "Tuesday", "time_window": "8:00-9:00 AM", "hour": 8, "rationale": "Finance professionals start early; Tuesday morning catches pre-market attention", "confidence": "high"},
            {"day": "Wednesday", "time_window": "10:00-11:00 AM", "hour": 10, "rationale": "Midweek mid-morning aligns with financial review cycles", "confidence": "high"},
            {"day": "Thursday", "time_window": "3:00-4:00 PM", "hour": 15, "rationale": "Late Thursday afternoon captures end-of-week financial planning", "confidence": "medium"},
        ],
        "b2c": [
            {"day": "Sunday", "time_window": "10:00-11:00 AM", "hour": 10, "rationale": "Weekend morning is when consumers review personal finances and plan ahead", "confidence": "high"},
            {"day": "Tuesday", "time_window": "7:00-8:00 PM", "hour": 19, "rationale": "Evening sends catch consumers during personal financial review time", "confidence": "medium"},
            {"day": "Thursday", "time_window": "12:00-1:00 PM", "hour": 12, "rationale": "Lunch-hour financial content has strong open rates before payday Fridays", "confidence": "medium"},
        ],
        "mixed": [
            {"day": "Tuesday", "time_window": "9:00-10:00 AM", "hour": 9, "rationale": "Tuesday morning balances professional and consumer finance audiences", "confidence": "high"},
            {"day": "Wednesday", "time_window": "10:00-11:00 AM", "hour": 10, "rationale": "Midweek mid-morning is consistently strong for finance content", "confidence": "medium"},
            {"day": "Sunday", "time_window": "10:00-11:00 AM", "hour": 10, "rationale": "Weekend morning financial planning emails reach consumer segments effectively", "confidence": "medium"},
        ],
    },
    "education": {
        "b2b": [
            {"day": "Tuesday", "time_window": "10:00-11:00 AM", "hour": 10, "rationale": "Education administrators and decision-makers are available mid-morning Tuesday", "confidence": "high"},
            {"day": "Wednesday", "time_window": "9:00-10:00 AM", "hour": 9, "rationale": "Wednesday morning catches academic leadership before midweek meetings", "confidence": "medium"},
            {"day": "Thursday", "time_window": "1:00-2:00 PM", "hour": 13, "rationale": "Early afternoon Thursday reaches educators during planning periods", "confidence": "medium"},
        ],
        "b2c": [
            {"day": "Sunday", "time_window": "7:00-8:00 PM", "hour": 19, "rationale": "Sunday evening is when students and parents plan the week ahead", "confidence": "high"},
            {"day": "Wednesday", "time_window": "5:00-6:00 PM", "hour": 17, "rationale": "Late afternoon midweek catches students after classes end", "confidence": "medium"},
            {"day": "Saturday", "time_window": "10:00-11:00 AM", "hour": 10, "rationale": "Weekend morning is strong for course enrollment and educational content", "confidence": "medium"},
        ],
        "mixed": [
            {"day": "Tuesday", "time_window": "10:00-11:00 AM", "hour": 10, "rationale": "Tuesday mid-morning works across institutional and student audiences", "confidence": "high"},
            {"day": "Wednesday", "time_window": "2:00-3:00 PM", "hour": 14, "rationale": "Midweek afternoon captures both administrators and students", "confidence": "medium"},
            {"day": "Sunday", "time_window": "7:00-8:00 PM", "hour": 19, "rationale": "Sunday evening planning time benefits consumer education sends", "confidence": "medium"},
        ],
    },
    "technology": {
        "b2b": [
            {"day": "Tuesday", "time_window": "10:00-11:00 AM", "hour": 10, "rationale": "Tech B2B buyers are most responsive mid-morning Tuesday after standup meetings", "confidence": "high"},
            {"day": "Wednesday", "time_window": "11:00 AM-12:00 PM", "hour": 11, "rationale": "Late morning Wednesday is a secondary peak for developer and IT decision-maker engagement", "confidence": "high"},
            {"day": "Thursday", "time_window": "2:00-3:00 PM", "hour": 14, "rationale": "Thursday afternoon captures tech buyers in evaluation and comparison mode", "confidence": "medium"},
        ],
        "b2c": [
            {"day": "Saturday", "time_window": "11:00 AM-12:00 PM", "hour": 11, "rationale": "Weekend late morning is peak for consumer tech browsing and deal hunting", "confidence": "high"},
            {"day": "Tuesday", "time_window": "8:00-9:00 PM", "hour": 20, "rationale": "Evening tech browsing on Tuesday drives strong consumer engagement", "confidence": "medium"},
            {"day": "Friday", "time_window": "12:00-1:00 PM", "hour": 12, "rationale": "Friday lunch break is when consumers explore tech purchases for the weekend", "confidence": "medium"},
        ],
        "mixed": [
            {"day": "Tuesday", "time_window": "10:00-11:00 AM", "hour": 10, "rationale": "Tuesday mid-morning is the universal sweet spot for technology audiences", "confidence": "high"},
            {"day": "Wednesday", "time_window": "11:00 AM-12:00 PM", "hour": 11, "rationale": "Late morning midweek captures both professional and personal tech interest", "confidence": "medium"},
            {"day": "Thursday", "time_window": "2:00-3:00 PM", "hour": 14, "rationale": "Thursday afternoon works across B2B evaluation and B2C research cycles", "confidence": "medium"},
        ],
    },
    "real_estate": {
        "b2b": [
            {"day": "Tuesday", "time_window": "9:00-10:00 AM", "hour": 9, "rationale": "Real estate professionals review market updates early Tuesday before showings", "confidence": "high"},
            {"day": "Wednesday", "time_window": "10:00-11:00 AM", "hour": 10, "rationale": "Midweek mid-morning aligns with property listing review cycles", "confidence": "medium"},
            {"day": "Thursday", "time_window": "2:00-3:00 PM", "hour": 14, "rationale": "Thursday afternoon catches agents planning weekend open houses", "confidence": "medium"},
        ],
        "b2c": [
            {"day": "Saturday", "time_window": "9:00-10:00 AM", "hour": 9, "rationale": "Weekend morning is when homebuyers actively browse listings", "confidence": "high"},
            {"day": "Sunday", "time_window": "10:00-11:00 AM", "hour": 10, "rationale": "Sunday morning open-house planning drives peak real estate consumer engagement", "confidence": "high"},
            {"day": "Wednesday", "time_window": "7:00-8:00 PM", "hour": 19, "rationale": "Midweek evening is when buyers research properties after work", "confidence": "medium"},
        ],
        "mixed": [
            {"day": "Tuesday", "time_window": "9:00-10:00 AM", "hour": 9, "rationale": "Tuesday morning reaches both agents and early-bird buyers", "confidence": "high"},
            {"day": "Saturday", "time_window": "9:00-10:00 AM", "hour": 9, "rationale": "Weekend morning captures consumer buyers and working agents alike", "confidence": "high"},
            {"day": "Thursday", "time_window": "2:00-3:00 PM", "hour": 14, "rationale": "Thursday afternoon pre-weekend planning benefits both audiences", "confidence": "medium"},
        ],
    },
    "professional_services": {
        "b2b": [
            {"day": "Tuesday", "time_window": "9:00-10:00 AM", "hour": 9, "rationale": "Professional services buyers begin vendor evaluation early Tuesday", "confidence": "high"},
            {"day": "Wednesday", "time_window": "10:00-11:00 AM", "hour": 10, "rationale": "Midweek mid-morning is the second-best window for consulting and services outreach", "confidence": "high"},
            {"day": "Thursday", "time_window": "3:00-4:00 PM", "hour": 15, "rationale": "Late Thursday captures decision-makers wrapping up weekly planning", "confidence": "medium"},
        ],
        "b2c": [
            {"day": "Monday", "time_window": "8:00-9:00 AM", "hour": 8, "rationale": "Monday morning is when consumers seek professional services for the new week", "confidence": "medium"},
            {"day": "Wednesday", "time_window": "6:00-7:00 PM", "hour": 18, "rationale": "Evening midweek reaches consumers researching accountants, lawyers, and consultants", "confidence": "medium"},
            {"day": "Saturday", "time_window": "10:00-11:00 AM", "hour": 10, "rationale": "Weekend morning is strong for consumer professional service discovery", "confidence": "medium"},
        ],
        "mixed": [
            {"day": "Tuesday", "time_window": "9:00-10:00 AM", "hour": 9, "rationale": "Tuesday morning is effective for both B2B buyers and individual consumers", "confidence": "high"},
            {"day": "Wednesday", "time_window": "10:00-11:00 AM", "hour": 10, "rationale": "Midweek mid-morning consistently performs well across service audiences", "confidence": "medium"},
            {"day": "Thursday", "time_window": "2:00-3:00 PM", "hour": 14, "rationale": "Thursday afternoon reaches decision-makers and individuals alike", "confidence": "medium"},
        ],
    },
    "nonprofit": {
        "b2b": [
            {"day": "Tuesday", "time_window": "10:00-11:00 AM", "hour": 10, "rationale": "Corporate partnership and grant officers review nonprofit outreach mid-morning Tuesday", "confidence": "medium"},
            {"day": "Wednesday", "time_window": "9:00-10:00 AM", "hour": 9, "rationale": "Wednesday morning catches CSR teams and foundation staff early in their day", "confidence": "medium"},
            {"day": "Thursday", "time_window": "2:00-3:00 PM", "hour": 14, "rationale": "Thursday afternoon is when corporate giving decisions are often finalized", "confidence": "medium"},
        ],
        "b2c": [
            {"day": "Tuesday", "time_window": "8:00-9:00 PM", "hour": 20, "rationale": "Evening appeals perform best when donors are relaxed and emotionally available", "confidence": "high"},
            {"day": "Saturday", "time_window": "10:00-11:00 AM", "hour": 10, "rationale": "Weekend morning is a top window for individual donor engagement", "confidence": "high"},
            {"day": "Thursday", "time_window": "12:00-1:00 PM", "hour": 12, "rationale": "Lunch-hour cause marketing has strong click-through among individual supporters", "confidence": "medium"},
        ],
        "mixed": [
            {"day": "Tuesday", "time_window": "10:00-11:00 AM", "hour": 10, "rationale": "Tuesday mid-morning balances corporate and individual donor engagement", "confidence": "high"},
            {"day": "Saturday", "time_window": "10:00-11:00 AM", "hour": 10, "rationale": "Weekend morning is effective for donor newsletters and impact stories", "confidence": "medium"},
            {"day": "Thursday", "time_window": "2:00-3:00 PM", "hour": 14, "rationale": "Thursday afternoon captures both institutional and individual supporters", "confidence": "medium"},
        ],
    },
    "general": {
        "b2b": [
            {"day": "Tuesday", "time_window": "10:00-11:00 AM", "hour": 10, "rationale": "Tuesday mid-morning is the most universally effective B2B send time", "confidence": "high"},
            {"day": "Wednesday", "time_window": "9:00-10:00 AM", "hour": 9, "rationale": "Wednesday morning is a strong secondary B2B window across all industries", "confidence": "high"},
            {"day": "Thursday", "time_window": "2:00-3:00 PM", "hour": 14, "rationale": "Thursday afternoon captures professionals in planning and review mode", "confidence": "medium"},
        ],
        "b2c": [
            {"day": "Saturday", "time_window": "10:00-11:00 AM", "hour": 10, "rationale": "Weekend morning is the top universal B2C engagement window", "confidence": "high"},
            {"day": "Tuesday", "time_window": "8:00-9:00 PM", "hour": 20, "rationale": "Tuesday evening browsing is a reliable B2C secondary peak", "confidence": "medium"},
            {"day": "Thursday", "time_window": "7:00-8:00 PM", "hour": 19, "rationale": "Thursday evening sees strong consumer engagement before the weekend", "confidence": "medium"},
        ],
        "mixed": [
            {"day": "Tuesday", "time_window": "10:00-11:00 AM", "hour": 10, "rationale": "Tuesday mid-morning is the safest all-purpose send time", "confidence": "high"},
            {"day": "Wednesday", "time_window": "2:00-3:00 PM", "hour": 14, "rationale": "Midweek afternoon works across both professional and consumer audiences", "confidence": "medium"},
            {"day": "Thursday", "time_window": "10:00-11:00 AM", "hour": 10, "rationale": "Thursday morning provides a reliable backup window for mixed audiences", "confidence": "medium"},
        ],
    },
}

VALID_INDUSTRIES = list(SEND_BENCHMARKS.keys())
VALID_AUDIENCE_TYPES = ["b2b", "b2c", "mixed"]


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def format_hour(hour_24):
    """Convert 24-hour integer to readable 12-hour string."""
    if hour_24 == 0:
        return "12:00 AM"
    elif hour_24 < 12:
        return f"{hour_24}:00 AM"
    elif hour_24 == 12:
        return "12:00 PM"
    else:
        return f"{hour_24 - 12}:00 PM"


def adjust_timezone(recommendations, tz_offset):
    """Adjust send times by a timezone offset (hours from EST)."""
    adjusted = []
    for rec in recommendations:
        original_hour = rec["hour"]
        new_hour = (original_hour + tz_offset) % 24

        # Format adjusted time window
        end_hour = (new_hour + 1) % 24
        time_window = f"{format_hour(new_hour)}-{format_hour(end_hour)}"

        adjusted_rec = dict(rec)
        adjusted_rec["time_window"] = time_window
        adjusted_rec["hour"] = new_hour

        # Day may shift if timezone pushes past midnight
        if original_hour + tz_offset >= 24:
            adjusted_rec["day_note"] = "Time shifted to next calendar day due to timezone adjustment"
        elif original_hour + tz_offset < 0:
            adjusted_rec["day_note"] = "Time shifted to previous calendar day due to timezone adjustment"

        adjusted.append(adjusted_rec)

    return adjusted


def get_recommendations(industry, audience_type, tz_offset=None):
    """Look up and return send time recommendations."""
    industry = industry.lower().strip()
    audience_type = audience_type.lower().strip()

    if industry not in SEND_BENCHMARKS:
        return {
            "error": f"Unknown industry: '{industry}'",
            "valid_industries": VALID_INDUSTRIES,
        }

    if audience_type not in VALID_AUDIENCE_TYPES:
        return {
            "error": f"Unknown audience type: '{audience_type}'",
            "valid_audience_types": VALID_AUDIENCE_TYPES,
        }

    raw = SEND_BENCHMARKS[industry][audience_type]

    # Deep copy to avoid mutating constants
    recs = [dict(r) for r in raw]

    timezone_label = "EST (UTC-5)"
    if tz_offset is not None and tz_offset != 0:
        recs = adjust_timezone(recs, tz_offset)
        sign = "+" if tz_offset >= 0 else ""
        timezone_label = f"EST {sign}{tz_offset}h (adjusted)"

    # Build final output with rank
    formatted = []
    for i, rec in enumerate(recs, 1):
        entry = {
            "rank": i,
            "day": rec["day"],
            "time_window": rec["time_window"],
            "rationale": rec["rationale"],
            "confidence": rec["confidence"],
        }
        if "day_note" in rec:
            entry["day_note"] = rec["day_note"]
        formatted.append(entry)

    return {
        "industry": industry,
        "audience_type": audience_type,
        "timezone": timezone_label,
        "recommendations": formatted,
        "methodology_note": (
            "Recommendations are based on aggregated industry benchmarks "
            "from email marketing platforms. Actual optimal times vary by "
            "list demographics, geography, and content type. A/B test send "
            "times with your own audience for best results."
        ),
        "data_last_updated": "2025-Q4",
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Recommend optimal email send times based on industry benchmarks"
    )
    parser.add_argument(
        "--industry", required=True,
        choices=VALID_INDUSTRIES,
        help="Industry vertical",
    )
    parser.add_argument(
        "--audience-type", required=True,
        choices=VALID_AUDIENCE_TYPES,
        help="Audience type: b2b, b2c, or mixed",
    )
    parser.add_argument(
        "--timezone", default=None,
        help='Timezone offset from EST base (e.g., "+5", "-3", "0")',
    )
    args = parser.parse_args()

    # Parse timezone offset
    tz_offset = None
    if args.timezone is not None:
        try:
            tz_offset = int(args.timezone.replace("+", ""))
        except ValueError:
            json.dump(
                {"error": f"Invalid timezone offset: '{args.timezone}'. Use an integer like '+5' or '-3'."},
                sys.stdout, indent=2,
            )
            print()
            sys.exit(1)

    result = get_recommendations(args.industry, args.audience_type, tz_offset)

    if "error" in result:
        json.dump(result, sys.stdout, indent=2)
        print()
        sys.exit(1)

    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
