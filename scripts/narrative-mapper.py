#!/usr/bin/env python3
"""
narrative-mapper.py
===================
Narrative Mapper — Map competitive positioning and narrative territories.

Analyses competitive narrative landscapes, identifies unoccupied territories,
detects positioning shifts, generates counter-narrative playbooks, and tracks
how the narrative landscape evolves over time.

Storage: ~/.claude-marketing/brands/{slug}/narrative/

Dependencies: none (stdlib only)

Usage:
    python narrative-mapper.py --brand acme --action map-landscape --data '{"dimensions": [{"name": "Innovation", "description": "Cutting-edge tech"}], "competitors": [{"name": "Rival", "positions": {"Innovation": 8}}], "your_positions": {"Innovation": 7}}'
    python narrative-mapper.py --brand acme --action find-gaps
    python narrative-mapper.py --brand acme --action detect-shifts --competitor Rival --new-positions '{"Innovation": 5}'
    python narrative-mapper.py --brand acme --action generate-counter --competitor Rival --their-move "Launched free tier" --move-type price-cut
    python narrative-mapper.py --brand acme --action track-narrative --data '{"competitors": [{"name": "Rival", "positions": {"Innovation": 6}}]}'
    python narrative-mapper.py --brand acme --action narrative-trend --since 2026-01-01
    python narrative-mapper.py --brand acme --action summary
"""

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

BRANDS_DIR = _common.brands_root()

MOVE_TYPES = ["price-cut", "feature-launch", "rebrand",
              "category-creation", "market-entry", "partnership"]

COUNTER_STRATEGIES = ["direct", "reframe", "category", "social-proof", "zeitgeist"]


# ── Helpers ─────────────────────────────────────────────────────────────────

def _load_json(path, default=None):
    if default is None:
        default = {}
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _save_json(path, data):
    _common.atomic_write_json(path, data)


def _narrative_dir(slug):
    return BRANDS_DIR / slug / "narrative"


def _euclidean(a, b, dims):
    return math.sqrt(sum((a.get(d, 0) - b.get(d, 0)) ** 2 for d in dims))


def _brand_check(slug):
    _, err = _common.get_brand_dir(slug)
    if err:
        return {"error": err}
    return None


# ── Actions ─────────────────────────────────────────────────────────────────

def map_landscape(slug, data_str):
    err = _brand_check(slug)
    if err:
        return err

    try:
        data = json.loads(data_str) if isinstance(data_str, str) else data_str
    except json.JSONDecodeError:
        return {"error": "Invalid JSON in --data"}

    dimensions = data.get("dimensions", [])
    competitors = data.get("competitors", [])
    your_positions = data.get("your_positions", {})
    dim_names = [d["name"] for d in dimensions]

    if not dim_names:
        return {"error": "Provide at least one dimension in dimensions[]"}

    # Build landscape map
    landscape = {"dimensions": dimensions, "competitors": [], "your_positions": your_positions}
    for comp in competitors:
        landscape["competitors"].append({
            "name": comp["name"],
            "positions": comp.get("positions", {}),
        })

    # Cluster competitors (within distance threshold on all dims)
    threshold = 2.0
    clusters = []
    assigned = set()
    for i, c1 in enumerate(competitors):
        if i in assigned:
            continue
        cluster = [c1["name"]]
        assigned.add(i)
        for j, c2 in enumerate(competitors):
            if j in assigned:
                continue
            dist = _euclidean(c1.get("positions", {}), c2.get("positions", {}), dim_names)
            if dist <= threshold:
                cluster.append(c2["name"])
                assigned.add(j)
        if len(cluster) > 1:
            avg_pos = {}
            members = [c for c in competitors if c["name"] in cluster]
            for d in dim_names:
                avg_pos[d] = round(sum(m.get("positions", {}).get(d, 0) for m in members) / len(members), 1)
            clusters.append({"members": cluster, "centroid": avg_pos})

    # Find gaps: dimension combos where no competitor scores above 6
    gaps = []
    for d in dim_names:
        comp_scores = [c.get("positions", {}).get(d, 0) for c in competitors]
        max_score = max(comp_scores) if comp_scores else 0
        your_score = your_positions.get(d, 0)
        if max_score < 6:
            gap_opportunity = (10 - max_score) * 0.7 + (10 - your_score) * 0.3
            gaps.append({"dimension": d, "max_competitor_score": max_score,
                         "your_score": your_score, "opportunity_score": round(gap_opportunity, 2)})
    gaps.sort(key=lambda g: g["opportunity_score"], reverse=True)

    # Your strongest / weakest
    sorted_dims = sorted(dim_names, key=lambda d: your_positions.get(d, 0), reverse=True)
    strongest = sorted_dims[:3] if len(sorted_dims) >= 3 else sorted_dims
    weakest = sorted_dims[-3:] if len(sorted_dims) >= 3 else sorted_dims

    result = {
        "landscape_map": landscape,
        "clusters": clusters,
        "gaps": gaps,
        "your_strongest_dimensions": strongest,
        "your_weakest_dimensions": weakest,
        "opportunity_scores": {g["dimension"]: g["opportunity_score"] for g in gaps},
    }

    # Persist landscape
    ndir = _narrative_dir(slug)
    _save_json(ndir / "landscape.json", {**result, "updated_at": datetime.now().isoformat()})

    return result


def find_gaps(slug):
    err = _brand_check(slug)
    if err:
        return err

    landscape = _load_json(_narrative_dir(slug) / "landscape.json")
    if not landscape or "landscape_map" not in landscape:
        return {"error": "No landscape data found. Run map-landscape first."}

    lm = landscape["landscape_map"]
    dim_names = [d["name"] for d in lm.get("dimensions", [])]
    competitors = lm.get("competitors", [])
    your_pos = lm.get("your_positions", {})

    gaps = []
    for d in dim_names:
        comp_scores = [c.get("positions", {}).get(d, 0) for c in competitors]
        max_comp = max(comp_scores) if comp_scores else 0

        # Find nearest competitor to a hypothetical high position
        nearest_comp = None
        nearest_dist = float("inf")
        target_pos = {dim: your_pos.get(dim, 5) for dim in dim_names}
        target_pos[d] = 9  # Hypothetical strong position

        for c in competitors:
            dist = _euclidean(target_pos, c.get("positions", {}), dim_names)
            if dist < nearest_dist:
                nearest_dist = dist
                nearest_comp = c["name"]

        customer_value = max(1, 10 - max_comp)
        credibility = max(1, your_pos.get(d, 5))
        distance_bonus = min(10, nearest_dist)
        score = round((customer_value * credibility * distance_bonus) / 100, 2)

        rec = "Strong opportunity" if score > 3 else ("Moderate opportunity" if score > 1.5 else "Low priority")
        gaps.append({
            "dimensions": [d],
            "scores": {d: max_comp},
            "nearest_competitor": nearest_comp,
            "distance": round(nearest_dist, 2),
            "opportunity_score": score,
            "recommendation": rec,
        })

    gaps.sort(key=lambda g: g["opportunity_score"], reverse=True)
    return {"gaps": gaps}


def detect_shifts(slug, competitor, new_positions_str):
    err = _brand_check(slug)
    if err:
        return err

    try:
        new_positions = json.loads(new_positions_str) if isinstance(new_positions_str, str) else new_positions_str
    except json.JSONDecodeError:
        return {"error": "Invalid JSON in --new-positions"}

    landscape = _load_json(_narrative_dir(slug) / "landscape.json")
    if not landscape or "landscape_map" not in landscape:
        return {"error": "No landscape data found. Run map-landscape first."}

    comps = landscape["landscape_map"].get("competitors", [])
    old_positions = {}
    for c in comps:
        if c["name"].lower() == competitor.lower():
            old_positions = c.get("positions", {})
            break

    if not old_positions:
        return {"error": f"Competitor '{competitor}' not found in landscape data."}

    shifts = []
    for dim, new_score in new_positions.items():
        old_score = old_positions.get(dim, 0)
        magnitude = abs(new_score - old_score)
        if magnitude > 0:
            direction = "increased" if new_score > old_score else "decreased"
            shifts.append({
                "dimension": dim,
                "old_score": old_score,
                "new_score": new_score,
                "direction": direction,
                "magnitude": magnitude,
            })

    significant = [s for s in shifts if s["magnitude"] > 2]
    if significant:
        implication = (f"{competitor} is making significant moves on "
                       f"{', '.join(s['dimension'] for s in significant)}. "
                       "This signals a strategic repositioning that may affect your positioning.")
        response = "Monitor closely and consider reinforcing your strengths in overlapping dimensions."
    elif shifts:
        implication = f"{competitor} has minor positioning adjustments. No immediate strategic threat."
        response = "Continue current strategy; review at next quarterly planning."
    else:
        implication = "No detectable shifts."
        response = "No action required."

    # Update stored positions
    for c in comps:
        if c["name"].lower() == competitor.lower():
            c["positions"].update(new_positions)
            break
    landscape["updated_at"] = datetime.now().isoformat()
    _save_json(_narrative_dir(slug) / "landscape.json", landscape)

    return {
        "competitor": competitor,
        "shifts": shifts,
        "significant_shifts": len(significant),
        "strategic_implication": implication,
        "recommended_response": response,
    }


def generate_counter(slug, competitor, their_move, move_type):
    err = _brand_check(slug)
    if err:
        return err

    # Strategy templates by move type
    playbooks = {
        "price-cut": [
            {"strategy_type": "reframe", "description": "Reframe the conversation from price to value and total cost of ownership.",
             "content_angles": ["ROI comparison", "Hidden costs of cheap solutions", "Customer success stories"],
             "timeline": "1-2 weeks", "channels": ["blog", "social", "email", "sales-enablement"], "risk_level": "low"},
            {"strategy_type": "social-proof", "description": "Amplify customer testimonials emphasizing value over price.",
             "content_angles": ["Case studies with hard ROI numbers", "Customer video testimonials", "Third-party reviews"],
             "timeline": "2-3 weeks", "channels": ["website", "social", "paid-ads"], "risk_level": "low"},
            {"strategy_type": "direct", "description": "Introduce a competitive tier or limited offer to match without devaluing core product.",
             "content_angles": ["Starter tier announcement", "Limited-time migration offer", "Comparison landing page"],
             "timeline": "2-4 weeks", "channels": ["website", "email", "paid-ads", "PR"], "risk_level": "medium"},
        ],
        "feature-launch": [
            {"strategy_type": "reframe", "description": "Reposition the new feature as table stakes and highlight your differentiated capabilities.",
             "content_angles": ["We had this since day one", "What really matters beyond features", "Integration depth"],
             "timeline": "1 week", "channels": ["blog", "social", "product-updates"], "risk_level": "low"},
            {"strategy_type": "category", "description": "Elevate the conversation above individual features to category leadership.",
             "content_angles": ["Vision content", "Industry trend analysis", "Platform vs point-solution narrative"],
             "timeline": "2-3 weeks", "channels": ["blog", "PR", "thought-leadership", "webinars"], "risk_level": "low"},
        ],
        "rebrand": [
            {"strategy_type": "zeitgeist", "description": "Use the rebrand moment to highlight your consistency and trust.",
             "content_angles": ["Stability messaging", "Track record content", "Customer continuity stories"],
             "timeline": "1-2 weeks", "channels": ["social", "email", "PR"], "risk_level": "low"},
            {"strategy_type": "direct", "description": "Launch a 'we've always been this' campaign showing your established positioning.",
             "content_angles": ["Heritage storytelling", "Product evolution timeline", "Customer relationship longevity"],
             "timeline": "2-4 weeks", "channels": ["blog", "social", "website", "video"], "risk_level": "medium"},
        ],
        "category-creation": [
            {"strategy_type": "category", "description": "Challenge the new category definition and propose a broader or better-fitting frame.",
             "content_angles": ["Alternative category definition", "Analyst briefings", "Thought leadership on market evolution"],
             "timeline": "2-4 weeks", "channels": ["PR", "analyst-relations", "blog", "webinars"], "risk_level": "medium"},
            {"strategy_type": "reframe", "description": "Acknowledge the trend but position yourself as the more complete solution.",
             "content_angles": ["Category plus approach", "Beyond the buzzword content", "Customer outcome focus"],
             "timeline": "1-2 weeks", "channels": ["blog", "social", "sales-enablement"], "risk_level": "low"},
        ],
        "market-entry": [
            {"strategy_type": "social-proof", "description": "Flood the zone with customer proof and incumbent advantages.",
             "content_angles": ["Customer count milestones", "Integration ecosystem", "Years of domain expertise"],
             "timeline": "1-2 weeks", "channels": ["social", "PR", "website", "paid-ads"], "risk_level": "low"},
            {"strategy_type": "direct", "description": "Create competitive comparison content targeting the new entrant's weaknesses.",
             "content_angles": ["Feature comparison", "Migration risk analysis", "Maturity gap content"],
             "timeline": "2-3 weeks", "channels": ["website", "paid-ads", "sales-enablement"], "risk_level": "medium"},
        ],
        "partnership": [
            {"strategy_type": "zeitgeist", "description": "Announce or highlight your own partnership ecosystem.",
             "content_angles": ["Partner ecosystem overview", "Integration marketplace", "Joint customer wins"],
             "timeline": "1-3 weeks", "channels": ["PR", "blog", "email", "partner-channels"], "risk_level": "low"},
            {"strategy_type": "reframe", "description": "Highlight independence and flexibility as strengths versus lock-in.",
             "content_angles": ["Open platform narrative", "Customer choice emphasis", "Vendor neutrality benefits"],
             "timeline": "1-2 weeks", "channels": ["blog", "social", "sales-enablement"], "risk_level": "low"},
        ],
    }

    responses = playbooks.get(move_type, playbooks["feature-launch"])
    assessment = (f"{competitor} has made a '{move_type}' move: {their_move}. "
                  f"This requires a calibrated response across {len(responses)} strategic options.")

    return {
        "counter_playbook": {
            "assessment": assessment,
            "competitor": competitor,
            "their_move": their_move,
            "move_type": move_type,
            "recommended_responses": responses,
            "generated_at": datetime.now().isoformat(),
        }
    }


def track_narrative(slug, data_str):
    err = _brand_check(slug)
    if err:
        return err

    try:
        data = json.loads(data_str) if isinstance(data_str, str) else data_str
    except json.JSONDecodeError:
        return {"error": "Invalid JSON in --data"}

    ndir = _narrative_dir(slug)
    snapshots = _load_json(ndir / "snapshots.json", [])
    if not isinstance(snapshots, list):
        snapshots = []

    snapshot = {
        "snapshot_id": f"snap-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "competitors": data.get("competitors", []),
        "recorded_at": datetime.now().isoformat(),
    }
    snapshots.append(snapshot)
    _save_json(ndir / "snapshots.json", snapshots)

    return {"status": "snapshot_saved", "snapshot_id": snapshot["snapshot_id"],
            "competitors_recorded": len(snapshot["competitors"]),
            "total_snapshots": len(snapshots)}


def narrative_trend(slug, since=None):
    err = _brand_check(slug)
    if err:
        return err

    ndir = _narrative_dir(slug)
    snapshots = _load_json(ndir / "snapshots.json", [])
    if not isinstance(snapshots, list):
        snapshots = []

    if since:
        snapshots = [s for s in snapshots if s.get("recorded_at", "") >= since]

    if len(snapshots) < 2:
        return {"snapshots_compared": len(snapshots), "biggest_shifts": [],
                "emerging_trends": [], "your_trajectory": "insufficient_data",
                "note": "Need at least 2 snapshots to detect trends."}

    # Compare first and last snapshots
    first = snapshots[0]
    last = snapshots[-1]

    shifts = []
    first_comps = {c["name"]: c.get("positions", {}) for c in first.get("competitors", [])}
    last_comps = {c["name"]: c.get("positions", {}) for c in last.get("competitors", [])}

    for name in set(list(first_comps.keys()) + list(last_comps.keys())):
        old = first_comps.get(name, {})
        new = last_comps.get(name, {})
        for dim in set(list(old.keys()) + list(new.keys())):
            old_val = old.get(dim, 0)
            new_val = new.get(dim, 0)
            if abs(new_val - old_val) >= 2:
                shifts.append({"competitor": name, "dimension": dim,
                               "old_score": old_val, "new_score": new_val,
                               "magnitude": abs(new_val - old_val)})

    shifts.sort(key=lambda s: s["magnitude"], reverse=True)

    # Emerging trends: dimensions where multiple competitors moved in same direction
    dim_moves = {}
    for s in shifts:
        d = s["dimension"]
        direction = "up" if s["new_score"] > s["old_score"] else "down"
        dim_moves.setdefault(d, []).append(direction)

    trends = []
    for d, moves in dim_moves.items():
        if len(moves) >= 2 and len(set(moves)) == 1:
            trends.append({"dimension": d, "direction": moves[0],
                           "competitors_moving": len(moves)})

    # Your trajectory from landscape
    landscape = _load_json(ndir / "landscape.json")
    your_pos = landscape.get("landscape_map", {}).get("your_positions", {})
    trajectory = "stable"
    if your_pos and shifts:
        your_dims = set(your_pos.keys())
        contested = [s for s in shifts if s["dimension"] in your_dims and s["new_score"] > s["old_score"]]
        if len(contested) > len(shifts) / 2:
            trajectory = "under_pressure"
        elif not contested:
            trajectory = "strengthening"

    return {"snapshots_compared": len(snapshots), "biggest_shifts": shifts[:10],
            "emerging_trends": trends, "your_trajectory": trajectory}


def summary_action(slug):
    err = _brand_check(slug)
    if err:
        return err

    ndir = _narrative_dir(slug)
    landscape = _load_json(ndir / "landscape.json")
    snapshots = _load_json(ndir / "snapshots.json", [])
    if not isinstance(snapshots, list):
        snapshots = []

    if not landscape or "landscape_map" not in landscape:
        return {"total_competitors_mapped": 0, "dimensions_tracked": 0,
                "your_strongest_position": None, "biggest_threat": None,
                "biggest_opportunity": None, "last_updated": None}

    lm = landscape["landscape_map"]
    comps = lm.get("competitors", [])
    dims = [d["name"] for d in lm.get("dimensions", [])]
    your_pos = lm.get("your_positions", {})

    # Strongest position
    strongest = max(dims, key=lambda d: your_pos.get(d, 0)) if dims else None

    # Biggest threat: competitor closest to your position overall
    threat = None
    min_dist = float("inf")
    for c in comps:
        dist = _euclidean(your_pos, c.get("positions", {}), dims)
        if dist < min_dist:
            min_dist = dist
            threat = c["name"]

    # Biggest opportunity: gap with highest opportunity score
    gaps = landscape.get("gaps", [])
    opportunity = gaps[0]["dimension"] if gaps else (landscape.get("opportunity_scores", {}) or {None: None})

    if isinstance(opportunity, dict):
        opp_items = list(opportunity.items())
        opportunity = opp_items[0][0] if opp_items else None

    return {
        "total_competitors_mapped": len(comps),
        "dimensions_tracked": len(dims),
        "your_strongest_position": strongest,
        "biggest_threat": threat,
        "biggest_opportunity": opportunity,
        "last_updated": landscape.get("updated_at"),
        "total_snapshots": len(snapshots),
    }


# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Narrative Mapper — Map competitive positioning and narrative territories for Digital Marketing Pro"
    )
    parser.add_argument("--brand", type=_common.path_component, required=True, help="Brand slug")
    parser.add_argument(
        "--action", required=True,
        choices=["map-landscape", "find-gaps", "detect-shifts",
                 "generate-counter", "track-narrative", "narrative-trend",
                 "summary"],
        help="Action to perform",
    )
    parser.add_argument("--data", help="JSON data payload")
    parser.add_argument("--competitor", help="Competitor name")
    parser.add_argument("--new-positions", help="JSON of new dimension scores (detect-shifts)")
    parser.add_argument("--their-move", help="Description of competitor move (generate-counter)")
    parser.add_argument("--move-type", choices=MOVE_TYPES,
                        help="Type of competitive move (generate-counter)")
    parser.add_argument("--since", help="Filter snapshots since date (narrative-trend)")

    args = parser.parse_args()
    args.brand = _common.slugify_brand(args.brand)

    if args.action == "map-landscape":
        if not args.data:
            print(json.dumps({"error": "Provide --data with dimensions, competitors, and your_positions"}))
            sys.exit(1)
        result = map_landscape(args.brand, args.data)

    elif args.action == "find-gaps":
        result = find_gaps(args.brand)

    elif args.action == "detect-shifts":
        if not args.competitor or not args.new_positions:
            print(json.dumps({"error": "Provide --competitor and --new-positions"}))
            sys.exit(1)
        result = detect_shifts(args.brand, args.competitor, args.new_positions)

    elif args.action == "generate-counter":
        if not args.competitor or not args.their_move or not args.move_type:
            print(json.dumps({"error": "Provide --competitor, --their-move, and --move-type"}))
            sys.exit(1)
        result = generate_counter(args.brand, args.competitor, args.their_move, args.move_type)

    elif args.action == "track-narrative":
        if not args.data:
            print(json.dumps({"error": "Provide --data with competitor positions"}))
            sys.exit(1)
        result = track_narrative(args.brand, args.data)

    elif args.action == "narrative-trend":
        result = narrative_trend(args.brand, args.since)

    elif args.action == "summary":
        result = summary_action(args.brand)

    _common.finish(result)


if __name__ == "__main__":
    main()
