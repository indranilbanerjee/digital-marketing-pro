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

BRANDS_DIR = Path.home() / ".claude-marketing" / "brands"


def get_brand_dir(slug):
    """Get and validate brand directory."""
    brand_dir = BRANDS_DIR / slug
    if not brand_dir.exists():
        return None, f"Brand '{slug}' not found. Run /dm:brand-setup first."
    return brand_dir, None


def _load_index(executions_dir):
    """Load the execution index file."""
    index_path = executions_dir / "_index.json"
    if not index_path.exists():
        return []
    try:
        return json.loads(index_path.read_text())
    except json.JSONDecodeError:
        return []


def _save_index(executions_dir, index):
    """Save the execution index file."""
    index_path = executions_dir / "_index.json"
    index_path.write_text(json.dumps(index, indent=2))


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

    # Save individual execution file
    filepath = executions_dir / f"{execution_id}.json"
    filepath.write_text(json.dumps(execution, indent=2))

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
            execution = json.loads(fp.read_text())
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


def main():
    parser = argparse.ArgumentParser(description="Execution audit trail for Digital Marketing Pro")
    parser.add_argument("--brand", required=True, help="Brand slug")
    parser.add_argument("--action", required=True,
                        choices=["log-execution", "get-history", "get-stats"],
                        help="Action to perform")
    parser.add_argument("--data", help="JSON data (for log-execution)")
    parser.add_argument("--platform", help="Filter history by platform")
    parser.add_argument("--status", help="Filter history by result (success/failure)")
    parser.add_argument("--limit", type=int, default=50, help="Max items to return")
    args = parser.parse_args()

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

    elif args.action == "get-history":
        result = get_history(args.brand, args.platform, args.status, args.limit)

    elif args.action == "get-stats":
        result = get_stats(args.brand)

    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
