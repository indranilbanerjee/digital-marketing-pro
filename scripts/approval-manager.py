#!/usr/bin/env python3
"""
approval-manager.py
===================
Manages the approval lifecycle for execution actions in Digital Marketing Pro.

Tracks drafts through pending -> approved -> executed (or rejected/failed) so
the plugin never publishes, sends, or launches without explicit user sign-off.

Storage: ~/.claude-marketing/brands/{slug}/approvals/

Usage:
    python approval-manager.py --brand acme --action create-approval --data '{"type": "publish-blog", "platform": "wordpress", "content_summary": "Q1 recap post", "risk_level": "medium"}'
    python approval-manager.py --brand acme --action list-pending
    python approval-manager.py --brand acme --action approve --id publish-blog-20260212-1
    python approval-manager.py --brand acme --action reject --id publish-blog-20260212-1 --data '{"reason": "Needs legal review"}'
    python approval-manager.py --brand acme --action mark-executed --id publish-blog-20260212-1 --data '{"execution_result": "success", "platform_response": "Published", "url": "https://example.com/post"}'
    python approval-manager.py --brand acme --action get-approval --id publish-blog-20260212-1
    python approval-manager.py --brand acme --action get-execution-log
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

BRANDS_DIR = Path.home() / ".claude-marketing" / "brands"

VALID_TYPES = [
    "publish-blog", "send-email", "launch-ad", "schedule-social",
    "send-report", "crm-sync", "send-sms",
]
VALID_RISK_LEVELS = ["low", "medium", "high", "critical"]


def get_brand_dir(slug):
    """Get and validate brand directory."""
    brand_dir = BRANDS_DIR / slug
    if not brand_dir.exists():
        return None, f"Brand '{slug}' not found. Run /dm:brand-setup first."
    return brand_dir, None


def _load_approval(filepath):
    """Load a single approval JSON file."""
    try:
        return json.loads(filepath.read_text())
    except json.JSONDecodeError:
        return None


def _load_all_approvals(approvals_dir):
    """Load all approval JSON files from the directory."""
    approvals = []
    if not approvals_dir.exists():
        return approvals
    for fp in sorted(approvals_dir.glob("*.json")):
        if fp.name.startswith("_"):
            continue
        approval = _load_approval(fp)
        if approval:
            approvals.append(approval)
    return approvals


def _next_seq(approvals_dir, prefix):
    """Get the next sequence number for an approval type + date prefix."""
    seq = 1
    for fp in approvals_dir.glob(f"{prefix}-*.json"):
        stem = fp.stem
        parts = stem.rsplit("-", 1)
        if len(parts) == 2:
            try:
                existing = int(parts[1])
                if existing >= seq:
                    seq = existing + 1
            except ValueError:
                pass
    return seq


def create_approval(slug, data):
    """Create a new approval request."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    # Validate required fields
    approval_type = data.get("type")
    if approval_type not in VALID_TYPES:
        return {"error": f"Invalid type '{approval_type}'. Must be one of: {', '.join(VALID_TYPES)}"}

    platform = data.get("platform")
    if not platform:
        return {"error": "Missing required field: platform"}

    content_summary = data.get("content_summary")
    if not content_summary:
        return {"error": "Missing required field: content_summary"}

    risk_level = data.get("risk_level", "medium")
    if risk_level not in VALID_RISK_LEVELS:
        return {"error": f"Invalid risk_level '{risk_level}'. Must be one of: {', '.join(VALID_RISK_LEVELS)}"}

    approvals_dir = brand_dir / "approvals"
    approvals_dir.mkdir(exist_ok=True)

    # Generate approval_id: {type}-{YYYYMMDD}-{seq}
    date_str = datetime.now().strftime("%Y%m%d")
    prefix = f"{approval_type}-{date_str}"
    seq = _next_seq(approvals_dir, prefix)
    approval_id = f"{prefix}-{seq}"

    approval = {
        "approval_id": approval_id,
        "type": approval_type,
        "status": "pending",
        "risk_level": risk_level,
        "platform": platform,
        "content_summary": content_summary,
        "compliance_check": data.get("compliance_check", None),
        "brand_voice_score": data.get("brand_voice_score", None),
        "created_at": datetime.now().isoformat(),
        "approved_by": None,
        "approved_at": None,
        "rejected_reason": None,
        "executed_at": None,
        "execution_result": None,
        "platform_response": None,
        "url": None,
        "rollback_data": None,
    }

    filepath = approvals_dir / f"{approval_id}.json"
    filepath.write_text(json.dumps(approval, indent=2))

    return {
        "status": "created",
        "approval_id": approval_id,
        "risk_level": risk_level,
        "path": str(filepath),
    }


def list_pending(slug):
    """List all approvals with status 'pending'."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    approvals_dir = brand_dir / "approvals"
    all_approvals = _load_all_approvals(approvals_dir)
    pending = [a for a in all_approvals if a.get("status") == "pending"]

    # Sort by risk level (critical first)
    risk_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    pending.sort(key=lambda a: risk_order.get(a.get("risk_level", "medium"), 2))

    return {"pending": pending, "total": len(pending)}


def approve(slug, approval_id):
    """Approve a pending approval request."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    filepath = brand_dir / "approvals" / f"{approval_id}.json"
    if not filepath.exists():
        return {"error": f"Approval '{approval_id}' not found."}

    approval = _load_approval(filepath)
    if not approval:
        return {"error": f"Approval file corrupted: {approval_id}"}

    if approval["status"] != "pending":
        return {"error": f"Cannot approve: current status is '{approval['status']}', expected 'pending'."}

    approval["status"] = "approved"
    approval["approved_by"] = "user"
    approval["approved_at"] = datetime.now().isoformat()

    filepath.write_text(json.dumps(approval, indent=2))

    return {
        "status": "approved",
        "approval_id": approval_id,
        "approved_at": approval["approved_at"],
    }


def reject(slug, approval_id, data):
    """Reject a pending approval request."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    reason = data.get("reason")
    if not reason:
        return {"error": "Missing required field: reason"}

    filepath = brand_dir / "approvals" / f"{approval_id}.json"
    if not filepath.exists():
        return {"error": f"Approval '{approval_id}' not found."}

    approval = _load_approval(filepath)
    if not approval:
        return {"error": f"Approval file corrupted: {approval_id}"}

    if approval["status"] != "pending":
        return {"error": f"Cannot reject: current status is '{approval['status']}', expected 'pending'."}

    approval["status"] = "rejected"
    approval["rejected_reason"] = reason

    filepath.write_text(json.dumps(approval, indent=2))

    return {
        "status": "rejected",
        "approval_id": approval_id,
        "reason": reason,
    }


def mark_executed(slug, approval_id, data):
    """Record execution result for an approved action."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    execution_result = data.get("execution_result")
    if execution_result not in ("success", "failure"):
        return {"error": "execution_result must be 'success' or 'failure'."}

    filepath = brand_dir / "approvals" / f"{approval_id}.json"
    if not filepath.exists():
        return {"error": f"Approval '{approval_id}' not found."}

    approval = _load_approval(filepath)
    if not approval:
        return {"error": f"Approval file corrupted: {approval_id}"}

    if approval["status"] != "approved":
        return {"error": f"Cannot mark executed: current status is '{approval['status']}', expected 'approved'."}

    approval["status"] = "executed" if execution_result == "success" else "failed"
    approval["executed_at"] = datetime.now().isoformat()
    approval["execution_result"] = execution_result
    approval["platform_response"] = data.get("platform_response")
    approval["url"] = data.get("url")
    approval["rollback_data"] = data.get("rollback_data")

    filepath.write_text(json.dumps(approval, indent=2))

    return {
        "status": approval["status"],
        "approval_id": approval_id,
        "executed_at": approval["executed_at"],
        "execution_result": execution_result,
    }


def get_approval(slug, approval_id):
    """Retrieve a specific approval by ID."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    filepath = brand_dir / "approvals" / f"{approval_id}.json"
    if not filepath.exists():
        return {"error": f"Approval '{approval_id}' not found."}

    approval = _load_approval(filepath)
    if not approval:
        return {"error": f"Approval file corrupted: {approval_id}"}

    return approval


def get_execution_log(slug):
    """List all executed or failed approvals with summary stats."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    approvals_dir = brand_dir / "approvals"
    all_approvals = _load_all_approvals(approvals_dir)
    executed = [a for a in all_approvals if a.get("status") in ("executed", "failed")]

    # Sort most recent first
    executed.sort(key=lambda a: a.get("executed_at", ""), reverse=True)

    # Summary stats
    total = len(executed)
    success_count = sum(1 for a in executed if a.get("status") == "executed")
    failed_count = sum(1 for a in executed if a.get("status") == "failed")
    by_platform = {}
    by_type = {}
    for a in executed:
        plat = a.get("platform", "unknown")
        by_platform[plat] = by_platform.get(plat, 0) + 1
        atype = a.get("type", "unknown")
        by_type[atype] = by_type.get(atype, 0) + 1

    return {
        "executions": executed,
        "total": total,
        "success_count": success_count,
        "failed_count": failed_count,
        "success_rate": round(success_count / total * 100, 1) if total else 0,
        "by_platform": by_platform,
        "by_type": by_type,
    }


def main():
    parser = argparse.ArgumentParser(description="Approval lifecycle manager for Digital Marketing Pro")
    parser.add_argument("--brand", required=True, help="Brand slug")
    parser.add_argument("--action", required=True,
                        choices=["create-approval", "list-pending", "approve", "reject",
                                 "mark-executed", "get-approval", "get-execution-log"],
                        help="Action to perform")
    parser.add_argument("--data", help="JSON data (for create/reject/mark-executed)")
    parser.add_argument("--id", help="Approval ID (for approve/reject/mark-executed/get-approval)")
    args = parser.parse_args()

    if args.action == "create-approval":
        if not args.data:
            print(json.dumps({"error": "Provide --data with approval JSON"}))
            sys.exit(1)
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --data"}))
            sys.exit(1)
        result = create_approval(args.brand, data)

    elif args.action == "list-pending":
        result = list_pending(args.brand)

    elif args.action == "approve":
        if not args.id:
            print(json.dumps({"error": "Provide --id for approve"}))
            sys.exit(1)
        result = approve(args.brand, args.id)

    elif args.action == "reject":
        if not args.id:
            print(json.dumps({"error": "Provide --id for reject"}))
            sys.exit(1)
        if not args.data:
            print(json.dumps({"error": "Provide --data with rejection reason JSON"}))
            sys.exit(1)
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --data"}))
            sys.exit(1)
        result = reject(args.brand, args.id, data)

    elif args.action == "mark-executed":
        if not args.id:
            print(json.dumps({"error": "Provide --id for mark-executed"}))
            sys.exit(1)
        if not args.data:
            print(json.dumps({"error": "Provide --data with execution result JSON"}))
            sys.exit(1)
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --data"}))
            sys.exit(1)
        result = mark_executed(args.brand, args.id, data)

    elif args.action == "get-approval":
        if not args.id:
            print(json.dumps({"error": "Provide --id for get-approval"}))
            sys.exit(1)
        result = get_approval(args.brand, args.id)

    elif args.action == "get-execution-log":
        result = get_execution_log(args.brand)

    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
