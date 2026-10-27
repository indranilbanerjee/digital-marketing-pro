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

import codecs
import hashlib
import json
import os
import re
import sys
import unicodedata
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


# Every script that imports this module writes UTF-8. Where stdout is a pipe (Claude Code's Bash
# tool, Cowork, any capture) Windows gives Python cp1252, and a Devanagari, CJK or emoji brand name
# raised UnicodeEncodeError mid-run. Reconfiguring a text stream after it has been written to is
# allowed, so the import order of a script doesn't matter.
ensure_utf8_stdout()


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


# Windows device names: no file or folder can carry one, with or without an extension.
WINDOWS_RESERVED = frozenset({"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                              *(f"lpt{i}" for i in range(1, 10))})


def _ascii_slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return re.sub(r"-+", "-", s).strip("-")[:60].rstrip("-")


def legacy_slug(name: str) -> str:
    """The slug before 3.40.0, which dropped every non-ASCII letter ("Café" -> "caf", any Devanagari
    or CJK name -> "brand"). Used only to find folders created under it."""
    return _ascii_slug(name or "") or "brand"


def safe_slug(text: str, fallback: str = "brand") -> str:
    """A file-name-safe ASCII slug that keeps different names apart.

    ASCII text gives exactly the old slug. Accents fold ("Café" -> "cafe"). When letters, digits
    or emoji from another script remain (Devanagari, CJK, Arabic, Cyrillic), the ASCII part gets a
    six-character tag from a hash of the name, so two such names never share a slug ("भारत चाय" ->
    "brand-d08c85"). A Windows device name gets "-<fallback>" appended."""
    name = unicodedata.normalize("NFKC", text or "").strip()
    folded = "".join(c for c in unicodedata.normalize("NFKD", name) if not unicodedata.combining(c))
    slug = _ascii_slug(folded)
    if any(not c.isascii() and unicodedata.category(c)[0] in "LNM" or unicodedata.category(c) == "So"
           for c in folded):
        tag = hashlib.sha256(name.casefold().encode("utf-8")).hexdigest()[:6]
        slug = f"{slug[:53].rstrip('-') or fallback}-{tag}"
    slug = slug or fallback
    return f"{slug}-{fallback}" if slug in WINDOWS_RESERVED else slug


def slugify_brand(name: str) -> str:
    """Canonical brand slug (safe_slug with the fallback "brand"). This is the ONE brand
    slugifier: all local variants (four of them across the tree) were killed."""
    return safe_slug(name, "brand")


def same_brand_name(a, b) -> bool:
    """True when two brand names are the same name (case and Unicode normal form aside)."""
    norm = lambda s: unicodedata.normalize("NFKC", str(s or "")).strip().casefold()  # noqa: E731
    return norm(a) == norm(b)


# Backwards-friendly alias: several scripts had a local `slugify()`.
slugify = slugify_brand


class UnsafePathError(ValueError):
    """A model- or user-supplied name would point outside its directory."""


def is_safe_component(name) -> bool:
    """True if `name` can only ever name an entry directly inside a directory:
    non-empty, no `/` or `\\`, no `..`, not absolute, no drive or stream colon,
    no NUL, at most 200 characters, and not a Windows device name (NUL, CON, COM1, ...). A colon is refused because on
    NTFS "a:b" writes an alternate data stream of "a"."""
    if not isinstance(name, str):
        return False
    n = name.strip()
    return bool(n) and n not in (".", "..") and not any(
        bad in n for bad in ("/", "\\", "..", ":", "\x00")
    ) and not os.path.isabs(n) and n.split(".")[0].lower() not in WINDOWS_RESERVED and len(n) <= 200


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
    candidate = base_path / f"{name.strip()}{suffix}"  # path-safe: checked by is_safe_component just above
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
    # 3. A folder named by the pre-3.40.0 slug ("Café" -> "caf"), used only when its profile is
    #    this brand's, so a name never lands in another brand's folder.
    old = legacy_slug(brand)
    if raw and old != slug and not (root / slug).exists() and (root / old / "profile.json").is_file():
        try:
            if same_brand_name(read_json(root / old / "profile.json").get("brand_name"), raw):
                return root / old
        except (OSError, ValueError, AttributeError):
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


# ── Optional packages (exact pins, printed, never installed) ────────
#
# Every optional package a script may ask for, at the exact version it was
# tested with. scripts/requirements.txt lists the same pins (a test keeps the
# two equal), and every missing-package message prints install_command(), so
# the command a user is shown is the one that was tested. No script runs pip;
# only `scripts/setup.py --install` does, when the user asks for it.

PINNED_DEPENDENCIES = {
    "nltk": "3.10.3",
    "textstat": "0.7.13",
    "beautifulsoup4": "4.15.0",
    "requests": "2.34.2",
    "qrcode": "8.2",
    "pillow": "12.3.0",
    "openai": "3.19.2",
    "anthropic": "1.8.0",
    "c2pa-python": "0.38.0",
    "cryptography": "46.0.3",
}


def pinned_specs(packages) -> list:
    """Map package names (any version specifier is ignored) to exact `name==x.y.z`
    pins. Raises ValueError for a package that has no pin."""
    out = []
    for p in packages:
        name = re.split(r"[<>=!~;\[ ]", str(p), maxsplit=1)[0].strip().lower().replace("_", "-")
        if name not in PINNED_DEPENDENCIES:
            raise ValueError(f"no pinned version for package {name!r}; add it to PINNED_DEPENDENCIES")
        out.append(f"{name}=={PINNED_DEPENDENCIES[name]}")
    return out


POWERSHELL_NOTE = "  # in PowerShell, put & before it"


def _shell_command(rest: str) -> str:
    """`<interpreter> <rest>` that pastes into Git Bash and PowerShell alike.

    Forward slashes: Git Bash (Claude Code's Bash tool on Windows) strips backslashes, so
    `C:\\Python313\\python.exe` became `C:Python313python.exe` and exit 127. The interpreter
    is quoted only when it holds a space, because PowerShell reads a quoted first token as a
    string and needs `& "..."`, which bash does not have; that case carries a trailing
    comment, which both shells ignore, telling PowerShell users to add the `&`."""
    exe = sys.executable or "python"
    exe = exe.replace("\\", "/")
    if " " in exe:
        return f'"{exe}" {rest}{POWERSHELL_NOTE}'
    return f"{exe} {rest}"


def install_command(packages) -> str:
    """The exact, pinned command a user would run to install `packages` into the
    interpreter running this script."""
    return _shell_command(f"-m pip install {' '.join(pinned_specs(packages))}")


def script_command(script: str, args: str = "") -> str:
    """A command line that runs one of this plugin's scripts from any folder: the running
    interpreter and the script's absolute path, always double-quoted, with forward slashes.
    Printed hints use it instead of `python scripts/x.py`, which works only when the shell
    sits in the plugin's folder."""
    path = (Path(__file__).resolve().parent / script).as_posix()
    return _shell_command(f'"{path}"' + (f" {args}" if args else ""))


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
    while (d / f"{prefix}-{stamp}-{n}.json").exists():  # path-safe: prefix is a constant in each caller, stamp a timestamp
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
    if status in ("consumed", "in-flight", "executed", "failed", "unknown"):
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
                    request_hash: str, summary=None, outcome=None) -> None:
    """After the attempt. Not sent (an error that proves no connection was made):
    release the claim. Sent, whatever the HTTP status, or outcome unknown (a timeout
    or reset after the request may have been delivered): consume it, because the
    platform may have acted. `outcome="unknown"` is recorded as such, not as failure:
    a single record gets status "unknown" (consumed), because a reader who saw "failed"
    could prepare the same write again by hand and send it twice."""
    result = outcome or ("success" if success else "failure")
    now = _iso(_utcnow())
    if item_index is None:  # standing
        if sent:
            record.setdefault("uses", []).append({"at": now, "payload_hash": request_hash,
                                                  "success": success, "result": result,
                                                  "summary": summary})
    elif item_index == -1:
        if sent:
            record["status"] = "unknown" if outcome == "unknown" else ("executed" if success else "failed")
            record["consumed_at"] = now
            record["execution_result"] = result
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
            item["execution_result"] = result
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


class JsonFileError(ValueError):
    """A JSON file that can't be used: not UTF-8, not JSON, or the wrong shape. The message says
    what to change. A ValueError, like json.JSONDecodeError and UnicodeDecodeError."""


def decode_text(raw: bytes, name: str = "the file") -> str:
    """UTF-8 (with or without a BOM) or UTF-16 with a BOM, which is what PowerShell 5.1's Out-File
    and `>` write. Anything else raises JsonFileError: a Windows "ANSI" save is not guessed at,
    since the guess would silently garble a non-Western code page."""
    if raw.startswith(codecs.BOM_UTF8):
        raw = raw[len(codecs.BOM_UTF8):]
    elif raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        try:
            return raw.decode("utf-16")
        except UnicodeDecodeError:
            pass
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        raise JsonFileError(f"{name} is not UTF-8 (it looks like a Windows 'ANSI' save, such as "
                            f"Windows-1252). Open it, save it as UTF-8, and run this again.") from None


def read_json(path):
    """Parse a JSON file through decode_text. Raises JsonFileError or json.JSONDecodeError (both
    ValueError) or OSError."""
    path = Path(path)
    return json.loads(decode_text(path.read_bytes(), path.name))


# The top-level sections of profile.json and their types (setup.py --create-brand writes them).
PROFILE_SHAPE = {"brand_name": str, "identity": dict, "business_model": dict, "industry": dict,
                 "target_markets": list, "brand_voice": dict, "channels": dict, "competitors": list,
                 "goals": dict, "language": dict}
_TYPE_WORD = {dict: "an object", list: "a list", str: "text"}


def profile_problems(profile) -> list:
    """What is wrongly shaped in a parsed profile.json, as sentences naming each field."""
    if not isinstance(profile, dict):
        return [f"profile.json must hold an object, not {_TYPE_WORD.get(type(profile), type(profile).__name__)}"]
    return [f"profile.json field '{key}' must be {_TYPE_WORD[want]}, not "
            f"{_TYPE_WORD.get(type(profile[key]), type(profile[key]).__name__)} ({json.dumps(profile[key])[:40]})"
            for key, want in PROFILE_SHAPE.items() if key in profile and not isinstance(profile[key], want)]


def load_profile(path) -> dict:
    """Read and check a brand's profile.json. Raises JsonFileError (or JSONDecodeError, OSError)
    with a message that names the encoding or the field to fix."""
    profile = read_json(path)
    problems = profile_problems(profile)
    if problems:
        raise JsonFileError("; ".join(problems) + ". Fix it in profile.json, or run "
                            "/digital-marketing-pro:brand-setup to rewrite it.")
    return profile


_JSON_KIND = {dict: "object", list: "array", str: "string", (int, float): "number", (dict, list): "object or array"}


def _kind_of(value) -> str:
    if isinstance(value, bool):
        return "true/false"
    for types, word in ((dict, "object"), (list, "array"), (str, "string"), ((int, float), "number")):
        if isinstance(value, types):
            return word
    return "null" if value is None else type(value).__name__


def json_arg(value, name: str, expect=dict, items=None):
    """Parse a JSON command-line option and check its shape, or print {"error": ...} and exit 2.

    `expect` is the top-level type (dict, list, or a tuple of them); `items` the type every element
    of a list must have. Before 3.40.0, null, a list or a string where an object was expected
    ended 15 scripts in AttributeError or TypeError."""
    try:
        data = json.loads(value)
    except (TypeError, ValueError) as exc:
        _input_error(f"{name} is not valid JSON: {exc}")
    if isinstance(data, bool) or not isinstance(data, expect):
        _input_error(f"{name} must be a JSON {_JSON_KIND.get(expect, 'value')}, not {_kind_of(data)}")
    if items is not None and isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, bool) or not isinstance(item, items):
                _input_error(f"{name} item {i} must be a {_JSON_KIND.get(items, 'value')}, not {_kind_of(item)}")
    return data


def _input_error(message: str):
    print(json.dumps({"error": message}, indent=2, ensure_ascii=False))
    sys.exit(2)


def fallback_exit(error: str, message: str, recommendation: str) -> None:
    """A scorer whose package or data is missing prints one JSON line and exits 0 (a fallback, not
    an error: eval-runner reports the dimension as missing and the result as partial)."""
    print(json.dumps({"fallback": True, "error": error, "message": message, "overall_score": None,
                      "recommendation": recommendation}, indent=2))
    sys.exit(0)


def load_nltk_tokenizers(recommendation: str):
    """Import nltk and make sure its sentence and word tokenizers work, downloading their data once.
    Returns (sent_tokenize, word_tokenize), or calls fallback_exit: no nltk, or tokenizer data that
    can't be downloaded (offline, or NLTK refusing a fetch through a proxy). Before 3.40.0 the
    download result was ignored and the scorer died later in a LookupError banner."""
    try:
        import nltk
    except ImportError:
        fallback_exit("nltk_not_installed", "NLTK not installed. This scorer requires it; install the "
                      "tested version with: " + install_command(["nltk"]), recommendation)
    from nltk.tokenize import sent_tokenize, word_tokenize
    for res in ("punkt_tab", "punkt"):
        try:
            nltk.data.find(f"tokenizers/{res}")
        except LookupError:
            try:
                nltk.download(res, quiet=True)
            except Exception:  # noqa: BLE001 - a failed download is reported below
                pass
    try:
        sent_tokenize("One. Two.")
        word_tokenize("One two.")
    except LookupError:
        fallback_exit("nltk_data_missing", "NLTK's tokenizer data (punkt_tab) is missing and could not be "
                      "downloaded: offline, or NLTK refused a fetch through a proxy. On a connected machine "
                      "run `python -m nltk.downloader punkt_tab punkt` (or setup.py --install lite), or set "
                      "NLTK_DATA to a folder that holds it.", recommendation)
    return sent_tokenize, word_tokenize


def _registry_documents():
    """The Documents folder Windows Explorer shows, from the "Personal" shell-folder value, expanded
    with this process's environment; None off Windows or when it can't be read."""
    if os.name != "nt":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as key:
            value, _ = winreg.QueryValueEx(key, "Personal")
        return Path(os.path.expandvars(value))
    except (OSError, ImportError):
        return None


def documents_dir() -> Path:
    """The user's Documents folder. On Windows that is where Explorer shows it, which OneDrive's
    "Known Folder Move" puts inside the OneDrive folder; before 3.40.0 deliverables went to a second,
    unsynced ~/Documents that Explorer's Documents page never shows. The registry folder is used
    only when it exists, so a run with another HOME/USERPROFILE (a test sandbox) stays inside it."""
    found = _registry_documents()
    if found is not None and found.is_dir():
        return found
    return Path.home() / "Documents"


# The keys eval-config-manager.py writes and eval-runner.py reads: one table, so the two can't drift.
# Before 3.40.0 the runner read "minimum_dimension_scores" and weights.full/quick/compliance, and it
# looked for them in the manager's whole {"brand", "config"} reply, so no brand setting ever applied.
EVAL_CONFIG_KEYS = {"auto_reject": "auto_reject_threshold", "minimums": "minimum_scores", "weights": "weights"}


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
        return read_json(path)
    except (ValueError, OSError) as exc:
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
