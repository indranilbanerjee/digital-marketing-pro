#!/usr/bin/env python3
"""
campaign-tracker.py
===================
Persistent campaign data storage and retrieval for Digital Marketing Pro.

Stores campaign plans, performance snapshots, and learnings in the brand's
~/.claude-marketing/brands/{slug}/ directory so the plugin can reference
past work and improve recommendations over time.

Usage:
    python campaign-tracker.py --brand acme --action save-campaign --data '{"name": "Q1 Launch", ...}'
    python campaign-tracker.py --brand acme --action list-campaigns
    python campaign-tracker.py --brand acme --action get-campaign --id q1-launch-2026
    python campaign-tracker.py --brand acme --action save-insight --data '{"type": "learning", ...}'
    python campaign-tracker.py --brand acme --action get-insights
    python campaign-tracker.py --brand acme --action save-performance --data '{"campaign_id": "...", ...}'
    python campaign-tracker.py --brand acme --action save-violation --data '{"rule": "...", "category": "restrictions", ...}'
    python campaign-tracker.py --brand acme --action get-violations --category restrictions --severity high
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


def get_brand_dir(slug):
    """Resolve + validate the brand directory. Delegates to _common so the slug
    is normalised (slugify at the boundary) and legacy raw-name dirs still
    resolve, with the standard not-found message."""
    return _common.get_brand_dir(slug)


def save_campaign(slug, data):
    """Save a campaign plan/result to the brand's campaigns directory."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    campaigns_dir = brand_dir / "campaigns"
    campaigns_dir.mkdir(exist_ok=True)

    # Generate campaign ID from name
    name = data.get("name", "untitled")
    campaign_id = name.lower().replace(" ", "-")[:50]
    timestamp = datetime.now().strftime("%Y%m%d")
    campaign_id = f"{campaign_id}-{timestamp}"

    campaign = {
        "campaign_id": campaign_id,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        **data,
    }

    # Save campaign file
    filepath = campaigns_dir / f"{campaign_id}.json"
    filepath.write_text(json.dumps(campaign, indent=2))

    # Update campaign index
    index_path = campaigns_dir / "_index.json"
    index = []
    if index_path.exists():
        try:
            index = json.loads(index_path.read_text())
        except json.JSONDecodeError:
            index = []

    entry = {
        "campaign_id": campaign_id,
        "name": data.get("name", "Untitled"),
        "status": data.get("status", "planned"),
        "channels": data.get("channels", []),
        "created_at": campaign["created_at"],
    }
    # Same name saved on the same day produces the same id — replace the
    # existing index row instead of duplicating it
    for i, existing in enumerate(index):
        if existing.get("campaign_id") == campaign_id:
            index[i] = entry
            break
    else:
        index.append(entry)
    index_path.write_text(json.dumps(index, indent=2))

    return {
        "status": "saved",
        "campaign_id": campaign_id,
        "path": str(filepath),
    }


def list_campaigns(slug):
    """List all campaigns for a brand."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    campaigns_dir = brand_dir / "campaigns"
    index_path = campaigns_dir / "_index.json"

    if not index_path.exists():
        return {"campaigns": [], "total": 0, "note": "No campaigns saved yet."}

    try:
        index = json.loads(index_path.read_text())
        return {"campaigns": index, "total": len(index)}
    except json.JSONDecodeError:
        return {"error": "Campaign index is corrupted."}


def get_campaign(slug, campaign_id):
    """Retrieve a specific campaign by ID."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    filepath = brand_dir / "campaigns" / f"{campaign_id}.json"
    if not filepath.exists():
        return {"error": f"Campaign '{campaign_id}' not found."}

    try:
        return json.loads(filepath.read_text())
    except json.JSONDecodeError:
        return {"error": f"Campaign file corrupted: {campaign_id}"}


def save_performance(slug, data):
    """Save a performance snapshot for a brand."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    perf_dir = brand_dir / "performance"
    perf_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    campaign_id = data.get("campaign_id", "general")

    snapshot = {
        "snapshot_id": f"{campaign_id}-{timestamp}",
        "recorded_at": datetime.now().isoformat(),
        **data,
    }

    filepath = perf_dir / f"{campaign_id}-{timestamp}.json"
    filepath.write_text(json.dumps(snapshot, indent=2))

    return {"status": "saved", "snapshot_id": snapshot["snapshot_id"], "path": str(filepath)}


def save_insight(slug, data):
    """Save a marketing insight/learning for the brand."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    insights_path = brand_dir / "insights.json"
    insights = []
    if insights_path.exists():
        try:
            insights = json.loads(insights_path.read_text())
        except json.JSONDecodeError:
            insights = []

    insight = {
        "recorded_at": datetime.now().isoformat(),
        "type": data.get("type", "learning"),
        "source": data.get("source", "session"),
        "insight": data.get("insight", ""),
        "context": data.get("context", ""),
        "actionable": data.get("actionable", True),
    }
    insights.append(insight)

    # Keep last 200 insights
    insights = insights[-200:]
    insights_path.write_text(json.dumps(insights, indent=2))

    return {"status": "saved", "total_insights": len(insights)}


def get_insights(slug, insight_type=None, limit=20):
    """Retrieve marketing insights for a brand."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    insights_path = brand_dir / "insights.json"
    if not insights_path.exists():
        return {"insights": [], "total": 0, "note": "No insights saved yet."}

    try:
        insights = json.loads(insights_path.read_text())
    except json.JSONDecodeError:
        return {"error": "Insights file corrupted."}

    if insight_type:
        insights = [i for i in insights if i.get("type") == insight_type]

    # Return most recent first
    insights = list(reversed(insights[-limit:]))
    return {"insights": insights, "total": len(insights)}


def save_violation(slug, data):
    """Save a guideline violation for tracking and pattern analysis."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    violations_path = brand_dir / "guideline-violations.json"
    violations = []
    if violations_path.exists():
        try:
            violations = json.loads(violations_path.read_text())
        except json.JSONDecodeError:
            violations = []

    violation = {
        "recorded_at": datetime.now().isoformat(),
        "rule": data.get("rule", ""),
        "category": data.get("category", ""),
        "severity": data.get("severity", "medium"),
        "content": data.get("content", ""),
        "suggestion": data.get("suggestion", ""),
        "source": data.get("source", "session"),
        "module": data.get("module", ""),
    }
    violations.append(violation)

    # Keep last 500 violations
    violations = violations[-500:]
    violations_path.write_text(json.dumps(violations, indent=2))

    return {"status": "saved", "total_violations": len(violations)}


def get_violations(slug, category=None, severity=None, limit=50):
    """Retrieve guideline violations for a brand."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    violations_path = brand_dir / "guideline-violations.json"
    if not violations_path.exists():
        return {"violations": [], "total": 0, "note": "No violations recorded."}

    try:
        violations = json.loads(violations_path.read_text())
    except json.JSONDecodeError:
        return {"error": "Violations file corrupted."}

    if category:
        violations = [v for v in violations if v.get("category") == category]
    if severity:
        violations = [v for v in violations if v.get("severity") == severity]

    # Return most recent first
    violations = list(reversed(violations[-limit:]))

    # Summary stats
    severity_counts = {}
    category_counts = {}
    for v in violations:
        sev = v.get("severity", "medium")
        cat = v.get("category", "unknown")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
        category_counts[cat] = category_counts.get(cat, 0) + 1

    return {
        "violations": violations,
        "total": len(violations),
        "by_severity": severity_counts,
        "by_category": category_counts,
    }


def main():
    parser = argparse.ArgumentParser(description="Campaign data persistence for Digital Marketing Pro")
    parser.add_argument("--brand", type=_common.path_component, required=True, help="Brand slug")
    parser.add_argument("--action", required=True,
                        choices=["save-campaign", "list-campaigns", "get-campaign",
                                 "save-performance", "save-insight", "get-insights",
                                 "save-violation", "get-violations"],
                        help="Action to perform")
    parser.add_argument("--data", help="JSON data (for save actions)")
    parser.add_argument("--id", help="Campaign ID (for get-campaign)")
    parser.add_argument("--type", dest="insight_type", help="Filter insights by type")
    parser.add_argument("--category", help="Filter violations by guideline category")
    parser.add_argument("--severity", help="Filter violations by severity (low/medium/high)")
    parser.add_argument("--limit", type=int, default=20, help="Max items to return")
    args = parser.parse_args()

    if args.action == "save-campaign":
        if not args.data:
            print(json.dumps({"error": "Provide --data with campaign JSON"}))
            sys.exit(1)
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --data"}))
            sys.exit(1)
        result = save_campaign(args.brand, data)

    elif args.action == "list-campaigns":
        result = list_campaigns(args.brand)

    elif args.action == "get-campaign":
        if not args.id:
            print(json.dumps({"error": "Provide --id for get-campaign"}))
            sys.exit(1)
        result = get_campaign(args.brand, args.id)

    elif args.action == "save-performance":
        if not args.data:
            print(json.dumps({"error": "Provide --data with performance JSON"}))
            sys.exit(1)
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --data"}))
            sys.exit(1)
        result = save_performance(args.brand, data)

    elif args.action == "save-insight":
        if not args.data:
            print(json.dumps({"error": "Provide --data with insight JSON"}))
            sys.exit(1)
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --data"}))
            sys.exit(1)
        result = save_insight(args.brand, data)

    elif args.action == "get-insights":
        result = get_insights(args.brand, args.insight_type, args.limit)

    elif args.action == "save-violation":
        if not args.data:
            print(json.dumps({"error": "Provide --data with violation JSON"}))
            sys.exit(1)
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --data"}))
            sys.exit(1)
        result = save_violation(args.brand, data)

    elif args.action == "get-violations":
        result = get_violations(args.brand, args.category, args.severity, args.limit)

    _common.finish(result)


if __name__ == "__main__":
    main()
