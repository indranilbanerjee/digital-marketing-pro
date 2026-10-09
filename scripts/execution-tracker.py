#!/usr/bin/env python3
"""
execution-tracker.py
====================
Audit trail for all executed actions across platforms in Digital Marketing Pro.

Logs every publish, send, launch, and sync so the plugin maintains a complete
record of what was done, when, and on which platform.

Storage: ~/.claude-marketing/brands/{slug}/executions/

Usage:
    python execution-tracker.py --brand acme --action log-execution --data '{"platform": "wordpress", "action_type": "publish-blog", "content_id": "q1-recap", "result": "success", "url": "https://example.com/q1", "details": "Published via REST API"}'
    python execution-tracker.py --brand acme --action get-history
    python execution-tracker.py --brand acme --action get-history --platform wordpress --status success --limit 10
    python execution-tracker.py --brand acme --action get-stats
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

BRANDS_DIR = _common.brands_root()


def get_brand_dir(slug):
    """Resolve + validate the brand directory. Delegates to _common so the slug
    is normalised (slugify at the boundary) and legacy raw-name dirs still
    resolve, with the standard not-found message."""
    return _common.get_brand_dir(slug)


def _rebuild_index_from_files(executions_dir):
    """Rebuild the summary index by rescanning the individual exec-*.json files.
    Used when _index.json is missing or corrupt so an interrupted/truncated
    write never silently erases the audit trail (H3)."""
    rebuilt = []
    for fp in sorted(executions_dir.glob("exec-*.json")):
        try:
            e = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        rebuilt.append({
            "execution_id": e.get("execution_id", fp.stem),
            "platform": e.get("platform"),
            "action_type": e.get("action_type"),
            "result": e.get("result"),
            "executed_at": e.get("executed_at"),
        })
    rebuilt.sort(key=lambda x: x.get("executed_at") or "")
    return rebuilt


def _load_index(executions_dir):
    """Load the execution index file. On a missing OR corrupt index, rebuild
    it from the individual exec-*.json files rather than defaulting to empty —
    a crash mid-write must never silently truncate the audit history."""
    index_path = executions_dir / "_index.json"
    if not index_path.exists():
        return _rebuild_index_from_files(executions_dir)
    try:
        return json.loads(index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _rebuild_index_from_files(executions_dir)


def _save_index(executions_dir, index):
    """Save the execution index file atomically (tmp + replace)."""
    _common.atomic_write_json(executions_dir / "_index.json", index)


def log_execution(slug, data):
    """Log an executed action to the audit trail."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    # Validate required fields
    platform = data.get("platform")
    if not platform:
        return {"error": "Missing required field: platform"}

    action_type = data.get("action_type")
    if not action_type:
        return {"error": "Missing required field: action_type"}

    result = data.get("result")
    if result not in ("success", "failure"):
        return {"error": "result must be 'success' or 'failure'."}

    executions_dir = brand_dir / "executions"
    executions_dir.mkdir(exist_ok=True)

    # Generate execution_id: exec-{platform}-{YYYYMMDD-HHMMSS}
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    execution_id = f"exec-{platform}-{timestamp}"

    execution = {
        "execution_id": execution_id,
        "platform": platform,
        "action_type": action_type,
        "content_id": data.get("content_id"),
        "result": result,
        "url": data.get("url"),
        "details": data.get("details"),
        "approval_id": data.get("approval_id"),
        "executed_at": datetime.now().isoformat(),
    }

    # Save individual execution file (atomically — this is the source of truth
    # the index is rebuilt from).
    filepath = executions_dir / f"{execution_id}.json"
    _common.atomic_write_json(filepath, execution)

    # Update index
    index = _load_index(executions_dir)
    index.append({
        "execution_id": execution_id,
        "platform": platform,
        "action_type": action_type,
        "result": result,
        "executed_at": execution["executed_at"],
    })
    _save_index(executions_dir, index)

    return {
        "status": "logged",
        "execution_id": execution_id,
        "path": str(filepath),
    }


def get_history(slug, platform=None, status=None, limit=50):
    """List all executions with optional filters, most recent first."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    executions_dir = brand_dir / "executions"
    if not executions_dir.exists():
        return {"executions": [], "total": 0, "note": "No executions logged yet."}

    # Load all execution files (not just index) for full detail
    executions = []
    for fp in sorted(executions_dir.glob("exec-*.json"), reverse=True):
        try:
            execution = json.loads(fp.read_text(encoding="utf-8"))
            executions.append(execution)
        except json.JSONDecodeError:
            continue

    # Apply filters
    if platform:
        executions = [e for e in executions if e.get("platform") == platform]
    if status:
        executions = [e for e in executions if e.get("result") == status]

    # Sort most recent first
    executions.sort(key=lambda e: e.get("executed_at", ""), reverse=True)

    # Apply limit
    total = len(executions)
    executions = executions[:limit]

    return {
        "executions": executions,
        "returned": len(executions),
        "total": total,
    }


def get_stats(slug):
    """Summary statistics for all executions."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    executions_dir = brand_dir / "executions"
    if not executions_dir.exists():
        return {
            "total_executed": 0,
            "by_platform": {},
            "by_status": {},
            "success_rate": 0,
            "last_execution": None,
            "note": "No executions logged yet.",
        }

    # Load index for fast stats
    index = _load_index(executions_dir)
    if not index:
        return {
            "total_executed": 0,
            "by_platform": {},
            "by_status": {},
            "success_rate": 0,
            "last_execution": None,
            "note": "No executions logged yet.",
        }

    total = len(index)
    by_platform = {}
    by_status = {}
    last_execution = None

    for entry in index:
        plat = entry.get("platform", "unknown")
        by_platform[plat] = by_platform.get(plat, 0) + 1

        result = entry.get("result", "unknown")
        by_status[result] = by_status.get(result, 0) + 1

        executed_at = entry.get("executed_at", "")
        if not last_execution or executed_at > last_execution:
            last_execution = executed_at

    success_count = by_status.get("success", 0)
    success_rate = round(success_count / total * 100, 1) if total else 0

    return {
        "total_executed": total,
        "by_platform": by_platform,
        "by_status": by_status,
        "success_rate": success_rate,
        "last_execution": last_execution,
    }


def resume_launch(slug, data):
    """Recovery path for an interrupted launch-campaign run (launch-campaign
    calls this after a mid-launch failure). Given a campaign_id and the step to
    resume from, return the executions already logged for that campaign plus a
    resume manifest so the orchestrator continues from the failed step instead
    of restarting the entire launch."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}
    campaign_id = data.get("campaign_id")
    if not campaign_id:
        return {"error": "Missing required field: campaign_id"}
    try:
        from_step = int(data.get("from_step"))
    except (TypeError, ValueError):
        return {"error": "from_step must be an integer (the step number to resume from)"}

    executions_dir = brand_dir / "executions"
    prior = []
    if executions_dir.exists():
        for fp in sorted(executions_dir.glob("exec-*.json")):
            try:
                e = json.loads(fp.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            haystack = f"{e.get('content_id') or ''} {e.get('details') or ''}"
            if campaign_id in haystack:
                prior.append({
                    "execution_id": e.get("execution_id"),
                    "action_type": e.get("action_type"),
                    "platform": e.get("platform"),
                    "result": e.get("result"),
                    "executed_at": e.get("executed_at"),
                })
    succeeded = [p for p in prior if p.get("result") == "success"]
    return {
        "status": "resume-ready",
        "campaign_id": campaign_id,
        "from_step": from_step,
        "prior_executions": prior,
        "already_succeeded": len(succeeded),
        "guidance": (
            "Re-run launch-campaign steps from from_step onward. Steps already "
            "logged as success (see prior_executions) should be skipped. "
            "Re-present the Execution gate and require typed approval before "
            "each remaining external action; never auto-retry a failed step."
        ),
    }


# v3.7.10 — connector-aware action resolver replaces the inline _stub_action.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from connector_resolver import resolve_action  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Execution audit trail for Digital Marketing Pro")
    parser.add_argument("--brand", type=_common.path_component, required=True, help="Brand slug")
    parser.add_argument("--action", required=True,
                        choices=["log-execution", "get-history", "get-stats",
                                 # failure-recovery path for launch-campaign
                                 "resume-launch",
                                 # v3.7.6 — launch-campaign skill surface
                                 "enable-automation", "schedule-posts",
                                 "notify-influencers", "pr-send", "internal-kickoff",
                                 # v3.7.7 — additional launch-campaign surface
                                 "launch-ads"],
                        help="Action to perform")
    parser.add_argument("--data", help="JSON data (for log-execution)")
    parser.add_argument("--platform", help="Filter history by platform")
    parser.add_argument("--status", help="Filter history by result (success/failure)")
    parser.add_argument("--limit", type=int, default=50, help="Max items to return")
    parser.add_argument("--plan", help="Path to approved campaign plan JSON "
                                       "(for schedule-posts / notify-influencers / pr-send / internal-kickoff)")
    parser.add_argument("--automation-id", help="Automation id (for enable-automation)")
    args = parser.parse_args()
    # Slugify at the boundary so every action resolves the same brand dir.
    args.brand = _common.slugify_brand(args.brand)

    if args.action == "log-execution":
        if not args.data:
            print(json.dumps({"error": "Provide --data with execution JSON"}))
            sys.exit(1)
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --data"}))
            sys.exit(1)
        result = log_execution(args.brand, data)

    elif args.action == "resume-launch":
        if not args.data:
            print(json.dumps({"error": "Provide --data with {\"campaign_id\":..,\"from_step\":N}"}))
            sys.exit(1)
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --data"}))
            sys.exit(1)
        result = resume_launch(args.brand, data)

    elif args.action == "get-history":
        result = get_history(args.brand, args.platform, args.status, args.limit)

    elif args.action == "get-stats":
        result = get_stats(args.brand)

    elif args.action in {"enable-automation", "schedule-posts",
                         "notify-influencers", "pr-send", "internal-kickoff",
                         "launch-ads"}:
        result = resolve_action(args.action, args.brand,
                                plan_path=args.plan,
                                automation_id=args.automation_id,
                                platform=args.platform)

    _common.finish(result)


if __name__ == "__main__":
    main()
