#!/usr/bin/env python3
"""
connector-status.py
===================
Connector discovery and status reporting for Digital Marketing Pro.

Reports which MCP connectors are configured (HTTP and npx), which are
available but not yet connected, and which skills gain capabilities
from each connector category.

Usage:
    python connector-status.py --action status          # Full status dashboard
    python connector-status.py --action list-available   # All available connectors
    python connector-status.py --action check <name>     # Check specific connector
    python connector-status.py --action setup-guide <name>  # Setup instructions for a connector
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Import the shared registry + helpers (single source of truth as of v3.7.12).
# Previously this file carried its own 600-line copy of CONNECTOR_REGISTRY,
# which created a drift risk every time we added a connector.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _connector_registry import (  # type: ignore  # noqa: E402
    CONNECTOR_REGISTRY,
    _load_mcp_json,
    is_connector_configured as _is_configured_impl,
    redact_secrets as _redact_secrets,
)

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
MCP_JSON = PLUGIN_ROOT / ".mcp.json"

# Thin adapter: the original _is_configured(name, info, servers) returned just
# a bool. The new shared helper returns (bool, evidence_dict). Strip evidence
# to preserve the existing call sites in status_dashboard / list_available /
# check_connector / setup_guide.
def _is_configured(name, connector_info, active_servers):
    configured, _ = _is_configured_impl(name, connector_info, active_servers)
    return configured

def status_dashboard():
    """Full status dashboard of all connectors."""
    active_servers = _load_mcp_json()

    categories = []
    total_connected = 0
    total_available = 0

    for cat_key, cat_info in CONNECTOR_REGISTRY.items():
        connected = []
        available = []

        for name, conn in cat_info["connectors"].items():
            total_available += 1
            entry = {
                "name": name,
                "description": conn["description"],
                "transport": conn["transport"],
                "skills_unlocked": conn["skills_unlocked"],
            }
            if conn.get("access"):
                entry["access"] = conn["access"]

            if _is_configured(name, conn, active_servers):
                entry["status"] = "connected"
                connected.append(entry)
                total_connected += 1
            else:
                entry["status"] = "available"
                if conn["transport"] == "npx":
                    entry["env_vars_needed"] = conn["env_vars"]
                    entry["note"] = "Claude Code only (requires npx)"
                else:
                    entry["note"] = "HTTP connector — works in Cowork + Claude Code"
                if "note" in conn:
                    entry["platform_note"] = conn["note"]
                available.append(entry)

        categories.append({
            "category": cat_key,
            "description": cat_info["description"],
            "connected": connected,
            "available": available,
            "connected_count": len(connected),
            "total_count": len(connected) + len(available),
        })

    return {
        "summary": {
            "total_connected": total_connected,
            "total_available": total_available,
            "coverage_percent": round(
                (total_connected / total_available * 100) if total_available else 0
            ),
        },
        "categories": categories,
    }


def list_available():
    """List all available connectors not yet configured."""
    active_servers = _load_mcp_json()
    available = []

    for cat_key, cat_info in CONNECTOR_REGISTRY.items():
        for name, conn in cat_info["connectors"].items():
            if not _is_configured(name, conn, active_servers):
                entry = {
                    "name": name,
                    "category": cat_key,
                    "description": conn["description"],
                    "transport": conn["transport"],
                    "skills_unlocked": conn["skills_unlocked"],
                }
                if conn.get("access"):
                    entry["access"] = conn["access"]
                if conn["transport"] == "npx":
                    entry["env_vars_needed"] = conn["env_vars"]
                available.append(entry)

    return {"available_connectors": available, "count": len(available)}


def check_connector(name):
    """Check status of a specific connector."""
    active_servers = _load_mcp_json()

    for cat_key, cat_info in CONNECTOR_REGISTRY.items():
        if name in cat_info["connectors"]:
            conn = cat_info["connectors"][name]
            configured = _is_configured(name, conn, active_servers)

            result = {
                "name": name,
                "category": cat_key,
                "description": conn["description"],
                "transport": conn["transport"],
                "status": "connected" if configured else "not_connected",
                "skills_unlocked": conn["skills_unlocked"],
            }

            if conn["transport"] == "http":
                result["url"] = conn.get("url", "")
                result["setup"] = conn.get(
                    "setup_note", "HTTP connector — auto-connects via OAuth when you first use it")
                if conn.get("access"):
                    result["access"] = conn["access"]
            elif conn.get("package_status") == "no-known-npm-package":
                result["package"] = None
                result["package_status"] = conn["package_status"]
                result["setup"] = conn.get("note", "No verified MCP package — use /digital-marketing-pro:add-integration.")
            else:
                result["package"] = conn.get("package", "")
                result["env_vars"] = conn.get("env_vars", [])
                if not configured:
                    env_status = {}
                    for v in conn.get("env_vars", []):
                        env_status[v] = "set" if os.environ.get(v) else "missing"
                    result["env_var_status"] = env_status
                    result["setup"] = (
                        f"Requires npx server. Set environment variables: "
                        f"{', '.join(conn['env_vars'])}. "
                        f"Then add to .mcp.json or use /digital-marketing-pro:add-integration."
                    )

            return result

    return {"error": f"Unknown connector: {name}", "hint": "Run --action list-available to see all connectors"}


def setup_guide(name):
    """Detailed setup guide for a specific connector."""
    active_servers = _load_mcp_json()

    for cat_key, cat_info in CONNECTOR_REGISTRY.items():
        if name in cat_info["connectors"]:
            conn = cat_info["connectors"][name]
            configured = _is_configured(name, conn, active_servers)

            guide = {
                "name": name,
                "category": cat_key,
                "description": conn["description"],
                "already_configured": configured,
                "skills_unlocked": conn["skills_unlocked"],
            }

            if conn["transport"] == "http":
                guide["transport"] = "http"
                guide["url"] = conn.get("url", "")
                if configured:
                    guide["steps"] = [
                        f"This connector is already in .mcp.json as an HTTP connector.",
                        f"When you first use a skill that needs {name}, Claude will prompt you to authorize via OAuth.",
                        f"No API keys or environment variables needed — authentication is handled by the platform.",
                        f"Works in both Claude Code and Cowork.",
                    ]
                else:
                    guide["steps"] = [
                        f"1. Copy the {name} entry from .mcp.json.connectors-reference into your .mcp.json.",
                        f"2. When you first use a skill that needs {name}, Claude will prompt you to authorize via OAuth.",
                        f"No API keys or environment variables needed — authentication is handled by the platform.",
                        f"Works in both Claude Code and Cowork.",
                    ]
                if conn.get("setup_note"):
                    # Official servers with their own auth/hosting rules: the
                    # generic "no keys needed" line would be wrong for them.
                    guide["steps"] = [s for s in guide["steps"]
                                      if not s.startswith("No API keys")]
                    guide["steps"].append(conn["setup_note"])
                if "<" in conn.get("url", ""):
                    guide["steps"] = [s for s in guide["steps"]
                                      if not s.startswith("Works in both")]
                    guide["steps"].append("Replace the <...> part of the URL with your own endpoint first. "
                                          "Cowork can reach it only once it is served at a reachable "
                                          "HTTPS URL; a local stdio run is Claude Code only.")
                if conn.get("access"):
                    guide["access"] = conn["access"]
                for key in ("status", "source"):
                    if conn.get(key):
                        guide[key] = conn[key]
                if configured:
                    guide["status_message"] = (
                        f"{name} is configured. Use any of these skills to activate it: "
                        + ", ".join(f"/dm:{s}" for s in conn["skills_unlocked"])
                    )
            elif conn.get("package_status") == "no-known-npm-package":
                guide["transport"] = "unavailable"
                guide["package"] = None
                guide["package_status"] = conn["package_status"]
                guide["steps"] = [
                    conn.get("note", "No verified MCP package on npm for this connector."),
                    f"Use /digital-marketing-pro:add-integration {name} to wire a custom MCP server you trust.",
                    "npx runs remote code — verify any package on npm before adding it to .mcp.json.",
                ]
            else:
                guide["transport"] = "npx"
                guide["package"] = conn.get("package", "")
                guide["env_vars"] = conn.get("env_vars", [])
                guide["steps"] = [
                    f"1. Obtain API credentials from the {name} platform.",
                    f"2. Set these environment variables: {', '.join(conn['env_vars'])}",
                    f"3. Add the connector to .mcp.json using /digital-marketing-pro:add-integration {name}",
                    f"   Or manually add this to .mcp.json:",
                ]
                guide["mcp_json_entry"] = {
                    name: {
                        "command": "npx",
                        "args": ["-y", conn["package"]],
                        "env": {v: f"${{{v}}}" for v in conn["env_vars"]},
                    }
                }
                guide["notes"] = [
                    "npx connectors require Node.js installed locally.",
                    "Works in Claude Code only (not Cowork).",
                    "API keys are read from environment variables — never stored in plugin files.",
                ]

            return guide

    return {"error": f"Unknown connector: {name}", "hint": "Run --action list-available to see all connectors"}


def _probe_only(name, brand):
    """Credential-safe config-presence check of a single connector — does NOT
    test network reachability or authentication. Returns one of:
    CONNECTED / NOT_CONNECTED / UNKNOWN_CONNECTOR, NEVER the credential value
    itself. Used by /validate-profile.

    Implementation note: this delegates to check_connector(name), which only
    inspects the local .mcp.json and environment variables, then re-shapes the
    response to a credential-safe summary suitable for logging."""
    raw = check_connector(name)
    if isinstance(raw, dict) and "error" in raw and "Unknown connector" in str(raw["error"]):
        return {"connector": name, "status": "UNKNOWN_CONNECTOR", "brand": brand}
    # Map the underlying check result to one of the safe statuses
    status = "OK"
    if isinstance(raw, dict):
        if raw.get("error"):
            err = str(raw["error"]).lower()
            if "401" in err or "unauthor" in err or "invalid" in err and "key" in err:
                status = "UNAUTHENTICATED"
            elif "404" in err or "not found" in err:
                status = "NOT_FOUND"
            elif "429" in err or "rate" in err:
                status = "RATE_LIMITED"
            elif "connection" in err or "timeout" in err or "network" in err or "dns" in err:
                status = "NETWORK_ERROR"
            elif "not configured" in err or "missing" in err.lower():
                status = "NOT_CONFIGURED"
            else:
                status = "ERROR"
        elif raw.get("status") in {"OK", "ok", "ready", "configured", "healthy"}:
            status = "OK"
        elif raw.get("status"):
            status = str(raw["status"]).upper()
    return {
        "connector": name,
        "status": status,
        "brand": brand,
        "credential_value_in_response": False,
        "note": "Probe-only check — credential values are never echoed in output.",
    }


def main():
    parser = argparse.ArgumentParser(description="Connector status and discovery")
    parser.add_argument("--action", required=True,
                        choices=["status", "list-available", "check", "setup-guide"])
    parser.add_argument("--name", help="Connector name (for check/setup-guide)")
    parser.add_argument("name_positional", nargs="?", help="Connector name (positional)")
    # v3.7.6 — validate-profile skill support
    parser.add_argument("--brand", help="Brand slug (context for probes; never written to output unless --probe-only)")
    parser.add_argument("--connectors", help="Comma-separated connector subset (with --probe-only)")
    parser.add_argument("--probe-only", action="store_true",
                        help="Credential-safe config-presence check for /validate-profile — does not test network reachability. Returns status (CONNECTED / NOT_CONNECTED / UNKNOWN_CONNECTOR) per connector without echoing credential values.")
    parser.add_argument("--no-secrets", action="store_true",
                        help="Walk the response object and redact any key that looks like a credential before printing. Use with any --action when the output may be logged or shared.")
    args = parser.parse_args()

    name = args.name or args.name_positional

    # v3.7.6 — credential-safe multi-connector probe path used by /validate-profile
    if args.probe_only:
        if args.connectors:
            connector_names = [c.strip() for c in args.connectors.split(",") if c.strip()]
        elif name:
            connector_names = [name]
        else:
            connector_names = []
        if not connector_names:
            result = {"error": "--probe-only requires --connectors <comma-list> or --name <single>"}
        else:
            probes = [_probe_only(n, args.brand) for n in connector_names]
            result = {"probe_mode": True, "brand": args.brand, "results": probes,
                      "summary": {s: sum(1 for p in probes if p.get("status") == s)
                                  for s in {p.get("status") for p in probes}}}
    elif args.action == "status":
        result = status_dashboard()
    elif args.action == "list-available":
        result = list_available()
    elif args.action == "check":
        if not name:
            result = {"error": "Provide connector name: --name <name>"}
        else:
            result = check_connector(name)
    elif args.action == "setup-guide":
        if not name:
            result = {"error": "Provide connector name: --name <name>"}
        else:
            result = setup_guide(name)
    else:
        result = {"error": f"Unknown action: {args.action}"}

    if args.no_secrets:
        result = _redact_secrets(result)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
