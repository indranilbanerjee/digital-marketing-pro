#!/usr/bin/env python3
"""
connector_executor.py
=====================
Stdlib HTTP executor that fires the request manifests produced by
connector_resolver.resolve_action(). Bridges the gap between
"manifest_ready" (the orchestrator could execute) and "actually executed".

Design constraints:
  * stdlib only (urllib.request) — no requests / httpx dependency
  * Write operations need --execute AND --approval-id. `--execute` without an id
    builds the exact request, writes a PENDING record holding its sha256 and a
    script-rendered preview, and exits 2. After the user types yes, the skill
    runs `approval-manager.py --action approve`. The fire step rebuilds the
    request and must match the hash; the record must be approved, inside its
    window (30 min to review, 15 min to fire) and unused. It is consumed once
    the request is sent (any HTTP status), released if nothing was sent.
    Batches get one record with per-item hashes. --confirm is ignored.
  * What this proves: the approval step ran for this exact request, once, in
    its window. It cannot prove who typed yes (the model runs every command),
    and MCP-server writes are outside it. Keep this script's --execute command
    out of your host's command allowlist so the host asks you each time.
  * Every execution is logged to execution-tracker (audit trail)
  * Read operations are safe to auto-execute when --execute is passed
  * Auth handled inline: Bearer, custom-header (Klaviyo/Brevo), Basic, query-param
  * OAuth-only connectors (Google Ads, Meta, LinkedIn, TikTok, Gmail, GCal, GSC,
    Twitter OAuth 1.0a) return mode="auth_required_oauth" — those need the MCP
    path because Python cannot run an OAuth flow from a script
  * Per-endpoint success codes are honored (Slack 200+body.ok, SendGrid 202,
    HubSpot POST 201, Klaviyo 200, etc.)
  * Timeouts default to 30 s; configurable
  * Secrets are redacted from all returned output via redact_secrets().

API:
    execute_manifest(http_request, env=None, data=None, timeout=30) -> dict
    execute_action(action_id, brand, *, execute=True, confirm=False,
                   data=None, timeout=30, **kwargs) -> dict
    list_executable_connectors() -> list[str]
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common  # noqa: E402
from connector_resolver import ACTION_SPECS, resolve_action  # type: ignore  # noqa: E402

APPROVAL_BLOCKED_EXIT = 2


# ─────────────────────────────────────────────────────────────────────────────
# Per-connector execute schema:
#   * connector name
#   * which env var holds the credential
#   * which auth pattern handler to use
#   * expected success status code(s)
#   * post-response logic check (e.g. Slack body.ok)
#   * which write actions are allowed (None = read-only)
#
# Verified against current vendor docs (May 2026 research pass) — see
# CHANGELOG v3.7.11 for source citations per endpoint.
# ─────────────────────────────────────────────────────────────────────────────

EXECUTE_PROFILES = {
    "slack": {
        "env_var": "SLACK_BOT_TOKEN",
        "auth": "bearer",
        "auth_header": "Authorization",
        "auth_format": "Bearer {credential}",
        "success_codes": [200],
        "post_check": "slack_body_ok",   # MUST verify response.body.ok = True
        "notes": "Bot token (xoxb-...). chat:write scope required.",
    },
    "hubspot": {
        "env_var": "HUBSPOT_PRIVATE_APP_TOKEN",
        "auth": "bearer",
        "auth_header": "Authorization",
        "auth_format": "Bearer {credential}",
        "success_codes": [200, 201],
        "notes": "Private App token. Required scopes vary per endpoint "
                 "(automation for /flows; marketing-email for /campaigns).",
    },
    "klaviyo": {
        "env_var": "KLAVIYO_PRIVATE_KEY",
        "auth": "custom_header",
        "auth_header": "Authorization",
        "auth_format": "Klaviyo-API-Key {credential}",
        "success_codes": [200, 201, 202],
        "notes": "Private API key. Revision header bumped to 2026-04-15. "
                 "PATCH ops require Content-Type: application/vnd.api+json.",
    },
    "sendgrid": {
        "env_var": "SENDGRID_API_KEY",
        "auth": "bearer",
        "auth_header": "Authorization",
        "auth_format": "Bearer {credential}",
        "success_codes": [200, 202],   # mail/send returns 202
        "notes": "API key starts with SG. — mail/send is async (202 + empty body).",
    },
    "brevo": {
        "env_var": "BREVO_API_KEY",
        "auth": "custom_header",
        "auth_header": "api-key",
        "auth_format": "{credential}",
        "success_codes": [200, 201],
        "notes": "Custom lowercase 'api-key' header, NOT Authorization Bearer.",
    },
    "customer-io": {
        "env_var": "CUSTOMERIO_APP_API_KEY",
        "auth": "bearer",
        "auth_header": "Authorization",
        "auth_format": "Bearer {credential}",
        "success_codes": [200, 201],
        "notes": "App API key, NOT Site/Track key. The /v1/send/email endpoint "
                 "rejects Site/Track keys.",
    },
    "mailchimp": {
        "env_var": "MAILCHIMP_API_KEY",
        "auth": "basic",
        "auth_header": "Authorization",
        "auth_format": "anystring:{credential}",   # basic-auth user:pass form
        "success_codes": [200],
        "notes": "Basic auth with arbitrary username and api-key as password. "
                 "Data-center is derived from the trailing -dcXX suffix in the key.",
        "extra_setup": "datacenter_suffix",
    },
    "ahrefs": {
        "env_var": "AHREFS_API_KEY",
        "auth": "bearer",
        "auth_header": "Authorization",
        "auth_format": "Bearer {credential}",
        "success_codes": [200],
        "notes": "Bearer token in Authorization header (not query param). "
                 "site-explorer endpoint is /metrics (not /overview).",
    },

    # OAuth-only connectors — execute path returns auth_required_oauth
    "google-ads":         {"oauth_only": True, "reason": "Google Ads requires OAuth2 + developer-token; use MCP path."},
    "meta-marketing":     {"oauth_only": True, "reason": "Meta Marketing API requires long-lived access token from FB Login flow; use MCP path."},
    "linkedin-marketing": {"oauth_only": True, "reason": "LinkedIn Marketing API requires OAuth2 with marketing scopes; use MCP path."},
    "linkedin-publishing":{"oauth_only": True, "reason": "LinkedIn Publishing API requires OAuth2; use MCP path."},
    "tiktok-ads":         {"oauth_only": True, "reason": "TikTok Business API requires OAuth2 advertiser-grant; use MCP path."},
    "twitter-x":          {"oauth_only": True, "reason": "Twitter/X Ads + posting requires OAuth 1.0a HMAC signing; use MCP path."},
    "gmail":              {"oauth_only": True, "reason": "Gmail API requires OAuth2 with gmail.send scope; use MCP path."},
    "google-calendar":    {"oauth_only": True, "reason": "Google Calendar API requires OAuth2; use MCP path."},
    "google-analytics":   {"oauth_only": True, "reason": "GA4 Admin API requires OAuth2 with analytics scopes; use MCP path."},
    "google-search-console": {"oauth_only": True, "reason": "Google Search Console API requires OAuth2 with webmasters scope; use MCP path."},
    "meta-graph":         {"oauth_only": True, "reason": "Meta Graph organic posting requires page-scoped OAuth token; use MCP path."},
    "salesforce":         {"oauth_only": True, "reason": "Salesforce REST API requires OAuth2 + instance URL; use MCP path."},
    "pipedrive":          {"oauth_only": True, "reason": "Pipedrive can use API token (simpler) — execute support TODO."},
    "zoho-crm":           {"oauth_only": True, "reason": "Zoho CRM requires OAuth refresh flow; use MCP path."},
    "buffer":             {"oauth_only": True, "reason": "Buffer requires OAuth2 access token; use MCP path."},
    "hootsuite":          {"oauth_only": True, "reason": "Hootsuite requires OAuth2; use MCP path."},
    "cision":             {"oauth_only": True, "reason": "Cision API access requires enterprise account + OAuth; use MCP path."},
    "muckrack":           {"oauth_only": True, "reason": "Muck Rack API token works but execute support TODO."},
    "amplitude":          {"oauth_only": True, "reason": "Amplitude HTTP API uses API key + secret — execute support TODO."},
    "similarweb":         {"oauth_only": True, "reason": "Similarweb API uses API key in query — execute support TODO."},
    "semrush":            {"oauth_only": True, "reason": "SEMrush uses API key in query — execute support TODO."},
    "moz":                {"oauth_only": True, "reason": "Moz requires HMAC-SHA1 signed requests; use MCP path."},
    "intercom":           {"oauth_only": True, "reason": "Intercom uses Bearer token — execute support TODO."},
    "canva":              {"oauth_only": True, "reason": "Canva Connect API requires OAuth2; use MCP path."},
    "figma":              {"oauth_only": True, "reason": "Figma requires personal access token; execute support TODO."},
    # Official ad-platform MCP servers — reachable only as MCP tools (checked 2026-10-04).
    "meta-ads":           {"oauth_only": True, "reason": "Meta Ads AI Connectors is a hosted MCP server with business login; use MCP path behind the typed approval gate."},
    "google-ads-mcp":     {"oauth_only": True, "reason": "Google Ads MCP is a read-only MCP server (GAQL search); use MCP path — it cannot execute writes at all."},
    "amazon-ads-mcp":     {"oauth_only": True, "reason": "Amazon Ads MCP Server needs partner API credentials via its MCP auth; use MCP path behind the typed approval gate."},
}


# ─────────────────────────────────────────────────────────────────────────────
# Template substitution
# ─────────────────────────────────────────────────────────────────────────────

_VAR_PATTERN = re.compile(r"\{([A-Z_][A-Z0-9_]*)\}")
_DATA_PATTERN = re.compile(r"\{([a-z][a-z0-9_.]*)\}")


def _scoped_env(env: dict, connector: str | None) -> dict:
    """Only the connector's own variables may be substituted into a request.
    Each executable connector's keys share its credential's vendor prefix
    (SLACK_, HUBSPOT_, MAILCHIMP_, ...); nothing else in the environment can
    leak into a URL, header or body through a {PLACEHOLDER}."""
    profile = EXECUTE_PROFILES.get(connector or "", {})
    env_var = profile.get("env_var")
    if not env_var:
        return {}
    prefix = env_var.split("_", 1)[0] + "_"
    return {k: v for k, v in env.items() if k.startswith(prefix)}


def _substitute_env(value: Any, env: dict) -> Any:
    """Replace {ENV_VAR_NAME} placeholders with env values. Recursive.
    Callers pass _scoped_env(...) so only the connector's own keys resolve."""
    if isinstance(value, str):
        def replace(match):
            var = match.group(1)
            return env.get(var, match.group(0))
        return _VAR_PATTERN.sub(replace, value)
    if isinstance(value, dict):
        return {k: _substitute_env(v, env) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute_env(x, env) for x in value]
    return value


def _substitute_data(value: Any, data: dict) -> Any:
    """Replace {data.path.to.field} placeholders. Recursive."""
    if isinstance(value, str):
        def replace(match):
            path = match.group(1).split(".")
            cur = data
            for key in path:
                if isinstance(cur, dict) and key in cur:
                    cur = cur[key]
                else:
                    return match.group(0)
            return str(cur) if not isinstance(cur, (dict, list)) else json.dumps(cur)
        return _DATA_PATTERN.sub(replace, value)
    if isinstance(value, dict):
        return {k: _substitute_data(v, data) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute_data(x, data) for x in value]
    return value


def _find_unresolved_placeholders(obj) -> list[str]:
    """Return any {placeholder} strings that survived substitution."""
    found = []
    if isinstance(obj, str):
        found.extend(_VAR_PATTERN.findall(obj))
        found.extend(_DATA_PATTERN.findall(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            found.extend(_find_unresolved_placeholders(v))
    elif isinstance(obj, list):
        for x in obj:
            found.extend(_find_unresolved_placeholders(x))
    return found


# ─────────────────────────────────────────────────────────────────────────────
# Auth handlers
# ─────────────────────────────────────────────────────────────────────────────

def _build_auth_header(profile: dict, credential: str, headers: dict) -> dict:
    """Build/inject the auth header per the connector's profile."""
    headers = dict(headers or {})
    auth_type = profile["auth"]
    header_name = profile["auth_header"]
    format_template = profile["auth_format"]

    if auth_type == "bearer":
        headers[header_name] = format_template.format(credential=credential)
    elif auth_type == "custom_header":
        headers[header_name] = format_template.format(credential=credential)
    elif auth_type == "basic":
        import base64
        userpass = format_template.format(credential=credential)
        encoded = base64.b64encode(userpass.encode("utf-8")).decode("ascii")
        headers[header_name] = f"Basic {encoded}"
    else:
        raise ValueError(f"unknown auth type: {auth_type}")
    return headers


def _mailchimp_dc_url(url: str, credential: str) -> str:
    """Mailchimp URL has a {dc} placeholder derived from key suffix.
    Key format: '<hex>-us6' -> dc='us6'.
    """
    if "{dc}" not in url and "{MAILCHIMP_DC}" not in url:
        return url
    if "-" not in credential:
        return url  # malformed key; let the call fail
    dc = credential.rsplit("-", 1)[-1]
    return url.replace("{dc}", dc).replace("{MAILCHIMP_DC}", dc)


# ─────────────────────────────────────────────────────────────────────────────
# Core executor
# ─────────────────────────────────────────────────────────────────────────────

def execute_manifest(http_request: dict, env: dict | None = None,
                     data: dict | None = None, timeout: int = 30,
                     connector: str | None = None) -> dict:
    """Execute a single HTTP request manifest produced by connector_resolver.
    Returns a structured result dict — never raises on HTTP errors."""
    built = build_request(http_request, env=env, data=data, connector=connector)
    if built.get("status") != "built":
        return built
    return send_request(built, timeout=timeout)


def build_request(http_request: dict, env: dict | None = None,
                  data: dict | None = None, connector: str | None = None) -> dict:
    """Resolve a manifest into the exact request that would be sent (no network).
    The approval hash and the user-facing preview are computed from this, and
    send_request() sends exactly this, so what was approved is what fires."""
    if env is None:
        env = dict(os.environ)
    if data is None:
        data = {}
    if not http_request or not isinstance(http_request, dict):
        return {"status": "error", "error": "http_request is empty or not a dict"}

    # Substitute placeholders — only the connector's own variables (Hermes review)
    spec = deepcopy(http_request)
    spec = _substitute_env(spec, _scoped_env(env, connector))
    if data:
        spec = _substitute_data(spec, data)

    method = (spec.get("method") or "GET").upper()
    url = spec.get("url") or ""
    headers = spec.get("headers", {}) or {}
    params = spec.get("params", {}) or {}
    body_template = spec.get("body_template")

    # Connector-specific URL post-processing
    if connector == "mailchimp" and env.get("MAILCHIMP_API_KEY"):
        url = _mailchimp_dc_url(url, env["MAILCHIMP_API_KEY"])

    # Check for unresolved placeholders (missing env vars / data)
    unresolved = _find_unresolved_placeholders({"url": url, "headers": headers,
                                                "params": params, "body": body_template})
    if unresolved:
        return {
            "status": "missing_credential",
            "error": f"Unresolved placeholders after substitution: {sorted(set(unresolved))}",
            "hint": "Set the missing env vars (or pass --data for body fields) "
                    "and retry. Omit --execute to see the substituted request without firing.",
            "method": method,
            "url": url,
            "elapsed_ms": 0,
        }

    # Build query string
    if params:
        qs = urllib.parse.urlencode([(k, str(v)) for k, v in params.items()])
        url = url + ("&" if "?" in url else "?") + qs

    # Build body
    body_bytes = None
    if body_template is not None and method in ("POST", "PUT", "PATCH", "DELETE"):
        ct = headers.get("Content-Type", "").lower()
        if "form-urlencoded" in ct:
            body_bytes = urllib.parse.urlencode(
                [(k, str(v)) for k, v in body_template.items()]
            ).encode("utf-8")
        else:
            body_bytes = json.dumps(body_template).encode("utf-8")

    return {"status": "built", "method": method, "url": url, "headers": headers,
            "body_bytes": body_bytes, "body": body_template}


def send_request(built: dict, timeout: int = 30) -> dict:
    """Send a request produced by build_request(). Never raises on HTTP errors.
    A result without 'http_status' means nothing reached the platform."""
    method, url, headers, body_bytes = built["method"], built["url"], built["headers"], built["body_bytes"]
    started = time.time()
    req = urllib.request.Request(url, data=body_bytes, method=method)
    for h, v in headers.items():
        req.add_header(h, str(v))

    # Fire
    response = None
    try:
        response = urllib.request.urlopen(req, timeout=timeout)
        status_code = response.status
        raw = response.read()
    except urllib.error.HTTPError as e:
        status_code = e.code
        try:
            raw = e.read()
        except Exception:
            raw = b""
    except urllib.error.URLError as e:
        return {
            "status": "network_error",
            "error": f"URLError: {e.reason}",
            "method": method,
            "url": url,
            "elapsed_ms": int((time.time() - started) * 1000),
        }
    except Exception as e:
        return {
            "status": "error",
            "error": f"{type(e).__name__}: {e}",
            "method": method,
            "url": url,
            "elapsed_ms": int((time.time() - started) * 1000),
        }
    finally:
        if response is not None:
            try:
                response.close()
            except Exception:
                pass

    # Parse response body
    parsed_body: Any = None
    try:
        parsed_body = json.loads(raw.decode("utf-8")) if raw else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        parsed_body = raw.decode("utf-8", errors="replace")[:1000] if raw else None

    elapsed_ms = int((time.time() - started) * 1000)

    return {
        "status": "executed",
        "http_status": status_code,
        "method": method,
        "url": url,
        "response_body": parsed_body,
        "elapsed_ms": elapsed_ms,
        "request_summary": {
            "method": method,
            "url_host": urllib.parse.urlparse(url).netloc,
            "auth_header_present": any(h.lower() in ("authorization", "api-key")
                                       for h in headers.keys()),
            "body_bytes": len(body_bytes) if body_bytes else 0,
        },
    }


def _check_success(result: dict, profile: dict) -> dict:
    """Apply per-connector success-code + post-check logic."""
    if result.get("status") != "executed":
        return result
    success_codes = profile.get("success_codes", [200, 201, 202])
    http_status = result.get("http_status")

    is_success = http_status in success_codes

    # Slack returns 200 even on logical failure; verify body.ok
    if profile.get("post_check") == "slack_body_ok":
        body = result.get("response_body")
        if isinstance(body, dict):
            slack_ok = bool(body.get("ok"))
            result["slack_ok_check"] = slack_ok
            if is_success and not slack_ok:
                is_success = False
                result["slack_error"] = body.get("error")

    result["success"] = is_success
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Secret redaction (applied to ALL returned output)
# ─────────────────────────────────────────────────────────────────────────────

_SECRET_QS = re.compile(
    r"(?i)\b(access_token|refresh_token|token|api[_-]?key|apikey|key|secret|"
    r"password|developer-token|auth)=[^&\s\"']+")
_BEARER = re.compile(r"(?i)(Bearer|Basic)\s+[A-Za-z0-9._\-+/=]+")


def _redact_str(s: str) -> str:
    s = _SECRET_QS.sub(lambda m: f"{m.group(1)}=REDACTED", s)
    s = _BEARER.sub(lambda m: f"{m.group(1)} REDACTED", s)
    return s


def redact_secrets(obj):
    """Recursively redact secret-looking tokens from executor output so a
    partially-substituted URL / header (e.g. the missing_credential branch that
    echoes the substituted request) never leaks a live credential."""
    if isinstance(obj, str):
        return _redact_str(obj)
    if isinstance(obj, dict):
        return {k: redact_secrets(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_secrets(v) for v in obj]
    return obj


# ─────────────────────────────────────────────────────────────────────────────
# Action-level executor (resolves THEN executes)
# ─────────────────────────────────────────────────────────────────────────────

def execute_action(action_id: str, brand: str, *,
                   execute: bool = True, confirm: bool = False,
                   data: dict | None = None, timeout: int = 30,
                   log_to_tracker: bool = True, env: dict | None = None,
                   approval_id: str | None = None,
                   **kwargs) -> dict:
    """Resolve an action and either execute it or return the manifest.

    Args:
      action_id:     one of ACTION_SPECS keys
      brand:         brand slug
      execute:       if False, returns the resolver response unchanged (no execution)
      confirm:       ignored (kept so old calls still parse); writes need approval_id
      approval_id:   for operation=='write': an approved, unexpired, unused record
                     whose payload hash matches this exact request. Without it a
                     write prepares a pending record and returns its preview.
      data:          domain data for body_template substitution (e.g.
                     {"plan": {"campaign_name": "X"}})
      timeout:       HTTP timeout seconds
      log_to_tracker: append execution to execution-tracker.py audit trail
      env:           env-var dict; defaults to os.environ
      **kwargs:      passed through to resolve_action
    """
    if env is None:
        env = dict(os.environ)

    # Step 1: resolve — with no side effects (local actions run only under execute)
    resolved = resolve_action(action_id, brand, run_local=False, **kwargs)
    resolved_mode = resolved.get("mode")

    if not execute:
        return resolved

    if resolved_mode == "local_ready":
        # Local-only action (writes a local config, sends nothing): run it now.
        local = resolve_action(action_id, brand, run_local=True, **kwargs)
        local["execute_attempted"] = True
        return local

    if resolved_mode == "stub_unconfigured":
        # No connector configured — execute mode can't help
        resolved["execute_attempted"] = False
        resolved["execute_blocked_reason"] = "no connector configured; nothing to execute"
        return resolved

    if resolved_mode != "manifest_ready":
        resolved["execute_attempted"] = False
        resolved["execute_blocked_reason"] = f"unknown mode: {resolved_mode}"
        return resolved

    # Step 2: structural checks (nothing is sent by any of these)
    spec = ACTION_SPECS.get(action_id, {})
    operation = spec.get("operation", "read")
    chosen = resolved.get("chosen_connector")
    profile = EXECUTE_PROFILES.get(chosen, {})
    if profile.get("oauth_only"):
        resolved["execute_attempted"] = False
        resolved["execute_blocked_reason"] = profile.get("reason", "OAuth-only connector")
        resolved["alternative"] = (
            f"Execute via the {chosen} MCP tool, behind the skill's typed `yes` and your host's "
            f"permission prompt. MCP writes are outside this executor's approval-record check. "
            f"The manifest above is the exact request shape the MCP will send."
        )
        return resolved
    if not profile:
        resolved["execute_attempted"] = False
        resolved["execute_blocked_reason"] = (
            f"no execute profile defined for connector '{chosen}'; "
            f"action can only be executed via the MCP path."
        )
        return resolved

    env_var = profile.get("env_var")
    credential = env.get(env_var) if env_var else None
    if not credential:
        resolved["execute_attempted"] = False
        resolved["execute_blocked_reason"] = f"env var {env_var} is not set"
        resolved["setup_hint_credential"] = (
            f"Set {env_var} with the {chosen} credential and retry. "
            f"Notes: {profile.get('notes', '')}"
        )
        return resolved

    # Step 3: build the exact request (auth injected, data substituted, no network)
    built = _build_for_action(resolved, profile, credential, env, data, chosen)
    if built.get("status") != "built":
        resolved["execute_attempted"] = False
        resolved["execution"] = built
        return resolved
    description = request_description(built, brand=brand, connector=chosen, action=action_id,
                                      credential_env=env_var, credential=credential, profile=profile)
    payload_hash = _common.action_payload_hash(description)

    # Step 4: the approval-record gate for writes
    approval_path = approval_record = approval_item = None
    if operation == "write":
        if not approval_id:
            new_id, _ = _common.write_approval_record(brand, "exec", {
                "kind": "single", "type": "execute-action", "brand": brand, "platform": chosen,
                "action": action_id, "credential_env": env_var, "payload_hash": payload_hash,
                "preview": description, "content_summary": f"{action_id} via {chosen}",
            })
            resolved.update({
                "execute_attempted": False,
                "approval_required": True,
                "approval_id": new_id,
                "approval_payload_hash": payload_hash,
                "preview": description,
                "next_steps": _next_steps(brand, new_id),
            })
            return resolved
        approval_path, approval_record, approval_item, why = _common.load_approval_for_execution(
            brand, approval_id, payload_hash, connector=chosen, action=action_id)
        if why:
            resolved.update({
                "execute_attempted": False,
                "approval_required": True,
                "execute_blocked_reason": why,
                "approval_payload_hash": payload_hash,
                "preview": description,
                "next_steps": ["Re-run this command WITHOUT --approval-id to prepare a fresh record for "
                               "this exact request, show its preview to the user, and continue only "
                               "after they type yes."],
            })
            return resolved
        _common.mark_approval_in_flight(approval_path, approval_record, approval_item)

    # Step 5: send exactly what was built (and, for writes, approved)
    exec_result = _check_success(send_request(built, timeout=timeout), profile)
    resolved["execute_attempted"] = True
    resolved["execution"] = exec_result
    if approval_path is not None:
        sent = exec_result.get("http_status") is not None
        _common.settle_approval(approval_path, approval_record, approval_item, sent=sent,
                                success=bool(exec_result.get("success")), request_hash=payload_hash,
                                summary=exec_result.get("http_status") or exec_result.get("error"))
        resolved["approval"] = {"approval_id": approval_id, "payload_hash": payload_hash,
                                "consumed": sent, "status": approval_record.get("status")}

    # Step 6: audit log, with a full copy of the approval record used
    if log_to_tracker:
        _log_execution(action_id, brand, chosen, exec_result, operation,
                       payload_hash=payload_hash, approval_record=approval_record)

    return resolved


def _build_for_action(resolved, profile, credential, env, data, chosen) -> dict:
    manifest = resolved.get("manifest", {})
    http_request = deepcopy(manifest.get("http_request") or {})
    http_request["headers"] = _build_auth_header(profile, credential, http_request.get("headers", {}))
    return build_request(http_request, env=env, data=data, connector=chosen)


def request_description(built: dict, *, brand: str, connector: str, action: str, credential_env: str,
                        credential: str, profile: dict) -> dict:
    """The fully resolved request, as hashed and as shown to the user: the
    credential's NAME is included, its value never is."""
    auth_header = (profile.get("auth_header") or "").lower()

    def scrub(value):
        if isinstance(value, str):
            return value.replace(credential, "<" + credential_env + ">") if credential else value
        if isinstance(value, dict):
            return {k: scrub(v) for k, v in value.items()}
        if isinstance(value, list):
            return [scrub(v) for v in value]
        return value

    headers = {k: scrub(str(v)) for k, v in (built.get("headers") or {}).items()
               if k.lower() != auth_header and k.lower() not in ("authorization", "api-key")}
    return {
        "brand": brand,
        "connector": connector,
        "action": action,
        "credential_env": credential_env,
        "method": built.get("method"),
        "url": scrub(built.get("url")),
        "headers": headers,
        "body": scrub(built.get("body")),
    }


def _next_steps(brand: str, approval_id: str) -> list:
    return [
        "Show the user the `preview` above exactly as printed (it is the request that will be sent).",
        "Only after the user types yes: python \"${CLAUDE_PLUGIN_ROOT}/scripts/approval-manager.py\" "
        f"--brand {brand} --action approve --id {approval_id}",
        f"Then re-run this same command with --approval-id {approval_id} (within "
        f"{_common.APPROVAL_FIRE_MINUTES} minutes of approving). The record is single-use.",
    ]


def prepare_batch(brand: str, items: list, *, env: dict | None = None, timeout: int = 30) -> dict:
    """One approval record for an ordered batch of writes, with an itemised
    preview built from each fully resolved request. Each item is fired later
    with the same --approval-id and is consumed on its own; a changed item fails
    alone."""
    if env is None:
        env = dict(os.environ)
    prepared, problems = [], []
    for i, item in enumerate(items):
        action_id = item.get("action")
        kwargs = {k: v for k, v in item.items() if k not in ("action", "data") and v is not None}
        resolved = resolve_action(action_id, brand, run_local=False, **kwargs)
        chosen = resolved.get("chosen_connector")
        profile = EXECUTE_PROFILES.get(chosen, {})
        if resolved.get("mode") != "manifest_ready" or profile.get("oauth_only") or not profile:
            problems.append({"index": i, "action": action_id, "reason": resolved.get("mode") or "not executable here"})
            continue
        credential = env.get(profile.get("env_var") or "")
        if not credential:
            problems.append({"index": i, "action": action_id, "reason": f"env var {profile.get('env_var')} is not set"})
            continue
        built = _build_for_action(resolved, profile, credential, env, item.get("data"), chosen)
        if built.get("status") != "built":
            problems.append({"index": i, "action": action_id, "reason": built.get("error")})
            continue
        description = request_description(built, brand=brand, connector=chosen, action=action_id,
                                          credential_env=profile.get("env_var"), credential=credential,
                                          profile=profile)
        prepared.append({"index": i, "action": action_id, "connector": chosen,
                         "payload_hash": _common.action_payload_hash(description), "preview": description})
    if problems:
        return {"status": "error", "error": "some batch items cannot be prepared; nothing was recorded",
                "problems": problems}
    approval_id, _ = _common.write_approval_record(brand, "batch", {
        "kind": "batch", "type": "execute-action", "brand": brand, "items": prepared,
        "content_summary": f"batch of {len(prepared)} writes",
    })
    return {"status": "prepared", "approval_id": approval_id, "items": prepared,
            "approval_required": True, "next_steps": _next_steps(brand, approval_id)}


def _log_execution(action_id: str, brand: str, connector: str,
                   exec_result: dict, operation: str, *, payload_hash: str | None = None,
                   approval_record: dict | None = None):
    """Append an entry to brands/{brand}/executions/. Writes carry a full copy of
    the approval record that let them fire, so a forged record is visible later."""
    brand_dir = _common.brand_dir(brand)
    if not brand_dir.exists():
        return  # don't fail just because brand doesn't exist
    executions_dir = brand_dir / "executions"
    executions_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    exec_id = f"exec-{connector}-{action_id}-{ts}"
    success = exec_result.get("success") or (exec_result.get("http_status") in (200, 201, 202)
                                             and exec_result.get("status") == "executed")
    entry = {
        "execution_id": exec_id,
        "action": action_id,
        "platform": connector,
        "operation": operation,
        "action_type": f"{action_id}-via-{connector}",
        "result": "success" if success else "failure",
        "http_status": exec_result.get("http_status"),
        "elapsed_ms": exec_result.get("elapsed_ms"),
        "executed_at": datetime.now().isoformat(),
        "error": exec_result.get("error") or exec_result.get("slack_error"),
        "payload_hash": payload_hash,
        "approval_record": deepcopy(approval_record) if approval_record else None,
    }
    try:
        (executions_dir / f"{exec_id}.json").write_text(json.dumps(entry, indent=2, default=str), encoding="utf-8")
    except Exception:
        pass  # logging never breaks the call


def list_executable_connectors() -> list[str]:
    """Names of connectors with execute profiles (excludes oauth_only)."""
    return sorted(name for name, p in EXECUTE_PROFILES.items()
                  if not p.get("oauth_only"))


def list_oauth_only_connectors() -> list[str]:
    """Names of connectors that require the MCP path."""
    return sorted(name for name, p in EXECUTE_PROFILES.items()
                  if p.get("oauth_only"))


if __name__ == "__main__":
    import argparse
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description=__doc__)
    # --action / --brand are NOT required: the --list-* flags must be reachable
    # without them (M1). Requiredness is enforced below only for execution.
    parser.add_argument("--action", help="action_id to execute")
    parser.add_argument("--brand", type=_common.path_component)
    parser.add_argument("--execute", action="store_true",
                        help="actually fire the request (default: dry-run / resolve only)")
    parser.add_argument("--confirm", action="store_true",
                        help="Ignored. Writes need --approval-id (see --help epilog / execute-action.md).")
    parser.add_argument("--approval-id",
                        help="Approved, unexpired, unused approval record for this exact write "
                             "(omit it once to prepare one and get its preview)")
    parser.add_argument("--prepare-batch", metavar="PLAN_JSON",
                        help="Prepare ONE approval record for a list of writes: "
                             '[{"action": "...", "data": {...}, "channel": "..."}, ...]')
    parser.add_argument("--data", help="JSON dict for body_template substitution")
    parser.add_argument("--channel", help="channel (for inventory/automations/cadence)")
    parser.add_argument("--automation-id", help="for enable-automation")
    parser.add_argument("--plan", help="path to plan JSON")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--list-executable", action="store_true",
                        help="List connectors with execute profiles")
    parser.add_argument("--list-oauth-only", action="store_true",
                        help="List connectors that require the MCP path")
    args = parser.parse_args()

    if args.list_executable:
        print(json.dumps({"executable_connectors": list_executable_connectors()}, indent=2))
        sys.exit(0)
    if args.list_oauth_only:
        print(json.dumps({"oauth_only_connectors": list_oauth_only_connectors()}, indent=2))
        sys.exit(0)

    if args.prepare_batch:
        if not args.brand:
            print(json.dumps({"error": "--brand is required with --prepare-batch"}, indent=2))
            sys.exit(1)
        try:
            items = json.loads(Path(args.prepare_batch).read_text(encoding="utf-8"))
            assert isinstance(items, list) and items
        except Exception as exc:
            print(json.dumps({"error": f"--prepare-batch needs a JSON list of items: {exc}"}, indent=2))
            sys.exit(1)
        batch = redact_secrets(prepare_batch(args.brand, items, timeout=args.timeout))
        print(json.dumps(batch, indent=2, default=str))
        sys.exit(APPROVAL_BLOCKED_EXIT if batch.get("status") == "prepared" else 1)

    # For an actual execution, --action and --brand are required.
    if not args.action or not args.brand:
        print(json.dumps({"error": "--action and --brand are required (unless using "
                                   "--list-executable / --list-oauth-only)"}, indent=2))
        sys.exit(1)

    # Guard the JSON parse so a malformed --data reports cleanly instead of
    # crashing with an uncaught traceback (M1).
    try:
        data = json.loads(args.data) if args.data else None
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": f"invalid JSON in --data: {exc}"}, indent=2))
        sys.exit(1)

    extra_kwargs = {}
    if args.channel:
        extra_kwargs["channel"] = args.channel
    if args.automation_id:
        extra_kwargs["automation_id"] = args.automation_id
    if args.plan:
        extra_kwargs["plan_path"] = args.plan

    result = execute_action(args.action, args.brand,
                            execute=args.execute, confirm=args.confirm,
                            data=data, timeout=args.timeout,
                            approval_id=args.approval_id, **extra_kwargs)
    # Redact any secrets that may have leaked into the output (e.g. a
    # substituted URL echoed by the missing_credential branch), then exit
    # non-zero when the execution reported failure (M1) so $? is trustworthy.
    result = redact_secrets(result)
    print(json.dumps(result, indent=2, default=str))
    if isinstance(result, dict) and result.get("approval_required") and not result.get("execute_attempted"):
        sys.exit(APPROVAL_BLOCKED_EXIT)  # 2: nothing fired; follow next_steps
    _success = True
    if isinstance(result, dict):
        if "error" in result:
            _success = False
        elif result.get("execution", {}).get("success") is False:
            _success = False
        elif result.get("success") is False:
            _success = False
    sys.exit(0 if _success else 1)
