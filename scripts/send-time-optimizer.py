#!/usr/bin/env python3
"""Recommend email send times — the list's own history first, dated population
baselines second, and the ESP's per-recipient optimization above both.

THE LADDER
----------
0. ESP SEND-TIME OPTIMIZATION: if the connected email platform offers
   per-recipient STO, use it before ANY global window — every output says so
   (judge it on clicks and conversions: opens are inflated). Global windows are
   for platforms without STO, first sends to new lists, and A/B baselines.
1. FIRST-PARTY (--history): the brand's own send log, ranked by clicks (opens only
   when the log has no clicks, labelled as inflated by Apple Mail Privacy Protection). Only the
   list's measured behavior can earn "high" confidence. Honest statistics:
   minimum send counts per bucket, sample sizes in the output, refusal to
   rank what the data cannot support.
2. SHIPPED BASELINE: curated population windows, stamped with BASELINE_AS_OF,
   capped at MEDIUM confidence, aging out (warn >180d, REFUSE >540d, exit 3).

Usage:
    python send-time-optimizer.py --industry saas --audience-type b2b
    python send-time-optimizer.py --industry ecommerce --audience-type b2c --timezone "+0"
    python send-time-optimizer.py --industry saas --audience-type b2b --history sends.json
      history format: [{"sent_at": ISO-8601, "clicks": N, "recipients": N}, ...]
      ("opens" is used only when an entry has no "clicks"; recipients optional)
"""

import argparse
import json
import sys
import os
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

# Population baselines below were last re-verified against current published
# email-engagement studies on this date. The suite fails when it ages out.
BASELINE_AS_OF = "2026-08-12"
BASELINE_WARN_DAYS = 180
BASELINE_STALE_DAYS = 540

MIN_TOTAL_SENDS = 12
MIN_BUCKET_SENDS = 3

STO_NOTE = (
    "If the connected email platform offers per-recipient send-time "
    "optimization, use it ABOVE any global window here. The doctrine: "
    "A/B test segment-level windows for 4-6 weeks (judge on clicks/conversions, "
    "not opens alone), then layer the ESP's STO for individual timing.")

BASELINE_CONFIDENCE_CEILING = (
    "medium — a population average can never be high-confidence for a specific "
    "list; 'high' is reachable only via --history (the list's own send log).")


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


DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
             "Saturday", "Sunday"]


def _hour_block(hour):
    start = (hour // 2) * 2
    return f"{start:02d}:00-{start + 2:02d}:00"


def analyze_history(entries):
    """Aggregate the list's own sends into ranked day x 2-hour windows by open
    rate (or click rate when opens are absent). Returns (payload, ok)."""
    parsed = []
    metric_kinds = set()
    for e in entries:
        try:
            ts = datetime.fromisoformat(str(e["sent_at"]).replace("Z", "+00:00"))
            # Clicks first: Apple Mail Privacy Protection pre-fetches tracking pixels, so opens
            # are inflated. Before 3.40.0 opens won whenever both were present.
            responses = float(e["clicks"] if e.get("clicks") is not None else e.get("opens"))
            metric_kinds.add("click" if e.get("clicks") is not None else "open")
            recipients = float(e.get("recipients", 0)) or None
            parsed.append((ts, responses, recipients))
        except (KeyError, ValueError, TypeError):
            continue
    if len(parsed) < MIN_TOTAL_SENDS:
        return ({"first_party_insufficient":
                 f"{len(parsed)} usable sends < {MIN_TOTAL_SENDS} minimum — "
                 "keep varying send times and re-run; falling back to the "
                 "population baseline."}, False)

    buckets = defaultdict(lambda: {"responses": 0.0, "recipients": 0.0,
                                   "sends": 0, "rates": []})
    for ts, responses, recipients in parsed:
        b = buckets[(ts.weekday(), _hour_block(ts.hour))]
        b["sends"] += 1
        if recipients:
            b["responses"] += responses
            b["recipients"] += recipients
            b["rates"].append(responses / recipients)
        else:
            b["rates"].append(responses)

    ranked = []
    thin = 0
    for (weekday, block), b in buckets.items():
        if b["sends"] < MIN_BUCKET_SENDS:
            thin += 1
            continue
        if b["recipients"]:
            metric = round(b["responses"] / b["recipients"], 4)
            metric_name = "click_rate" if "click" in metric_kinds else "open_rate"
        else:
            metric = round(sum(b["rates"]) / len(b["rates"]), 2)
            metric_name = "avg_responses"
        n = b["sends"]
        confidence = "high" if n >= 8 else ("medium" if n >= 5 else "low")
        ranked.append({
            "day": DAY_NAMES[weekday],
            "time_window": block,
            metric_name: metric,
            "sample_size": n,
            "confidence": confidence,
        })
    if not ranked:
        return ({"first_party_insufficient":
                 f"no day/time bucket reaches {MIN_BUCKET_SENDS} sends — "
                 "send log is too scattered to rank; falling back to the "
                 "population baseline."}, False)

    ranked.sort(key=lambda r: -(r.get("click_rate") or r.get("open_rate") or r.get("avg_responses") or 0))
    if "open" in metric_kinds and "click" not in metric_kinds:
        for r in ranked:
            r["metric_note"] = ("Ranked by opens, which Apple Mail Privacy Protection inflates: add clicks "
                                "to the send log for a ranking you can trust")
    for i, r in enumerate(ranked):
        r["rank"] = i + 1
    return ({
        "recommendations": ranked[:5],
        "total_sends_analyzed": len(parsed),
        "buckets_below_minimum": thin,
        "note": "Ranked from THIS list's send log — re-run quarterly; list "
                "composition and inbox behavior drift.",
    }, True)

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

    # Build final output with rank. Table values keep their RELATIVE ordering
    # signal; absolute confidence is capped — population data cannot be "high"
    # for a specific list.
    formatted = []
    for i, rec in enumerate(recs, 1):
        entry = {
            "rank": i,
            "day": rec["day"],
            "time_window": rec["time_window"],
            "rationale": rec["rationale"],
            "relative_strength": rec["confidence"],
        }
        if "day_note" in rec:
            entry["day_note"] = rec["day_note"]
        formatted.append(entry)

    age = baseline_age_days()
    return {
        "industry": industry,
        "audience_type": audience_type,
        "timezone": timezone_label,
        "basis": "population-baseline",
        "baseline_as_of": BASELINE_AS_OF,
        "baseline_age_days": age,
        "confidence_ceiling": BASELINE_CONFIDENCE_CEILING,
        "sto_note": STO_NOTE,
        "recommendations": formatted,
        "methodology_note": (
            "Population windows from aggregated email-platform studies. "
            "Actual optimal times vary by list demographics, geography, and "
            "content type — these are A/B starting points, not answers."
        ),
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
    parser.add_argument(
        "--history",
        help="Path to a JSON file of the list's own send log "
             '([{"sent_at": ISO-8601, "opens": N, "recipients": N}, ...]) — '
             "first-party data outranks every population baseline",
    )
    args = parser.parse_args()

    # ── Rung 1: the list's own send log ─────────────────────────────
    if args.history:
        path = Path(args.history)
        if not path.exists():
            _common.finish({"error": f"history file not found: {args.history}"})
            sys.exit(1)
        try:
            entries = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            _common.finish({"error": f"history file is not valid JSON: {exc}"})
            sys.exit(1)
        fp, ok = analyze_history(entries)
        if ok:
            fp.update({"basis": "first-party", "sto_note": STO_NOTE,
                       "industry": args.industry,
                       "audience_type": args.audience_type})
            _common.finish(fp)
            return
        # fall through to baseline, carrying the explanation
        insufficiency = fp
    else:
        insufficiency = None

    # ── Rung 2: dated population baseline (refuses when stale) ──────
    status, age = baseline_status()
    if status == "stale":
        _common.finish({
            "basis": "refused",
            "error": (
                f"Population baseline is {age} days old (as of {BASELINE_AS_OF}) "
                "— refusing to recommend from it. Refresh the tables against "
                "current published email-engagement studies, or pass the list's "
                "own send log via --history (which never goes stale)."),
        })
        sys.exit(3)

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
        _common.finish(result)
        sys.exit(1)

    if insufficiency:
        result.update(insufficiency)
    if status == "aging":
        result["warning"] = (
            f"Baseline is {age} days old — re-verify against current published "
            "email-engagement data before building a send calendar on it.")

    _common.finish(result)


if __name__ == "__main__":
    main()
