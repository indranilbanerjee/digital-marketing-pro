#!/usr/bin/env python3
"""
auto-save-insight.py — Conditionally save a marketing insight based on brand opt-in.

This script implements the opt-in counterpart to the v3.0 SessionEnd hook
that was removed in v3.1. Skills and agents call it whenever they want to
record a session-level insight; it consults the brand profile's
`auto_save_insights` boolean and either saves the insight via the existing
campaign-tracker.py persistence or no-ops cleanly.

Default behaviour (`auto_save_insights` not set or false): NO-OP.
Opt-in behaviour (`auto_save_insights: true` in profile.json): SAVE.

Why the opt-in exists
---------------------
v3.0 and earlier had a global SessionEnd hook that prompted insight-saving
at every session end across every project. v3.1 removed that hook for
multi-plugin hygiene reasons. v3.2 reintroduces the same capability as
opt-in per brand: only brands that explicitly enable it get the auto-save
behaviour, and even then only when skills explicitly call this helper.

Usage
-----
    # No-op safe default — checks profile.json, returns "no_op" if disabled
    python auto-save-insight.py --brand acme --type session_learning \\
        --insight "LinkedIn Document Ads outperform Sponsored Content for our B2B audience"

    # With explicit context for richer insight metadata
    python auto-save-insight.py --brand acme --type campaign_outcome \\
        --insight "Q1 retargeting CPL dropped 30% after creative refresh" \\
        --context "Q1 2026 retargeting campaign" \\
        --source "campaign-plan + performance-report"

    # Force save regardless of opt-in (used when user explicitly approves a save)
    python auto-save-insight.py --brand acme --type voice_drift \\
        --insight "Recent blog posts trending more formal than profile target" \\
        --force

    # Dry run — show what would be saved without writing
    python auto-save-insight.py --brand acme --type session_learning \\
        --insight "..." --dry-run

Output
------
JSON to stdout in all cases:

    {"status": "saved", "insight_id": "ins-XXXX", "brand": "acme"}
    {"status": "no_op", "reason": "auto_save_insights not enabled", "brand": "acme"}
    {"status": "no_op", "reason": "no profile found", "brand": "acme"}
    {"status": "dry_run", "would_save": {...}, "brand": "acme"}
    {"status": "error", "error": "..."}

Exit codes: 0 success (including no_op + dry_run), 1 on error.

How skills should integrate
---------------------------
At the end of a meaningful session, a skill calls:

    python "${CLAUDE_PLUGIN_ROOT}/scripts/auto-save-insight.py" \\
        --brand {slug} \\
        --type session_learning \\
        --insight "{1-sentence summary of what was learned this session}" \\
        --context "{what work produced this insight}" \\
        --source "{which skill / agent}"

If the brand has not opted in, the call is a clean no-op (returns
status: "no_op"). Skills should not surface no_op as an error — it is
the user's choice not to opt into ambient learning capture.

Author: Indranil Banerjee
Plugin: Digital Marketing Pro
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402


# ---------------------------------------------------------------------------
# Workspace + profile resolution
# ---------------------------------------------------------------------------

def workspace_root() -> Path:
    """Return the workspace root. Delegates to the shared _common canon so all
    scripts resolve to the SAME place (honours CLAUDE_MARKETING_HOME for tests,
    CLAUDE_PLUGIN_DATA/digital-marketing-pro when that dir exists, else
    ~/.claude-marketing)."""
    return _common.workspace_root()


def brand_profile_path(brand_slug: str) -> Path:
    return _common.safe_child(workspace_root() / "brands", brand_slug) / "profile.json"


def campaign_tracker_path() -> Path:
    """Resolve campaign-tracker.py relative to this script."""
    return Path(__file__).parent / "campaign-tracker.py"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Opt-in detection
# ---------------------------------------------------------------------------

def is_opted_in(brand_slug: str) -> tuple[bool, str]:
    """Return (opted_in, reason). Returns False with reason if no profile or flag missing/false."""
    profile_path = brand_profile_path(brand_slug)
    if not profile_path.exists():
        return False, f"no profile found at {profile_path}"
    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, f"profile.json is not valid JSON: {exc}"
    flag = profile.get("auto_save_insights", False)
    if flag is True:
        return True, "auto_save_insights enabled"
    return False, "auto_save_insights not enabled"


# ---------------------------------------------------------------------------
# Save via campaign-tracker.py (the canonical persister)
# ---------------------------------------------------------------------------

def save_via_campaign_tracker(brand_slug: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Invoke campaign-tracker.py to save the insight. Returns the persisted result or error."""
    tracker = campaign_tracker_path()
    if not tracker.exists():
        # Fallback: write directly to insights.json
        return save_directly(brand_slug, payload)

    cmd = [
        sys.executable,
        str(tracker),
        "--brand", brand_slug,
        "--action", "save-insight",
        "--data", json.dumps(payload),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "campaign-tracker.py timed out"}
    except (OSError, FileNotFoundError) as exc:
        return {"status": "error", "error": f"campaign-tracker.py exec failed: {exc}"}

    # campaign-tracker.py may exit 0 but report a JSON-level error (e.g.,
    # "Brand not found" because it uses a different workspace resolver than
    # this script). Detect that and fall back to direct write so the insight
    # actually gets persisted to the same workspace this script reads from.
    tracker_failed = result.returncode != 0
    tracker_out: dict[str, Any] = {}
    if not tracker_failed and result.stdout.strip():
        try:
            tracker_out = json.loads(result.stdout)
            # Treat JSON-level error responses as failures even if exit was 0.
            if isinstance(tracker_out, dict) and tracker_out.get("error"):
                tracker_failed = True
        except json.JSONDecodeError:
            tracker_out = {"raw_output": result.stdout.strip()}

    if tracker_failed:
        # Fall back to direct write so the insight is persisted in the
        # workspace this script reads from (same workspace as dm-status.py).
        fallback = save_directly(brand_slug, payload)
        if tracker_out:
            fallback["tracker_attempt"] = tracker_out
        return fallback

    return {
        "status": "saved",
        "insight_id": payload.get("id"),
        "brand": brand_slug,
        "via": "campaign-tracker.py",
        "tracker_output": tracker_out,
    }


def save_directly(brand_slug: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Fallback persistence: append to brands/{slug}/insights.json directly."""
    insights_path = _common.safe_child(workspace_root() / "brands", brand_slug) / "insights.json"
    insights_path.parent.mkdir(parents=True, exist_ok=True)
    container: dict[str, Any]
    if insights_path.exists():
        try:
            data = json.loads(insights_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {"insights": []}
        if isinstance(data, list):
            container = {"insights": data}
        elif isinstance(data, dict):
            container = data
            if "insights" not in container:
                container["insights"] = []
        else:
            container = {"insights": []}
    else:
        container = {"insights": []}
    container["insights"].append(payload)
    container["last_updated_at"] = now_iso()

    # Atomic write
    tmp = insights_path.with_suffix(insights_path.suffix + ".tmp")
    tmp.write_text(json.dumps(container, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(insights_path)
    return {
        "status": "saved",
        "insight_id": payload.get("id"),
        "brand": brand_slug,
        "via": "direct_write",
        "path": str(insights_path),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "id": f"ins-{uuid.uuid4().hex[:10]}",
        "type": args.type,
        "insight": args.insight,
        "context": args.context or "",
        "source": args.source or "auto-save-insight",
        "recorded_at": now_iso(),
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="auto-save-insight.py",
        description="Conditionally save a marketing insight based on the brand's opt-in flag.",
    )
    parser.add_argument("--brand", type=_common.path_component, required=True, help="Brand slug")
    parser.add_argument("--type", required=True, help="Insight type (e.g., session_learning, campaign_outcome, voice_drift, audience_finding, competitive)")
    parser.add_argument("--insight", required=True, help="The insight text (1-2 sentences)")
    parser.add_argument("--context", default="", help="What work produced this insight")
    parser.add_argument("--source", default="", help="Which skill or agent generated this insight")
    parser.add_argument("--force", action="store_true", help="Save regardless of opt-in flag")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be saved without writing")
    args = parser.parse_args(argv)

    if not _common.is_safe_component(args.brand):
        print(json.dumps({"status": "error", "error": f"unsafe --brand {args.brand!r}: use the brand slug"}, indent=2))
        return 1

    if not args.insight.strip():
        print(json.dumps({"status": "error", "error": "--insight cannot be empty"}, indent=2))
        return 1

    # Opt-in check
    opted_in, reason = is_opted_in(args.brand)

    if not opted_in and not args.force:
        print(json.dumps({
            "status": "no_op",
            "reason": reason,
            "brand": args.brand,
            "hint": "To enable ambient insight capture, set 'auto_save_insights': true in the brand profile.json",
        }, indent=2))
        return 0

    payload = build_payload(args)

    if args.dry_run:
        print(json.dumps({
            "status": "dry_run",
            "would_save": payload,
            "brand": args.brand,
            "via": "campaign-tracker.py" if campaign_tracker_path().exists() else "direct_write",
        }, indent=2))
        return 0

    result = save_via_campaign_tracker(args.brand, payload)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("status") in ("saved", "no_op", "dry_run") else 1


if __name__ == "__main__":
    sys.exit(main())
