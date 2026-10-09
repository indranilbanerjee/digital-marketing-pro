#!/usr/bin/env python3
"""Journey Engine — Customer journey state machine with simulation.

Design, simulate, and track customer journeys using a state-machine model.
Supports Monte Carlo simulation of cohort progression, bottleneck detection,
and touchpoint mapping across channels.

Dependencies: none (stdlib only)

Usage:
    python journey-engine.py --action create-journey --brand acme --name "Onboarding Flow" --states '[{"name":"Awareness","description":"First touch"}]' --transitions '[{"from_state":"Awareness","to_state":"Consideration","trigger":"ad_click","probability":0.4,"channel":"paid_search","content_brief":"Search ad"}]'
    python journey-engine.py --action simulate --brand acme --journey-id onboarding-flow --cohort-size 5000
    python journey-engine.py --action list-journeys --brand acme
    python journey-engine.py --action get-journey --brand acme --journey-id onboarding-flow
    python journey-engine.py --action analyze-bottleneck --brand acme --journey-id onboarding-flow
    python journey-engine.py --action touchpoint-map --brand acme --journey-id onboarding-flow
    python journey-engine.py --action delete-journey --brand acme --journey-id onboarding-flow
"""

import argparse
import json
import random
import sys
from datetime import datetime
from pathlib import Path
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

# Default dwell time (days) per state when not specified
DEFAULT_DWELL_DAYS = 3
# Max steps before a simulated customer is considered "stuck"
MAX_SIM_STEPS = 50


def _get_brand_dir(slug):
    """Resolve + validate the brand directory via _common (slug normalised,
    legacy raw-name dirs honoured, standard not-found message)."""
    return _common.get_brand_dir(slug)


def _journeys_dir(brand_dir):
    d = brand_dir / "journeys"
    d.mkdir(exist_ok=True)
    return d


def _journey_id_from_name(name):
    return name.lower().replace(" ", "-").replace("_", "-")[:60]


def _load_journey(brand_dir, journey_id):
    fp, path_err = _common.child_or_error(_journeys_dir(brand_dir), journey_id, ".json")
    if path_err:
        return None, path_err
    if not fp.exists():
        return None, f"Journey '{journey_id}' not found."
    try:
        return json.loads(fp.read_text(encoding="utf-8")), None
    except json.JSONDecodeError:
        return None, f"Journey file corrupted: {journey_id}"


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def create_journey(slug, name, states, transitions):
    brand_dir, err = _get_brand_dir(slug)
    if err:
        return {"error": err}

    state_names = {s["name"] for s in states}
    validation_errors = []

    # Validate transitions reference existing states
    for i, t in enumerate(transitions):
        if t.get("from_state") not in state_names:
            validation_errors.append(f"Transition {i}: from_state '{t.get('from_state')}' not in states")
        if t.get("to_state") not in state_names:
            validation_errors.append(f"Transition {i}: to_state '{t.get('to_state')}' not in states")
        prob = t.get("probability", 0)
        if not (0 <= prob <= 1):
            validation_errors.append(f"Transition {i}: probability {prob} not in [0, 1]")

    if validation_errors:
        return {"error": "Validation failed", "validation_errors": validation_errors}

    # Check outbound probabilities per state don't exceed 1
    for sn in state_names:
        outbound = [t for t in transitions if t["from_state"] == sn]
        total_prob = sum(t.get("probability", 0) for t in outbound)
        if total_prob > 1.0001:
            validation_errors.append(f"State '{sn}': outbound probabilities sum to {round(total_prob, 4)} (>1)")

    if validation_errors:
        return {"error": "Validation failed", "validation_errors": validation_errors}

    journey_id = _journey_id_from_name(name)
    now = datetime.now().isoformat()

    journey = {
        "journey_id": journey_id,
        "name": name,
        "brand": slug,
        "states": states,
        "transitions": transitions,
        "created_at": now,
        "updated_at": now,
    }

    jdir = _journeys_dir(brand_dir)
    fp, path_err = _common.child_or_error(jdir, journey_id, ".json")
    if path_err:
        return {"error": path_err}
    fp.write_text(json.dumps(journey, indent=2), encoding="utf-8")

    return {
        "status": "created",
        "journey_id": journey_id,
        "states_count": len(states),
        "transitions_count": len(transitions),
        "validation": "passed",
        "path": str(fp),
    }


def simulate(slug, journey_id, cohort_size, seed):
    brand_dir, err = _get_brand_dir(slug)
    if err:
        return {"error": err}

    journey, err = _load_journey(brand_dir, journey_id)
    if err:
        return {"error": err}

    states = journey["states"]
    transitions = journey["transitions"]
    state_names = [s["name"] for s in states]
    if not state_names:
        return {"error": "Journey has no states."}

    start_state = state_names[0]
    # Build transition lookup: from_state -> list of (to_state, probability, channel)
    trans_map = {}
    for t in transitions:
        fs = t["from_state"]
        trans_map.setdefault(fs, []).append({
            "to_state": t["to_state"],
            "probability": t.get("probability", 0),
            "channel": t.get("channel", "unknown"),
        })

    # Determine terminal states (no outbound transitions)
    terminal_states = {sn for sn in state_names if sn not in trans_map}

    # Dwell times per state
    dwell_map = {}
    for s in states:
        dwell_map[s["name"]] = s.get("dwell_days", DEFAULT_DWELL_DAYS)

    rng = random.Random(seed)
    state_visit_counts = {sn: 0 for sn in state_names}
    state_reach_counts = {sn: 0 for sn in state_names}
    channel_touchpoints = {}
    touchpoint_counts = []
    journey_times = []
    converted_count = 0
    last_state = state_names[-1]  # assume last state is "conversion" goal

    for _ in range(cohort_size):
        current = start_state
        visited = set()
        steps = 0
        total_days = 0.0
        customer_channels = []

        while steps < MAX_SIM_STEPS:
            state_visit_counts[current] = state_visit_counts.get(current, 0) + 1
            if current not in visited:
                state_reach_counts[current] = state_reach_counts.get(current, 0) + 1
                visited.add(current)

            total_days += dwell_map.get(current, DEFAULT_DWELL_DAYS)

            if current in terminal_states:
                break

            outbound = trans_map.get(current, [])
            if not outbound:
                break

            # Decide next state using probabilities
            roll = rng.random()
            cumulative = 0.0
            moved = False
            for tr in outbound:
                cumulative += tr["probability"]
                if roll < cumulative:
                    customer_channels.append(tr["channel"])
                    ch = tr["channel"]
                    channel_touchpoints[ch] = channel_touchpoints.get(ch, 0) + 1
                    current = tr["to_state"]
                    moved = True
                    break

            if not moved:
                # Drop off — probabilities didn't cover roll
                break

            steps += 1

        touchpoint_counts.append(len(customer_channels))
        journey_times.append(total_days)

        if current == last_state:
            converted_count += 1

    # Build funnel
    state_funnel = []
    for sn in state_names:
        state_funnel.append({
            "state": sn,
            "reached": state_reach_counts.get(sn, 0),
            "pct_of_cohort": round(state_reach_counts.get(sn, 0) / cohort_size * 100, 1),
        })

    # Drop-off rates between consecutive states
    drop_off_rates = {}
    for i in range(1, len(state_names)):
        prev_reach = state_reach_counts.get(state_names[i - 1], 0)
        curr_reach = state_reach_counts.get(state_names[i], 0)
        if prev_reach > 0:
            drop_off = round((1 - curr_reach / prev_reach) * 100, 1)
        else:
            drop_off = 100.0
        drop_off_rates[f"{state_names[i-1]} -> {state_names[i]}"] = drop_off

    # Identify bottleneck (highest drop-off)
    bottleneck_state = None
    max_drop = -1
    for key, val in drop_off_rates.items():
        if val > max_drop:
            max_drop = val
            bottleneck_state = key

    # Channel distribution
    total_touches = sum(channel_touchpoints.values()) or 1
    channel_dist = {ch: round(cnt / total_touches * 100, 1) for ch, cnt in channel_touchpoints.items()}

    avg_touchpoints = round(sum(touchpoint_counts) / len(touchpoint_counts), 1) if touchpoint_counts else 0
    avg_time = round(sum(journey_times) / len(journey_times), 1) if journey_times else 0

    return {
        "journey_id": journey_id,
        "cohort_size": cohort_size,
        "seed": seed,
        "conversion_rate": round(converted_count / cohort_size * 100, 2),
        "avg_touchpoints": avg_touchpoints,
        "avg_time_to_convert_days": avg_time,
        "state_funnel": state_funnel,
        "bottleneck_state": bottleneck_state,
        "drop_off_rates": drop_off_rates,
        "channel_distribution": channel_dist,
        "converted": converted_count,
    }


def list_journeys(slug):
    brand_dir, err = _get_brand_dir(slug)
    if err:
        return {"error": err}

    jdir = brand_dir / "journeys"
    if not jdir.exists():
        return {"journeys": [], "total": 0, "note": "No journeys created yet."}

    journeys = []
    for fp in sorted(jdir.glob("*.json")):
        try:
            j = json.loads(fp.read_text(encoding="utf-8"))
            journeys.append({
                "journey_id": j.get("journey_id", fp.stem),
                "name": j.get("name", "Untitled"),
                "states_count": len(j.get("states", [])),
                "transitions_count": len(j.get("transitions", [])),
                "created_at": j.get("created_at", ""),
            })
        except json.JSONDecodeError:
            continue

    return {"journeys": journeys, "total": len(journeys)}


def get_journey(slug, journey_id):
    brand_dir, err = _get_brand_dir(slug)
    if err:
        return {"error": err}

    journey, err = _load_journey(brand_dir, journey_id)
    if err:
        return {"error": err}
    return journey


def analyze_bottleneck(slug, journey_id, data):
    brand_dir, err = _get_brand_dir(slug)
    if err:
        return {"error": err}

    journey, err = _load_journey(brand_dir, journey_id)
    if err:
        return {"error": err}

    states = journey["states"]
    transitions = journey["transitions"]
    state_names = [s["name"] for s in states]

    # If actual data provided, use it; otherwise derive from transition probabilities
    if data:
        state_conversions = data
    else:
        # Simulate expected flow: start with 1.0 at first state
        flow = {state_names[0]: 1.0}
        trans_map = {}
        for t in transitions:
            trans_map.setdefault(t["from_state"], []).append(t)

        for sn in state_names:
            if sn not in flow:
                flow[sn] = 0.0
            outbound = trans_map.get(sn, [])
            for tr in outbound:
                dest = tr["to_state"]
                flow[dest] = flow.get(dest, 0.0) + flow[sn] * tr.get("probability", 0)

        state_conversions = {sn: round(flow.get(sn, 0.0), 4) for sn in state_names}

    # Find the biggest drop between consecutive states
    bottleneck = None
    worst_drop = -1
    upstream_states = []

    for i in range(1, len(state_names)):
        prev = state_conversions.get(state_names[i - 1], 0)
        curr = state_conversions.get(state_names[i], 0)
        if prev > 0:
            drop = (prev - curr) / prev
        else:
            drop = 1.0

        if drop > worst_drop:
            worst_drop = drop
            bottleneck = state_names[i - 1]
            upstream_states = state_names[:i]

    # Generate recommendations based on bottleneck position
    recommendations = []
    if bottleneck:
        idx = state_names.index(bottleneck) if bottleneck in state_names else 0
        position = idx / max(len(state_names) - 1, 1)

        if position < 0.3:
            recommendations = [
                "Improve awareness messaging and targeting",
                "Test alternative acquisition channels",
                "Review entry criteria alignment with audience",
            ]
        elif position < 0.6:
            recommendations = [
                "Strengthen mid-funnel content and nurture sequences",
                "Add social proof and case studies at this stage",
                "Reduce friction in the transition to next stage",
            ]
        else:
            recommendations = [
                "Simplify the conversion/purchase process",
                "Add urgency or incentive at decision point",
                "Implement retargeting for drop-offs at this stage",
                "Review pricing or offer alignment",
            ]

    return {
        "journey_id": journey_id,
        "bottleneck_state": bottleneck,
        "drop_off_rate": round(worst_drop * 100, 1) if worst_drop >= 0 else 0,
        "state_flow": state_conversions,
        "upstream_states": upstream_states,
        "recommended_interventions": recommendations,
    }


def touchpoint_map(slug, journey_id):
    brand_dir, err = _get_brand_dir(slug)
    if err:
        return {"error": err}

    journey, err = _load_journey(brand_dir, journey_id)
    if err:
        return {"error": err}

    transitions = journey["transitions"]

    channels_used = set()
    touchpoints_per_channel = {}
    sequence_flow = []

    for t in transitions:
        ch = t.get("channel", "unspecified")
        channels_used.add(ch)
        touchpoints_per_channel.setdefault(ch, []).append({
            "from_state": t["from_state"],
            "to_state": t["to_state"],
            "trigger": t.get("trigger", ""),
            "content_brief": t.get("content_brief", ""),
        })
        sequence_flow.append({
            "step": f"{t['from_state']} -> {t['to_state']}",
            "channel": ch,
            "trigger": t.get("trigger", ""),
            "content_brief": t.get("content_brief", ""),
            "probability": t.get("probability", 0),
        })

    return {
        "journey_id": journey_id,
        "channels_used": sorted(channels_used),
        "touchpoints_per_channel": {ch: len(tps) for ch, tps in touchpoints_per_channel.items()},
        "touchpoints_detail": touchpoints_per_channel,
        "sequence_flow": sequence_flow,
        "total_touchpoints": len(transitions),
    }


def delete_journey(slug, journey_id):
    brand_dir, err = _get_brand_dir(slug)
    if err:
        return {"error": err}

    fp, path_err = _common.child_or_error(_journeys_dir(brand_dir), journey_id, ".json")
    if path_err:
        return {"error": path_err}
    if not fp.exists():
        return {"error": f"Journey '{journey_id}' not found."}

    fp.unlink()
    return {"status": "deleted", "journey_id": journey_id}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Journey Engine — Customer journey state machine with simulation"
    )
    parser.add_argument("--action", required=True,
                        choices=["create-journey", "simulate", "list-journeys",
                                 "get-journey", "analyze-bottleneck",
                                 "touchpoint-map", "delete-journey"],
                        help="Action to perform")
    parser.add_argument("--brand", type=_common.path_component, help="Brand slug")
    parser.add_argument("--name", help="Journey name (for create-journey)")
    parser.add_argument("--states", help="JSON array of state objects (for create-journey)")
    parser.add_argument("--transitions", help="JSON array of transition objects (for create-journey)")
    parser.add_argument("--journey-id", dest="journey_id", help="Journey ID")
    parser.add_argument("--cohort-size", dest="cohort_size", type=int, default=1000,
                        help="Number of simulated customers (default: 1000)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility (default: 42)")
    parser.add_argument("--data", help="JSON with actual conversion data per state (for analyze-bottleneck)")
    args = parser.parse_args()

    result = None

    if not args.brand:
        print(json.dumps({"error": "Provide --brand slug"}))
        sys.exit(1)
    args.brand = _common.slugify_brand(args.brand)

    if args.action == "create-journey":
        if not args.name:
            print(json.dumps({"error": "Provide --name for the journey"}))
            sys.exit(1)
        if not args.states:
            print(json.dumps({"error": "Provide --states JSON array"}))
            sys.exit(1)
        if not args.transitions:
            print(json.dumps({"error": "Provide --transitions JSON array"}))
            sys.exit(1)
        try:
            states = json.loads(args.states)
            transitions = json.loads(args.transitions)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --states or --transitions"}))
            sys.exit(1)
        result = create_journey(args.brand, args.name, states, transitions)

    elif args.action == "simulate":
        if not args.journey_id:
            print(json.dumps({"error": "Provide --journey-id"}))
            sys.exit(1)
        result = simulate(args.brand, args.journey_id, args.cohort_size, args.seed)

    elif args.action == "list-journeys":
        result = list_journeys(args.brand)

    elif args.action == "get-journey":
        if not args.journey_id:
            print(json.dumps({"error": "Provide --journey-id"}))
            sys.exit(1)
        result = get_journey(args.brand, args.journey_id)

    elif args.action == "analyze-bottleneck":
        if not args.journey_id:
            print(json.dumps({"error": "Provide --journey-id"}))
            sys.exit(1)
        data = None
        if args.data:
            try:
                data = json.loads(args.data)
            except json.JSONDecodeError:
                print(json.dumps({"error": "Invalid JSON in --data"}))
                sys.exit(1)
        result = analyze_bottleneck(args.brand, args.journey_id, data)

    elif args.action == "touchpoint-map":
        if not args.journey_id:
            print(json.dumps({"error": "Provide --journey-id"}))
            sys.exit(1)
        result = touchpoint_map(args.brand, args.journey_id)

    elif args.action == "delete-journey":
        if not args.journey_id:
            print(json.dumps({"error": "Provide --journey-id"}))
            sys.exit(1)
        result = delete_journey(args.brand, args.journey_id)

    if result is not None:
        _common.finish(result)


if __name__ == "__main__":
    main()
