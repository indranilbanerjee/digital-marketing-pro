#!/usr/bin/env python3
"""
intelligence-graph.py
=====================
Compound marketing intelligence system for Digital Marketing Pro.

Stores structured learnings from agents, queries them by context, tracks
confidence over time with evidence, synthesizes cross-agent patterns,
and exports actionable playbooks.  Supports time-decay and archival.

Storage: ~/.claude-marketing/brands/{slug}/intelligence/active/
         ~/.claude-marketing/brands/{slug}/intelligence/archived/

Dependencies: none (stdlib only)

Usage:
    python intelligence-graph.py --brand acme --action save-learning --agent seo-specialist --insight "Long-form content (2000+ words) outperforms short posts by 3x on organic traffic" --conditions '{"channel":"organic","audience":"developers","objective":"traffic"}' --confidence 0.8
    python intelligence-graph.py --brand acme --action query-relevant --context '{"channel":"organic","objective":"traffic"}'
    python intelligence-graph.py --brand acme --action update-confidence --learning-id lrn_abc123 --direction up --evidence "Confirmed in Q1 2026 content audit"
    python intelligence-graph.py --brand acme --action get-patterns --dimension channel
    python intelligence-graph.py --brand acme --action get-stats
    python intelligence-graph.py --brand acme --action archive-stale --max-age-days 180 --min-confidence 0.3
    python intelligence-graph.py --brand acme --action export-playbook --channel organic --min-confidence 0.6
    python intelligence-graph.py --brand acme --action apply-time-decay --decay-rate 0.01
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

BRANDS_DIR = _common.brands_root()

CONTEXT_DIMENSIONS = ["channel", "audience", "objective", "industry", "campaign_type"]


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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _intel_dirs(slug):
    base = BRANDS_DIR / slug / "intelligence"
    active = base / "active"
    archived = base / "archived"
    return base, active, archived


def _load_all_learnings(active_dir):
    if not active_dir.exists():
        return []
    learnings = []
    for f in sorted(active_dir.glob("lrn_*.json")):
        obj = _load_json(f, None)
        if obj and isinstance(obj, dict):
            learnings.append(obj)
    return learnings


def _brand_check(slug):
    brand_dir = BRANDS_DIR / slug
    if not brand_dir.exists():
        return {"error": f"Brand '{slug}' not found. Run /digital-marketing-pro:brand-setup first."}
    return None


# ── Actions ──────────────────────────────────────────────────────────────────

def save_learning(slug, agent, insight, conditions, confidence, evidence):
    err = _brand_check(slug)
    if err:
        return err

    ts = datetime.now().isoformat()
    raw = f"{slug}:{agent}:{insight}:{ts}"
    learning_id = "lrn_" + hashlib.sha256(raw.encode()).hexdigest()[:12]

    record = {
        "learning_id": learning_id,
        "brand": slug,
        "source_agent": agent,
        "insight": insight,
        "conditions": conditions,
        "confidence": round(min(1.0, max(0.0, confidence)), 2),
        "evidence": [{"text": evidence, "direction": "initial", "added_at": ts}] if evidence else [],
        "created_at": ts,
        "last_validated": ts,
    }

    _, active_dir, _ = _intel_dirs(slug)
    active_dir.mkdir(parents=True, exist_ok=True)
    _save_json(active_dir / f"{learning_id}.json", record)

    return {"status": "saved", "learning_id": learning_id, "confidence": record["confidence"]}


def query_relevant(slug, context):
    err = _brand_check(slug)
    if err:
        return err

    _, active_dir, _ = _intel_dirs(slug)
    learnings = _load_all_learnings(active_dir)
    if not learnings:
        return {"results": [], "total": 0, "note": "No learnings stored yet."}

    now = datetime.now()
    scored = []
    for l in learnings:
        conds = l.get("conditions", {})
        # Relevance: how many context dimensions match
        match_count = 0
        total_dims = 0
        for dim in CONTEXT_DIMENSIONS:
            ctx_val = context.get(dim)
            cond_val = conds.get(dim)
            if ctx_val:
                total_dims += 1
                if cond_val and cond_val.lower() == ctx_val.lower():
                    match_count += 1

        if total_dims == 0:
            relevance = 0.5  # no context provided, give equal weight
        else:
            relevance = match_count / total_dims

        # Recency factor: newer = higher (half-life 90 days)
        try:
            created = datetime.fromisoformat(l["last_validated"])
            age_days = (now - created).days
        except (KeyError, ValueError):
            age_days = 365

        recency = max(0.1, 1.0 / (1 + age_days / 90))

        conf = l.get("confidence", 0.5)
        final_score = round(relevance * conf * recency, 4)

        if final_score > 0:
            scored.append({
                "learning_id": l["learning_id"],
                "insight": l["insight"],
                "confidence": conf,
                "source_agent": l.get("source_agent", "unknown"),
                "relevance_score": round(relevance, 3),
                "recency_factor": round(recency, 3),
                "final_score": final_score,
                "age_days": age_days,
                "conditions": conds,
            })

    scored.sort(key=lambda s: -s["final_score"])
    top = scored[:10]
    return {"results": top, "total": len(scored), "context_used": context}


def update_confidence(slug, learning_id, direction, evidence):
    err = _brand_check(slug)
    if err:
        return err

    _, active_dir, _ = _intel_dirs(slug)
    fpath = active_dir / f"{learning_id}.json"
    if not fpath.exists():
        return {"error": f"Learning '{learning_id}' not found."}

    record = _load_json(fpath, {})
    old_conf = record.get("confidence", 0.5)

    if direction == "up":
        new_conf = min(1.0, old_conf + 0.1)
    else:
        new_conf = max(0.0, old_conf - 0.2)

    record["confidence"] = round(new_conf, 2)
    record["last_validated"] = datetime.now().isoformat()
    record.setdefault("evidence", []).append({
        "text": evidence,
        "direction": direction,
        "added_at": datetime.now().isoformat(),
    })

    _save_json(fpath, record)
    return {
        "learning_id": learning_id,
        "old_confidence": round(old_conf, 2),
        "new_confidence": round(new_conf, 2),
        "total_evidence_count": len(record["evidence"]),
    }


def get_patterns(slug, dimension):
    err = _brand_check(slug)
    if err:
        return err

    _, active_dir, _ = _intel_dirs(slug)
    learnings = _load_all_learnings(active_dir)
    if not learnings:
        return {"patterns": [], "dimension": dimension, "note": "No learnings stored yet."}

    # Group by dimension value
    groups = {}
    for l in learnings:
        val = l.get("conditions", {}).get(dimension, "unspecified")
        groups.setdefault(val, []).append(l)

    patterns = []
    for dim_val, items in sorted(groups.items()):
        confs = [i.get("confidence", 0.5) for i in items]
        avg_conf = round(sum(confs) / len(confs), 3) if confs else 0
        agents = list(set(i.get("source_agent", "unknown") for i in items))

        # Top insights: highest confidence first
        sorted_items = sorted(items, key=lambda i: -i.get("confidence", 0))
        top_insights = [{"insight": i["insight"], "confidence": i["confidence"]} for i in sorted_items[:5]]

        patterns.append({
            "dimension_value": dim_val,
            "learnings_count": len(items),
            "avg_confidence": avg_conf,
            "top_insights": top_insights,
            "contributing_agents": agents,
        })

    patterns.sort(key=lambda p: -p["learnings_count"])
    return {"patterns": patterns, "dimension": dimension, "total_groups": len(patterns)}


def get_stats(slug):
    err = _brand_check(slug)
    if err:
        return err

    _, active_dir, archived_dir = _intel_dirs(slug)
    learnings = _load_all_learnings(active_dir)

    if not learnings:
        return {"total_learnings": 0, "by_agent": {}, "by_channel": {}, "avg_confidence": 0, "highest_confidence_learning": None, "stalest_learning": None, "freshest_learning": None}

    by_agent = {}
    by_channel = {}
    confs = []
    for l in learnings:
        agent = l.get("source_agent", "unknown")
        by_agent[agent] = by_agent.get(agent, 0) + 1
        ch = l.get("conditions", {}).get("channel", "unspecified")
        by_channel[ch] = by_channel.get(ch, 0) + 1
        confs.append(l.get("confidence", 0.5))

    avg_conf = round(sum(confs) / len(confs), 3)

    # Highest confidence
    highest = max(learnings, key=lambda l: l.get("confidence", 0))
    highest_out = {"learning_id": highest["learning_id"], "insight": highest["insight"], "confidence": highest["confidence"]}

    # Stalest (oldest last_validated)
    stalest = min(learnings, key=lambda l: l.get("last_validated", l.get("created_at", "")))
    stalest_out = {"learning_id": stalest["learning_id"], "insight": stalest["insight"], "last_validated": stalest.get("last_validated", stalest.get("created_at"))}

    # Freshest
    freshest = max(learnings, key=lambda l: l.get("last_validated", l.get("created_at", "")))
    freshest_out = {"learning_id": freshest["learning_id"], "insight": freshest["insight"], "last_validated": freshest.get("last_validated", freshest.get("created_at"))}

    # Archived count
    archived_count = len(list(archived_dir.glob("lrn_*.json"))) if archived_dir.exists() else 0

    return {
        "total_learnings": len(learnings),
        "archived_learnings": archived_count,
        "by_agent": by_agent,
        "by_channel": by_channel,
        "avg_confidence": avg_conf,
        "highest_confidence_learning": highest_out,
        "stalest_learning": stalest_out,
        "freshest_learning": freshest_out,
    }


def archive_stale(slug, max_age_days, min_confidence):
    err = _brand_check(slug)
    if err:
        return err

    _, active_dir, archived_dir = _intel_dirs(slug)
    archived_dir.mkdir(parents=True, exist_ok=True)
    learnings = _load_all_learnings(active_dir)

    now = datetime.now()
    archived = 0
    for l in learnings:
        try:
            validated = datetime.fromisoformat(l.get("last_validated", l.get("created_at", "")))
            age = (now - validated).days
        except ValueError:
            age = max_age_days + 1

        conf = l.get("confidence", 0.5)
        if age > max_age_days and conf < min_confidence:
            lid = l["learning_id"]
            src = active_dir / f"{lid}.json"
            dst = archived_dir / f"{lid}.json"
            l["archived_at"] = now.isoformat()
            l["archive_reason"] = f"age={age}d, confidence={conf}"
            _save_json(dst, l)
            if src.exists():
                src.unlink()
            archived += 1

    remaining = len(learnings) - archived
    return {"archived_count": archived, "remaining_count": remaining, "criteria": {"max_age_days": max_age_days, "min_confidence": min_confidence}}


def export_playbook(slug, channel=None, audience=None, min_confidence=0.6):
    err = _brand_check(slug)
    if err:
        return err

    _, active_dir, _ = _intel_dirs(slug)
    learnings = _load_all_learnings(active_dir)

    # Filter
    filtered = []
    for l in learnings:
        if l.get("confidence", 0) < min_confidence:
            continue
        conds = l.get("conditions", {})
        if channel and conds.get("channel", "").lower() != channel.lower():
            continue
        if audience and conds.get("audience", "").lower() != audience.lower():
            continue
        filtered.append(l)

    filtered.sort(key=lambda l: -l.get("confidence", 0))

    context_parts = []
    if channel:
        context_parts.append(f"channel={channel}")
    if audience:
        context_parts.append(f"audience={audience}")
    context_str = ", ".join(context_parts) if context_parts else "all"

    title = f"Marketing Playbook — {slug}"
    if channel:
        title += f" / {channel.title()}"

    rules = []
    for l in filtered:
        rules.append({
            "rule": l["insight"],
            "confidence": l["confidence"],
            "source_agent": l.get("source_agent", "unknown"),
            "evidence_count": len(l.get("evidence", [])),
            "last_validated": l.get("last_validated", l.get("created_at")),
        })

    return {
        "playbook_title": title,
        "context": context_str,
        "min_confidence": min_confidence,
        "rules_count": len(rules),
        "rules": rules,
    }


def apply_time_decay(slug, decay_rate):
    err = _brand_check(slug)
    if err:
        return err

    _, active_dir, _ = _intel_dirs(slug)
    learnings = _load_all_learnings(active_dir)

    if not learnings:
        return {"total_affected": 0, "avg_confidence_before": 0, "avg_confidence_after": 0}

    now = datetime.now()
    confs_before = []
    confs_after = []
    affected = 0

    for l in learnings:
        old_conf = l.get("confidence", 0.5)
        confs_before.append(old_conf)

        try:
            validated = datetime.fromisoformat(l.get("last_validated", l.get("created_at", "")))
            months = (now - validated).days / 30.0
        except ValueError:
            months = 6.0

        decay = decay_rate * months
        new_conf = max(0.0, round(old_conf - decay, 3))

        if new_conf != old_conf:
            l["confidence"] = new_conf
            _save_json(active_dir / f"{l['learning_id']}.json", l)
            affected += 1

        confs_after.append(new_conf)

    avg_before = round(sum(confs_before) / len(confs_before), 3)
    avg_after = round(sum(confs_after) / len(confs_after), 3)

    return {
        "total_affected": affected,
        "total_learnings": len(learnings),
        "avg_confidence_before": avg_before,
        "avg_confidence_after": avg_after,
        "decay_rate_per_month": decay_rate,
    }


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Intelligence Graph — Compound marketing intelligence system for Digital Marketing Pro"
    )
    parser.add_argument("--brand", type=_common.path_component, required=True, help="Brand slug")
    parser.add_argument("--action", required=True,
                        choices=["save-learning", "query-relevant",
                                 "update-confidence", "get-patterns",
                                 "get-stats", "archive-stale",
                                 "export-playbook", "apply-time-decay"],
                        help="Action to perform")
    parser.add_argument("--agent", help="Source agent name (for save-learning)")
    parser.add_argument("--insight", help="Learning text (for save-learning)")
    parser.add_argument("--conditions", help="JSON context conditions (for save-learning)")
    parser.add_argument("--confidence", type=float, default=0.5,
                        help="Initial confidence 0-1 (default: 0.5)")
    parser.add_argument("--evidence", help="Supporting evidence text")
    parser.add_argument("--context", help="JSON query context (for query-relevant)")
    parser.add_argument("--learning-id", help="Learning ID (for update-confidence)")
    parser.add_argument("--direction", choices=["up", "down"],
                        help="Confidence direction (for update-confidence)")
    parser.add_argument("--dimension", choices=CONTEXT_DIMENSIONS,
                        help="Grouping dimension (for get-patterns)")
    parser.add_argument("--max-age-days", type=int, default=180,
                        help="Max age in days for archive-stale (default: 180)")
    parser.add_argument("--min-confidence", type=float, default=None,
                        help="Min confidence threshold (default: 0.3 for archive, 0.6 for playbook)")
    parser.add_argument("--channel", help="Filter by channel (for export-playbook)")
    parser.add_argument("--audience", help="Filter by audience (for export-playbook)")
    parser.add_argument("--decay-rate", type=float, default=0.01,
                        help="Decay rate per month (default: 0.01)")

    args = parser.parse_args()

    # Resolve per-action --min-confidence defaults (None = not provided, so an
    # explicit 0.3 is no longer mistaken for "use the playbook default").
    if args.min_confidence is None:
        args.min_confidence = 0.6 if args.action == "export-playbook" else 0.3

    def _parse_json(raw, label):
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            print(json.dumps({"error": f"Invalid JSON in {label}: {e}"}))
            sys.exit(1)

    if args.action == "save-learning":
        if not args.agent or not args.insight:
            print(json.dumps({"error": "--agent and --insight required for save-learning"}))
            sys.exit(1)
        conditions = _parse_json(args.conditions, "--conditions") if args.conditions else {}
        result = save_learning(args.brand, args.agent, args.insight, conditions, args.confidence, args.evidence)

    elif args.action == "query-relevant":
        if not args.context:
            print(json.dumps({"error": "--context required for query-relevant (JSON)"}))
            sys.exit(1)
        context = _parse_json(args.context, "--context")
        result = query_relevant(args.brand, context)

    elif args.action == "update-confidence":
        if not args.learning_id or not args.direction:
            print(json.dumps({"error": "--learning-id and --direction required for update-confidence"}))
            sys.exit(1)
        result = update_confidence(args.brand, args.learning_id, args.direction, args.evidence or "")

    elif args.action == "get-patterns":
        if not args.dimension:
            print(json.dumps({"error": "--dimension required for get-patterns"}))
            sys.exit(1)
        result = get_patterns(args.brand, args.dimension)

    elif args.action == "get-stats":
        result = get_stats(args.brand)

    elif args.action == "archive-stale":
        result = archive_stale(args.brand, args.max_age_days, args.min_confidence)

    elif args.action == "export-playbook":
        result = export_playbook(args.brand, args.channel, args.audience, args.min_confidence)

    elif args.action == "apply-time-decay":
        result = apply_time_decay(args.brand, args.decay_rate)

    _common.finish(result)


if __name__ == "__main__":
    main()
