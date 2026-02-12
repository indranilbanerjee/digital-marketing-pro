#!/usr/bin/env python3
"""
credential-manager.py
=====================
Per-brand credential profile management for agency multi-client workflows.

Stores credential REFERENCES (environment variable names), NOT actual secrets.
Profiles live at ~/.claude-marketing/credentials/{brand_slug}.json so agents
can discover which env vars to use when switching between clients.

Usage:
    python credential-manager.py --action create-profile --data '{"brand_slug": "acme-corp", "platforms": {...}, ...}'
    python credential-manager.py --action list-profiles
    python credential-manager.py --action get-profile --id acme-corp
    python credential-manager.py --action switch-profile --id acme-corp
    python credential-manager.py --action validate-profile --id acme-corp
    python credential-manager.py --action delete-profile --id acme-corp
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

CREDENTIALS_DIR = Path.home() / ".claude-marketing" / "credentials"


def _now_iso():
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json(path):
    """Load a JSON file, returning (data, err)."""
    if not path.exists():
        return None, f"File not found: {path.name}"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError:
        return None, f"Corrupted JSON: {path.name}"


def _active_path():
    """Return path to the active-profile marker file."""
    return CREDENTIALS_DIR / "_active-profile.json"


def create_profile(data):
    """Create a new credential profile for a brand."""
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)

    brand_slug = data.get("brand_slug")
    if not brand_slug:
        return {"error": "brand_slug is required in --data"}

    platforms = data.get("platforms")
    if not platforms or not isinstance(platforms, dict):
        return {"error": "platforms object is required in --data"}

    now = _now_iso()
    profile = {
        "brand_slug": brand_slug,
        "created_at": now,
        "updated_at": now,
        "platforms": platforms,
        "default_crm": data.get("default_crm", ""),
        "default_email": data.get("default_email", ""),
        "default_ads": data.get("default_ads", []),
    }

    filepath = CREDENTIALS_DIR / f"{brand_slug}.json"
    filepath.write_text(json.dumps(profile, indent=2), encoding="utf-8")

    return {
        "status": "created",
        "brand_slug": brand_slug,
        "platforms": list(platforms.keys()),
        "path": str(filepath),
    }


def list_profiles():
    """List all credential profiles."""
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)

    profiles = []
    for fp in sorted(CREDENTIALS_DIR.glob("*.json")):
        if fp.name.startswith("_"):
            continue
        data, err = _load_json(fp)
        if err:
            continue
        profiles.append({
            "brand_slug": data.get("brand_slug", fp.stem),
            "platform_count": len(data.get("platforms", {})),
            "created_at": data.get("created_at", ""),
        })

    # Check active profile
    active_slug = None
    active_data, _ = _load_json(_active_path())
    if active_data:
        active_slug = active_data.get("brand_slug")

    return {
        "profiles": profiles,
        "total": len(profiles),
        "active_profile": active_slug,
    }


def get_profile(brand_slug):
    """Load and return a full credential profile."""
    filepath = CREDENTIALS_DIR / f"{brand_slug}.json"
    data, err = _load_json(filepath)
    if err:
        return {"error": f"Profile '{brand_slug}' not found."}
    return data


def switch_profile(brand_slug):
    """Set a profile as the active credential profile."""
    filepath = CREDENTIALS_DIR / f"{brand_slug}.json"
    data, err = _load_json(filepath)
    if err:
        return {"error": f"Profile '{brand_slug}' not found. Create it first."}

    now = _now_iso()
    active = {
        "brand_slug": brand_slug,
        "switched_at": now,
    }
    _active_path().write_text(json.dumps(active, indent=2), encoding="utf-8")

    platforms = list(data.get("platforms", {}).keys())
    return {
        "status": "switched",
        "brand_slug": brand_slug,
        "switched_at": now,
        "active_platforms": platforms,
    }


def validate_profile(brand_slug):
    """Validate that env vars referenced in a profile are set."""
    filepath = CREDENTIALS_DIR / f"{brand_slug}.json"
    data, err = _load_json(filepath)
    if err:
        return {"error": f"Profile '{brand_slug}' not found."}

    platforms = data.get("platforms", {})
    validation = {}
    total_vars = 0
    total_configured = 0

    for platform, config in platforms.items():
        vars_list = config.get("vars", [])
        missing = [v for v in vars_list if not os.environ.get(v)]
        configured = len(vars_list) - len(missing)
        total_vars += len(vars_list)
        total_configured += configured

        validation[platform] = {
            "configured": len(missing) == 0,
            "missing_vars": missing,
            "total_vars": len(vars_list),
            "configured_count": configured,
        }

    return {
        "brand_slug": brand_slug,
        "validation": validation,
        "summary": {
            "total_vars": total_vars,
            "configured": total_configured,
            "missing": total_vars - total_configured,
            "fully_configured": total_configured == total_vars,
        },
    }


def delete_profile(brand_slug):
    """Delete a credential profile."""
    filepath = CREDENTIALS_DIR / f"{brand_slug}.json"
    if not filepath.exists():
        return {"error": f"Profile '{brand_slug}' not found."}

    filepath.unlink()

    # Clear active profile if this was it
    active_data, _ = _load_json(_active_path())
    if active_data and active_data.get("brand_slug") == brand_slug:
        _active_path().unlink(missing_ok=True)

    return {
        "status": "deleted",
        "brand_slug": brand_slug,
        "active_cleared": (
            active_data is not None
            and active_data.get("brand_slug") == brand_slug
        ),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Credential profile management for Digital Marketing Pro"
    )
    parser.add_argument(
        "--action", required=True,
        choices=[
            "create-profile", "list-profiles", "get-profile",
            "switch-profile", "validate-profile", "delete-profile",
        ],
        help="Action to perform",
    )
    parser.add_argument("--data", help="JSON data (for create-profile)")
    parser.add_argument("--id", help="Brand slug (for get/switch/validate/delete)")
    args = parser.parse_args()

    if args.action == "create-profile":
        if not args.data:
            print(json.dumps({"error": "Provide --data with profile JSON"}))
            sys.exit(1)
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON in --data"}))
            sys.exit(1)
        result = create_profile(data)

    elif args.action == "list-profiles":
        result = list_profiles()

    elif args.action == "get-profile":
        if not args.id:
            print(json.dumps({"error": "Provide --id (brand slug) for get-profile"}))
            sys.exit(1)
        result = get_profile(args.id)

    elif args.action == "switch-profile":
        if not args.id:
            print(json.dumps({"error": "Provide --id (brand slug) for switch-profile"}))
            sys.exit(1)
        result = switch_profile(args.id)

    elif args.action == "validate-profile":
        if not args.id:
            print(json.dumps({"error": "Provide --id (brand slug) for validate-profile"}))
            sys.exit(1)
        result = validate_profile(args.id)

    elif args.action == "delete-profile":
        if not args.id:
            print(json.dumps({"error": "Provide --id (brand slug) for delete-profile"}))
            sys.exit(1)
        result = delete_profile(args.id)

    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
