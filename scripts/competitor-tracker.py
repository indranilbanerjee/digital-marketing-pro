#!/usr/bin/env python3
"""
competitor-tracker.py
=====================
Competitor Tracker — Monitor competitive landscape with change detection.

Stores competitor baselines, detects changes between scans, tracks mentions,
share of voice, ad sightings, pricing changes, and win/loss events. Provides
alert summaries across the full competitive landscape.

Storage: ~/.claude-marketing/brands/{slug}/competitors/

Usage:
    python competitor-tracker.py --brand acme --action save-baseline --competitor Rival --url https://rival.com --data '{"tagline": "We do X", "key_features": ["A","B"]}'
    python competitor-tracker.py --brand acme --action scan --competitor Rival --data '{"tagline": "We do Y"}'
    python competitor-tracker.py --brand acme --action diff --competitor Rival
    python competitor-tracker.py --brand acme --action track-mentions --competitor Rival --platform reddit --sentiment positive --content "Saw Rival praised"
    python competitor-tracker.py --brand acme --action share-of-voice --data '{"keywords": [{"keyword": "crm software", "your_rank": 3, "competitor_ranks": {"Rival": 1}}]}'
    python competitor-tracker.py --brand acme --action track-ads --competitor Rival --platform google --ad-type search --content "Free trial ad"
    python competitor-tracker.py --brand acme --action track-pricing --competitor Rival --data '{"plans": [{"name": "Pro", "price": 49, "features": ["A"]}]}'
    python competitor-tracker.py --brand acme --action alert-summary --since 2026-01-01
    python competitor-tracker.py --brand acme --action win-loss --competitor Rival --outcome won --deal-size 50000 --reason "Better onboarding"
    python competitor-tracker.py --brand acme --action list
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

BRANDS_DIR = _common.brands_root()

MENTION_PLATFORMS = ["reddit", "twitter", "linkedin", "news", "blog", "forum"]
SENTIMENTS = ["positive", "negative", "neutral"]
AD_PLATFORMS = ["google", "meta", "linkedin", "tiktok"]
AD_TYPES = ["search", "display", "social", "video"]
OUTCOMES = ["won", "lost"]


def get_brand_dir(slug):
    """Resolve + validate the brand directory. Delegates to _common so the slug
    is normalised (slugify at the boundary) and legacy raw-name dirs still
    resolve, with the standard not-found message."""
    return _common.get_brand_dir(slug)


def _slugify(name):
    """Create a filesystem-safe slug from a name."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _load_json(path):
    """Safely load a JSON file."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else [data]
    except (json.JSONDecodeError, OSError):
        return []


def _load_json_obj(path):
    """Safely load a JSON file expecting an object."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_json(path, data):
    """Write JSON data to file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def save_baseline(slug, competitor, url, data):
    """Save initial competitor snapshot."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    comp_slug = _slugify(competitor)
    comp_dir = brand_dir / "competitors" / comp_slug
    comp_dir.mkdir(parents=True, exist_ok=True)

    try:
        parsed = json.loads(data) if isinstance(data, str) else data
    except json.JSONDecodeError:
        return {"error": "Invalid JSON in --data"}

    baseline = {
        "competitor": competitor,
        "slug": comp_slug,
        "url": url,
        "data": parsed,
        "created_at": datetime.now().isoformat(),
    }

    _save_json(comp_dir / "baseline.json", baseline)

    return {
        "status": "baseline_saved",
        "competitor": competitor,
        "url": url,
        "fields_tracked": list(parsed.keys()),
    }


def scan(slug, competitor, data):
    """Compare current competitor data against baseline."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    comp_slug = _slugify(competitor)
    comp_dir = brand_dir / "competitors" / comp_slug

    try:
        current = json.loads(data) if isinstance(data, str) else data
    except json.JSONDecodeError:
        return {"error": "Invalid JSON in --data"}

    baseline = _load_json_obj(comp_dir / "baseline.json")
    if not baseline:
        return {"error": f"No baseline found for '{competitor}'. Run --action save-baseline first."}
    baseline_data = baseline.get("data", {})

    # Calculate diff
    new_fields = [k for k in current if k not in baseline_data]
    removed_fields = [k for k in baseline_data if k not in current]
    changed_fields = []
    for k in current:
        if k in baseline_data and current[k] != baseline_data[k]:
            changed_fields.append({
                "field": k,
                "old": baseline_data[k],
                "new": current[k],
            })

    scan_result = {
        "competitor": competitor,
        "scanned_at": datetime.now().isoformat(),
        "new_fields": new_fields,
        "changed_fields": changed_fields,
        "removed_fields": removed_fields,
        "total_changes": len(new_fields) + len(changed_fields) + len(removed_fields),
    }

    # Save scan history
    scans_path = comp_dir / "scans.json"
    scans = _load_json(scans_path)
    scans.append(scan_result)
    _save_json(scans_path, scans)

    return scan_result


def diff(slug, competitor):
    """Show all changes since baseline for a competitor."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    comp_slug = _slugify(competitor)
    scans_path = brand_dir / "competitors" / comp_slug / "scans.json"
    scans = _load_json(scans_path)

    if not scans:
        return {"competitor": competitor, "changes": [], "note": "No scans recorded yet."}

    scans.sort(key=lambda s: s.get("scanned_at", ""))
    return {"competitor": competitor, "scan_count": len(scans), "changes": scans}


def track_mentions(slug, competitor, platform, sentiment, content, url=None):
    """Record a brand mention observation."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    comp_slug = _slugify(competitor)
    mentions_dir = brand_dir / "competitors" / comp_slug / "mentions"
    mentions_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    mention = {
        "mention_id": f"mention-{ts}",
        "competitor": competitor,
        "platform": platform,
        "sentiment": sentiment,
        "content": content,
        "url": url,
        "recorded_at": datetime.now().isoformat(),
    }

    _save_json(mentions_dir / f"mention-{ts}.json", mention)
    return {"status": "recorded", **mention}


def share_of_voice(slug, data):
    """Record and calculate share of voice data."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    try:
        parsed = json.loads(data) if isinstance(data, str) else data
    except json.JSONDecodeError:
        return {"error": "Invalid JSON in --data"}

    keywords = parsed.get("keywords", [])
    if not keywords:
        return {"error": "Provide keywords array in --data"}

    # Calculate visibility scores (lower rank = higher score, max 10)
    scores = {}  # competitor -> total score
    your_total = 0
    for kw in keywords:
        your_rank = kw.get("your_rank", 0)
        your_score = max(0, 11 - your_rank) if your_rank > 0 else 0
        your_total += your_score

        for comp, rank in kw.get("competitor_ranks", {}).items():
            comp_score = max(0, 11 - rank) if rank > 0 else 0
            scores[comp] = scores.get(comp, 0) + comp_score

    all_scores = {"you": your_total, **scores}
    grand_total = sum(all_scores.values()) or 1
    sov = {name: round(sc / grand_total * 100, 1) for name, sc in all_scores.items()}

    sov_dir = brand_dir / "competitors" / "sov"
    sov_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    record = {
        "recorded_at": datetime.now().isoformat(),
        "keywords_analyzed": len(keywords),
        "raw_scores": all_scores,
        "share_of_voice_pct": sov,
    }
    _save_json(sov_dir / f"sov-{ts}.json", record)

    return {"status": "recorded", **record}


def track_ads(slug, competitor, platform, ad_type, content, url=None):
    """Record a competitor ad sighting."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    comp_slug = _slugify(competitor)
    ads_dir = brand_dir / "competitors" / comp_slug / "ads"
    ads_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    record = {
        "ad_id": f"ad-{ts}",
        "competitor": competitor,
        "platform": platform,
        "ad_type": ad_type,
        "content": content,
        "url": url,
        "recorded_at": datetime.now().isoformat(),
    }

    _save_json(ads_dir / f"ad-{ts}.json", record)
    return {"status": "recorded", **record}


def track_pricing(slug, competitor, data):
    """Record competitor pricing data and compare to previous snapshot."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    try:
        parsed = json.loads(data) if isinstance(data, str) else data
    except json.JSONDecodeError:
        return {"error": "Invalid JSON in --data"}

    comp_slug = _slugify(competitor)
    comp_dir = brand_dir / "competitors" / comp_slug
    comp_dir.mkdir(parents=True, exist_ok=True)

    pricing_path = comp_dir / "pricing.json"
    previous = _load_json_obj(pricing_path)

    changes = []
    if previous.get("plans"):
        prev_plans = {p["name"]: p for p in previous["plans"]}
        for plan in parsed.get("plans", []):
            name = plan.get("name")
            if name in prev_plans:
                if plan.get("price") != prev_plans[name].get("price"):
                    changes.append({
                        "plan": name,
                        "old_price": prev_plans[name].get("price"),
                        "new_price": plan.get("price"),
                    })

    record = {
        "competitor": competitor,
        "plans": parsed.get("plans", []),
        "recorded_at": datetime.now().isoformat(),
    }
    _save_json(pricing_path, record)

    # Persist detected price changes so alert-summary can surface them
    if changes:
        history_path = comp_dir / "pricing-history.json"
        history = _load_json(history_path)
        history.append({
            "recorded_at": record["recorded_at"],
            "competitor": competitor,
            "changes": changes,
        })
        _save_json(history_path, history)

    return {
        "status": "recorded",
        "competitor": competitor,
        "plans_tracked": len(parsed.get("plans", [])),
        "price_changes": changes,
    }


def alert_summary(slug, since):
    """Aggregate all competitive changes since a date."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    comp_root = brand_dir / "competitors"
    if not comp_root.exists():
        return {"changes": [], "note": "No competitors tracked yet."}

    results = {"scans": [], "mentions": [], "ads": [], "pricing": [], "win_loss": []}

    for comp_dir in comp_root.iterdir():
        if not comp_dir.is_dir() or comp_dir.name in ("sov", "win-loss"):
            continue
        comp_name = comp_dir.name

        # Scans
        for scan_rec in _load_json(comp_dir / "scans.json"):
            if scan_rec.get("scanned_at", "") >= since and scan_rec.get("total_changes", 0) > 0:
                results["scans"].append(scan_rec)

        # Mentions
        mentions_dir = comp_dir / "mentions"
        if mentions_dir.exists():
            for fp in mentions_dir.glob("mention-*.json"):
                rec = _load_json_obj(fp)
                if rec.get("recorded_at", "") >= since:
                    results["mentions"].append(rec)

        # Ads
        ads_dir = comp_dir / "ads"
        if ads_dir.exists():
            for fp in ads_dir.glob("ad-*.json"):
                rec = _load_json_obj(fp)
                if rec.get("recorded_at", "") >= since:
                    results["ads"].append(rec)

        # Pricing changes
        for rec in _load_json(comp_dir / "pricing-history.json"):
            if rec.get("recorded_at", "") >= since:
                results["pricing"].append(rec)

    # Win/loss
    wl_dir = comp_root / "win-loss"
    if wl_dir.exists():
        for fp in wl_dir.glob("*.json"):
            rec = _load_json_obj(fp)
            if rec.get("recorded_at", "") >= since:
                results["win_loss"].append(rec)

    total = sum(len(v) for v in results.values())
    return {"since": since, "total_events": total, **results}


def win_loss(slug, competitor, outcome, deal_size=None, reason=None, segment=None):
    """Record a win/loss event."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    wl_dir = brand_dir / "competitors" / "win-loss"
    wl_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    record = {
        "event_id": f"wl-{ts}",
        "competitor": competitor,
        "outcome": outcome,
        "deal_size": deal_size,
        "reason": reason,
        "segment": segment,
        "recorded_at": datetime.now().isoformat(),
    }

    _save_json(wl_dir / f"wl-{ts}.json", record)
    return {"status": "recorded", **record}


def list_competitors(slug):
    """List all tracked competitors for the brand."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    comp_root = brand_dir / "competitors"
    if not comp_root.exists():
        return {"competitors": [], "total": 0, "note": "No competitors tracked yet."}

    competitors = []
    for comp_dir in sorted(comp_root.iterdir()):
        if not comp_dir.is_dir() or comp_dir.name in ("sov", "win-loss"):
            continue
        baseline = _load_json_obj(comp_dir / "baseline.json")
        scans = _load_json(comp_dir / "scans.json")
        last_scan = scans[-1].get("scanned_at") if scans else None
        total_changes = sum(s.get("total_changes", 0) for s in scans)

        competitors.append({
            "name": baseline.get("competitor", comp_dir.name),
            "url": baseline.get("url"),
            "last_scan": last_scan,
            "total_changes": total_changes,
        })

    return {"competitors": competitors, "total": len(competitors)}


def main():
    parser = argparse.ArgumentParser(
        description="Competitor intelligence tracking for Digital Marketing Pro"
    )
    parser.add_argument("--brand", type=_common.path_component, required=True, help="Brand slug")
    parser.add_argument(
        "--action", required=True,
        choices=[
            "save-baseline", "scan", "diff", "track-mentions",
            "share-of-voice", "track-ads", "track-pricing",
            "alert-summary", "win-loss", "list",
        ],
        help="Action to perform",
    )
    parser.add_argument("--competitor", help="Competitor name")
    parser.add_argument("--url", help="Competitor URL (save-baseline) or source URL")
    parser.add_argument("--data", help="JSON data payload")
    parser.add_argument("--platform", choices=MENTION_PLATFORMS + AD_PLATFORMS,
                        help="Platform (track-mentions, track-ads)")
    parser.add_argument("--sentiment", choices=SENTIMENTS, help="Mention sentiment")
    parser.add_argument("--content", help="Description or content text")
    parser.add_argument("--ad-type", choices=AD_TYPES, help="Ad type (track-ads)")
    parser.add_argument("--since", help="Start date YYYY-MM-DD (alert-summary)")
    parser.add_argument("--outcome", choices=OUTCOMES, help="Win or loss (win-loss)")
    parser.add_argument("--deal-size", type=float, help="Deal size (win-loss)")
    parser.add_argument("--reason", help="Win/loss reason")
    parser.add_argument("--segment", help="Market segment (win-loss)")
    args = parser.parse_args()

    if args.action == "save-baseline":
        if not args.competitor or not args.url or not args.data:
            print(json.dumps({"error": "Provide --competitor, --url, and --data"}))
            sys.exit(1)
        result = save_baseline(args.brand, args.competitor, args.url, args.data)

    elif args.action == "scan":
        if not args.competitor or not args.data:
            print(json.dumps({"error": "Provide --competitor and --data"}))
            sys.exit(1)
        result = scan(args.brand, args.competitor, args.data)

    elif args.action == "diff":
        if not args.competitor:
            print(json.dumps({"error": "Provide --competitor"}))
            sys.exit(1)
        result = diff(args.brand, args.competitor)

    elif args.action == "track-mentions":
        if not args.competitor or not args.platform or not args.sentiment or not args.content:
            print(json.dumps({"error": "Provide --competitor, --platform, --sentiment, and --content"}))
            sys.exit(1)
        result = track_mentions(args.brand, args.competitor, args.platform,
                                args.sentiment, args.content, args.url)

    elif args.action == "share-of-voice":
        if not args.data:
            print(json.dumps({"error": "Provide --data with keywords JSON"}))
            sys.exit(1)
        result = share_of_voice(args.brand, args.data)

    elif args.action == "track-ads":
        if not args.competitor or not args.platform or not args.ad_type or not args.content:
            print(json.dumps({"error": "Provide --competitor, --platform, --ad-type, and --content"}))
            sys.exit(1)
        result = track_ads(args.brand, args.competitor, args.platform,
                           args.ad_type, args.content, args.url)

    elif args.action == "track-pricing":
        if not args.competitor or not args.data:
            print(json.dumps({"error": "Provide --competitor and --data"}))
            sys.exit(1)
        result = track_pricing(args.brand, args.competitor, args.data)

    elif args.action == "alert-summary":
        if not args.since:
            print(json.dumps({"error": "Provide --since YYYY-MM-DD"}))
            sys.exit(1)
        result = alert_summary(args.brand, args.since)

    elif args.action == "win-loss":
        if not args.competitor or not args.outcome:
            print(json.dumps({"error": "Provide --competitor and --outcome"}))
            sys.exit(1)
        result = win_loss(args.brand, args.competitor, args.outcome,
                          args.deal_size, args.reason, args.segment)

    elif args.action == "list":
        result = list_competitors(args.brand)

    _common.finish(result)


if __name__ == "__main__":
    main()
