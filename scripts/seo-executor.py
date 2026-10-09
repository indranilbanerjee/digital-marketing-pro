#!/usr/bin/env python3
"""
seo-executor.py
===============
SEO Executor — Track and manage SEO implementation changes.

Records meta tag updates, schema deployments, redirects, sitemap submissions,
and indexing requests. Provides bulk operations and status tracking so the
plugin maintains a complete audit trail of all SEO changes.

Storage: ~/.claude-marketing/brands/{slug}/seo/

Usage:
    python seo-executor.py --brand acme --action update-meta --url https://example.com/ --title "New Title" --description "New desc"
    python seo-executor.py --brand acme --action deploy-schema --url https://example.com/ --schema-type FAQ --schema-data '{"mainEntity": []}'
    python seo-executor.py --brand acme --action create-redirect --source-url /old --target-url /new --type 301
    python seo-executor.py --brand acme --action submit-sitemap --sitemap-url https://example.com/sitemap.xml
    python seo-executor.py --brand acme --action request-indexing --url https://example.com/new-page
    python seo-executor.py --brand acme --action bulk-meta-update --spec-file /path/to/spec.json
    python seo-executor.py --brand acme --action status --status pending
    python seo-executor.py --brand acme --action complete --change-id meta-20260213-143000
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

SCHEMA_TYPES = [
    "Organization", "Product", "FAQ", "HowTo", "Article",
    "LocalBusiness", "BreadcrumbList",
]


def get_brand_dir(slug):
    """Resolve + validate the brand directory. Delegates to _common so the slug
    is normalised (slugify at the boundary) and legacy raw-name dirs still
    resolve, with the standard not-found message."""
    return _common.get_brand_dir(slug)


def _change_id(prefix):
    """Generate a unique change ID with timestamp."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{ts}"


def _load_json(path):
    """Safely load a JSON file, returning empty list on failure."""
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save_json(path, data):
    """Write JSON data to file atomically, creating parent dirs as needed."""
    _common.atomic_write_json(path, data)


def update_meta(slug, url, title=None, description=None,
                og_title=None, og_description=None):
    """Record a meta tag update request."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    if not url:
        return {"error": "Missing required --url"}

    changes_dir = brand_dir / "seo" / "changes"
    changes_dir.mkdir(parents=True, exist_ok=True)

    change_id = _change_id("meta")

    # Check for existing baseline for this URL
    old_values = None
    for fp in changes_dir.glob("meta-*.json"):
        try:
            existing = json.loads(fp.read_text(encoding="utf-8"))
            if existing.get("url") == url and existing.get("status") == "completed":
                old_values = {
                    "title": existing.get("new_title"),
                    "description": existing.get("new_description"),
                    "og_title": existing.get("new_og_title"),
                    "og_description": existing.get("new_og_description"),
                }
        except (json.JSONDecodeError, OSError):
            continue

    change = {
        "change_id": change_id,
        "type": "meta-update",
        "url": url,
        "old_values": old_values,
        "new_title": title,
        "new_description": description,
        "new_og_title": og_title,
        "new_og_description": og_description,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
    }

    _save_json(changes_dir / f"{change_id}.json", change)

    return {
        "status": "recorded",
        "change_id": change_id,
        "url": url,
        "old_values": old_values,
        "new_values": {
            "title": title,
            "description": description,
            "og_title": og_title,
            "og_description": og_description,
        },
        "change_status": "pending",
    }


def deploy_schema(slug, url, schema_type, schema_data):
    """Record a schema markup deployment request."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    if schema_type not in SCHEMA_TYPES:
        return {"error": f"Invalid --schema-type. Choose from: {', '.join(SCHEMA_TYPES)}"}

    try:
        parsed = json.loads(schema_data) if isinstance(schema_data, str) else schema_data
    except json.JSONDecodeError:
        return {"error": "Invalid JSON in --schema-data"}

    schema_dir = brand_dir / "seo" / "schema"
    schema_dir.mkdir(parents=True, exist_ok=True)

    deploy_id = _change_id(f"schema-{schema_type.lower()}")

    record = {
        "deployment_id": deploy_id,
        "type": "schema-deployment",
        "url": url,
        "schema_type": schema_type,
        "schema_data": parsed,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
    }

    _save_json(schema_dir / f"{deploy_id}.json", record)

    return {
        "status": "recorded",
        "deployment_id": deploy_id,
        "url": url,
        "schema_type": schema_type,
    }


def create_redirect(slug, source_url, target_url, redirect_type):
    """Record a redirect creation request, checking for chains."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    if redirect_type not in ("301", "302"):
        return {"error": "--type must be 301 or 302"}

    redirects_dir = brand_dir / "seo" / "redirects"
    redirects_dir.mkdir(parents=True, exist_ok=True)

    # Check for redirect chains
    existing_redirects = {}
    for fp in redirects_dir.glob("redirect-*.json"):
        try:
            r = json.loads(fp.read_text(encoding="utf-8"))
            existing_redirects[r.get("source_url")] = r.get("target_url")
        except (json.JSONDecodeError, OSError):
            continue

    chain_warning = None
    if target_url in existing_redirects:
        chain_warning = (
            f"Redirect chain detected: {source_url} -> {target_url} -> "
            f"{existing_redirects[target_url]}. Consider pointing directly "
            f"to {existing_redirects[target_url]}."
        )
    if source_url in existing_redirects.values():
        for src, tgt in existing_redirects.items():
            if tgt == source_url:
                chain_warning = (
                    f"Redirect chain detected: {src} -> {source_url} -> "
                    f"{target_url}. Consider updating the existing redirect "
                    f"from {src} to point directly to {target_url}."
                )
                break

    redirect_id = _change_id("redirect")

    record = {
        "redirect_id": redirect_id,
        "type": "redirect",
        "source_url": source_url,
        "target_url": target_url,
        "redirect_type": int(redirect_type),
        "status": "pending",
        "chain_warning": chain_warning,
        "created_at": datetime.now().isoformat(),
    }

    _save_json(redirects_dir / f"{redirect_id}.json", record)

    result = {
        "status": "recorded",
        "redirect_id": redirect_id,
        "source_url": source_url,
        "target_url": target_url,
        "redirect_type": int(redirect_type),
    }
    if chain_warning:
        result["warning"] = chain_warning
    return result


def submit_sitemap(slug, sitemap_url):
    """Record a sitemap submission request."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    seo_dir = brand_dir / "seo"
    seo_dir.mkdir(parents=True, exist_ok=True)

    submissions = _load_json(seo_dir / "sitemap-submissions.json")
    entry = {
        "sitemap_url": sitemap_url,
        "status": "pending",
        "submitted_at": datetime.now().isoformat(),
    }
    submissions.append(entry)
    _save_json(seo_dir / "sitemap-submissions.json", submissions)

    return {"status": "recorded", "sitemap_url": sitemap_url, "total_submissions": len(submissions)}


def request_indexing(slug, url):
    """Record an indexing request."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    indexing_dir = brand_dir / "seo" / "indexing"
    indexing_dir.mkdir(parents=True, exist_ok=True)

    request_id = _change_id("index")
    record = {
        "request_id": request_id,
        "type": "indexing-request",
        "url": url,
        "status": "pending",
        "requested_at": datetime.now().isoformat(),
    }

    _save_json(indexing_dir / f"{request_id}.json", record)
    return {"status": "recorded", "request_id": request_id, "url": url}


def bulk_meta_update(slug, spec_file):
    """Process a bulk meta update spec file."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    spec_path = Path(spec_file)
    if not spec_path.exists():
        return {"error": f"Spec file not found: {spec_file}"}

    try:
        entries = json.loads(spec_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"error": "Invalid JSON in spec file"}

    if not isinstance(entries, list):
        return {"error": "Spec file must contain a JSON array of {url, title, description}"}

    valid = 0
    invalid = 0
    change_ids = []

    for entry in entries:
        url = entry.get("url")
        if not url:
            invalid += 1
            continue
        result = update_meta(
            slug, url,
            title=entry.get("title"),
            description=entry.get("description"),
        )
        if "error" in result:
            invalid += 1
        else:
            valid += 1
            change_ids.append(result["change_id"])

    return {
        "status": "bulk_processed",
        "total": len(entries),
        "valid": valid,
        "invalid": invalid,
        "change_ids": change_ids,
    }


def get_status(slug, status_filter="all"):
    """Show all SEO changes for the brand, optionally filtered by status."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    seo_dir = brand_dir / "seo"
    if not seo_dir.exists():
        return {"changes": [], "total": 0, "note": "No SEO changes recorded yet."}

    changes = []
    for sub in ("changes", "schema", "redirects", "indexing"):
        sub_dir = seo_dir / sub
        if not sub_dir.exists():
            continue
        for fp in sub_dir.glob("*.json"):
            if fp.name.startswith("_"):
                continue
            try:
                record = json.loads(fp.read_text(encoding="utf-8"))
                changes.append(record)
            except (json.JSONDecodeError, OSError):
                continue

    if status_filter != "all":
        changes = [c for c in changes if c.get("status") == status_filter]

    changes.sort(key=lambda c: c.get("created_at", c.get("requested_at", "")), reverse=True)

    return {"changes": changes, "total": len(changes)}


def complete_change(slug, change_id):
    """Mark a change as completed."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    seo_dir = brand_dir / "seo"
    if not seo_dir.exists():
        return {"error": "No SEO changes recorded yet."}

    for sub in ("changes", "schema", "redirects", "indexing"):
        sub_dir = seo_dir / sub
        if not sub_dir.exists():
            continue
        for fp in sub_dir.glob("*.json"):
            if fp.name.startswith("_"):
                continue
            try:
                record = json.loads(fp.read_text(encoding="utf-8"))
                rid = (record.get("change_id") or record.get("deployment_id")
                       or record.get("redirect_id") or record.get("request_id"))
                if rid == change_id:
                    record["status"] = "completed"
                    record["completed_at"] = datetime.now().isoformat()
                    _save_json(fp, record)
                    return {"status": "completed", "change_id": change_id, "completed_at": record["completed_at"]}
            except (json.JSONDecodeError, OSError):
                continue

    return {"error": f"Change '{change_id}' not found."}


def main():
    parser = argparse.ArgumentParser(
        description="SEO execution management for Digital Marketing Pro"
    )
    parser.add_argument("--brand", type=_common.path_component, required=True, help="Brand slug")
    parser.add_argument(
        "--action", required=True,
        choices=[
            "update-meta", "deploy-schema", "create-redirect",
            "submit-sitemap", "request-indexing", "bulk-meta-update",
            "status", "complete",
            # v3.7.7 — campaign-audit skill surface
            "audit-current",
        ],
        help="Action to perform",
    )
    parser.add_argument("--url", help="Target URL")
    parser.add_argument("--title", help="New meta title (update-meta)")
    parser.add_argument("--description", help="New meta description (update-meta)")
    parser.add_argument("--og-title", help="New OG title (update-meta)")
    parser.add_argument("--og-description", help="New OG description (update-meta)")
    parser.add_argument("--schema-type", choices=SCHEMA_TYPES, help="Schema type (deploy-schema)")
    parser.add_argument("--schema-data", help="Schema JSON string (deploy-schema)")
    parser.add_argument("--source-url", help="Redirect source URL (create-redirect)")
    parser.add_argument("--target-url", help="Redirect target URL (create-redirect)")
    parser.add_argument("--type", dest="redirect_type", choices=["301", "302"],
                        help="Redirect type (create-redirect)")
    parser.add_argument("--sitemap-url", help="Sitemap URL (submit-sitemap)")
    parser.add_argument("--spec-file", help="Path to bulk spec JSON (bulk-meta-update)")
    parser.add_argument("--status", dest="status_filter", default="all",
                        choices=["pending", "completed", "failed", "all"],
                        help="Filter by status (status action)")
    parser.add_argument("--change-id", help="Change ID to complete (complete action)")
    args = parser.parse_args()

    if args.action == "update-meta":
        if not args.url:
            print(json.dumps({"error": "Provide --url for update-meta"}))
            sys.exit(1)
        result = update_meta(args.brand, args.url, args.title, args.description,
                             args.og_title, args.og_description)

    elif args.action == "deploy-schema":
        if not args.url or not args.schema_type or not args.schema_data:
            print(json.dumps({"error": "Provide --url, --schema-type, and --schema-data"}))
            sys.exit(1)
        result = deploy_schema(args.brand, args.url, args.schema_type, args.schema_data)

    elif args.action == "create-redirect":
        if not args.source_url or not args.target_url or not args.redirect_type:
            print(json.dumps({"error": "Provide --source-url, --target-url, and --type"}))
            sys.exit(1)
        result = create_redirect(args.brand, args.source_url, args.target_url, args.redirect_type)

    elif args.action == "submit-sitemap":
        if not args.sitemap_url:
            print(json.dumps({"error": "Provide --sitemap-url"}))
            sys.exit(1)
        result = submit_sitemap(args.brand, args.sitemap_url)

    elif args.action == "request-indexing":
        if not args.url:
            print(json.dumps({"error": "Provide --url for request-indexing"}))
            sys.exit(1)
        result = request_indexing(args.brand, args.url)

    elif args.action == "bulk-meta-update":
        if not args.spec_file:
            print(json.dumps({"error": "Provide --spec-file path"}))
            sys.exit(1)
        result = bulk_meta_update(args.brand, args.spec_file)

    elif args.action == "status":
        result = get_status(args.brand, args.status_filter)

    elif args.action == "complete":
        if not args.change_id:
            print(json.dumps({"error": "Provide --change-id to complete"}))
            sys.exit(1)
        result = complete_change(args.brand, args.change_id)

    elif args.action == "audit-current":
        # v3.7.10 — resolved via connector_resolver (was inline stub in v3.7.7)
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).resolve().parent))
        from connector_resolver import resolve_action  # noqa: E402
        result = resolve_action("audit-current", args.brand)

    _common.finish(result)


if __name__ == "__main__":
    main()
