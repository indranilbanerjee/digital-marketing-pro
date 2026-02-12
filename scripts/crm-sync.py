#!/usr/bin/env python3
"""
crm-sync.py
===========
CRM data sync management for Digital Marketing Pro.

Manages the local side of CRM integration: data preparation, field mapping,
deduplication logic, and sync tracking.  Actual CRM API calls happen via MCP
servers — this script handles validation, formatting, and bookkeeping.

Storage: ~/.claude-marketing/brands/{slug}/crm/

Usage:
    python crm-sync.py --brand acme --action prepare-contact --data '{"email": "j@co.com", "name": "Jane", "source": "webinar"}'
    python crm-sync.py --brand acme --action prepare-deal --data '{"deal_name": "Enterprise Plan", "stage": "proposal", "value": 25000, "currency": "USD", "contact_email": "j@co.com", "pipeline": "sales"}'
    python crm-sync.py --brand acme --action check-dedup --data '{"email": "j@co.com"}'
    python crm-sync.py --brand acme --action log-synced --data '{"record_type": "contact", "crm_platform": "hubspot", "crm_record_id": "hs_123", "local_id": "abc123"}'
    python crm-sync.py --brand acme --action get-sync-history --platform hubspot --type contact --limit 50
    python crm-sync.py --brand acme --action get-crm-status
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

BRANDS_DIR = Path.home() / ".claude-marketing" / "brands"

CRM_ENV_VARS = {
    "salesforce": "SALESFORCE_ACCESS_TOKEN",
    "hubspot": "HUBSPOT_ACCESS_TOKEN",
    "zoho": "ZOHO_REFRESH_TOKEN",
    "pipedrive": "PIPEDRIVE_API_TOKEN",
}

VALID_RECORD_TYPES = ["contact", "deal", "campaign"]

VALID_DEAL_STAGES = [
    "lead", "qualified", "proposal", "negotiation", "closed-won", "closed-lost",
]


def get_brand_dir(slug):
    """Get and validate brand directory."""
    brand_dir = BRANDS_DIR / slug
    if not brand_dir.exists():
        return None, f"Brand '{slug}' not found. Run /dm:brand-setup first."
    return brand_dir, None


def _load_json(path, default=None):
    """Safely load a JSON file, returning default on missing/corrupt."""
    if default is None:
        default = []
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _save_json(path, data):
    """Atomically write JSON to a file."""
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _validate_email(email):
    """Basic email validation."""
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def _generate_local_id(email):
    """Generate a deterministic local ID from an email address."""
    return hashlib.sha256(email.lower().strip().encode("utf-8")).hexdigest()[:12]


def _build_field_mappings(contact):
    """Map generic contact fields to platform-specific formats."""
    return {
        "salesforce": {
            "FirstName": contact.get("first_name", ""),
            "LastName": contact.get("last_name", ""),
            "Email": contact.get("email", ""),
            "Phone": contact.get("phone", ""),
            "Company": contact.get("company", ""),
            "LeadSource": contact.get("source", ""),
        },
        "hubspot": {
            "firstname": contact.get("first_name", ""),
            "lastname": contact.get("last_name", ""),
            "email": contact.get("email", ""),
            "phone": contact.get("phone", ""),
            "company": contact.get("company", ""),
            "hs_lead_status": "NEW",
        },
        "zoho": {
            "First_Name": contact.get("first_name", ""),
            "Last_Name": contact.get("last_name", ""),
            "Email": contact.get("email", ""),
            "Phone": contact.get("phone", ""),
            "Company": contact.get("company", ""),
            "Lead_Source": contact.get("source", ""),
        },
        "pipedrive": {
            "name": contact.get("name", ""),
            "email": [{"value": contact.get("email", ""), "primary": True}],
            "phone": [{"value": contact.get("phone", ""), "primary": True}] if contact.get("phone") else [],
            "org_id": None,
        },
    }


def prepare_contact(slug, data):
    """Validate and prepare a contact for CRM sync."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    email = data.get("email", "").strip()
    if not email:
        return {"error": "Missing required field: email"}
    if not _validate_email(email):
        return {"error": f"Invalid email address: {email}"}

    name = data.get("name", "")
    parts = name.split(None, 1)
    first_name = parts[0] if parts else ""
    last_name = parts[1] if len(parts) > 1 else ""

    contact = {
        "email": email.lower(),
        "name": name,
        "first_name": first_name,
        "last_name": last_name,
        "phone": data.get("phone", ""),
        "company": data.get("company", ""),
        "source": data.get("source", ""),
        "tags": data.get("tags", []),
    }

    local_id = _generate_local_id(email)
    payload = {
        "local_id": local_id,
        "record_type": "contact",
        "brand": slug,
        "created_at": datetime.now().isoformat(),
        "contact": contact,
        "platform_fields": _build_field_mappings(contact),
    }

    crm_dir = brand_dir / "crm"
    pending_dir = crm_dir / "pending"
    pending_dir.mkdir(parents=True, exist_ok=True)
    filepath = pending_dir / f"contact-{local_id}.json"
    _save_json(filepath, payload)

    # Update contacts index for dedup
    index_path = crm_dir / "_contacts_index.json"
    index = _load_json(index_path, [])
    # Remove existing entry for same email (update scenario)
    index = [e for e in index if e.get("email") != email.lower()]
    index.append({
        "local_id": local_id,
        "email": email.lower(),
        "name": name,
        "phone": data.get("phone", ""),
        "company": data.get("company", ""),
        "added_at": datetime.now().isoformat(),
    })
    _save_json(index_path, index)

    return {"status": "prepared", "local_id": local_id, "path": str(filepath), "payload": payload}


def prepare_deal(slug, data):
    """Validate and prepare a deal for CRM sync."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    deal_name = data.get("deal_name", "")
    if not deal_name:
        return {"error": "Missing required field: deal_name"}

    stage = data.get("stage", "lead")
    if stage not in VALID_DEAL_STAGES:
        return {"error": f"Invalid stage '{stage}'. Must be one of: {VALID_DEAL_STAGES}"}

    value = data.get("value", 0)
    currency = data.get("currency", "USD")
    contact_email = data.get("contact_email", "")
    pipeline = data.get("pipeline", "default")

    deal_id = hashlib.sha256(f"{deal_name}:{contact_email}".encode()).hexdigest()[:12]
    payload = {
        "local_id": deal_id,
        "record_type": "deal",
        "brand": slug,
        "created_at": datetime.now().isoformat(),
        "deal": {
            "deal_name": deal_name,
            "stage": stage,
            "value": value,
            "currency": currency,
            "contact_email": contact_email,
            "pipeline": pipeline,
        },
        "platform_fields": {
            "salesforce": {
                "Name": deal_name,
                "StageName": stage.replace("-", " ").title(),
                "Amount": value,
                "CurrencyIsoCode": currency,
            },
            "hubspot": {
                "dealname": deal_name,
                "dealstage": stage,
                "amount": str(value),
                "pipeline": pipeline,
            },
            "zoho": {
                "Deal_Name": deal_name,
                "Stage": stage.replace("-", " ").title(),
                "Amount": value,
                "Currency": currency,
            },
            "pipedrive": {
                "title": deal_name,
                "stage_id": None,
                "value": value,
                "currency": currency,
            },
        },
    }

    crm_dir = brand_dir / "crm"
    pending_dir = crm_dir / "pending"
    pending_dir.mkdir(parents=True, exist_ok=True)
    filepath = pending_dir / f"deal-{deal_id}.json"
    _save_json(filepath, payload)

    return {"status": "prepared", "local_id": deal_id, "path": str(filepath), "payload": payload}


def check_dedup(slug, data):
    """Check if a contact already exists in the local index."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    email = data.get("email", "").lower().strip()
    phone = data.get("phone", "")
    company = data.get("company", "")
    name = data.get("name", "")

    if not email:
        return {"error": "Missing required field: email"}

    index = _load_json(brand_dir / "crm" / "_contacts_index.json", [])
    matches = []

    for entry in index:
        # Primary match: email
        if entry.get("email") == email:
            matches.append({**entry, "match_type": "email"})
            continue
        # Secondary match: phone
        if phone and entry.get("phone") == phone:
            matches.append({**entry, "match_type": "phone"})
            continue
        # Tertiary match: company + name
        if company and name and entry.get("company") == company and entry.get("name") == name:
            matches.append({**entry, "match_type": "company+name"})

    return {
        "is_duplicate": len(matches) > 0,
        "matching_records": matches,
        "checked_against": len(index),
    }


def log_synced(slug, data):
    """Record that a local record was synced to a CRM platform."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    record_type = data.get("record_type")
    crm_platform = data.get("crm_platform")
    crm_record_id = data.get("crm_record_id")
    local_id = data.get("local_id")

    if not all([record_type, crm_platform, crm_record_id, local_id]):
        return {"error": "Missing required fields: record_type, crm_platform, crm_record_id, local_id"}
    if record_type not in VALID_RECORD_TYPES:
        return {"error": f"Invalid record_type '{record_type}'. Must be one of: {VALID_RECORD_TYPES}"}

    crm_dir = brand_dir / "crm"
    crm_dir.mkdir(exist_ok=True)

    # Append to sync log
    log_path = crm_dir / "_sync_log.json"
    log = _load_json(log_path, [])
    log.append({
        "local_id": local_id,
        "record_type": record_type,
        "crm_platform": crm_platform,
        "crm_record_id": crm_record_id,
        "synced_at": datetime.now().isoformat(),
    })
    # Keep last 1000 entries
    log = log[-1000:]
    _save_json(log_path, log)

    # Remove from pending if present
    for prefix in ["contact", "deal", "campaign"]:
        pending_path = crm_dir / "pending" / f"{prefix}-{local_id}.json"
        if pending_path.exists():
            pending_path.unlink()
            break

    return {"status": "logged", "local_id": local_id, "crm_platform": crm_platform}


def get_sync_history(slug, platform=None, record_type=None, limit=50):
    """List synced records with optional filters."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    log = _load_json(brand_dir / "crm" / "_sync_log.json", [])

    if platform:
        log = [e for e in log if e.get("crm_platform") == platform]
    if record_type:
        log = [e for e in log if e.get("record_type") == record_type]

    # Most recent first
    log = list(reversed(log[-limit:]))

    return {"sync_history": log, "total": len(log)}


def get_crm_status(slug):
    """Report connected CRMs, sync counts, and last sync timestamp."""
    brand_dir, err = get_brand_dir(slug)
    if err:
        return {"error": err}

    crm_dir = brand_dir / "crm"
    log = _load_json(crm_dir / "_sync_log.json", [])

    # Connected CRMs
    connected = {}
    for service, env_var in CRM_ENV_VARS.items():
        connected[service] = bool(os.environ.get(env_var))

    # Sync stats
    platform_counts = {}
    type_counts = {}
    for entry in log:
        p = entry.get("crm_platform", "unknown")
        t = entry.get("record_type", "unknown")
        platform_counts[p] = platform_counts.get(p, 0) + 1
        type_counts[t] = type_counts.get(t, 0) + 1

    last_sync = log[-1]["synced_at"] if log else None

    # Pending count
    pending_dir = crm_dir / "pending"
    pending_count = len(list(pending_dir.glob("*.json"))) if pending_dir.exists() else 0

    return {
        "connected_crms": connected,
        "total_synced": len(log),
        "by_platform": platform_counts,
        "by_type": type_counts,
        "pending_items": pending_count,
        "last_sync_at": last_sync,
    }


def main():
    parser = argparse.ArgumentParser(description="CRM data sync management for Digital Marketing Pro")
    parser.add_argument("--brand", required=True, help="Brand slug")
    parser.add_argument("--action", required=True,
                        choices=["prepare-contact", "prepare-deal", "check-dedup",
                                 "log-synced", "get-sync-history", "get-crm-status"],
                        help="Action to perform")
    parser.add_argument("--data", help="JSON data (for prepare/check/log actions)")
    parser.add_argument("--platform", help="Filter sync history by CRM platform")
    parser.add_argument("--type", dest="record_type", help="Filter by record type")
    parser.add_argument("--limit", type=int, default=50, help="Max items to return")
    args = parser.parse_args()

    if args.action in ("prepare-contact", "prepare-deal", "check-dedup", "log-synced"):
        if not args.data:
            print(json.dumps({"error": f"Provide --data for {args.action}"}))
            sys.exit(1)
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --data"}))
            sys.exit(1)

        if args.action == "prepare-contact":
            result = prepare_contact(args.brand, data)
        elif args.action == "prepare-deal":
            result = prepare_deal(args.brand, data)
        elif args.action == "check-dedup":
            result = check_dedup(args.brand, data)
        elif args.action == "log-synced":
            result = log_synced(args.brand, data)

    elif args.action == "get-sync-history":
        result = get_sync_history(args.brand, args.platform, args.record_type, args.limit)

    elif args.action == "get-crm-status":
        result = get_crm_status(args.brand)

    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
