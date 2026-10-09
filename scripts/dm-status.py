#!/usr/bin/env python3
"""
dm-status.py — Unified Digital Marketing Pro status snapshot.

Reads brand profile, engagement state, recent insights, recent compliance
violations, and Python dependency mode, then prints a single human-readable
status summary.

In v3.0 and earlier, the SessionStart hook ran setup.py automatically at
every Claude Code session start to print a 15-line brand summary banner.
v3.1 removed that hook because it fired globally across every project.
This script is the explicit replacement: a user-invoked status snapshot
that produces an even richer view (including engagement state and
insight age) on demand.

Usage:
    python dm-status.py                          # Active brand, full snapshot
    python dm-status.py --brand acme             # Specific brand snapshot
    python dm-status.py --json                   # Machine-readable JSON output
    python dm-status.py --quiet                  # Compact one-line status
    python dm-status.py --section brand          # Only the brand section
    python dm-status.py --section engagements    # Only engagement state
    python dm-status.py --section insights       # Only recent insights
    python dm-status.py --section compliance     # Only recent compliance violations
    python dm-status.py --section deps           # Only Python dependency status

Sections (in default order):
    brand        Active brand profile summary
    engagements  Active engagements with current part + days-since-update
    insights     Last 5 insights captured + days since last save
    compliance   Last 5 compliance violations + count in last 30 days
    deps         Python dependency mode (knowledge-only / lite / full)

Exit codes:
    0  Success
    1  No brand profile / no active brand and brand argument missing
    2  Filesystem error reading state files

Author: Indranil Banerjee
Plugin: Digital Marketing Pro
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402


# ---------------------------------------------------------------------------
# Paths and resolution
# ---------------------------------------------------------------------------

def workspace_root() -> Path:
    """Return the workspace root. Delegates to the shared _common canon so all
    scripts resolve to the SAME place (honours CLAUDE_MARKETING_HOME for tests,
    CLAUDE_PLUGIN_DATA/digital-marketing-pro when that dir exists, else
    ~/.claude-marketing)."""
    return _common.workspace_root()


def brand_dir(brand_slug: str) -> Path:
    return workspace_root() / "brands" / brand_slug


def active_brand_path() -> Path:
    return workspace_root() / "brands" / "_active-brand.json"


def resolve_brand_slug(provided: Optional[str]) -> Optional[str]:
    """Resolve the brand slug from the argument or active-brand pointer."""
    if provided:
        return provided
    pointer = active_brand_path()
    if not pointer.exists():
        return None
    try:
        data = json.loads(pointer.read_text(encoding="utf-8"))
        return data.get("active_slug")
    except (json.JSONDecodeError, OSError):
        return None


# ---------------------------------------------------------------------------
# Section: brand
# ---------------------------------------------------------------------------

def collect_brand_section(brand_slug: str) -> dict[str, Any]:
    profile_path = brand_dir(brand_slug) / "profile.json"
    section: dict[str, Any] = {
        "section": "brand",
        "brand_slug": brand_slug,
        "profile_exists": profile_path.exists(),
    }
    if not profile_path.exists():
        section["error"] = f"profile.json not found at {profile_path}"
        return section

    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        section["error"] = f"profile.json is not valid JSON: {exc}"
        return section

    identity = profile.get("identity", {})
    voice = profile.get("brand_voice", {})
    business = profile.get("business_model", {})
    industry = profile.get("industry", {})
    channels = profile.get("channels", {})
    goals = profile.get("goals", {})
    competitors = profile.get("competitors", [])
    markets = profile.get("target_markets", [])
    languages = profile.get("language", {})

    section.update({
        "brand_name": profile.get("brand_name") or identity.get("name", "Unknown"),
        "tagline": identity.get("tagline", ""),
        "industry_primary": industry.get("primary", "Not set"),
        "industry_regulated": bool(industry.get("regulated", False)),
        "regulation_codes": industry.get("regulation_codes", []),
        "business_model_type": business.get("type", "Not set"),
        "revenue_model": business.get("revenue_model", "Not set"),
        "voice": {
            "formality": voice.get("formality"),
            "energy": voice.get("energy"),
            "humor": voice.get("humor"),
            "authority": voice.get("authority"),
            "personality_traits": voice.get("personality_traits", []),
        },
        "active_channels": channels.get("active", []),
        "primary_channel": channels.get("primary"),
        "competitor_count": len(competitors),
        "competitor_names": [c.get("name") for c in competitors[:5] if c.get("name")],
        "market_count": len(markets),
        "primary_language": languages.get("primary_language"),
        "secondary_languages": languages.get("secondary_languages", []),
        "primary_goal": goals.get("primary_objective"),
        "kpis": goals.get("kpis", []),
        "auto_save_insights": profile.get("auto_save_insights", False),
        "profile_path": str(profile_path),
    })
    return section


# ---------------------------------------------------------------------------
# Section: engagements
# ---------------------------------------------------------------------------

def collect_engagements_section(brand_slug: str) -> dict[str, Any]:
    engagements_dir = brand_dir(brand_slug) / "engagements"
    section: dict[str, Any] = {
        "section": "engagements",
        "engagements_dir": str(engagements_dir),
        "engagements": [],
    }
    if not engagements_dir.exists():
        section["count"] = 0
        return section

    now = datetime.now(timezone.utc)
    for eng_dir in sorted(engagements_dir.iterdir()):
        if not eng_dir.is_dir():
            continue
        state_path = eng_dir / "_engagement.json"
        if not state_path.exists():
            section["engagements"].append({
                "engagement_id": eng_dir.name,
                "status": "no_state_file",
            })
            continue
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            section["engagements"].append({
                "engagement_id": eng_dir.name,
                "status": "state_unreadable",
            })
            continue

        current_part = state.get("current_part", "?")
        parts = state.get("parts", {})
        completed_parts = [p for p, v in parts.items() if v.get("status") == "completed"]
        in_progress_parts = [p for p, v in parts.items() if v.get("status") == "in_progress"]
        awaiting_input_parts = [p for p, v in parts.items() if v.get("status") == "awaiting_input"]
        blocked_parts = [p for p, v in parts.items() if v.get("status") == "blocked"]

        last_updated = state.get("last_updated_at")
        days_since_update = _days_since(last_updated, now)

        # Count outstanding decisions
        rerun_decisions = state.get("rerun_decisions", [])
        pending_decisions = [d for d in rerun_decisions if d.get("user_decision") == "pending"]

        section["engagements"].append({
            "engagement_id": state.get("engagement_id", eng_dir.name),
            "current_part": current_part,
            "current_part_name": parts.get(str(current_part), {}).get("name", ""),
            "completed_parts": sorted(completed_parts, key=_part_sort_key),
            "in_progress_parts": in_progress_parts,
            "awaiting_input_parts": awaiting_input_parts,
            "blocked_parts": blocked_parts,
            "last_updated_at": last_updated,
            "days_since_update": days_since_update,
            "pending_rerun_decisions": len(pending_decisions),
            "version_history_doc_count": len(state.get("version_history", {})),
        })

    section["count"] = len(section["engagements"])
    return section


# ---------------------------------------------------------------------------
# Section: insights
# ---------------------------------------------------------------------------

def collect_insights_section(brand_slug: str) -> dict[str, Any]:
    insights_path = brand_dir(brand_slug) / "insights.json"
    section: dict[str, Any] = {
        "section": "insights",
        "insights_path": str(insights_path),
        "insights_exists": insights_path.exists(),
        "recent_insights": [],
        "total_count": 0,
        "days_since_last_insight": None,
    }
    if not insights_path.exists():
        return section

    try:
        data = json.loads(insights_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        section["error"] = f"insights.json is not valid JSON: {exc}"
        return section

    # insights.json is typically a list or {"insights": [...]}
    if isinstance(data, list):
        insights = data
    elif isinstance(data, dict):
        insights = data.get("insights") or data.get("items") or []
    else:
        insights = []

    section["total_count"] = len(insights)
    if not insights:
        return section

    # Sort by recorded_at descending if available
    def _ts(entry: dict) -> str:
        return entry.get("recorded_at") or entry.get("timestamp") or entry.get("captured_at") or ""

    sorted_insights = sorted(insights, key=_ts, reverse=True)
    last_5 = sorted_insights[:5]
    section["recent_insights"] = [
        {
            "type": e.get("type", ""),
            "insight": _truncate(e.get("insight") or e.get("text") or "", 120),
            "recorded_at": _ts(e),
        }
        for e in last_5
    ]
    section["days_since_last_insight"] = _days_since(_ts(sorted_insights[0]), datetime.now(timezone.utc))
    return section


# ---------------------------------------------------------------------------
# Section: compliance violations
# ---------------------------------------------------------------------------

def collect_compliance_section(brand_slug: str) -> dict[str, Any]:
    violations_path = brand_dir(brand_slug) / "guideline-violations.json"
    section: dict[str, Any] = {
        "section": "compliance",
        "violations_path": str(violations_path),
        "violations_exists": violations_path.exists(),
        "recent_violations": [],
        "total_count": 0,
        "count_last_30_days": 0,
    }
    if not violations_path.exists():
        return section

    try:
        data = json.loads(violations_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        section["error"] = f"violations file is not valid JSON: {exc}"
        return section

    if isinstance(data, list):
        violations = data
    elif isinstance(data, dict):
        violations = data.get("violations") or data.get("items") or []
    else:
        violations = []

    section["total_count"] = len(violations)
    if not violations:
        return section

    def _ts(entry: dict) -> str:
        return entry.get("recorded_at") or entry.get("timestamp") or ""

    sorted_violations = sorted(violations, key=_ts, reverse=True)
    last_5 = sorted_violations[:5]
    section["recent_violations"] = [
        {
            "rule": v.get("rule", ""),
            "category": v.get("category", ""),
            "severity": v.get("severity", ""),
            "recorded_at": _ts(v),
        }
        for v in last_5
    ]

    # Count violations in last 30 days
    now = datetime.now(timezone.utc)
    count_recent = 0
    for v in violations:
        ts = _ts(v)
        days = _days_since(ts, now)
        if days is not None and days <= 30:
            count_recent += 1
    section["count_last_30_days"] = count_recent
    return section


# ---------------------------------------------------------------------------
# Section: dependency status
# ---------------------------------------------------------------------------

def collect_deps_section() -> dict[str, Any]:
    section: dict[str, Any] = {
        "section": "deps",
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "mode": "knowledge-only",
        "available": [],
        "missing": [],
    }

    optional_packages = [
        ("nltk", "lite"),
        ("textstat", "lite"),
        ("requests", "full"),
        ("beautifulsoup4", "full"),
        ("qrcode", "full"),
        ("Pillow", "full"),
    ]

    lite_present = True
    full_present = True
    for pkg, tier in optional_packages:
        # beautifulsoup4 imports as bs4
        import_name = "bs4" if pkg == "beautifulsoup4" else pkg
        # qrcode and Pillow have lowercase import names
        import_name = import_name.lower() if import_name in ("Pillow",) else import_name
        if import_name == "Pillow".lower():
            import_name = "PIL"
        try:
            __import__(import_name)
            section["available"].append(pkg)
        except ImportError:
            section["missing"].append(pkg)
            if tier == "lite":
                lite_present = False
            full_present = False

    if full_present:
        section["mode"] = "full"
    elif lite_present:
        section["mode"] = "lite"
    else:
        section["mode"] = "knowledge-only"

    return section


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _days_since(timestamp_str: Optional[str], now: datetime) -> Optional[int]:
    """Return days between an ISO 8601 timestamp and now. Returns None on parse failure."""
    if not timestamp_str:
        return None
    try:
        # Handle Z suffix
        if timestamp_str.endswith("Z"):
            ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        else:
            ts = datetime.fromisoformat(timestamp_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        delta = now - ts
        return max(delta.days, 0)
    except (ValueError, TypeError):
        return None


def _truncate(text: str, n: int) -> str:
    if len(text) <= n:
        return text
    return text[: n - 3] + "..."


def _part_sort_key(part: str) -> tuple:
    """Sort engagement parts numerically (1, 2, 3, ..., 12)."""
    try:
        return (int(part),)
    except ValueError:
        return (999, part)


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

def render_text(snapshot: dict[str, Any], quiet: bool = False) -> str:
    """Render a human-readable text status snapshot."""
    lines: list[str] = []
    sections = snapshot.get("sections", {})

    if quiet:
        # One-line compact summary
        brand = sections.get("brand", {})
        eng = sections.get("engagements", {})
        deps = sections.get("deps", {})
        brand_name = brand.get("brand_name", "(no brand)")
        eng_count = eng.get("count", 0)
        active_engs = sum(
            1 for e in eng.get("engagements", [])
            if e.get("current_part") and not _all_completed(e)
        )
        return (
            f"DMP STATUS | {brand_name} | engagements: {active_engs} active / {eng_count} total | "
            f"deps: {deps.get('mode', '?')}"
        )

    lines.append("=" * 60)
    lines.append("  DIGITAL MARKETING PRO — STATUS SNAPSHOT")
    lines.append(f"  Generated: {snapshot.get('generated_at', '')}")
    lines.append("=" * 60)

    # Brand section
    brand = sections.get("brand")
    if brand:
        lines.append("")
        lines.append("BRAND")
        lines.append("-" * 60)
        if "error" in brand:
            lines.append(f"  ERROR: {brand['error']}")
        elif not brand.get("profile_exists"):
            lines.append("  No brand profile found.")
            lines.append(f"  Run /digital-marketing-pro:brand-setup to create one.")
        else:
            lines.append(f"  Name:         {brand['brand_name']} ({brand['brand_slug']})")
            if brand.get("tagline"):
                lines.append(f"  Tagline:      {brand['tagline']}")
            lines.append(f"  Industry:     {brand['industry_primary']} (regulated: {'yes' if brand['industry_regulated'] else 'no'})")
            if brand["regulation_codes"]:
                lines.append(f"  Regulations:  {', '.join(brand['regulation_codes'])}")
            lines.append(f"  Model:        {brand['business_model_type']} | Revenue: {brand['revenue_model']}")
            v = brand["voice"]
            voice_str = " | ".join([
                f"Formality {v['formality']}/10" if v.get('formality') is not None else "Formality —",
                f"Energy {v['energy']}/10" if v.get('energy') is not None else "Energy —",
                f"Humor {v['humor']}/10" if v.get('humor') is not None else "Humor —",
                f"Authority {v['authority']}/10" if v.get('authority') is not None else "Authority —",
            ])
            lines.append(f"  Voice:        {voice_str}")
            if v.get("personality_traits"):
                lines.append(f"  Traits:       {', '.join(v['personality_traits'])}")
            if brand["active_channels"]:
                lines.append(f"  Channels:     {', '.join(brand['active_channels'])}")
                if brand.get("primary_channel"):
                    lines.append(f"  Primary:      {brand['primary_channel']}")
            if brand.get("primary_language"):
                lang_str = brand["primary_language"]
                if brand.get("secondary_languages"):
                    lang_str += f" (+ {', '.join(brand['secondary_languages'])})"
                lines.append(f"  Languages:    {lang_str}")
            lines.append(f"  Markets:      {brand['market_count']} configured")
            if brand["competitor_names"]:
                lines.append(f"  Competitors:  {', '.join(brand['competitor_names'])}")
            else:
                lines.append(f"  Competitors:  {brand['competitor_count']} configured")
            if brand.get("primary_goal"):
                lines.append(f"  Primary goal: {brand['primary_goal']}")
            lines.append(f"  Auto-save:    insights = {'enabled' if brand['auto_save_insights'] else 'disabled (opt-in via auto_save_insights in profile.json)'}")

    # Engagements section
    eng = sections.get("engagements")
    if eng:
        lines.append("")
        lines.append("ENGAGEMENTS")
        lines.append("-" * 60)
        if eng["count"] == 0:
            lines.append("  No engagements yet.")
            lines.append("  Run /digital-marketing-pro:engagement start <brand-slug> <engagement-id> to begin one.")
        else:
            for e in eng["engagements"]:
                if e.get("status") in ("no_state_file", "state_unreadable"):
                    lines.append(f"  {e['engagement_id']}: {e['status']}")
                    continue
                line1 = f"  {e['engagement_id']}"
                line2 = f"    Part {e['current_part']}: {e['current_part_name']}"
                line3 = (
                    f"    Completed: {len(e['completed_parts'])} / 12"
                    + (f" | In progress: {','.join(e['in_progress_parts'])}" if e['in_progress_parts'] else "")
                    + (f" | Awaiting input: {','.join(e['awaiting_input_parts'])}" if e['awaiting_input_parts'] else "")
                    + (f" | Blocked: {','.join(e['blocked_parts'])}" if e['blocked_parts'] else "")
                )
                line4_parts = []
                if e.get("days_since_update") is not None:
                    line4_parts.append(f"Updated {e['days_since_update']}d ago")
                if e.get("pending_rerun_decisions"):
                    line4_parts.append(f"{e['pending_rerun_decisions']} pending re-run decision(s)")
                if e.get("version_history_doc_count"):
                    line4_parts.append(f"{e['version_history_doc_count']} doc(s) versioned")
                line4 = "    " + " | ".join(line4_parts) if line4_parts else ""

                lines.append(line1)
                lines.append(line2)
                lines.append(line3)
                if line4:
                    lines.append(line4)

    # Insights section
    ins = sections.get("insights")
    if ins:
        lines.append("")
        lines.append("RECENT INSIGHTS")
        lines.append("-" * 60)
        if ins.get("total_count", 0) == 0:
            lines.append("  No insights captured yet.")
            lines.append("  Insights are saved via campaign-tracker.py or auto-saved if profile.json")
            lines.append("  has 'auto_save_insights: true' (v3.2+ opt-in).")
        else:
            lines.append(f"  Total: {ins['total_count']} insights")
            if ins.get("days_since_last_insight") is not None:
                lines.append(f"  Last saved: {ins['days_since_last_insight']}d ago")
            for entry in ins["recent_insights"]:
                lines.append(f"    · [{entry.get('type', '?')}] {entry.get('insight', '')}")

    # Compliance violations section
    comp = sections.get("compliance")
    if comp:
        lines.append("")
        lines.append("RECENT COMPLIANCE VIOLATIONS")
        lines.append("-" * 60)
        if comp.get("total_count", 0) == 0:
            lines.append("  No violations recorded.")
        else:
            lines.append(f"  Total: {comp['total_count']} | Last 30 days: {comp['count_last_30_days']}")
            for v in comp["recent_violations"]:
                lines.append(f"    · [{v['severity']}] {v['rule']} ({v['category']})")

    # Deps section
    deps = sections.get("deps")
    if deps:
        lines.append("")
        lines.append("PYTHON DEPENDENCIES")
        lines.append("-" * 60)
        lines.append(f"  Python:       {deps['python_version']}")
        lines.append(f"  Mode:         {deps['mode']}")
        if deps["available"]:
            lines.append(f"  Available:    {', '.join(deps['available'])}")
        if deps["missing"]:
            lines.append(f"  Missing:      {', '.join(deps['missing'])}")
            if deps["mode"] == "knowledge-only":
                lines.append(f"  Hint: pip install nltk textstat (lite mode)")

    lines.append("")
    lines.append("=" * 60)
    lines.append("Tip: /digital-marketing-pro:status --json for machine-readable output")
    lines.append("Tip: /digital-marketing-pro:status --quiet for one-line summary")
    lines.append("=" * 60)
    return "\n".join(lines)


def _all_completed(eng: dict[str, Any]) -> bool:
    return len(eng.get("completed_parts", [])) == 12


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dm-status.py",
        description="Unified Digital Marketing Pro status snapshot.",
    )
    parser.add_argument("--brand", type=_common.path_component, help="Brand slug (defaults to active brand)")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of formatted text")
    parser.add_argument("--quiet", action="store_true", help="Compact one-line status")
    parser.add_argument(
        "--section",
        choices=["brand", "engagements", "insights", "compliance", "deps", "all"],
        default="all",
        help="Limit output to a specific section (default: all)",
    )
    args = parser.parse_args(argv)

    brand_slug = resolve_brand_slug(args.brand)
    if not brand_slug:
        if args.json:
            print(json.dumps({
                "error": "no_active_brand",
                "message": "No active brand. Pass --brand <slug> or run /digital-marketing-pro:brand-setup.",
                "workspace": str(workspace_root()),
            }, indent=2))
        else:
            print("No active brand found.")
            print("Pass --brand <slug> explicitly, or run /digital-marketing-pro:brand-setup to create one.")
            print(f"Workspace: {workspace_root()}")
        return 1

    sections: dict[str, Any] = {}
    selected = args.section

    try:
        if selected in ("brand", "all"):
            sections["brand"] = collect_brand_section(brand_slug)
        if selected in ("engagements", "all"):
            sections["engagements"] = collect_engagements_section(brand_slug)
        if selected in ("insights", "all"):
            sections["insights"] = collect_insights_section(brand_slug)
        if selected in ("compliance", "all"):
            sections["compliance"] = collect_compliance_section(brand_slug)
        if selected in ("deps", "all"):
            sections["deps"] = collect_deps_section()
    except (PermissionError, OSError) as exc:
        msg = f"Filesystem error: {exc}"
        if args.json:
            print(json.dumps({"error": "filesystem_error", "message": msg}, indent=2))
        else:
            print(msg)
        return 2

    snapshot = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "brand_slug": brand_slug,
        "workspace": str(workspace_root()),
        "sections": sections,
    }

    if args.json:
        print(json.dumps(snapshot, indent=2, ensure_ascii=False))
    else:
        print(render_text(snapshot, quiet=args.quiet))

    return 0


if __name__ == "__main__":
    sys.exit(main())
