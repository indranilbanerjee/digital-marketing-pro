#!/usr/bin/env python3
"""
action-doctor.py
================
Per-action readiness diagnostic for Digital Marketing Pro.

For every action in the connector_resolver ACTION_SPECS table, report:
  - Which connector(s) would unlock it
  - Whether any of those connectors are currently configured
  - The resolved mode (real / manifest_ready / stub_unconfigured)
  - For unconfigured actions, the exact one-step setup hint

This is the canonical pre-flight check before running campaign-audit /
launch-campaign, and the answer to "which of the 14 stub actions are
actually live in my environment right now?"

Usage:
    python action-doctor.py --brand acme                     # full readiness map
    python action-doctor.py --brand acme --action inventory  # one action
    python action-doctor.py --brand acme --channel google_ads  # filter by channel
    python action-doctor.py --brand acme --json              # machine-readable
    python action-doctor.py --brand acme --summary           # one-line counts only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Cross-platform safety: force UTF-8 stdout on Windows cp1252 consoles.
# Without this, any non-ASCII character in the report crashes with
# UnicodeEncodeError. errors='replace' means worst case we emit a "?".
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from connector_resolver import (  # noqa: E402
    ACTION_SPECS,
    _load_mcp_json,
    find_connector,
    is_connector_configured,
    resolve_action,
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402

# Model curator freshness check (degrades gracefully if curator is missing).
try:
    from resolve_model import registry_age_days, get_registry  # noqa: E402
except ImportError:  # pragma: no cover
    registry_age_days = None  # type: ignore[assignment]
    get_registry = None  # type: ignore[assignment]

# Cowork+Drive routing check (degrades gracefully).
try:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location(
        "drive_sync_state",
        Path(__file__).resolve().parent / "drive-sync-state.py",
    )
    if _spec and _spec.loader:
        _dss = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_dss)
        read_cowork_config = _dss.read_cowork_config  # type: ignore[attr-defined]
    else:
        read_cowork_config = None  # type: ignore[assignment]
except Exception:  # pragma: no cover
    read_cowork_config = None  # type: ignore[assignment]


REGISTRY_STALE_WARN_DAYS = 60   # warn when model registry is older than this
REGISTRY_STALE_ERROR_DAYS = 120  # call out as urgent when older than this


def _probe_environment():
    """Inline environment probe to keep action-doctor self-contained."""
    import platform
    cwd_str = str(Path.cwd()).replace("\\", "/")
    is_cowork = (
        "/sessions/" in cwd_str
        or cwd_str.startswith("/mnt")
        or "remote-plugins" in cwd_str
        or os.environ.get("ANTHROPIC_COWORK_SESSION_ID")
    )
    if is_cowork:
        return "cowork-sandbox"
    sysname = platform.system()
    if sysname == "Windows":
        return "claude-code-windows"
    if sysname == "Darwin":
        return "claude-code-mac"
    if sysname == "Linux":
        return "claude-code-linux"
    return "unknown"


def _model_curator_status():
    """Return a dict describing model-registry freshness and any required action."""
    if registry_age_days is None or get_registry is None:
        return {
            "available": False,
            "reason": "scripts/resolve_model.py not importable",
        }
    try:
        age = registry_age_days()
        reg = get_registry()
    except Exception as exc:  # pragma: no cover
        return {"available": False, "reason": f"{type(exc).__name__}: {exc}"}

    if age is None:
        return {
            "available": True,
            "last_updated": None,
            "age_days": None,
            "severity": "warn",
            "message": "Model registry has no last_updated timestamp. Treat all model IDs as suspect.",
            "action": "python refresh_models.py (from the plugin scripts/ directory)",
        }
    severity = "ok"
    message = f"Model registry is {age} days old. Within the {REGISTRY_STALE_WARN_DAYS}-day refresh window."
    action = None
    if age >= REGISTRY_STALE_ERROR_DAYS:
        severity = "urgent"
        message = (
            f"Model registry is {age} days old (>{REGISTRY_STALE_ERROR_DAYS} = URGENT). "
            "Frontier models shift ~every 6 weeks; deprecated IDs will start returning 404 silently."
        )
        action = ("Set ANTHROPIC_API_KEY / OPENAI_API_KEY / GEMINI_API_KEY / EVOLINK_API_KEY "
                  "in your environment, then run: python refresh_models.py "
                  "(cross-shell: the POSIX 'VAR=... command' prefix does not work in PowerShell)")
    elif age >= REGISTRY_STALE_WARN_DAYS:
        severity = "warn"
        message = (
            f"Model registry is {age} days old (>{REGISTRY_STALE_WARN_DAYS} = stale). "
            "Run refresh_models.py to check provider drift before any high-volume run."
        )
        action = ("Set ANTHROPIC_API_KEY / OPENAI_API_KEY / GEMINI_API_KEY / EVOLINK_API_KEY "
                  "in your environment, then run: python refresh_models.py "
                  "(cross-shell: the POSIX 'VAR=... command' prefix does not work in PowerShell)")

    return {
        "available": True,
        "last_updated": reg.get("last_updated"),
        "next_review_due": reg.get("next_review_due"),
        "age_days": age,
        "severity": severity,
        "message": message,
        "action": action,
    }


def _cowork_routing_status(env_name):
    """Cowork+Drive routing readiness. Only meaningful when env is Cowork."""
    if env_name != "cowork-sandbox":
        return {
            "environment": env_name,
            "applicable": False,
            "severity": "n/a",
            "message": "Local Claude Code detected. Cowork+Drive routing is not required here.",
        }
    if read_cowork_config is None:
        return {
            "environment": env_name,
            "applicable": True,
            "configured": False,
            "severity": "urgent",
            "message": "drive-sync-state.py not importable; Cowork brand state will not persist across sessions.",
            "action": "/digital-marketing-pro:cowork-setup",
        }
    cfg = read_cowork_config()
    if cfg.get("configured"):
        return {
            "environment": env_name,
            "applicable": True,
            "configured": True,
            "severity": "ok",
            "drive_root_folder_url": cfg.get("drive_root_folder_url"),
            "drive_root_folder_name": cfg.get("drive_root_folder_name"),
            "message": f"Cowork+Drive routing active. Root: {cfg.get('drive_root_folder_name', '?')}",
        }
    return {
        "environment": env_name,
        "applicable": True,
        "configured": False,
        "severity": "urgent",
        "message": "Cowork sandbox detected but Drive routing is not configured. Brand state will vanish at session end.",
        "action": "/digital-marketing-pro:cowork-setup",
    }


def _per_action_readiness(brand, channel=None):
    """Resolve every action and bucket by mode."""
    active_servers = _load_mcp_json()
    rows = []
    for action_id, spec in sorted(ACTION_SPECS.items()):
        kwargs = {"channel": channel} if channel else {}
        if spec["operation"] != "local":
            candidates = spec["candidate_connectors"](kwargs) or []
            configured = []
            for c in candidates:
                info = find_connector(c)
                if info is None:
                    continue
                ok, _ = is_connector_configured(c, info, active_servers)
                if ok:
                    configured.append(c)
            mode = "manifest_ready" if configured else "stub_unconfigured"
        else:
            candidates = []
            configured = []
            mode = "real"
        rows.append({
            "action": action_id,
            "script": spec["script"],
            "operation": spec["operation"],
            "purpose": spec["purpose"],
            "candidate_connectors": candidates,
            "configured_connectors": configured,
            "mode": mode,
        })
    return rows


def _summary_counts(rows):
    counts = {"real": 0, "manifest_ready": 0, "stub_unconfigured": 0}
    for r in rows:
        counts[r["mode"]] = counts.get(r["mode"], 0) + 1
    return counts


def _format_text_report(brand, rows, counts):
    """Pretty terminal-friendly report."""
    lines = []
    total = len(rows)
    lines.append(f"DMP action readiness for brand '{brand}': "
                 f"{counts.get('real', 0)} real, "
                 f"{counts.get('manifest_ready', 0)} manifest-ready, "
                 f"{counts.get('stub_unconfigured', 0)} stub-unconfigured "
                 f"(total {total})")
    lines.append("")
    lines.append(f"{'ACTION':22s}  {'MODE':18s}  {'OP':6s}  {'CONNECTOR(S)':45s}")
    lines.append("-" * 95)
    for r in rows:
        if r["mode"] == "real":
            conn_display = "(local execution -- no connector needed)"
        elif r["mode"] == "manifest_ready":
            conn_display = f"[OK] {', '.join(r['configured_connectors'])}"
        else:
            conn_display = f"[--] needs one of: {', '.join(r['candidate_connectors'][:3])}"
            if len(r["candidate_connectors"]) > 3:
                conn_display += f" (+{len(r['candidate_connectors']) - 3} more)"
        lines.append(f"{r['action']:22s}  {r['mode']:18s}  {r['operation']:6s}  {conn_display}")
    lines.append("")
    unconfigured = [r for r in rows if r["mode"] == "stub_unconfigured"]
    if unconfigured:
        lines.append(f"To unlock the {len(unconfigured)} stub-unconfigured action(s):")
        lines.append("  python scripts/connector-status.py --action setup-guide --name <connector>")
        lines.append("  ... then add the printed snippet to .mcp.json under mcpServers.")
        lines.append("")
        lines.append("Or run any individual action -- it returns the same setup hint inline.")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Per-action readiness diagnostic for Digital Marketing Pro."
    )
    parser.add_argument("--brand", type=_common.path_component, default="default",
                        help="Brand slug (used for write-side actions; readiness is brand-agnostic)")
    parser.add_argument("--action",
                        help="Drill into a single action and print resolve_action's full response.")
    parser.add_argument("--channel",
                        help="Channel context for actions that need one (google_ads / meta_ads / "
                             "email / facebook / linkedin / etc.)")
    parser.add_argument("--json", action="store_true",
                        help="Emit machine-readable JSON.")
    parser.add_argument("--summary", action="store_true",
                        help="Print only the one-line summary counts.")
    args = parser.parse_args()

    # Single-action drill-in (always JSON — the previous --json/else branches
    # were identical dead code).
    if args.action:
        kwargs = {"channel": args.channel} if args.channel else {}
        result = resolve_action(args.action, args.brand, **kwargs)
        print(json.dumps(result, indent=2))
        return

    rows = _per_action_readiness(args.brand, channel=args.channel)
    counts = _summary_counts(rows)
    env_name = _probe_environment()
    model_status = _model_curator_status()
    cowork_status = _cowork_routing_status(env_name)

    if args.summary:
        print(f"{counts.get('real', 0)} real | "
              f"{counts.get('manifest_ready', 0)} manifest-ready | "
              f"{counts.get('stub_unconfigured', 0)} stub-unconfigured "
              f"(total {len(rows)})  |  env={env_name}  |  "
              f"model_registry={model_status.get('severity', '?')}  |  "
              f"cowork_drive={cowork_status.get('severity', 'n/a')}")
        return

    if args.json:
        print(json.dumps({
            "brand": args.brand,
            "channel_filter": args.channel,
            "summary": counts,
            "total_actions": len(rows),
            "actions": rows,
            "environment": env_name,
            "model_curator": model_status,
            "cowork_routing": cowork_status,
        }, indent=2))
    else:
        print(_format_text_report(args.brand, rows, counts))
        print()
        print("=== ENVIRONMENT ===")
        print(f"Detected: {env_name}")
        print()
        print("=== MODEL CURATOR ===")
        if model_status.get("available"):
            print(f"Registry last_updated: {model_status.get('last_updated', '?')} "
                  f"({model_status.get('age_days', '?')} days ago)")
            print(f"[{model_status.get('severity', '?').upper()}] {model_status.get('message', '')}")
            if model_status.get("action"):
                print(f"Action: {model_status['action']}")
        else:
            print(f"Curator unavailable: {model_status.get('reason', 'unknown')}")
        print()
        print("=== COWORK+DRIVE ROUTING ===")
        print(f"[{cowork_status.get('severity', '?').upper()}] {cowork_status.get('message', '')}")
        if cowork_status.get("action"):
            print(f"Action: {cowork_status['action']}")


if __name__ == "__main__":
    main()
