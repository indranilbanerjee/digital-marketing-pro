#!/usr/bin/env python3
"""
geo-tracker.py
==============
GEO Tracker — Monitor brand visibility across AI engines.

Tracks how AI platforms (ChatGPT, Perplexity, Gemini, Copilot, Google AI Mode,
AI Overviews — 6 surfaces as of May 2026) represent a brand in their responses.
Records visibility audits, baselines, competitive benchmarks, narrative
alignment, and entity consistency to produce an overall GEO health score.

Note: 'ai-mode' is Google's conversational search default (Gemini 3.5 Flash,
launched I/O 2026) and is a SEPARATE surface from 'ai-overviews' (the SERP
summary block) — both should be tracked independently.

Storage: ~/.claude-marketing/brands/{slug}/geo/

Usage:
    python geo-tracker.py --brand acme --action audit-visibility --query "best CRM" --platform chatgpt --result cited --context "Acme CRM was listed first"
    python geo-tracker.py --brand acme --action save-baseline --data '[{"query": "best CRM", "platform": "chatgpt", "result": "cited", "score": 10}]'
    python geo-tracker.py --brand acme --action diff --data '[{"query": "best CRM", "platform": "chatgpt", "result": "mentioned", "score": 7}]'
    python geo-tracker.py --brand acme --action benchmark-competitors --query "best CRM" --your-result cited --competitors '[{"name": "Rival", "result": "mentioned", "score": 7}]'
    python geo-tracker.py --brand acme --action track-narrative --platform chatgpt --query "what is Acme" --narrative "Acme is a CRM" --alignment aligned
    python geo-tracker.py --brand acme --action entity-check --platform wikidata --entity-name "Acme Corp" --status present --details "Entity exists"
    python geo-tracker.py --brand acme --action platform-breakdown
    python geo-tracker.py --brand acme --action summary
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

BRANDS_DIR = _common.brands_root()

# Canonical 6 AI-visibility surfaces — single source of truth in _common so
# aeo-audit, geo-monitor, share-of-voice and serp-tracker never drift. The
# display names below map 1:1 to the platform slugs this script accepts.
CANONICAL_AI_SURFACES = _common.AI_VISIBILITY_SURFACES  # display names
SURFACE_SLUGS = {
    "Google AI Mode": "ai-mode",
    "Google AI Overviews": "ai-overviews",
    "ChatGPT": "chatgpt",
    "Perplexity": "perplexity",
    "Gemini": "gemini",
    "Copilot": "copilot",
}
PLATFORMS = [SURFACE_SLUGS[s] for s in CANONICAL_AI_SURFACES]
RESULTS = ["cited", "mentioned", "concept-only", "absent", "misrepresented"]
RESULT_SCORES = {
    "cited": 10,
    "mentioned": 7,
    "concept-only": 3,
    "absent": 0,
    "misrepresented": -5,
}
ALIGNMENTS = ["aligned", "drifting", "misrepresented"]
ENTITY_PLATFORMS = ["wikidata", "google-kp", "wikipedia", "directory"]
ENTITY_STATUSES = ["present", "absent", "inconsistent", "outdated"]


def get_brand_dir(slug):
    """Resolve + validate the brand directory. Delegates to _common so the slug
    is normalised (slugify at the boundary) and legacy raw-name dirs still
    resolve, with the standard not-found message."""
    return _common.get_brand_dir(slug)


def _load_json(path):
    """Safely load a JSON file, returning empty list on failure."""
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


def audit_visibility(slug, query, platform, result, context, url=None):
    """Record an AI visibility audit result."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    score = RESULT_SCORES.get(result, 0)

    audits_dir = brand_dir / "geo" / "audits"
    audits_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    audit = {
        "audit_id": f"audit-{ts}",
        "query": query,
        "platform": platform,
        "result": result,
        "score": score,
        "context": context,
        "url": url,
        "recorded_at": datetime.now().isoformat(),
    }

    _save_json(audits_dir / f"audit-{ts}.json", audit)
    return {"status": "recorded", **audit}


def save_baseline(slug, data):
    """Save baseline AI visibility snapshot."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    try:
        entries = json.loads(data) if isinstance(data, str) else data
    except json.JSONDecodeError:
        return {"error": "Invalid JSON in --data"}

    if not isinstance(entries, list):
        return {"error": "--data must be a JSON array"}

    geo_dir = brand_dir / "geo"
    geo_dir.mkdir(parents=True, exist_ok=True)

    # Enrich entries with scores if missing
    for entry in entries:
        if "score" not in entry:
            entry["score"] = RESULT_SCORES.get(entry.get("result", "absent"), 0)

    baseline = {
        "entries": entries,
        "created_at": datetime.now().isoformat(),
        "query_count": len(entries),
        "average_score": round(sum(e.get("score", 0) for e in entries) / max(len(entries), 1), 1),
    }

    _save_json(geo_dir / "baseline.json", baseline)

    return {
        "status": "baseline_saved",
        "query_count": baseline["query_count"],
        "average_score": baseline["average_score"],
    }


def diff(slug, data):
    """Compare current audit data to baseline."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    try:
        current = json.loads(data) if isinstance(data, str) else data
    except json.JSONDecodeError:
        return {"error": "Invalid JSON in --data"}

    baseline = _load_json_obj(brand_dir / "geo" / "baseline.json")
    baseline_entries = baseline.get("entries", [])

    if not baseline_entries:
        return {"error": "No baseline saved. Run save-baseline first."}

    # Index baseline by (query, platform)
    base_map = {}
    for e in baseline_entries:
        key = (e.get("query", ""), e.get("platform", ""))
        base_map[key] = e

    improvements = []
    declines = []
    unchanged = []

    for entry in current:
        if "score" not in entry:
            entry["score"] = RESULT_SCORES.get(entry.get("result", "absent"), 0)
        key = (entry.get("query", ""), entry.get("platform", ""))
        base = base_map.get(key)
        if not base:
            improvements.append({**entry, "delta": entry["score"], "note": "new query"})
            continue
        delta = entry["score"] - base.get("score", 0)
        record = {**entry, "baseline_score": base.get("score", 0), "delta": delta}
        if delta > 0:
            improvements.append(record)
        elif delta < 0:
            declines.append(record)
        else:
            unchanged.append(record)

    base_avg = baseline.get("average_score", 0)
    current_avg = round(sum(e.get("score", 0) for e in current) / max(len(current), 1), 1)

    return {
        "improvements": improvements,
        "declines": declines,
        "unchanged": unchanged,
        "score_delta": round(current_avg - base_avg, 1),
        "baseline_avg": base_avg,
        "current_avg": current_avg,
    }


def benchmark_competitors(slug, query, your_result, competitors):
    """Record competitive GEO benchmark."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    try:
        comp_data = json.loads(competitors) if isinstance(competitors, str) else competitors
    except json.JSONDecodeError:
        return {"error": "Invalid JSON in --competitors"}

    your_score = RESULT_SCORES.get(your_result, 0)
    all_entries = [{"name": "you", "result": your_result, "score": your_score}]
    for c in comp_data:
        score = c.get("score", RESULT_SCORES.get(c.get("result", "absent"), 0))
        all_entries.append({"name": c["name"], "result": c.get("result"), "score": score})

    all_entries.sort(key=lambda e: e["score"], reverse=True)
    total = sum(max(e["score"], 0) for e in all_entries) or 1
    sov = {e["name"]: round(max(e["score"], 0) / total * 100, 1) for e in all_entries}
    your_rank = next((i + 1 for i, e in enumerate(all_entries) if e["name"] == "you"), 0)

    benchmarks_dir = brand_dir / "geo" / "benchmarks"
    benchmarks_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    record = {
        "query": query,
        "your_result": your_result,
        "your_score": your_score,
        "your_rank": your_rank,
        "rankings": all_entries,
        "share_of_voice": sov,
        "recorded_at": datetime.now().isoformat(),
    }
    _save_json(benchmarks_dir / f"bench-{ts}.json", record)

    return {"status": "recorded", **record}


def track_narrative(slug, platform, query, narrative, alignment):
    """Record what an AI engine says about the brand."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    narratives_dir = brand_dir / "geo" / "narratives"
    narratives_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    record = {
        "narrative_id": f"narr-{ts}",
        "platform": platform,
        "query": query,
        "narrative": narrative,
        "alignment": alignment,
        "recorded_at": datetime.now().isoformat(),
    }

    _save_json(narratives_dir / f"narr-{ts}.json", record)
    return {"status": "recorded", **record}


def entity_check(slug, platform, entity_name, status, details):
    """Record entity consistency audit."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    entities_dir = brand_dir / "geo" / "entities"
    entities_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    record = {
        "check_id": f"entity-{ts}",
        "platform": platform,
        "entity_name": entity_name,
        "status": status,
        "details": details,
        "recorded_at": datetime.now().isoformat(),
    }

    _save_json(entities_dir / f"entity-{ts}.json", record)
    return {"status": "recorded", **record}


def platform_breakdown(slug):
    """Get per-platform visibility summary."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    audits_dir = brand_dir / "geo" / "audits"
    if not audits_dir.exists():
        return {"platforms": {}, "note": "No audit data yet."}

    by_platform = {}
    for fp in audits_dir.glob("audit-*.json"):
        rec = _load_json_obj(fp)
        plat = rec.get("platform", "unknown")
        if plat not in by_platform:
            by_platform[plat] = {"scores": [], "results": {}}
        by_platform[plat]["scores"].append(rec.get("score", 0))
        r = rec.get("result", "unknown")
        by_platform[plat]["results"][r] = by_platform[plat]["results"].get(r, 0) + 1

    summary = {}
    for plat, info in by_platform.items():
        scores = info["scores"]
        avg = round(sum(scores) / max(len(scores), 1), 1)
        summary[plat] = {
            "average_score": avg,
            "audit_count": len(scores),
            "result_distribution": info["results"],
        }

    # Rank platforms
    ranked = sorted(summary.items(), key=lambda x: x[1]["average_score"], reverse=True)
    rankings = [{"platform": p, **d} for p, d in ranked]

    return {"platforms": rankings, "total_platforms": len(rankings)}


def geo_summary(slug):
    """Overall GEO health summary for the brand."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    geo_dir = brand_dir / "geo"
    if not geo_dir.exists():
        return {"note": "No GEO data tracked yet.", "total_queries": 0}

    # Audits
    all_scores = []
    audits_dir = geo_dir / "audits"
    if audits_dir.exists():
        for fp in audits_dir.glob("audit-*.json"):
            rec = _load_json_obj(fp)
            all_scores.append(rec.get("score", 0))

    # Platform breakdown
    pb = platform_breakdown(slug)
    platforms = pb.get("platforms", [])
    best = platforms[0]["platform"] if platforms else None
    worst = platforms[-1]["platform"] if platforms else None

    # Narrative alignment
    narr_dir = geo_dir / "narratives"
    total_narr = 0
    aligned_narr = 0
    if narr_dir.exists():
        for fp in narr_dir.glob("narr-*.json"):
            rec = _load_json_obj(fp)
            total_narr += 1
            if rec.get("alignment") == "aligned":
                aligned_narr += 1
    alignment_pct = round(aligned_narr / max(total_narr, 1) * 100, 1)

    # Entity consistency
    ent_dir = geo_dir / "entities"
    total_ent = 0
    consistent_ent = 0
    if ent_dir.exists():
        for fp in ent_dir.glob("entity-*.json"):
            rec = _load_json_obj(fp)
            total_ent += 1
            if rec.get("status") == "present":
                consistent_ent += 1
    entity_pct = round(consistent_ent / max(total_ent, 1) * 100, 1)

    # Trend: compare first half of scores to second half
    trend = "stable"
    if len(all_scores) >= 4:
        mid = len(all_scores) // 2
        first_avg = sum(all_scores[:mid]) / mid
        second_avg = sum(all_scores[mid:]) / (len(all_scores) - mid)
        if second_avg > first_avg + 1:
            trend = "improving"
        elif second_avg < first_avg - 1:
            trend = "declining"

    avg_score = round(sum(all_scores) / max(len(all_scores), 1), 1) if all_scores else 0

    return {
        "total_queries_tracked": len(all_scores),
        "average_visibility_score": avg_score,
        "max_possible_score": 10,
        "best_platform": best,
        "worst_platform": worst,
        "narrative_alignment_pct": alignment_pct,
        "narratives_tracked": total_narr,
        "entity_consistency_pct": entity_pct,
        "entities_tracked": total_ent,
        "trend": trend,
        "platform_count": len(platforms),
    }


def main():
    parser = argparse.ArgumentParser(
        description="GEO (Generative Engine Optimization) tracking for Digital Marketing Pro"
    )
    parser.add_argument("--brand", type=_common.path_component, required=True, help="Brand slug")
    parser.add_argument(
        "--action", required=True,
        choices=[
            "audit-visibility", "save-baseline", "diff",
            "benchmark-competitors", "track-narrative", "entity-check",
            "platform-breakdown", "summary",
        ],
        help="Action to perform",
    )
    parser.add_argument("--query", help="Test query (audit-visibility, benchmark-competitors)")
    parser.add_argument("--platform", choices=PLATFORMS + ENTITY_PLATFORMS,
                        help="AI platform or entity platform")
    parser.add_argument("--result", choices=RESULTS, help="Visibility result")
    parser.add_argument("--context", help="What the AI said about the brand")
    parser.add_argument("--url", help="Citation URL (optional)")
    parser.add_argument("--data", help="JSON data payload")
    parser.add_argument("--your-result", choices=RESULTS, help="Your result (benchmark)")
    parser.add_argument("--competitors", help="JSON array of competitor results (benchmark)")
    parser.add_argument("--narrative", help="AI narrative text (track-narrative)")
    parser.add_argument("--alignment", choices=ALIGNMENTS, help="Narrative alignment")
    parser.add_argument("--entity-name", help="Entity name (entity-check)")
    parser.add_argument("--status", dest="entity_status", choices=ENTITY_STATUSES,
                        help="Entity status (entity-check)")
    parser.add_argument("--details", help="Entity check details")
    args = parser.parse_args()

    if args.action == "audit-visibility":
        if not args.query or not args.platform or not args.result or not args.context:
            print(json.dumps({"error": "Provide --query, --platform, --result, and --context"}))
            sys.exit(1)
        result = audit_visibility(args.brand, args.query, args.platform,
                                  args.result, args.context, args.url)

    elif args.action == "save-baseline":
        if not args.data:
            print(json.dumps({"error": "Provide --data with baseline JSON array"}))
            sys.exit(1)
        result = save_baseline(args.brand, args.data)

    elif args.action == "diff":
        if not args.data:
            print(json.dumps({"error": "Provide --data with current results JSON array"}))
            sys.exit(1)
        result = diff(args.brand, args.data)

    elif args.action == "benchmark-competitors":
        if not args.query or not args.your_result or not args.competitors:
            print(json.dumps({"error": "Provide --query, --your-result, and --competitors"}))
            sys.exit(1)
        result = benchmark_competitors(args.brand, args.query,
                                       args.your_result, args.competitors)

    elif args.action == "track-narrative":
        if not args.platform or not args.query or not args.narrative or not args.alignment:
            print(json.dumps({"error": "Provide --platform, --query, --narrative, and --alignment"}))
            sys.exit(1)
        result = track_narrative(args.brand, args.platform, args.query,
                                 args.narrative, args.alignment)

    elif args.action == "entity-check":
        if not args.platform or not args.entity_name or not args.entity_status or not args.details:
            print(json.dumps({"error": "Provide --platform, --entity-name, --status, and --details"}))
            sys.exit(1)
        result = entity_check(args.brand, args.platform, args.entity_name,
                              args.entity_status, args.details)

    elif args.action == "platform-breakdown":
        result = platform_breakdown(args.brand)

    elif args.action == "summary":
        result = geo_summary(args.brand)

    _common.finish(result)


if __name__ == "__main__":
    main()
