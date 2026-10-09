#!/usr/bin/env python3
"""
_common.py
==========
Shared helpers for every Digital Marketing Pro Python script. Stdlib only.

Why this exists: the tracker/checkpoint/state scripts each carried private
copies of workspace resolution, slugification, JSON persistence, the
brand-not-found message, and stdout encoding guards - and the copies drifted.
Four different workspace resolvers and four different slugifiers produced
different directories for the same brand (the "split-brain" storage bug), and
39 scripts printed their result with a trailer that swallowed the error exit
code. This module is now the single source of truth. Scripts hard-require it:
`import _common` works because sys.path[0] is scripts/ when a script is invoked
as `python scripts/x.py`; each script also inserts its own directory into
sys.path defensively.

Path policy (DMP canon):
  * workspace_root() - $CLAUDE_MARKETING_HOME if set (used by tests); else
    $CLAUDE_PLUGIN_DATA/digital-marketing-pro if $CLAUDE_PLUGIN_DATA is set AND
    that directory exists; else ~/.claude-marketing.
  * brands_root()    - workspace_root()/brands   (the `brands/` segment is
    canonical for DMP).
  * brand_dir(brand) - backward compatible: if a legacy directory named with
    the RAW brand string already exists under brands_root(), keep using it;
    otherwise use the canonical slug directory (slugify_brand()).
  * get_brand_dir(slug) - (dir, error) tuple with the standard not-found
    message, mirroring the ~24 private copies it replaces.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Constants ───────────────────────────────────────────────────────

BRAND_NOT_FOUND = (
    "Brand '{slug}' not found. Run /digital-marketing-pro:brand-setup first."
)

# Canonical AI-visibility surfaces (single source of truth for the SEO/AEO/GEO
# cluster). geo-tracker.py, aeo-audit, geo-monitor, share-of-voice and
# serp-tracker all reference this list so they never drift out of sync.
AI_VISIBILITY_SURFACES = [
    "Google AI Mode",
    "Google AI Overviews",
    "ChatGPT",
    "Perplexity",
    "Gemini",
    "Copilot",
]


# ── Encoding ────────────────────────────────────────────────────────

def ensure_utf8_stdout() -> None:
    """Force UTF-8 (errors=replace) on stdout/stderr.

    Windows consoles default to cp1252; printing JSON containing em dashes or
    non-Latin content would otherwise raise UnicodeEncodeError mid-pipeline.
    """
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


# ── Time ────────────────────────────────────────────────────────────

def now_iso() -> str:
    """Current UTC timestamp in ISO 8601 with a 'Z' suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Paths ───────────────────────────────────────────────────────────

def workspace_root() -> Path:
    """Root of Digital Marketing Pro persistent data.

    Resolution order:
      1. $CLAUDE_MARKETING_HOME (explicit override; used by tests)
      2. $CLAUDE_PLUGIN_DATA/digital-marketing-pro if $CLAUDE_PLUGIN_DATA is
         set (non-empty) AND that directory exists; $PLUGIN_DATA (the Agent
         Plugins 1.0 standard name — non-Claude hosts set only this) is the
         fallback spelling
      3. ~/.claude-marketing
    """
    override = os.environ.get("CLAUDE_MARKETING_HOME")
    if override:
        return Path(override).expanduser()
    plugin_data = os.environ.get("CLAUDE_PLUGIN_DATA") or os.environ.get("PLUGIN_DATA")
    if plugin_data:  # empty string must NOT resolve to Path(".")
        base = Path(plugin_data).expanduser()
        if base.exists():
            return base / "digital-marketing-pro"
    return Path.home() / ".claude-marketing"


def brands_root() -> Path:
    """Directory holding all per-brand data: workspace_root()/brands."""
    return workspace_root() / "brands"


def slugify_brand(name: str) -> str:
    """Canonical brand slug: lowercase, non-alphanumeric runs → single hyphen,
    trimmed, max 60 chars. Empty input yields 'brand'. This is the ONE
    slugifier - all local variants (four of them across the tree) were killed."""
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower())
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:60].rstrip("-") or "brand"


# Backwards-friendly alias: several scripts had a local `slugify()`.
slugify = slugify_brand


class UnsafePathError(ValueError):
    """A model- or user-supplied name would point outside its directory."""


def is_safe_component(name) -> bool:
    """True if `name` can only ever name an entry directly inside a directory:
    non-empty, no `/` or `\\`, no `..`, not absolute, no drive or stream colon,
    no NUL."""
    if not isinstance(name, str):
        return False
    n = name.strip()
    return bool(n) and n not in (".", "..") and not any(
        bad in n for bad in ("/", "\\", "..", ":", "\x00")
    ) and not os.path.isabs(n)


def safe_child(base, name, suffix: str = "") -> Path:
    """Return base/<name><suffix>, guaranteed to be a direct child of base.

    Every ID that reaches a file path (run_id, member_id, content_hash,
    template/SOP/guideline names, journey_id, schedule_id, approval_id, raw
    brand names) goes through here, so `../..`, absolute paths and backslash
    tricks cannot reach a delete or a write outside the plugin's data.
    Raises UnsafePathError; callers turn it into their usual {"error": ...}.
    """
    if not is_safe_component(name):
        raise UnsafePathError(f"unsafe name {name!r}: use a plain name without path separators or '..'")
    base_path = Path(base)
    candidate = base_path / f"{name.strip()}{suffix}"
    if candidate.resolve().parent != base_path.resolve():
        raise UnsafePathError(f"unsafe name {name!r}: resolves outside {base_path}")
    return candidate


def path_component(value: str) -> str:
    """argparse `type=` for every --brand / --slug / --run-id / --client value:
    accepts a plain name (spaces and punctuation are fine, the slug is derived
    later) and rejects anything that could act as a path."""
    import argparse
    if not is_safe_component(value):
        raise argparse.ArgumentTypeError(
            f"{value!r} must be a plain name with no '/', backslash, '..' or drive prefix "
            "(use the brand slug or run id)")
    return value


def child_or_error(base, name, suffix: str = ""):
    """(path, None) or (None, error message): safe_child in the (value, error)
    shape the managers already use for get_brand_dir()."""
    try:
        return safe_child(base, name, suffix), None
    except UnsafePathError as exc:
        return None, str(exc)


def brand_dir(brand: str) -> Path:
    """Per-brand data directory under brands_root().

    Backward compatibility: if a directory named with the raw brand string
    already exists (created by pre-v3.15 scripts), keep using it so existing
    tracking/checkpoint data stays reachable. Also honours an even older
    location without the `brands/` segment (used by checkpoint-manager /
    output-publisher / drive-sync-state before this release). Otherwise use
    the canonical slug directory.
    """
    root = brands_root()
    raw = (brand or "").strip()
    slug = slugify_brand(brand)
    if raw and is_safe_component(raw):
        # 1. Legacy raw-name directory under brands/ (a single path component
        #    only: a raw `../..` must never resolve outside brands/)
        try:
            legacy_raw = safe_child(root, raw)
            if legacy_raw.is_dir():
                return legacy_raw
        except (OSError, ValueError):
            pass
    # 2. Legacy no-`brands/` directory (old checkpoint/output/drive layout)
    try:
        legacy_flat = workspace_root() / slug
        if legacy_flat.is_dir():
            return legacy_flat
    except (OSError, ValueError):
        pass
    return root / slug


def get_brand_dir(slug: str):
    """Return (brand_dir, error). Mirrors the ~24 private copies: validates the
    brand directory exists, else returns the standard not-found message. The
    slug is normalised through slugify_brand() so callers that pass a raw brand
    name still resolve. Backward-compatible with legacy raw-name dirs."""
    d = brand_dir(slug)
    if not d.exists():
        return None, BRAND_NOT_FOUND.format(slug=slugify_brand(slug))
    return d, None


# ── Outbound URL guard (fetchers) ───────────────────────────────────

def public_url_error(url: str):
    """None if `url` may be fetched, else the reason. http/https only, and the
    host must resolve only to public addresses: loopback, private, link-local
    (incl. the 169.254.169.254 cloud-metadata endpoint), CGNAT, reserved and
    multicast are refused. Call it for EVERY redirect hop, not just the first.
    (Hermes review, smaller notes: the fetchers used the default opener, so
    file:// worked and redirects were followed unchecked.)"""
    import ipaddress
    import socket
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
    except ValueError:
        return f"unparseable URL {url!r}"
    if parsed.scheme not in ("http", "https"):
        return f"only http:// and https:// URLs are fetched, not {parsed.scheme or 'no scheme'!r}"
    host = parsed.hostname
    if not host:
        return f"URL has no host: {url!r}"
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError, ValueError):
        return None  # unresolvable: the fetch itself will fail and report it
    for info in infos:
        ip = ipaddress.ip_address(str(info[4][0]).split("%")[0])
        if not ip.is_global or ip.is_multicast:
            return (f"refusing to fetch {host}: it resolves to {ip}, a non-public address "
                    "(loopback, private, link-local or cloud-metadata ranges are blocked)")
    return None


# ── Approval records (payload-bound, single-use, windowed) ──────────
#
# What this proves, and what it does not: the model runs every command, so no
# script can tell the user's keystrokes from the model's, and a process running
# as the user can rewrite these files. A record proves that the approval step
# ran for this exact payload hash, once, inside its window. Live writes sent by
# connector_executor.py cannot fire without a matching record; writes made
# through an MCP server tool are outside this gate (they rely on the skill's
# typed `yes` and the host's permission prompt). Every fire is logged with a
# full copy of the record, so a forged record is visible afterwards.

APPROVAL_PENDING_MINUTES = 30      # time to review a pending record
APPROVAL_FIRE_MINUTES = 15         # time to fire once approved
STANDING_MAX_DAYS = {"executor": 7, "autopilot": 30}


def _utcnow():
    return datetime.now(timezone.utc)


def _iso(dt) -> str:
    return dt.isoformat()


def _expired(stamp) -> bool:
    try:
        return not stamp or datetime.fromisoformat(stamp) <= _utcnow()
    except ValueError:
        return True


def action_payload_hash(payload) -> str:
    """sha256 over canonical JSON of the fully resolved request description
    (brand, connector, action, credential env-var NAME, method, URL, non-auth
    headers, body). Computed by the executor at prepare and again at fire."""
    import hashlib
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def approvals_dir(brand: str) -> Path:
    return brand_dir(brand) / "approvals"


def write_approval_record(brand: str, prefix: str, record: dict) -> tuple:
    """Create approvals/<prefix>-<YYYYMMDD-HHMMSS>-<n>.json. Returns (id, path)."""
    d = approvals_dir(brand)
    d.mkdir(parents=True, exist_ok=True)
    stamp = _utcnow().strftime("%Y%m%d-%H%M%S")
    n = 1
    while (d / f"{prefix}-{stamp}-{n}.json").exists():
        n += 1
    approval_id = f"{prefix}-{stamp}-{n}"
    path = safe_child(d, approval_id, ".json")
    record = dict(record, approval_id=approval_id)
    record.setdefault("status", "pending")
    record.setdefault("created_at", _iso(_utcnow()))
    record.setdefault("pending_expires_at", _iso(_utcnow() + timedelta(minutes=APPROVAL_PENDING_MINUTES)))
    atomic_write_json(path, record)
    return approval_id, path


def load_approval_for_execution(brand: str, approval_id, payload_hash: str, *, connector: str = "",
                                action: str = ""):
    """Can this approval fire this exact payload now?
    Returns (path, record, item_index, None) or (None, None, None, reason).
    item_index is the batch item to consume, -1 for a single record, None for
    a standing record."""
    if not approval_id:
        return None, None, None, "no --approval-id"
    path, err = child_or_error(approvals_dir(brand), approval_id, ".json")
    if err:
        return None, None, None, err
    record = load_json_safe(path) if path.exists() else None
    if not isinstance(record, dict) or "error" in record:
        return None, None, None, f"approval '{approval_id}' not found or unreadable for brand '{brand}'"
    status = record.get("status")
    if record.get("brand") and record["brand"] != brand:
        return None, None, None, f"approval '{approval_id}' belongs to brand '{record['brand']}'"
    if status in ("consumed", "in-flight", "executed", "failed"):
        return None, None, None, f"approval '{approval_id}' was already used; prepare a new one"
    if status != "approved":
        return None, None, None, f"approval '{approval_id}' is '{status}', not 'approved'"

    if record.get("kind") == "standing":
        scope = record.get("scope") or {}
        if _expired(record.get("expires_at")):
            return None, None, None, f"standing approval '{approval_id}' expired at {record.get('expires_at')}"
        if scope.get("connector") and scope["connector"] != connector:
            return None, None, None, f"standing approval '{approval_id}' covers connector '{scope['connector']}', not '{connector}'"
        if action not in (scope.get("actions") or []):
            return None, None, None, f"standing approval '{approval_id}' does not cover action '{action}'"
        today = _utcnow().date().isoformat()
        used_today = sum(1 for u in record.get("uses", []) if str(u.get("at", "")).startswith(today))
        if used_today >= int(record.get("max_uses_per_day") or 0):
            return None, None, None, (f"standing approval '{approval_id}' reached its cap of "
                                      f"{record.get('max_uses_per_day')} uses today")
        return path, record, None, None

    if _expired(record.get("fire_expires_at")):
        return None, None, None, (f"approval '{approval_id}' expired at {record.get('fire_expires_at')} "
                                  "(fire window after approval); prepare a new one")
    items = record.get("items")
    if items is not None:  # batch: one approval, itemised preview, per-item consumption
        for i, item in enumerate(items):
            if item.get("payload_hash") == payload_hash:
                if item.get("consumed_at"):
                    return None, None, None, f"batch item {i} of '{approval_id}' was already sent"
                return path, record, i, None
        return None, None, None, (f"this request is not one of the {len(items)} items approved in batch "
                                  f"'{approval_id}' (hash mismatch); prepare a new batch")
    if record.get("payload_hash") != payload_hash:
        return None, None, None, (f"approval '{approval_id}' was approved for a different request "
                                  "(hash mismatch); prepare and approve this exact request")
    return path, record, -1, None


def mark_approval_in_flight(path, record: dict, item_index) -> None:
    """Claim the approval just before sending: a crash mid-send leaves it
    'in-flight', which counts as used, so it can never fire twice."""
    now = _iso(_utcnow())
    if item_index is None:
        pass  # standing: recorded as a use after the send
    elif item_index == -1:
        record["status"] = "in-flight"
        record["in_flight_at"] = now
    else:
        record["items"][item_index]["in_flight_at"] = now
    atomic_write_json(path, record)


def settle_approval(path, record: dict, item_index, *, sent: bool, success: bool,
                    request_hash: str, summary=None) -> None:
    """After the attempt. Not sent (network error before the platform saw it):
    release the claim. Sent, whatever the HTTP status: consume it, because the
    platform may have acted."""
    now = _iso(_utcnow())
    if item_index is None:  # standing
        if sent:
            record.setdefault("uses", []).append({"at": now, "payload_hash": request_hash,
                                                  "success": success, "summary": summary})
    elif item_index == -1:
        if sent:
            record["status"] = "executed" if success else "failed"
            record["consumed_at"] = now
            record["execution_result"] = "success" if success else "failure"
            record["platform_response"] = summary
        else:
            record["status"] = "approved"
            record["last_unsent_attempt"] = {"at": now, "summary": summary}
        record.pop("in_flight_at", None)
    else:
        item = record["items"][item_index]
        item.pop("in_flight_at", None)
        if sent:
            item["consumed_at"] = now
            item["execution_result"] = "success" if success else "failure"
        else:
            item["last_unsent_attempt"] = now
        if all(it.get("consumed_at") for it in record["items"]):
            record["status"] = "consumed"
            record["consumed_at"] = now
    atomic_write_json(path, record)


# ── JSON persistence ────────────────────────────────────────────────

def atomic_write_json(path, data) -> None:
    """Write JSON atomically: tmp file in the same directory + Path.replace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    tmp.replace(path)


# Alias used by scripts that called their local helper write_json_atomic().
write_json_atomic = atomic_write_json


def atomic_write_text(path, text: str) -> None:
    """Write text atomically (tmp file in the same directory + Path.replace).
    Used for Markdown artefacts like the Living Instruction File."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def load_json_safe(path):
    """Load JSON, never raise. On failure returns a dict with 'error' and
    'recovery' keys instead of the payload; callers check `"error" in result`
    (payloads produced by DMP never carry a top-level 'error' key)."""
    path = Path(path)
    if not path.exists():
        return {
            "error": f"file not found: {path}",
            "missing": True,
            "recovery": "Initialise it first (e.g. --action init) or check the brand name.",
        }
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {
            "error": f"corrupt or unreadable JSON at {path}: {type(exc).__name__}: {exc}",
            "corrupt": True,
            "recovery": (
                f"The file may have been truncated by an interrupted write. "
                f"Inspect {path} manually; a sibling '{path.name}.tmp' file (if present) "
                f"may hold the last attempted write. Re-run init to start fresh."
            ),
        }


# ── CLI result handling ─────────────────────────────────────────────

def finish(result) -> None:
    """Print the result JSON and exit: 1 when the result carries an error,
    0 otherwise. Every DMP CLI script funnels its final result through this so
    shell callers can trust $? (this fixes the 39 scripts whose trailer
    `json.dump(result, sys.stdout)` always exited 0, even on error)."""
    ensure_utf8_stdout()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    is_error = isinstance(result, dict) and "error" in result
    sys.exit(1 if is_error else 0)
