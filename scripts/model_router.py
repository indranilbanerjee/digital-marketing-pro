#!/usr/bin/env python3
"""model_router.py: choose a model by JOB from the provider's own live list, never by name.

WHY
---
A model id written into a plugin is a claim about the day it was written. The registry
(scripts/model_registry.json) made that claim reviewable; this module stops depending on it
for the decision. A job in the plugin's hint book names a provider and either a model LINE
or a model FAMILY, never an id:
  * Anthropic: `line` is a field of GET /v1/models ("do not infer a line from the id"), and
    the list reports each model's lifecycle and retirement date.
  * OpenAI: GET /v1/models gives only id, created, owned_by and an optional shutdown_date,
    so a job names a FAMILY pattern over ids with a (?P<version>...) group, and lifecycle
    comes from that shutdown_date plus the deprecations record an agent read from OpenAI's
    deprecations page into the hint book (with its source and date). Fine-tuned models
    follow their base model's schedule.
  * Google: models.list gives each model's name ("models/<id>"), version, token limits and
    the generation methods it supports, with no lifecycle and no release date. A job names a
    FAMILY pattern and the methods it calls (its `capabilities`, such as generateContent),
    which the list must report. Lifecycle AND release dates come from the deprecations
    record an agent read from Google's deprecations page. That page's shutdown dates are the
    earliest possible ones and it marks the models already shut down, so a model past its
    date that the page does not mark is kept with a warning, not refused. A model whose
    endpoint the page says now routes to another is never picked. A listed model missing
    from the record has no known release date, so it waits (with a warning) until the record
    is re-read.
At run time the router lists the models this key can use and picks, in the job's line or
family, the newest (highest version, then newest) model that is:
  * `active` (no shutdown announced, not retired, not routed to another model);
  * generally available: no preview/exp/beta/alpha/rc id, no moving "latest" alias, no dated
    snapshot, no fine-tune;
  * at least MIN_GA_DAYS old (a brand-new release is never promoted on day one);
  * equipped with every capability the job's rule requires.
The registry stays as the fallback: offline, the caller's shipped default is used and the
answer is tagged "offline". Offline, the registry and the hint book's deprecations record
(both local data) also stand in for the list's lifecycle data: a model about to be sent that
either marks deprecated warns, one past its shutdown is refused, and one the record says now
routes to another model warns that the answer comes from that model, as on the live path.
The stricter source wins and its message names it.

A model asked for by name is kept if it is active; kept with a warning if it is deprecated
(naming the retirement date and the model the router would pick); and refused, exit 2, if it
is retired, naming that replacement. Nothing is swapped silently.

LIMITS (the plan's rules 5, 8 and 10)
-------------------------------------
* Discovery happens only when a job needs a model and the cache is stale: never at install
  or import. One list call per provider and credential per TTL_DAYS serves every job in the
  hint book.
* The cache is keyed by provider, job and credential NAME (an environment variable name),
  never the key. It stores the chosen ids, their lifecycle dates and counts; never the list,
  and never a fine-tuned model's name (at an agency those name clients).
* Each key goes only to its own vendor, the Anthropic one with the same anthropic-version
  header as the caller's generation call, the Google one in the x-goog-api-key header and
  never in the URL (where proxies and server logs keep it).
* MODEL_ROUTER_OFFLINE=1 makes no call at all.
* Deterministic: the same list on the same day gives the same answer. Learning from
  approvals belongs to a server, not to this file.

This file is copied byte for byte into each plugin that uses it; a parity test in each repo
keeps the copies identical. Stdlib only, Python 3.10+.

CLI (prints one JSON object; exit 0 chosen, 2 refused or bad input):
    python model_router.py --hints FILE --job JOB --provider anthropic|google|openai \\
        --credential-name NAME [--requested ID] [--default-model ID] \\
        [--cache FILE] [--anthropic-version VERSION] [--ignore-deprecations-record] [--backend NAME]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROUTER = "model_router/1"
TTL_DAYS = 7
MIN_GA_DAYS = 14
RECORD_RECHECK_DAYS = 30
TIMEOUT_S = 10.0
MAX_PAGES = 20  # pages left after this many: an error, never a short list
OFFLINE_ENV = "MODEL_ROUTER_OFFLINE"
ANTHROPIC_MODELS_URL = "https://api.anthropic.com/v1/models"
OPENAI_MODELS_URL = "https://api.openai.com/v1/models"
GOOGLE_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"
LIFECYCLES = ("active", "deprecated", "retired")
NON_GA = re.compile(r"(?:^|[-_.])(?:preview|exp|experimental|beta|alpha|rc\d*)(?:$|[-_.])", re.I)
MOVING_ALIAS = re.compile(r"(?:^|[-_.])latest$", re.I)  # hot-swapped with each release
DATED_SNAPSHOT = re.compile(r"-(?:\d{4}-\d{2}-\d{2}|\d{2}-\d{4}|\d{2}-\d{2})$")  # 2024-08-06, 09-2025, 05-20
GOOGLE_RECORD_FIELDS = ("released", "shutdown", "shut_down", "replacement", "redirects_to")
CREDENTIAL_NAME = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
CACHE_FIELDS = frozenset({"model", "lifecycle", "retires_at", "line", "replacement", "replacement_from",
                          "discovered_at", "source", "counts"})
RULE_REQUIRED = ("provider", "source", "read_on")
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
NEVER = "9999-12-31T00:00:00Z"  # a release time we could not read: never old enough to promote


class RouterError(Exception):
    """The router refuses: the caller must not send a request. exit_code is for CLIs."""

    def __init__(self, reason: str, exit_code: int = 2):
        super().__init__(reason)
        self.reason, self.exit_code = reason, exit_code


class FetchError(Exception):
    """A list call failed. kind: auth | http | unavailable | timeout | network | schema."""

    def __init__(self, kind: str, detail: str, code: int | None = None):
        super().__init__(f"{kind}: {detail}")
        self.kind, self.detail, self.code = kind, detail, code


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(stamp) -> datetime | None:
    """RFC 3339 or YYYY-MM-DD to an aware datetime; Python 3.10's fromisoformat takes no 'Z'."""
    if not isinstance(stamp, str) or not stamp:
        return None
    text = stamp.strip().replace("Z", "+00:00").replace("z", "+00:00")
    text = re.sub(r"(\.\d{1,6})\d*(?=[+-]\d\d:\d\d$)", lambda m: m.group(1).ljust(7, "0"), text)
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _scrub(text: str, secret: str) -> str:
    return text.replace(secret, "[key]") if secret else text


def _base_id(model_id: str) -> str:
    """ft:BASE:org::suffix -> BASE (OpenAI: fine-tunes follow their base model's shutdown)."""
    return model_id.split(":")[1] if model_id.startswith("ft:") and model_id.count(":") >= 2 else model_id


# --- HTTP ------------------------------------------------------------------------------------

def _get_json(req, opener, timeout: float, api_key: str, items: str = "data", omit_empty: bool = False) -> dict:
    try:
        with opener(req, timeout=timeout) as resp:
            page = json.loads(resp.read().decode("utf-8-sig"))
    except urllib.error.HTTPError as exc:
        detail = _scrub(f"HTTP {exc.code} {_error_text(exc)}".strip(), api_key)
        kind = ("auth" if exc.code in (401, 403) else
                "unavailable" if exc.code == 429 or exc.code >= 500 else "http")
        raise FetchError(kind, detail, exc.code) from None
    except (TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        kind = "timeout" if isinstance(reason, TimeoutError) or "timed out" in str(reason) else "network"
        raise FetchError(kind, _scrub(str(reason), api_key)) from None
    except ValueError:
        raise FetchError("schema", "the model list was not JSON") from None
    if isinstance(page, dict) and omit_empty and items not in page:
        page[items] = []  # proto3 JSON leaves an empty repeated field out
    if not isinstance(page, dict) or not isinstance(page.get(items), list):
        raise FetchError("schema", f"the model list had no {items} array")
    return page


def _error_text(exc: urllib.error.HTTPError) -> str:
    """The error's type, status and code only: providers echo part of a rejected key in the message."""
    try:
        err = json.loads(exc.read().decode("utf-8-sig")).get("error", {})
        return " ".join(str(err[k]) for k in ("type", "status", "code")
                        if err.get(k) and str(err[k]) != str(exc.code))
    except Exception:
        return ""


def _pages(first_url: str, headers: dict, api_key: str, cursor: str, timeout: float, urlopen,
           retry_without=None, *, items: str = "data", id_field: str = "id", next_token: str | None = None) -> list:
    """Every page of a model list. Anthropic and OpenAI page by has_more/last_id; Google by
    nextPageToken, leaving an empty list's `models` key out. A list still going after
    MAX_PAGES is refused: a short list would make a listed model look unlisted."""
    opener = urlopen or urllib.request.urlopen
    out: list = []
    url, after = first_url, None
    for _ in range(MAX_PAGES):
        full = url + (("&" if "?" in url else "?") + urllib.parse.urlencode({cursor: after}) if after else "")
        req = urllib.request.Request(full, method="GET")
        for name, value in headers.items():
            req.add_header(name, value)
        try:
            page = _get_json(req, opener, timeout, api_key, items, omit_empty=bool(next_token))
        except FetchError as exc:
            if exc.code == 400 and retry_without and not out and url != retry_without:
                url = retry_without  # an API version without the filter: list without it
                continue
            raise
        out.extend(m for m in page[items] if isinstance(m, dict) and isinstance(m.get(id_field), str))
        after = page.get(next_token) if next_token else (page.get("has_more") and page.get("last_id"))
        if not after:
            return out
    raise FetchError("schema", f"the model list had more than {MAX_PAGES} pages; a partial list is not used")


# --- Anthropic adapter -----------------------------------------------------------------------

def fetch_anthropic(api_key: str, anthropic_version: str | None, *, timeout: float = TIMEOUT_S,
                    urlopen=None) -> list:
    """Every model this key can see, retired ones included, across pages. Without the
    lifecycle filter (an older API version), retired models go unlisted."""
    plain = ANTHROPIC_MODELS_URL + "?" + urllib.parse.urlencode([("limit", "1000")])
    filtered = ANTHROPIC_MODELS_URL + "?" + urllib.parse.urlencode(
        [("limit", "1000")] + [("lifecycle[]", stage) for stage in LIFECYCLES])
    headers = {"x-api-key": api_key}
    if anthropic_version:
        headers["anthropic-version"] = anthropic_version
    return _pages(filtered, headers, api_key, "after_id", timeout, urlopen, retry_without=plain)


def _norm_anthropic(raw: list, hints: dict, now: datetime) -> tuple:
    if any("lifecycle" not in m for m in raw):
        return None, "the model list has no lifecycle field, so deprecation cannot be checked"
    return [dict(m) for m in raw], None


def _requested_anthropic(requested: str, models: list, rule: dict, hints: dict, now: datetime) -> dict:
    found = next((m for m in models if m["id"] == requested), None)
    line = (found or {}).get("line") or rule.get("line")
    best, _ = choose(models, {"line": line, "capabilities": rule.get("capabilities")}, now)
    return {"lifecycle": (found or {}).get("lifecycle", "unlisted"), "retires_at": (found or {}).get("retires_at"),
            "line": line, "replacement": best["id"] if best else None}


# --- OpenAI adapter (presence plus recorded lifecycle) ---------------------------------------

def fetch_openai(api_key: str, _api_version: str | None = None, *, timeout: float = TIMEOUT_S,
                 urlopen=None) -> list:
    """Every model this key can see: id, created, owned_by and, when announced, shutdown_date."""
    return _pages(OPENAI_MODELS_URL, {"Authorization": f"Bearer {api_key}"}, api_key, "after", timeout, urlopen)


def _record(hints: dict, provider: str) -> dict:
    return ((hints.get("deprecations") or {}).get(provider) or {}).get("models") or {}


def _shutdown_lifecycle(shutdown, now: datetime) -> str:
    when = _parse(shutdown) if shutdown else None
    if not shutdown:
        return "active"
    return "retired" if when and when.date() <= now.date() else "deprecated"


def _norm_openai(raw: list, hints: dict, now: datetime) -> tuple:
    record, out = _record(hints, "openai"), []
    for m in raw:
        shutdown = m.get("shutdown_date") or record.get(_base_id(m["id"]), {}).get("shutdown")
        created = m.get("created")
        out.append({"id": m["id"], "line": None, "retires_at": shutdown or None,
                    "lifecycle": _shutdown_lifecycle(shutdown, now),
                    "created_at": (_iso(datetime.fromtimestamp(created, timezone.utc))
                                   if isinstance(created, (int, float)) and created > 0 else NEVER)})
    return out, None


def _requested_openai(requested: str, models: list, rule: dict, hints: dict, now: datetime) -> dict:
    found = next((m for m in models if m["id"] == requested), None)
    noted = _record(hints, "openai").get(_base_id(requested), {})
    if found:
        lifecycle, retires = found["lifecycle"], found["retires_at"]
    elif noted.get("shutdown"):
        lifecycle, retires = _shutdown_lifecycle(noted["shutdown"], now), noted["shutdown"]
    else:
        lifecycle, retires = "unlisted", None
    return {"lifecycle": lifecycle, "retires_at": retires, "line": None,
            **_replacement(noted.get("replacement"), models, rule, now)}


def _replacement(recorded: str | None, models: list, rule: dict, now: datetime) -> dict:
    """The vendor's recommended replacement from the record, else the router's own pick; the
    messages say which, because the two can differ."""
    if recorded:
        return {"replacement": recorded, "replacement_from": "record"}
    best, _ = choose(models, rule, now)
    return {"replacement": best["id"] if best else None, "replacement_from": "router"}


# --- Google adapter (presence plus recorded lifecycle and release dates) ----------------------

def fetch_google(api_key: str, _api_version: str | None = None, *, timeout: float = TIMEOUT_S,
                 urlopen=None) -> list:
    """Every model this key can see. The key travels in the x-goog-api-key header, never in the
    URL: Google's own curl examples put it there as ?key=, where proxies and server logs keep it."""
    return _pages(GOOGLE_MODELS_URL + "?" + urllib.parse.urlencode({"pageSize": 1000}),
                  {"x-goog-api-key": api_key}, api_key, "pageToken", timeout, urlopen,
                  items="models", id_field="name", next_token="nextPageToken")


def _google_id(name: str) -> str:
    return name[len("models/"):] if name.startswith("models/") else name


def _month_or_day(value) -> date | None:
    """YYYY-MM-DD as given; YYYY-MM (the page gives only a month for some models) as the month's
    LAST day, so the age rule never clears a model earlier than it could have been released."""
    if not isinstance(value, str):
        return None
    try:
        if re.fullmatch(r"\d{4}-\d{2}", value):
            year, month = int(value[:4]), int(value[5:])
            if not 1 <= month <= 12:
                return None
            return date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)
        return date.fromisoformat(value) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) else None
    except ValueError:
        return None


def _google_lifecycle(noted: dict) -> str:
    if noted.get("shut_down"):
        return "retired"
    if noted.get("redirects_to"):
        return "redirected"
    return "deprecated" if noted.get("shutdown") else "active"


def _norm_google(raw: list, hints: dict, now: datetime) -> tuple:
    record, out = _record(hints, "google"), []
    for m in raw:
        mid = _google_id(m["name"])
        noted = record.get(mid, {})
        released = _month_or_day(noted.get("released"))
        methods = [x for x in m.get("supportedGenerationMethods") or [] if isinstance(x, str)]
        out.append({"id": mid, "line": None, "lifecycle": _google_lifecycle(noted),
                    "retires_at": noted.get("shutdown"),
                    "created_at": released.isoformat() + "T00:00:00Z" if released else NEVER,
                    "capabilities": {x: {"supported": True} for x in methods}})
    return out, None


def _requested_google(requested: str, models: list, rule: dict, hints: dict, now: datetime) -> dict:
    mid = _google_id(requested)
    found = next((m for m in models if m["id"] == mid), None)
    noted = _record(hints, "google").get(mid, {})
    if found:
        lifecycle, retires = found["lifecycle"], found["retires_at"]
    elif noted and _google_lifecycle(noted) != "active":
        lifecycle, retires = _google_lifecycle(noted), noted.get("shutdown")
    else:
        lifecycle, retires = "unlisted", None
    return {"lifecycle": lifecycle, "retires_at": retires, "line": None,
            **_replacement(noted.get("redirects_to") or noted.get("replacement"), models, rule, now)}


ADAPTERS = {
    "anthropic": {"fetch": fetch_anthropic, "source": ANTHROPIC_MODELS_URL,
                  "normalize": _norm_anthropic, "requested": _requested_anthropic},
    "google": {"fetch": fetch_google, "source": GOOGLE_MODELS_URL, "dates_from_record": True,
               "normalize": _norm_google, "requested": _requested_google},
    "openai": {"fetch": fetch_openai, "source": OPENAI_MODELS_URL,
               "normalize": _norm_openai, "requested": _requested_openai},
}
# The service each adapter's list call reaches, which is also the service its deprecations record
# describes. A registry entry's replacement_by_backend is keyed by these names.
PROVIDER_BACKEND = {"anthropic": "anthropic", "openai": "openai", "google": "gemini-api"}


# --- selection -------------------------------------------------------------------------------

def _not_promotable(model_id: str) -> bool:
    return bool(":" in model_id or NON_GA.search(model_id) or MOVING_ALIAS.search(model_id)
                or DATED_SNAPSHOT.search(model_id))


def _has_capabilities(model: dict, required) -> bool:
    for path in required or ():
        node = model.get("capabilities")
        for part in path.split("."):
            node = node.get(part) if isinstance(node, dict) else None
        if not (isinstance(node, dict) and node.get("supported") is True):
            return False
    return True


def _version(match) -> tuple:
    try:
        return tuple(int(p) for p in match.group("version").split("."))
    except (IndexError, ValueError, AttributeError):
        return ()


def choose(models: list, rule: dict, now: datetime) -> tuple:
    """(best model dict or None, counts) for one rule: a `line`, or a `family` pattern."""
    if rule.get("family"):
        pattern = re.compile(rule["family"])
        matched = [(m, pattern.fullmatch(m["id"])) for m in models]
        in_line = [(m, _version(hit)) for m, hit in matched if hit]
    else:
        in_line = [(m, ()) for m in models if m.get("line") == rule.get("line")]
    floor = now - timedelta(days=MIN_GA_DAYS)
    ready = [(m, v) for m, v in in_line
             if m.get("lifecycle") == "active" and not _not_promotable(m["id"])
             and _has_capabilities(m, rule.get("capabilities"))]
    eligible = [(m, v) for m, v in ready if (_parse(m.get("created_at")) or EPOCH) <= floor]
    eligible.sort(key=lambda mv: (mv[1], _parse(mv[0].get("created_at")) or EPOCH, mv[0]["id"]), reverse=True)
    counts = {"listed": len(models), "in_line": len(in_line), "eligible": len(eligible)}
    top = eligible[0][1] if eligible else None
    held = sum(1 for m, v in ready if m.get("created_at") == NEVER and (top is None or v > top))
    if held:
        counts["held_undated"] = held  # newer than the pick, but no release date to clear the age rule
    return (eligible[0][0] if eligible else None), counts


def _date_problem(value, where: str, field: str) -> list:
    if not isinstance(value, str) or not value.strip():
        return [f"{where}: {field} missing"]
    try:
        date.fromisoformat(value)
    except ValueError:
        return [f"{where}: {field} must be YYYY-MM-DD"]
    return []


def validate_hints(hints) -> list:
    """Problems with a hint book; every rule and record carries its source and the date it was read."""
    if not isinstance(hints, dict) or hints.get("schema") != 1 or not isinstance(hints.get("jobs"), dict):
        return ["hint book must be {\"schema\": 1, \"jobs\": {...}}"]
    out = []
    for job, rule in sorted(hints["jobs"].items()):
        if not isinstance(rule, dict):
            out.append(f"{job}: rule must be an object")
            continue
        for field in ("provider", "source"):
            if not isinstance(rule.get(field), str) or not rule[field].strip():
                out.append(f"{job}: {field} missing")
        out += _date_problem(rule.get("read_on"), job, "read_on")
        if rule.get("provider") and rule["provider"] not in ADAPTERS:
            out.append(f"{job}: no adapter for provider {rule['provider']!r}")
        if isinstance(rule.get("source"), str) and rule["source"] and not rule["source"].startswith("https://"):
            out.append(f"{job}: source must be an https URL")
        has_line, has_family = bool(rule.get("line")), bool(rule.get("family"))
        if has_line == has_family:
            out.append(f"{job}: give line or family, not both" if has_line else f"{job}: give line or family")
        elif has_line and rule.get("provider") in ("openai", "google"):
            out.append(f"{job}: {rule['provider']} lists no model lines, so give a family")
        if has_family:
            try:
                if "version" not in re.compile(rule["family"]).groupindex:
                    out.append(f"{job}: family needs a (?P<version>...) group")
            except (re.error, TypeError):
                out.append(f"{job}: family is not a valid pattern")
        caps = rule.get("capabilities", [])
        if not isinstance(caps, list) or not all(isinstance(c, str) for c in caps):
            out.append(f"{job}: capabilities must be a list of names")
        elif caps and rule.get("provider") == "openai":
            out.append(f"{job}: openai lists no capabilities, so none can be required")
        elif not caps and rule.get("provider") == "google":
            out.append(f"{job}: google jobs must name the generation methods they call in capabilities "
                       f"(for example generateContent), since the list mixes text, image, speech and embedding models")
    for provider, record in sorted((hints.get("deprecations") or {}).items()):
        where = f"deprecations.{provider}"
        if not isinstance(record, dict) or not isinstance(record.get("models"), dict):
            out.append(f"{where}: needs source, read_on and models")
            continue
        if not str(record.get("source", "")).startswith("https://"):
            out.append(f"{where}: source missing")
        out += _date_problem(record.get("read_on"), where, "read_on")
        for mid, entry in sorted(record["models"].items()):
            if not isinstance(entry, dict):
                out.append(f"{where}.{mid}: must be an object")
                continue
            if provider == "google":
                out += _google_entry_problems(f"{where}.{mid}", entry)
                continue
            out += _date_problem(entry.get("shutdown"), f"{where}.{mid}", "shutdown")
            if not isinstance(entry.get("replacement"), str) or not entry["replacement"]:
                out.append(f"{where}.{mid}: replacement missing")
    return out


def _google_entry_problems(where: str, entry: dict) -> list:
    """One row of Google's deprecations page: the release date, the earliest shutdown date, whether
    the page marks it as already shut down, its recommended replacement, or the model its
    endpoint now routes to. Every field is optional; an empty row says nothing."""
    if not entry:
        return [f"{where}: empty; give at least its release date"]
    out = [f"{where}: unknown field {k}" for k in sorted(entry) if k not in GOOGLE_RECORD_FIELDS]
    if "released" in entry and _month_or_day(entry["released"]) is None:
        out.append(f"{where}: released must be YYYY-MM-DD or YYYY-MM")
    if "shutdown" in entry:
        out += _date_problem(entry["shutdown"], where, "shutdown")
    if "shut_down" in entry and not isinstance(entry["shut_down"], bool):
        out.append(f"{where}: shut_down must be true or false")
    if entry.get("shut_down") and "shutdown" not in entry:
        out.append(f"{where}: shut_down needs its shutdown date")
    for field in ("replacement", "redirects_to"):
        if field in entry and (not isinstance(entry[field], str) or not entry[field].strip()):
            out.append(f"{where}: {field} must name a model")
    return out


# --- cache -----------------------------------------------------------------------------------

def _empty_cache() -> dict:
    return {"schema": 1, "router": ROUTER, "entries": {}}


def _load_cache(path) -> tuple:
    if path is None or not Path(path).exists():
        return _empty_cache(), None
    try:
        cache = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        if isinstance(cache, dict) and cache.get("schema") == 1 and isinstance(cache.get("entries"), dict):
            return cache, None
    except (OSError, ValueError):
        pass
    return _empty_cache(), f"model-router cache at {path} was unreadable and has been rebuilt"


def _save_cache(path, cache: dict) -> None:
    if path is None:
        return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = {k: {f: v for f, v in e.items() if f in CACHE_FIELDS} for k, e in cache["entries"].items()}
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps({"schema": 1, "router": ROUTER, "entries": clean}, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    os.replace(tmp, path)


def _fresh(entry, now: datetime) -> bool:
    found = _parse((entry or {}).get("discovered_at"))
    return bool(found) and timedelta(0) <= now - found <= timedelta(days=TTL_DAYS)


# --- the route -------------------------------------------------------------------------------

def route(job: str, hints: dict, *, provider: str, credential_name: str, api_key: str,
          default_model: str | None, requested: str | None = None, fetch=None, cache_path=None,
          now: datetime | None = None, anthropic_version: str | None = None, env=None,
          registry: dict | None = None, record_applies: bool = True, backend: str | None = None) -> dict:
    """The model to send for `job`, with where the answer came from. Raises RouterError.

    `registry` is the plugin's shipped model registry (its `models` list). With no live list
    (offline, a timeout, provider trouble), the model about to be sent is checked against it
    and against the hint book's deprecations record for the provider: deprecated warns, past
    its shutdown refuses, the same contract as the live path; the stricter source wins.

    `record_applies=False` says that record describes another service than the one this call
    goes to (a Vertex AI run, for example: Vertex retires Gemini models on its own schedule).
    The record is then ignored for this call, live and offline, and no cache is used.

    `backend` names the service the request goes to when it isn't the provider's own API (default
    PROVIDER_BACKEND[provider]). It picks a registry entry's replacement for that service from its
    replacement_by_backend; a Vertex AI run passes backend="vertex" with record_applies=False."""
    env = os.environ if env is None else env
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if not isinstance(credential_name, str) or not CREDENTIAL_NAME.match(credential_name):
        raise RouterError("credential_name must be the NAME of the environment variable that holds the "
                          "key (for example ANTHROPIC_API_KEY), never the key itself")
    problems = validate_hints(hints)
    if problems:
        raise RouterError("hint book: " + "; ".join(problems))
    rule = hints["jobs"].get(job)
    if rule is None:
        raise RouterError(f"no hint-book rule for job {job!r}")
    if rule["provider"] != provider:
        raise RouterError(f"job {job!r} is for {rule['provider']!r}, not {provider!r}")
    adapter = ADAPTERS[provider]
    backend = backend or PROVIDER_BACKEND.get(provider)
    if not record_applies:
        # The record describes another service: ignore it everywhere, and keep this call's
        # answers out of a cache that record-based calls read.
        hints = {**hints, "deprecations": {k: v for k, v in (hints.get("deprecations") or {}).items() if k != provider}}
        cache_path = None
    base = {"job": job, "provider": provider, "line": rule.get("line"), "family": rule.get("family"),
            "model_requested": requested, "replacement": None, "router": ROUTER, "reason": None, "warnings": []}
    record = (hints.get("deprecations") or {}).get(provider)
    if record:
        age = (now.date() - date.fromisoformat(record["read_on"])).days
        if age > RECORD_RECHECK_DAYS:
            base["warnings"].append(f"the {provider} deprecations record was read {age} days ago; "
                                    f"re-read {record['source']} and update the hint book")
    held_hint = (f"re-read {record['source']} and add the missing release dates to the hint book's {provider} "
                 f"deprecations record" if adapter.get("dates_from_record") and record else None)

    if str(env.get(OFFLINE_ENV, "")).strip().lower() in ("1", "true", "yes"):
        return _offline(base, requested, default_model, f"{OFFLINE_ENV} is set", registry, now, record, backend)

    cache, cache_warning = _load_cache(cache_path)
    if cache_warning:
        base["warnings"].append(cache_warning)
    entries = cache["entries"]
    listed_key = f"{provider}|listed|{credential_name}"
    job_key = f"{provider}|job:{job}|{credential_name}"
    private = bool(requested and ":" in requested)  # a fine-tune's name stays out of the cache
    model_key = f"{provider}|model:{requested}|{credential_name}" if requested and not private else None
    if (_fresh(entries.get(listed_key), now) and job_key in entries
            and (not requested or (model_key and model_key in entries))):
        return _answer(base, entries[job_key], entries.get(model_key) if model_key else None, "cache",
                       now, held_hint)

    why = "cache unreadable" if cache_warning else ("cache stale" if listed_key in entries else "no cache")
    print(f"model-router: listing {provider} models for {credential_name} ({why})", file=sys.stderr)
    try:
        listed = (fetch or adapter["fetch"])(api_key, anthropic_version)
    except FetchError as exc:
        if exc.kind in ("auth", "http"):
            raise RouterError(f"{provider} refused the model-list call ({_scrub(exc.detail, api_key)}); "
                              f"check {credential_name}") from None
        return _offline(base, requested, default_model,
                        f"{provider} model list unavailable ({exc.kind}: {_scrub(exc.detail, api_key)})",
                        registry, now, record, backend)
    if not listed:
        raise RouterError(f"{provider} returned no models for {credential_name}; check the key's access")
    models, problem = adapter["normalize"](listed, hints, now)
    if problem:
        return _offline(base, requested, default_model, problem, registry, now, record, backend)

    source, stamp = adapter["source"], _iso(now)
    for key in [k for k in entries if k.startswith(f"{provider}|") and k.endswith(f"|{credential_name}")]:
        del entries[key]
    entries[listed_key] = {"discovered_at": stamp, "source": source, "counts": {"listed": len(models)}}
    for name, other in hints["jobs"].items():
        if other["provider"] != provider:
            continue
        best, counts = choose(models, other, now)
        entries[f"{provider}|job:{name}|{credential_name}"] = {
            "model": best["id"] if best else None, "lifecycle": best.get("lifecycle") if best else None,
            "retires_at": best.get("retires_at") if best else None, "line": other.get("line"),
            "discovered_at": stamp, "source": source, "counts": counts}
    asked = None
    if requested:
        asked = {"model": requested, "discovered_at": stamp, "source": source,
                 **adapter["requested"](requested, models, rule, hints, now)}
        if model_key:
            entries[model_key] = asked
    _save_cache(cache_path, cache)
    return _answer(base, entries[job_key], asked, "live", now, held_hint)


def registry_entry(registry: dict | None, model_id: str) -> tuple:
    """(entry, matched id) for a model in the shipped registry, or (None, None). An undated id
    matches its dated snapshot when exactly one exists (claude-sonnet-4-5 ->
    claude-sonnet-4-5-20250929: the vendor's alias convention)."""
    models = [m for m in (registry or {}).get("models", []) if isinstance(m, dict) and m.get("id")]
    exact = [m for m in models if m["id"] == model_id]
    if exact:
        return exact[0], model_id
    dated = [m for m in models if re.fullmatch(re.escape(model_id) + r"-\d{8}", m["id"])]
    return (dated[0], dated[0]["id"]) if len(dated) == 1 else (None, None)


SEVERITY = {"known": 0, "deprecated": 1, "redirected": 2, "retired": 3}


def registry_replacement(entry: dict, backend: str | None = None) -> str | None:
    """A registry entry's replacement for the service a request goes to: its replacement_by_backend
    entry for that backend, else its replacement_id (the default for one-id readers)."""
    return (entry.get("replacement_by_backend") or {}).get(backend) or entry.get("replacement_id")


def _registry_verdict(registry: dict | None, model: str, today: date, backend: str | None = None) -> dict | None:
    entry, matched = registry_entry(registry, model)
    if entry is None:
        return None
    shut = _parse(entry.get("shutdown_date"))
    when = shut.date() if shut else None
    kind = ("retired" if entry.get("status") == "retired" or (when and when <= today) else
            "deprecated" if entry.get("status") == "deprecated" or when else "known")
    return {"kind": kind, "shutdown": when, "replacement": registry_replacement(entry, backend),
            "shown": model if matched == model else f"{model} ({matched})", "source": "the shipped registry"}


def _record_verdict(provider: str, record: dict | None, model: str, today: date) -> dict | None:
    """What the hint book's deprecations record says about a model, read the way the live path
    reads it: Google's shut_down, redirects_to and earliest shutdown date; OpenAI's shutdown
    date (a fine-tune follows its base model)."""
    entry = ((record or {}).get("models") or {}).get(_google_id(model) if provider == "google" else _base_id(model))
    if not isinstance(entry, dict):
        return None
    shut = _parse(entry.get("shutdown"))
    when = shut.date() if shut else None
    if provider == "google":
        kind = {"active": "known"}.get(_google_lifecycle(entry), _google_lifecycle(entry))
    else:
        kind = "retired" if when and when <= today else "deprecated" if when else "known"
    return {"kind": kind, "shutdown": when, "replacement": entry.get("redirects_to") or entry.get("replacement"),
            "shown": model, "source": f"the hint book's {provider} deprecations record (read {record['read_on']})",
            "earliest": provider == "google"}


def _offline(base: dict, requested: str | None, default_model: str | None, reason: str,
             registry: dict | None = None, now: datetime | None = None, record: dict | None = None,
             backend: str | None = None) -> dict:
    """The shipped default or the named model, tagged offline. With no live list, the model is
    checked against the shipped registry AND the hint book's deprecations record (local data,
    shipped beside this file). The stricter of the two wins, and its message names its source."""
    model = requested or default_model
    if not model:
        raise RouterError(f"no model for job {base['job']!r}: {reason}, and there is no shipped default")
    out = {**base, "model": model, "basis": "offline", "offline": True, "reason": reason,
           "source": "shipped-default", "discovered_at": None, "counts": None,
           "warnings": list(base["warnings"])}
    today = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).date()
    found = [v for v in (_record_verdict(base["provider"], record, model, today),
                         _registry_verdict(registry, model, today, backend)) if v]
    if not found:
        if registry is not None:
            where = f" or the hint book's {base['provider']} deprecations record" if record else ""
            out["warnings"].append(f"{model} is not in the shipped registry{where}, so its lifecycle could not be "
                                   f"checked without the live list")
        return out
    # Stricter first: the more severe verdict, then the earlier shutdown; the record wins a tie.
    v = max(found, key=lambda x: (SEVERITY[x["kind"]], -(x["shutdown"] or date.max).toordinal()))
    shown, source, when = v["shown"], v["source"], v["shutdown"].isoformat() if v["shutdown"] else None
    instead = v["replacement"] or "a current model"
    if v["kind"] == "retired":
        raise RouterError(f"{shown} is retired{' (shut down ' + when + ')' if when else ''} according to "
                          f"{source}: requests naming it fail. Use {instead}.")
    if v["kind"] == "known":
        return out
    if requested:
        out["replacement"] = v["replacement"]
    if v["kind"] == "redirected":
        why = ("Sending it because it was asked for by name" if requested else "It is the shipped default")
        out["warnings"].append(f"{shown} is no longer served as itself according to {source}: {base['provider']} "
                               f"routes requests for it to {instead}. {why}; the answer will come from {instead}.")
        return out
    why = "Keeping it because it was asked for by name." if requested else "It is the shipped default."
    if v.get("earliest") and when and v["shutdown"] <= today:
        out["warnings"].append(f"{shown} is past its announced shutdown date ({when}) according to {source} and "
                               f"may stop working at any time; its replacement is {instead}. {why}")
    else:
        out["warnings"].append(f"{shown} is deprecated and retires {when or 'on a date not yet announced'} "
                               f"according to {source}; its replacement is {instead}. {why}")
    return out


def _answer(base: dict, chosen: dict, asked: dict | None, basis: str, now: datetime | None = None,
            held_hint: str | None = None) -> dict:
    out = {**base, "model": chosen.get("model"), "basis": basis, "offline": False,
           "source": chosen.get("source"), "discovered_at": chosen.get("discovered_at"),
           "counts": chosen.get("counts"), "warnings": list(base["warnings"])}
    if asked:
        requested, replacement = asked["model"], asked.get("replacement")
        out["replacement"] = replacement
        instead = replacement or "a current model"
        where = f"active {asked['line']} model" if asked.get("line") else "current model in the job's family"
        recorded = asked.get("replacement_from") == "record"
        if asked.get("lifecycle") == "retired":
            why = (f"the replacement {base['provider']}'s deprecations page names" if recorded
                   else f"the newest {where} this key can use")
            raise RouterError(f"{requested} is retired: requests naming it fail. Use {instead}, {why}.")
        if asked.get("lifecycle") == "deprecated":
            when = (asked.get("retires_at") or "")[:10]
            pick = (f"{base['provider']}'s deprecations page names {instead} as its replacement" if recorded
                    else f"the router would choose {instead}")
            if when and now and when <= now.date().isoformat():
                # Google's dates are the earliest possible shutdown; the page marks what is really off.
                out["warnings"].append(f"{requested} is past its announced shutdown date ({when}) and may stop "
                                       f"working at any time; {pick}. Keeping {requested} because it was asked "
                                       f"for by name.")
            else:
                out["warnings"].append(f"{requested} is deprecated and retires {when or 'on a date not yet announced'}; "
                                       f"{pick}. Keeping {requested} because it was asked for by name.")
        elif asked.get("lifecycle") == "redirected":
            out["warnings"].append(f"{requested} is no longer served as itself: {base['provider']} routes requests "
                                   f"for it to {instead}. Sending {requested} because it was asked for by name; "
                                   f"the answer will come from {instead}.")
        elif asked.get("lifecycle") == "unlisted":
            out["warnings"].append(f"{requested} is not in {base['provider']}'s model list for this key; "
                                   f"sending it anyway, without a lifecycle check.")
        out["model"], out["basis"] = requested, "requested"
        return out
    kind = f"{base['line']} model" if base.get("line") else "model in the job's family"
    held = (out.get("counts") or {}).get("held_undated")
    note = (f"{held} newer {kind}{'s' if held > 1 else ''} {'have' if held > 1 else 'has'} no known release "
            f"date, so the {MIN_GA_DAYS}-day rule cannot clear {'them' if held > 1 else 'it'} yet"
            + (f"; {held_hint}" if held_hint else "")) if held else None
    if not out["model"]:
        raise RouterError(f"no active, generally available {kind} at least {MIN_GA_DAYS} days old with the "
                          f"required capabilities is visible to this key" + (f" ({note})" if note else ""))
    if note:
        out["warnings"].append(note)
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Choose a model by job from the provider's live list.")
    p.add_argument("--hints", required=True, type=Path, help="the plugin's hint book (JSON)")
    p.add_argument("--job", required=True)
    p.add_argument("--provider", required=True, choices=sorted(ADAPTERS))
    p.add_argument("--credential-name", required=True, help="environment variable that holds the key")
    p.add_argument("--requested", help="a model asked for by name")
    p.add_argument("--default-model", help="the shipped default, used offline (default: the job's "
                                                "default_alias, resolved in the registry)")
    p.add_argument("--registry", type=Path, default=Path(__file__).resolve().parent / "model_registry.json",
                   help="the plugin's model registry (default: model_registry.json next to this file)")
    p.add_argument("--cache", type=Path, help="cache file (omit for no cache)")
    p.add_argument("--anthropic-version", default="2023-06-01")
    p.add_argument("--ignore-deprecations-record", action="store_true",
                   help="the hint book's deprecations record describes another service than this call's "
                        "(for example Vertex AI, which retires Gemini models on its own schedule)")
    p.add_argument("--backend", help="the service this call goes to, when it isn't the provider's own API "
                                     "(for example vertex); picks a registry entry's replacement for it")
    args = p.parse_args(argv)
    if not CREDENTIAL_NAME.match(args.credential_name):
        # Never echo it: a key pasted here by mistake must not reach the output.
        print(json.dumps({"error": "--credential-name must be the NAME of an environment variable "
                                   "(for example ANTHROPIC_API_KEY), not the key"}))
        return 2
    try:
        hints = json.loads(args.hints.read_text(encoding="utf-8-sig"))
        registry = (json.loads(args.registry.read_text(encoding="utf-8-sig"))
                    if args.registry and args.registry.is_file() else None)
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": f"cannot read the hint book or registry: {exc}"}))
        return 2
    default_model = args.default_model
    alias = ((hints.get("jobs") or {}).get(args.job) or {}).get("default_alias")
    if not default_model and registry and alias:
        default_model = (registry.get("aliases") or {}).get(alias)
    try:
        key = os.environ.get(args.credential_name, "")
        if not key and str(os.environ.get(OFFLINE_ENV, "")).strip().lower() not in ("1", "true", "yes"):
            raise RouterError(f"{args.credential_name} is not set")
        result = route(args.job, hints, provider=args.provider, credential_name=args.credential_name,
                       api_key=key, default_model=default_model, requested=args.requested,
                       cache_path=args.cache, anthropic_version=args.anthropic_version, registry=registry,
                       record_applies=not args.ignore_deprecations_record, backend=args.backend)
    except RouterError as exc:
        print(json.dumps({"error": exc.reason}))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
