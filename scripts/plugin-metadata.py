#!/usr/bin/env python3
"""
plugin-metadata.py
==================
Single source of truth for "what's in this Digital Marketing Pro install right now."
Returns LIVE counts and lists by reading the filesystem and plugin.json -
nothing hardcoded.

Used by /digital-marketing-pro:status, /digital-marketing-pro:doctor, and
/digital-marketing-pro:cowork-setup so version + count strings never drift
out of sync with reality when a skill is added or a release ships.

Usage:
    python plugin-metadata.py                # all metadata, JSON
    python plugin-metadata.py --section version
    python plugin-metadata.py --section assets
    python plugin-metadata.py --section connectors
    python plugin-metadata.py --section skills-list
    python plugin-metadata.py --section commands-list
    python plugin-metadata.py --section environment
    python plugin-metadata.py --section all-with-environment
    python plugin-metadata.py --format text    # human-readable instead of JSON
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SLASH_PREFIX = "/digital-marketing-pro:"


def probe_version() -> dict:
    pj = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
    if not pj.exists():
        return {"error": f"plugin.json missing at {pj}"}
    try:
        data = json.loads(pj.read_text(encoding="utf-8-sig"))
        return {
            "name": data.get("name"),
            "version": data.get("version"),
            "license": data.get("license"),
            "homepage": data.get("homepage"),
            "required_min_version": data.get("requiredMinimumVersion"),
        }
    except (json.JSONDecodeError, OSError) as e:
        return {"error": f"{type(e).__name__}: {e}"}


def probe_assets() -> dict:
    return {
        "agents": _count_files(PLUGIN_ROOT / "agents", "*.md"),
        "skills_total": _count_dirs(PLUGIN_ROOT / "skills"),
        "commands": _count_files(PLUGIN_ROOT / "commands", "*.md"),
        "scripts": _count_files(PLUGIN_ROOT / "scripts", "*.py"),
        "reference_docs": _count_files(PLUGIN_ROOT / "docs", "*.md"),
    }


def probe_connectors() -> dict:
    http_ref = PLUGIN_ROOT / ".mcp.json.connectors-reference"
    npx_example = PLUGIN_ROOT / ".mcp.json.example"
    active = PLUGIN_ROOT / ".mcp.json"

    http_count = 0
    if http_ref.exists():
        try:
            data = json.loads(http_ref.read_text(encoding="utf-8-sig"))
            servers = data.get("mcpServers_reference") or data.get("mcpServers") or {}
            http_count = sum(1 for cfg in servers.values()
                             if isinstance(cfg, dict) and cfg.get("type") == "http")
        except (json.JSONDecodeError, OSError):
            pass

    npx_count = 0
    if npx_example.exists():
        try:
            data = json.loads(npx_example.read_text(encoding="utf-8-sig"))
            servers = data.get("mcpServers") or {}
            npx_count = sum(1 for cfg in servers.values()
                            if isinstance(cfg, dict) and cfg.get("command") == "npx")
        except (json.JSONDecodeError, OSError):
            pass

    active_count = 0
    active_names: list[str] = []
    if active.exists():
        try:
            data = json.loads(active.read_text(encoding="utf-8-sig"))
            servers = data.get("mcpServers") or {}
            active_count = len(servers)
            active_names = sorted(servers.keys())
        except (json.JSONDecodeError, OSError):
            pass

    return {
        "available_http": http_count,
        "available_npx": npx_count,
        "available_total": http_count + npx_count,
        "active_count": active_count,
        "active_names": active_names,
        "cowork_compatible_count": http_count,
    }


def probe_skills_list() -> list[dict]:
    skills_dir = PLUGIN_ROOT / "skills"
    if not skills_dir.exists():
        return []
    out = []
    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        description = ""
        if skill_md.exists():
            description = _extract_description(skill_md)
        out.append({
            "skill_dir": skill_dir.name,
            "slash_command": f"{SLASH_PREFIX}{skill_dir.name}",
            "description": description,
        })
    return out


def probe_commands_list() -> list[dict]:
    cmd_dir = PLUGIN_ROOT / "commands"
    if not cmd_dir.exists():
        return []
    out = []
    for cmd_md in sorted(cmd_dir.glob("*.md")):
        slash_name = cmd_md.stem
        description = _extract_description(cmd_md)
        out.append({
            "command_file": cmd_md.name,
            "slash_command": f"{SLASH_PREFIX}{slash_name}",
            "description": description,
        })
    return out


def probe_environment() -> dict:
    """Detect runtime environment hints - local Claude Code vs Cowork sandbox.

    Critical for the cowork-setup flow: brand-state writes to ~/.claude-marketing/
    DO NOT persist across Cowork sessions (GitHub issue #51398 documents the same
    bug for ${CLAUDE_PLUGIN_DATA}), so Cowork users must route through a Drive MCP.
    """
    import platform
    cwd = Path.cwd()
    cwd_str = str(cwd).replace("\\", "/")
    home = str(Path.home()).replace("\\", "/")

    indicators = {
        "platform": platform.system(),
        "python": platform.python_version(),
        "cwd": cwd_str,
        "home": home,
        "writable_cwd": _is_writable(cwd),
    }

    is_cowork = (
        "/sessions/" in cwd_str
        or cwd_str.startswith("/mnt")
        or "remote-plugins" in cwd_str
        or os.environ.get("ANTHROPIC_COWORK_SESSION_ID")
    )
    is_windows_host = platform.system() == "Windows" and home.startswith("C:")

    environment = (
        "cowork-sandbox" if is_cowork
        else "claude-code-windows" if is_windows_host
        else "claude-code-mac" if platform.system() == "Darwin"
        else "claude-code-linux" if platform.system() == "Linux"
        else "unknown"
    )

    cowork_warning = None
    if is_cowork:
        cowork_warning = (
            "Cowork sandbox detected. Brand state at ~/.claude-marketing/ writes "
            "to the per-session Linux sandbox, NOT a persistent location. "
            "Files vanish at session end. Run /digital-marketing-pro:cowork-setup "
            "to route brand state through a Drive MCP so it persists for the team."
        )

    return {
        "environment": environment,
        "indicators": indicators,
        "cowork_warning": cowork_warning,
    }


def _count_files(directory: Path, pattern: str) -> int:
    if not directory.exists():
        return 0
    return len(list(directory.glob(pattern)))


def _count_dirs(directory: Path) -> int:
    if not directory.exists():
        return 0
    return sum(1 for p in directory.iterdir() if p.is_dir())


def _extract_description(md_path: Path) -> str:
    try:
        text = md_path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return ""
    m = re.match(r"^---\n(.*?)\n---", text, flags=re.DOTALL)
    if m:
        fm = m.group(1)
        dm = re.search(r'^description:\s*["\']?(.*?)["\']?\s*$', fm, flags=re.MULTILINE)
        if dm:
            return dm.group(1).strip().rstrip('"\'')
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("---"):
            return line[:200]
    return ""


def _is_writable(p: Path) -> bool:
    try:
        test = p / ".dmp-write-probe"
        test.write_text("ok", encoding="utf-8")
        test.unlink()
        return True
    except (OSError, PermissionError):
        return False


def all_sections() -> dict:
    return {
        "version": probe_version(),
        "assets": probe_assets(),
        "connectors": probe_connectors(),
        "skills": probe_skills_list(),
        "commands": probe_commands_list(),
    }


def all_with_environment() -> dict:
    payload = all_sections()
    payload["environment"] = probe_environment()
    return payload


def format_text(data: dict) -> str:
    lines = []
    v = data.get("version", {})
    a = data.get("assets", {})
    c = data.get("connectors", {})
    env = data.get("environment", {})

    lines.append("=== DIGITAL MARKETING PRO ===")
    lines.append(f"Version: {v.get('version', '?')}")
    if v.get("required_min_version"):
        lines.append(f"  requires Claude Code >= {v['required_min_version']}")
    lines.append(
        f"Agents: {a.get('agents', '?')}  |  Skills: {a.get('skills_total', '?')}  "
        f"|  Commands: {a.get('commands', '?')}  |  Scripts: {a.get('scripts', '?')}"
    )
    lines.append(
        f"Connectors: {c.get('available_http', '?')} HTTP + "
        f"{c.get('available_npx', '?')} npx available "
        f"({c.get('active_count', 0)} currently active)"
    )
    lines.append(
        f"Cowork-compatible connectors: {c.get('cowork_compatible_count', '?')} "
        "(HTTP only - npx connectors don't run in Cowork)"
    )
    if env:
        e = env.get("environment", "unknown")
        lines.append(f"Environment: {e}")
        warn = env.get("cowork_warning")
        if warn:
            lines.append("")
            lines.append(f"WARNING: {warn}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--section", default="all",
                        choices=["all", "all-with-environment", "version", "assets",
                                 "connectors", "skills-list", "commands-list",
                                 "environment"])
    parser.add_argument("--format", default="json", choices=["json", "text"])
    args = parser.parse_args()

    section = args.section
    if section == "all":
        data = all_sections()
    elif section == "all-with-environment":
        data = all_with_environment()
    elif section == "version":
        data = probe_version()
    elif section == "assets":
        data = probe_assets()
    elif section == "connectors":
        data = probe_connectors()
    elif section == "skills-list":
        data = probe_skills_list()
    elif section == "commands-list":
        data = probe_commands_list()
    elif section == "environment":
        data = probe_environment()
    else:
        data = {"error": f"unknown section: {section}"}

    if args.format == "text" and isinstance(data, dict):
        if section in ("all", "all-with-environment"):
            print(format_text(data))
        else:
            for k, v in data.items():
                print(f"{k}: {'not set' if v is None else v}")  # never a bare Python None
    else:
        print(json.dumps(data, indent=2, ensure_ascii=False))

    return 1 if isinstance(data, dict) and "error" in data else 0


if __name__ == "__main__":
    sys.exit(main())
