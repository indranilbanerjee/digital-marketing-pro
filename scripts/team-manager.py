#!/usr/bin/env python3
"""
team-manager.py
===============
Manage team roles, permissions, approval chains, and capacity for brand teams.

Stores team member profiles, a roster index, and task assignments inside
~/.claude-marketing/brands/{slug}/team/ so agents can route work, enforce
approval chains, and track capacity utilization across the team.

Usage:
    python team-manager.py --brand acme --action add-member --data '{"member_id": "jane-doe", "name": "Jane Doe", ...}'
    python team-manager.py --brand acme --action remove-member --id jane-doe
    python team-manager.py --brand acme --action list-team
    python team-manager.py --brand acme --action list-team --role content-lead
    python team-manager.py --brand acme --action update-role --id jane-doe --data '{"role": "brand-manager"}'
    python team-manager.py --brand acme --action get-approval-chain --data '{"action_type": "publish-blog", "risk_level": "high"}'
    python team-manager.py --brand acme --action check-capacity
    python team-manager.py --brand acme --action assign-task --data '{"member_id": "jane-doe", "task_description": "...", ...}'
    python team-manager.py --brand acme --action get-assignments --id jane-doe --status pending
"""

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

BRANDS_DIR = Path.home() / ".claude-marketing" / "brands"

VALID_ROLES = [
    "content-lead", "media-buyer", "email-manager", "social-manager",
    "analytics-lead", "brand-manager", "agency-admin", "seo-specialist",
    "cro-specialist", "growth-engineer",
]

ROLE_APPROVAL_LEVEL = {
    "agency-admin": "critical",
    "brand-manager": "high",
    "content-lead": "medium",
    "media-buyer": "medium",
    "email-manager": "medium",
    "social-manager": "medium",
    "analytics-lead": "medium",
    "seo-specialist": "low",
    "cro-specialist": "low",
    "growth-engineer": "low",
}

RISK_ORDER = ["low", "medium", "high", "critical"]


def _now_iso():
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_brand_dir(slug):
    """Get and validate brand directory."""
    brand_dir = BRANDS_DIR / slug
    if not brand_dir.exists():
        return None, f"Brand '{slug}' not found. Run /dm:brand-setup first."
    return brand_dir, None


def _load_json(path):
    """Load a JSON file, returning (data, err)."""
    if not path.exists():
        return None, f"File not found: {path.name}"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError:
        return None, f"Corrupted JSON: {path.name}"


def _risk_index(level):
    """Return numeric index for a risk level."""
    try:
        return RISK_ORDER.index(level)
    except ValueError:
        return 0


def _update_roster(team_dir, member_id, action="add", summary=None):
    """Add or remove a member from the _roster.json index."""
    roster_path = team_dir / "_roster.json"
    roster = []
    if roster_path.exists():
        try:
            roster = json.loads(roster_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            roster = []

    if action == "remove":
        roster = [m for m in roster if m.get("member_id") != member_id]
    elif action == "add" and summary:
        # Remove existing entry first to avoid duplicates
        roster = [m for m in roster if m.get("member_id") != member_id]
        roster.append(summary)

    roster_path.write_text(json.dumps(roster, indent=2), encoding="utf-8")


def add_member(slug, data):
    """Add a team member."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    team_dir = brand_dir / "team"
    team_dir.mkdir(exist_ok=True)

    member_id = data.get("member_id")
    name = data.get("name")
    role = data.get("role")

    if not member_id or not name or not role:
        return {"error": "member_id, name, and role are required in --data"}

    if role not in VALID_ROLES:
        return {"error": f"Invalid role '{role}'. Must be one of: {', '.join(VALID_ROLES)}"}

    capacity = data.get("capacity", {"max_weekly_tasks": 20})
    now = _now_iso()

    member = {
        "member_id": member_id,
        "name": name,
        "role": role,
        "permissions": data.get("permissions", []),
        "channels": data.get("channels", []),
        "regions": data.get("regions", []),
        "capacity": {
            "max_weekly_tasks": capacity.get("max_weekly_tasks", 20),
            "current_tasks": 0,
        },
        "approval_level": ROLE_APPROVAL_LEVEL.get(role, "low"),
        "added_at": now,
        "updated_at": now,
    }

    filepath = team_dir / f"{member_id}.json"
    filepath.write_text(json.dumps(member, indent=2), encoding="utf-8")

    # Update roster index
    _update_roster(team_dir, member_id, "add", {
        "member_id": member_id,
        "name": name,
        "role": role,
        "added_at": now,
    })

    return {
        "status": "added",
        "member_id": member_id,
        "role": role,
        "approval_level": member["approval_level"],
        "path": str(filepath),
    }


def remove_member(slug, member_id):
    """Remove a team member."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    team_dir = brand_dir / "team"
    filepath = team_dir / f"{member_id}.json"

    if not filepath.exists():
        return {"error": f"Member '{member_id}' not found."}

    filepath.unlink()
    _update_roster(team_dir, member_id, "remove")

    return {"status": "removed", "member_id": member_id}


def list_team(slug, role_filter=None):
    """List all team members, optionally filtered by role."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    team_dir = brand_dir / "team"
    if not team_dir.exists():
        return {"members": [], "total": 0, "note": "No team members added yet."}

    members = []
    for fp in sorted(team_dir.glob("*.json")):
        if fp.name.startswith("_"):
            continue
        if fp.name == "assignments":
            continue
        data, load_err = _load_json(fp)
        if load_err:
            continue

        if role_filter and data.get("role") != role_filter:
            continue

        cap = data.get("capacity", {})
        max_tasks = cap.get("max_weekly_tasks", 20)
        current = cap.get("current_tasks", 0)
        util = round((current / max_tasks) * 100, 1) if max_tasks > 0 else 0

        members.append({
            "member_id": data.get("member_id", fp.stem),
            "name": data.get("name", ""),
            "role": data.get("role", ""),
            "channels": data.get("channels", []),
            "capacity_utilization": f"{util}%",
            "approval_level": data.get("approval_level", "low"),
        })

    return {"members": members, "total": len(members)}


def update_role(slug, member_id, data):
    """Update a member's role and/or permissions."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    team_dir = brand_dir / "team"
    filepath = team_dir / f"{member_id}.json"
    member, load_err = _load_json(filepath)
    if load_err:
        return {"error": f"Member '{member_id}' not found."}

    new_role = data.get("role")
    if new_role:
        if new_role not in VALID_ROLES:
            return {"error": f"Invalid role '{new_role}'. Must be one of: {', '.join(VALID_ROLES)}"}
        member["role"] = new_role
        member["approval_level"] = ROLE_APPROVAL_LEVEL.get(new_role, "low")

    if "permissions" in data:
        member["permissions"] = data["permissions"]

    member["updated_at"] = _now_iso()
    filepath.write_text(json.dumps(member, indent=2), encoding="utf-8")

    # Update roster
    _update_roster(team_dir, member_id, "add", {
        "member_id": member_id,
        "name": member.get("name", ""),
        "role": member["role"],
        "added_at": member.get("added_at", ""),
    })

    return {
        "status": "updated",
        "member_id": member_id,
        "role": member["role"],
        "approval_level": member["approval_level"],
        "permissions": member["permissions"],
    }


def get_approval_chain(slug, data):
    """Build an approval chain for a given action type and risk level."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    action_type = data.get("action_type")
    risk_level = data.get("risk_level", "medium")

    if not action_type:
        return {"error": "action_type is required in --data"}
    if risk_level not in RISK_ORDER:
        return {"error": f"Invalid risk_level '{risk_level}'. Must be one of: {', '.join(RISK_ORDER)}"}

    team_dir = brand_dir / "team"
    if not team_dir.exists():
        return {"approval_chain": [], "note": "No team members configured."}

    required_index = _risk_index(risk_level)
    approvers = []

    for fp in sorted(team_dir.glob("*.json")):
        if fp.name.startswith("_"):
            continue
        member, load_err = _load_json(fp)
        if load_err:
            continue

        member_level = member.get("approval_level", "low")
        if _risk_index(member_level) >= required_index:
            approvers.append({
                "member_id": member.get("member_id", fp.stem),
                "name": member.get("name", ""),
                "role": member.get("role", ""),
                "approval_level": member_level,
            })

    # Sort by approval level descending (critical first)
    approvers.sort(key=lambda a: _risk_index(a["approval_level"]), reverse=True)

    return {
        "action_type": action_type,
        "risk_level": risk_level,
        "approval_chain": approvers,
        "total_approvers": len(approvers),
    }


def check_capacity(slug):
    """Check capacity utilization for all team members."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    team_dir = brand_dir / "team"
    if not team_dir.exists():
        return {"members": [], "total": 0, "note": "No team members configured."}

    members = []
    for fp in sorted(team_dir.glob("*.json")):
        if fp.name.startswith("_"):
            continue
        member, load_err = _load_json(fp)
        if load_err:
            continue

        cap = member.get("capacity", {})
        max_tasks = cap.get("max_weekly_tasks", 20)
        current = cap.get("current_tasks", 0)
        util_pct = round((current / max_tasks) * 100, 1) if max_tasks > 0 else 0

        members.append({
            "member_id": member.get("member_id", fp.stem),
            "name": member.get("name", ""),
            "role": member.get("role", ""),
            "max_weekly_tasks": max_tasks,
            "current_tasks": current,
            "utilization_pct": util_pct,
            "available": util_pct < 85.0,
        })

    available_count = sum(1 for m in members if m["available"])
    return {
        "members": members,
        "total": len(members),
        "available_count": available_count,
    }


def assign_task(slug, data):
    """Assign a task to a team member."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    member_id = data.get("member_id")
    task_desc = data.get("task_description")
    if not member_id or not task_desc:
        return {"error": "member_id and task_description are required in --data"}

    team_dir = brand_dir / "team"
    member_path = team_dir / f"{member_id}.json"
    member, load_err = _load_json(member_path)
    if load_err:
        return {"error": f"Member '{member_id}' not found."}

    # Increment current tasks
    cap = member.get("capacity", {"max_weekly_tasks": 20, "current_tasks": 0})
    cap["current_tasks"] = cap.get("current_tasks", 0) + 1
    member["capacity"] = cap
    member["updated_at"] = _now_iso()
    member_path.write_text(json.dumps(member, indent=2), encoding="utf-8")

    # Save assignment
    assignments_dir = team_dir / "assignments"
    assignments_dir.mkdir(exist_ok=True)

    assignment_id = f"task-{uuid.uuid4().hex[:8]}"
    now = _now_iso()
    assignment = {
        "assignment_id": assignment_id,
        "member_id": member_id,
        "task_description": task_desc,
        "channel": data.get("channel", ""),
        "priority": data.get("priority", "medium"),
        "due_date": data.get("due_date", ""),
        "status": "pending",
        "assigned_at": now,
        "updated_at": now,
    }

    filepath = assignments_dir / f"{assignment_id}.json"
    filepath.write_text(json.dumps(assignment, indent=2), encoding="utf-8")

    return {
        "status": "assigned",
        "assignment_id": assignment_id,
        "member_id": member_id,
        "priority": assignment["priority"],
        "path": str(filepath),
    }


def get_assignments(slug, member_filter=None, status_filter=None, limit=50):
    """List assignments, optionally filtered by member and/or status."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    assignments_dir = brand_dir / "team" / "assignments"
    if not assignments_dir.exists():
        return {"assignments": [], "total": 0, "note": "No assignments yet."}

    assignments = []
    for fp in sorted(assignments_dir.glob("*.json")):
        if fp.name.startswith("_"):
            continue
        data, load_err = _load_json(fp)
        if load_err:
            continue

        if member_filter and data.get("member_id") != member_filter:
            continue
        if status_filter and data.get("status") != status_filter:
            continue

        assignments.append(data)

    # Sort by assigned_at descending (most recent first)
    assignments.sort(key=lambda a: a.get("assigned_at", ""), reverse=True)
    assignments = assignments[:limit]

    return {"assignments": assignments, "total": len(assignments)}


def main():
    parser = argparse.ArgumentParser(
        description="Team role and capacity management for Digital Marketing Pro"
    )
    parser.add_argument("--brand", required=True, help="Brand slug")
    parser.add_argument(
        "--action", required=True,
        choices=[
            "add-member", "remove-member", "list-team", "update-role",
            "get-approval-chain", "check-capacity", "assign-task",
            "get-assignments",
        ],
        help="Action to perform",
    )
    parser.add_argument("--data", help="JSON data (for add/update/assign actions)")
    parser.add_argument("--id", help="Member ID (for member-specific operations)")
    parser.add_argument("--role", help="Filter by role (for list-team)")
    parser.add_argument("--status", help="Filter assignments by status (pending|in-progress|completed)")
    parser.add_argument("--limit", type=int, default=50, help="Max items to return")
    args = parser.parse_args()

    if args.action == "add-member":
        if not args.data:
            print(json.dumps({"error": "Provide --data with member JSON"}))
            sys.exit(1)
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --data"}))
            sys.exit(1)
        result = add_member(args.brand, data)

    elif args.action == "remove-member":
        if not args.id:
            print(json.dumps({"error": "Provide --id (member_id) for remove-member"}))
            sys.exit(1)
        result = remove_member(args.brand, args.id)

    elif args.action == "list-team":
        result = list_team(args.brand, args.role)

    elif args.action == "update-role":
        if not args.id:
            print(json.dumps({"error": "Provide --id (member_id) for update-role"}))
            sys.exit(1)
        if not args.data:
            print(json.dumps({"error": "Provide --data with role/permissions JSON"}))
            sys.exit(1)
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --data"}))
            sys.exit(1)
        result = update_role(args.brand, args.id, data)

    elif args.action == "get-approval-chain":
        if not args.data:
            print(json.dumps({"error": "Provide --data with action_type and risk_level"}))
            sys.exit(1)
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --data"}))
            sys.exit(1)
        result = get_approval_chain(args.brand, data)

    elif args.action == "check-capacity":
        result = check_capacity(args.brand)

    elif args.action == "assign-task":
        if not args.data:
            print(json.dumps({"error": "Provide --data with task assignment JSON"}))
            sys.exit(1)
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --data"}))
            sys.exit(1)
        result = assign_task(args.brand, data)

    elif args.action == "get-assignments":
        result = get_assignments(args.brand, args.id, args.status, args.limit)

    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
