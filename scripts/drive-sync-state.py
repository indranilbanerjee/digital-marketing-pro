#!/usr/bin/env python3
"""
drive-sync-state.py
===================
Local-side state management for the Cowork+Drive routing introduced in
v3.12.0. Python scripts cannot call MCP tools directly (MCPs are exposed
to Claude/agent, not subprocess). So this script manages the LOCAL state
that tells the agent what needs syncing to Drive.

Why this matters: Cowork's per-session ephemeral filesystem means
~/.claude-marketing/ writes vanish at session end (GitHub issue #51398
documents the same bug for ${CLAUDE_PLUGIN_DATA}). To survive across
Cowork sessions, brand profiles + plans + reports must round-trip through
a Drive MCP. This script is the bookkeeping ledger.

Three concerns:

  1. Brand profile sync state - has this profile been uploaded to Drive?
     when was it last synced? what's the local vs Drive content hash?

  2. Plan/report checkpoint sync - which output files from a given run
     still need uploading to Drive?

  3. Cowork+Drive root config - which Drive folder is this team's
     DigitalMarketingPro root? (set by cowork-setup, read everywhere)

The agent reads these markers after running Python steps and uses its
Drive MCP tools to perform the actual file transfers.

State files:

  <workspace>/_cowork-config.json                        (Drive root + namespace)
  <workspace>/brands/{brand-slug}/_drive-sync.json        (per-brand sync state)
  <workspace>/brands/{brand-slug}/runs/{run}/_sync-pending.json (per-run pending uploads)

Usage:
    # Cowork+Drive config
    python drive-sync-state.py --action read-config
    python drive-sync-state.py --action write-config --data '{...}'

    # Brand profile sync
    python drive-sync-state.py --action profile-needs-upload --brand acme
    python drive-sync-state.py --action profile-mark-uploaded --brand acme --drive-file-id 1abcd... --drive-url https://...
    python drive-sync-state.py --action profile-mark-downloaded --brand acme --drive-file-id 1abcd... --content-hash sha256:...
    python drive-sync-state.py --action profile-drive-state --brand acme

    # Run checkpoint sync
    python drive-sync-state.py --action add-pending-upload --brand acme --run-id 20260608-... --file 00-input.md
    python drive-sync-state.py --action list-pending-uploads --brand acme --run-id 20260608-...
    python drive-sync-state.py --action mark-uploaded --brand acme --run-id 20260608-... --file 00-input.md --drive-file-id 1abcd...
    python drive-sync-state.py --action list-runs-needing-sync --brand acme
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import os  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

CLAUDE_MARKETING = _common.workspace_root()
COWORK_CONFIG_PATH = CLAUDE_MARKETING / "_cowork-config.json"


# ---------------------------------------------------------------------------
# Cowork+Drive config (per-environment, not per-brand)
# ---------------------------------------------------------------------------

def read_cowork_config() -> dict:
    if not COWORK_CONFIG_PATH.exists():
        return {"configured": False,
                "note": "Run /digital-marketing-pro:cowork-setup to wire DMP for Cowork team usage."}
    try:
        data = json.loads(COWORK_CONFIG_PATH.read_text(encoding="utf-8"))
        data["configured"] = True
        return data
    except (json.JSONDecodeError, OSError) as e:
        return {"configured": False, "error": f"{type(e).__name__}: {e}"}


def write_cowork_config(data: dict) -> dict:
    CLAUDE_MARKETING.mkdir(parents=True, exist_ok=True)
    payload = {
        **data,
        "configured_at": data.get("configured_at") or _now_iso(),
    }
    _common.atomic_write_json(COWORK_CONFIG_PATH, payload)
    return {"status": "written", "path": str(COWORK_CONFIG_PATH), "config": payload}


# ---------------------------------------------------------------------------
# Brand profile sync state
# ---------------------------------------------------------------------------

def _brand_sync_path(brand: str) -> Path:
    return _common.brand_dir(brand) / "_drive-sync.json"


def _profile_path(brand: str) -> Path:
    return _common.brand_dir(brand) / "profile.json"


def profile_needs_upload(brand: str) -> dict:
    profile = _profile_path(brand)
    if not profile.exists():
        return {"brand": brand, "needs_upload": False,
                "reason": "no local profile.json exists"}
    local_hash = _file_hash(profile)
    sync = _read_brand_sync(brand)
    last_uploaded_hash = sync.get("last_uploaded_hash")
    if not last_uploaded_hash:
        return {"brand": brand, "needs_upload": True,
                "reason": "never uploaded to Drive",
                "local_hash": local_hash,
                "local_path": str(profile)}
    if local_hash != last_uploaded_hash:
        return {"brand": brand, "needs_upload": True,
                "reason": "local content differs from last uploaded",
                "local_hash": local_hash,
                "last_uploaded_hash": last_uploaded_hash,
                "local_path": str(profile)}
    return {"brand": brand, "needs_upload": False,
            "reason": "local matches last uploaded",
            "hash": local_hash}


def profile_mark_uploaded(brand: str, drive_file_id: str, drive_url: str | None) -> dict:
    profile = _profile_path(brand)
    if not profile.exists():
        return {"error": f"local profile.json does not exist for brand {brand}"}
    local_hash = _file_hash(profile)
    sync = _read_brand_sync(brand)
    sync["last_uploaded_hash"] = local_hash
    sync["drive_file_id"] = drive_file_id
    sync["drive_url"] = drive_url
    sync["last_uploaded_at"] = _now_iso()
    _write_brand_sync(brand, sync)
    return {"status": "recorded",
            "brand": brand,
            "drive_file_id": drive_file_id,
            "drive_url": drive_url,
            "content_hash": local_hash}


def profile_mark_downloaded(brand: str, drive_file_id: str, content_hash: str) -> dict:
    sync = _read_brand_sync(brand)
    sync["last_uploaded_hash"] = content_hash
    sync["drive_file_id"] = drive_file_id
    sync["last_downloaded_at"] = _now_iso()
    _write_brand_sync(brand, sync)
    return {"status": "recorded",
            "brand": brand,
            "drive_file_id": drive_file_id,
            "content_hash": content_hash}


def profile_drive_state(brand: str) -> dict:
    sync = _read_brand_sync(brand)
    profile = _profile_path(brand)
    local_hash = _file_hash(profile) if profile.exists() else None
    return {
        "brand": brand,
        "local_profile_exists": profile.exists(),
        "local_profile_path": str(profile),
        "local_content_hash": local_hash,
        "last_uploaded_hash": sync.get("last_uploaded_hash"),
        "in_sync": local_hash is not None and local_hash == sync.get("last_uploaded_hash"),
        "drive_file_id": sync.get("drive_file_id"),
        "drive_url": sync.get("drive_url"),
        "last_uploaded_at": sync.get("last_uploaded_at"),
        "last_downloaded_at": sync.get("last_downloaded_at"),
    }


# ---------------------------------------------------------------------------
# Run checkpoint sync state
# ---------------------------------------------------------------------------

def _run_pending_path(brand: str, run_id: str) -> Path:
    return _common.safe_child(_common.brand_dir(brand) / "runs", run_id) / "_sync-pending.json"


def add_pending_upload(brand: str, run_id: str, file: str) -> dict:
    path = _run_pending_path(brand, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = _read_pending(path)
    if file not in pending["pending"]:
        pending["pending"].append(file)
        pending["last_updated"] = _now_iso()
    _write_pending(path, pending)
    return {"status": "added", "run_id": run_id, "file": file,
            "total_pending": len(pending["pending"])}


def list_pending_uploads(brand: str, run_id: str) -> dict:
    path = _run_pending_path(brand, run_id)
    if not path.exists():
        return {"brand": brand, "run_id": run_id, "pending": [], "uploaded": []}
    pending = _read_pending(path)
    return {
        "brand": brand,
        "run_id": run_id,
        "pending": pending["pending"],
        "uploaded": pending["uploaded"],
        "last_updated": pending.get("last_updated"),
    }


def mark_run_file_uploaded(brand: str, run_id: str, file: str,
                           drive_file_id: str) -> dict:
    path = _run_pending_path(brand, run_id)
    if not path.exists():
        return {"error": f"no pending sync record for brand={brand} run={run_id}"}
    pending = _read_pending(path)
    if file in pending["pending"]:
        pending["pending"].remove(file)
    if file not in {u["file"] for u in pending["uploaded"]}:
        pending["uploaded"].append({"file": file,
                                    "drive_file_id": drive_file_id,
                                    "uploaded_at": _now_iso()})
    pending["last_updated"] = _now_iso()
    _write_pending(path, pending)
    return {"status": "marked", "file": file, "drive_file_id": drive_file_id,
            "still_pending": len(pending["pending"])}


def list_runs_needing_sync(brand: str) -> dict:
    runs_dir = _common.brand_dir(brand) / "runs"
    if not runs_dir.exists():
        return {"brand": brand, "runs": []}
    needing = []
    for run_dir in sorted(runs_dir.iterdir()):
        if not run_dir.is_dir():
            continue
        pending_path = run_dir / "_sync-pending.json"
        if not pending_path.exists():
            continue
        try:
            pending = json.loads(pending_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if pending.get("pending"):
            needing.append({
                "run_id": run_dir.name,
                "pending_count": len(pending["pending"]),
                "pending_files": pending["pending"],
            })
    return {"brand": brand, "runs": needing}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_brand_sync(brand: str) -> dict:
    path = _brand_sync_path(brand)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_brand_sync(brand: str, data: dict):
    path = _brand_sync_path(brand)
    path.parent.mkdir(parents=True, exist_ok=True)
    _common.atomic_write_json(path, data)


def _read_pending(path: Path) -> dict:
    if not path.exists():
        return {"pending": [], "uploaded": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("pending", [])
        data.setdefault("uploaded", [])
        return data
    except (json.JSONDecodeError, OSError):
        return {"pending": [], "uploaded": []}


def _write_pending(path: Path, data: dict):
    _common.atomic_write_json(path, data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action", required=True, choices=[
        "read-config", "write-config",
        "profile-needs-upload", "profile-mark-uploaded",
        "profile-mark-downloaded", "profile-drive-state",
        "add-pending-upload", "list-pending-uploads",
        "mark-uploaded", "list-runs-needing-sync",
    ])
    parser.add_argument("--brand", type=_common.path_component, help="brand slug or name")
    parser.add_argument("--run-id", type=_common.path_component, help="run identifier")
    parser.add_argument("--file", help="file path / name")
    parser.add_argument("--drive-file-id", help="Drive file ID from MCP response")
    parser.add_argument("--drive-url", help="Drive webViewLink")
    parser.add_argument("--content-hash", help="content hash (for downloads)")
    parser.add_argument("--data", help="JSON payload for write-config")
    args = parser.parse_args()

    if args.action == "read-config":
        result = read_cowork_config()
    elif args.action == "write-config":
        if not args.data:
            result = {"error": "--data required (JSON)"}
        else:
            try:
                result = write_cowork_config(json.loads(args.data))
            except json.JSONDecodeError as e:
                result = {"error": f"invalid JSON in --data: {e}"}
    elif args.action == "profile-needs-upload":
        result = profile_needs_upload(args.brand) if args.brand else {"error": "--brand required"}
    elif args.action == "profile-mark-uploaded":
        if not (args.brand and args.drive_file_id):
            result = {"error": "--brand and --drive-file-id required"}
        else:
            result = profile_mark_uploaded(args.brand, args.drive_file_id, args.drive_url)
    elif args.action == "profile-mark-downloaded":
        if not (args.brand and args.drive_file_id and args.content_hash):
            result = {"error": "--brand, --drive-file-id, --content-hash required"}
        else:
            result = profile_mark_downloaded(args.brand, args.drive_file_id, args.content_hash)
    elif args.action == "profile-drive-state":
        result = profile_drive_state(args.brand) if args.brand else {"error": "--brand required"}
    elif args.action == "add-pending-upload":
        if not (args.brand and args.run_id and args.file):
            result = {"error": "--brand, --run-id, --file required"}
        else:
            result = add_pending_upload(args.brand, args.run_id, args.file)
    elif args.action == "list-pending-uploads":
        if not (args.brand and args.run_id):
            result = {"error": "--brand and --run-id required"}
        else:
            result = list_pending_uploads(args.brand, args.run_id)
    elif args.action == "mark-uploaded":
        if not (args.brand and args.run_id and args.file and args.drive_file_id):
            result = {"error": "--brand, --run-id, --file, --drive-file-id required"}
        else:
            result = mark_run_file_uploaded(args.brand, args.run_id, args.file, args.drive_file_id)
    elif args.action == "list-runs-needing-sync":
        result = list_runs_needing_sync(args.brand) if args.brand else {"error": "--brand required"}
    else:
        result = {"error": f"unknown action: {args.action}"}

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
