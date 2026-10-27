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
At run time the router lists the models this key can use and picks, in the job's line or
family, the newest (highest version, then newest) model that is:
  * `active` (no shutdown announced, not retired);
  * generally available: no preview/exp/beta/alpha/rc id, no dated snapshot, no fine-tune;
  * at least MIN_GA_DAYS old (a brand-new release is never promoted on day one);
  * equipped with every capability the job's rule requires.
The registry stays as the fallback: offline, the caller's shipped default is used and the
answer is tagged "offline". Offline, the registry also stands in for the list's lifecycle
data: a model about to be sent that the registry marks deprecated warns, and one past its
shutdown is refused, as on the live path.

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
  header as the caller's generation call.
* MODEL_ROUTER_OFFLINE=1 makes no call at all.
* Deterministic: the same list on the same day gives the same answer. Learning from
  approvals belongs to a server, not to this file.

This file is copied byte for byte into each plugin that uses it; a parity test in each repo
keeps the copies identical. Stdlib only, Python 3.10+.

CLI (prints one JSON object; exit 0 chosen, 2 refused or bad input):
    python model_router.py --hints FILE --job JOB --provider anthropic|openai \\
        --credential-name NAME [--requested ID] [--default-model ID] \\
        [--cache FILE] [--anthropic-version VERSION]
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
OFFLINE_ENV = "MODEL_ROUTER_OFFLINE"
ANTHROPIC_MODELS_URL = "https://api.anthropic.com/v1/models"
OPENAI_MODELS_URL = "https://api.openai.com/v1/models"
LIFECYCLES = ("active", "deprecated", "retired")
NON_GA = re.compile(r"(?:^|[-_.])(?:preview|exp|experimental|beta|alpha|rc\d*)(?:$|[-_.])", re.I)
DATED_SNAPSHOT = re.compile(r"-\d{4}-\d{2}-\d{2}$")
CREDENTIAL_NAME = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
CACHE_FIELDS = frozenset({"model", "lifecycle", "retires_at", "line", "replacement",
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

def _get_json(req, opener, timeout: float, api_key: str) -> dict:
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
    if not isinstance(page, dict) or not isinstance(page.get("data"), list):
        raise FetchError("schema", "the model list had no data array")
    return page


def _error_text(exc: urllib.error.HTTPError) -> str:
    """The error's type and code only: providers echo part of a rejected key in the message."""
    try:
        err = json.loads(exc.read().decode("utf-8-sig")).get("error", {})
        return " ".join(str(err[k]) for k in ("type", "code") if err.get(k))
    except Exception:
        return ""


def _pages(first_url: str, headers: dict, api_key: str, cursor: str, timeout: float, urlopen,
           retry_without=None) -> list:
    opener = urlopen or urllib.request.urlopen
    out: list = []
    url, after = first_url, None
    for _ in range(20):
        full = url + (("&" if "?" in url else "?") + urllib.parse.urlencode({cursor: after}) if after else "")
        req = urllib.request.Request(full, method="GET")
        for name, value in headers.items():
            req.add_header(name, value)
        try:
            page = _get_json(req, opener, timeout, api_key)
        except FetchError as exc:
            if exc.code == 400 and retry_without and not out and url != retry_without:
                url = retry_without  # an API version without the filter: list without it
                continue
            raise
        out.extend(m for m in page["data"] if isinstance(m, dict) and isinstance(m.get("id"), str))
        if not page.get("has_more") or not page.get("last_id"):
            return out
        after = page["last_id"]
    return out


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


def _openai_record(hints: dict) -> dict:
    return ((hints.get("deprecations") or {}).get("openai") or {}).get("models") or {}


def _shutdown_lifecycle(shutdown, now: datetime) -> str:
    when = _parse(shutdown) if shutdown else None
    if not shutdown:
        return "active"
    return "retired" if when and when.date() <= now.date() else "deprecated"


def _norm_openai(raw: list, hints: dict, now: datetime) -> tuple:
    record, out = _openai_record(hints), []
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
    noted = _openai_record(hints).get(_base_id(requested), {})
    if found:
        lifecycle, retires = found["lifecycle"], found["retires_at"]
    elif noted.get("shutdown"):
        lifecycle, retires = _shutdown_lifecycle(noted["shutdown"], now), noted["shutdown"]
    else:
        lifecycle, retires = "unlisted", None
    replacement = noted.get("replacement")
    if not replacement:
        best, _ = choose(models, rule, now)
        replacement = best["id"] if best else None
    return {"lifecycle": lifecycle, "retires_at": retires, "line": None, "replacement": replacement}


ADAPTERS = {
    "anthropic": {"fetch": fetch_anthropic, "source": ANTHROPIC_MODELS_URL,
                  "normalize": _norm_anthropic, "requested": _requested_anthropic},
    "openai": {"fetch": fetch_openai, "source": OPENAI_MODELS_URL,
               "normalize": _norm_openai, "requested": _requested_openai},
}


# --- selection -------------------------------------------------------------------------------

def _not_promotable(model_id: str) -> bool:
    return bool(":" in model_id or NON_GA.search(model_id) or DATED_SNAPSHOT.search(model_id))


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
    eligible = [(m, v) for m, v in in_line
                if m.get("lifecycle") == "active" and not _not_promotable(m["id"])
                and (_parse(m.get("created_at")) or EPOCH) <= floor
                and _has_capabilities(m, rule.get("capabilities"))]
    eligible.sort(key=lambda mv: (mv[1], _parse(mv[0].get("created_at")) or EPOCH, mv[0]["id"]), reverse=True)
    counts = {"listed": len(models), "in_line": len(in_line), "eligible": len(eligible)}
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
            out += _date_problem(entry.get("shutdown"), f"{where}.{mid}", "shutdown")
            if not isinstance(entry.get("replacement"), str) or not entry["replacement"]:
                out.append(f"{where}.{mid}: replacement missing")
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
          registry: dict | None = None) -> dict:
    """The model to send for `job`, with where the answer came from. Raises RouterError.

    `registry` is the plugin's shipped model registry (its `models` list). With no live list
    (offline, a timeout, provider trouble), the model about to be sent is checked against it:
    deprecated warns, past its shutdown refuses, the same contract as the live path."""
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
    base = {"job": job, "provider": provider, "line": rule.get("line"), "family": rule.get("family"),
            "model_requested": requested, "replacement": None, "router": ROUTER, "reason": None, "warnings": []}
    record = (hints.get("deprecations") or {}).get(provider)
    if record:
        age = (now.date() - date.fromisoformat(record["read_on"])).days
        if age > RECORD_RECHECK_DAYS:
            base["warnings"].append(f"the {provider} deprecations record was read {age} days ago; "
                                    f"re-read {record['source']} and update the hint book")

    if str(env.get(OFFLINE_ENV, "")).strip().lower() in ("1", "true", "yes"):
        return _offline(base, requested, default_model, f"{OFFLINE_ENV} is set", registry, now)

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
        return _answer(base, entries[job_key], entries.get(model_key) if model_key else None, "cache")

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
                        registry, now)
    if not listed:
        raise RouterError(f"{provider} returned no models for {credential_name}; check the key's access")
    models, problem = adapter["normalize"](listed, hints, now)
    if problem:
        return _offline(base, requested, default_model, problem, registry, now)

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
    return _answer(base, entries[job_key], asked, "live")


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


def _offline(base: dict, requested: str | None, default_model: str | None, reason: str,
             registry: dict | None = None, now: datetime | None = None) -> dict:
    model = requested or default_model
    if not model:
        raise RouterError(f"no model for job {base['job']!r}: {reason}, and there is no shipped default")
    out = {**base, "model": model, "basis": "offline", "offline": True, "reason": reason,
           "source": "shipped-default", "discovered_at": None, "counts": None,
           "warnings": list(base["warnings"])}
    if registry is None:
        return out
    entry, matched = registry_entry(registry, model)
    if entry is None:
        out["warnings"].append(f"{model} is not in the shipped registry, so its lifecycle could not be checked "
                               f"without the live list")
        return out
    shown = model if matched == model else f"{model} ({matched})"
    replacement = entry.get("replacement_id") or "a current model"
    shut = _parse(entry.get("shutdown_date"))
    when = shut.date().isoformat() if shut else None
    today = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).date()
    if entry.get("status") == "retired" or (shut and shut.date() <= today):
        raise RouterError(f"{shown} is retired{' (shut down ' + when + ')' if when else ''} according to the "
                          f"shipped registry: requests naming it fail. Use {replacement}.")
    if entry.get("status") == "deprecated" or shut:
        if requested:
            out["replacement"] = entry.get("replacement_id")
        why = "Keeping it because it was asked for by name." if requested else "It is the shipped default."
        out["warnings"].append(f"{shown} is deprecated and retires {when or 'on a date not yet announced'} "
                               f"according to the shipped registry; its replacement is {replacement}. {why}")
    return out


def _answer(base: dict, chosen: dict, asked: dict | None, basis: str) -> dict:
    out = {**base, "model": chosen.get("model"), "basis": basis, "offline": False,
           "source": chosen.get("source"), "discovered_at": chosen.get("discovered_at"),
           "counts": chosen.get("counts"), "warnings": list(base["warnings"])}
    if asked:
        requested, replacement = asked["model"], asked.get("replacement")
        out["replacement"] = replacement
        instead = replacement or "a current model"
        where = f"active {asked['line']} model" if asked.get("line") else "current model in the job's family"
        if asked.get("lifecycle") == "retired":
            raise RouterError(f"{requested} is retired: requests naming it fail. Use {instead}, the newest "
                              f"{where} this key can use.")
        if asked.get("lifecycle") == "deprecated":
            when = (asked.get("retires_at") or "")[:10] or "on a date not yet announced"
            out["warnings"].append(f"{requested} is deprecated and retires {when}; the router would choose "
                                   f"{instead}. Keeping {requested} because it was asked for by name.")
        elif asked.get("lifecycle") == "unlisted":
            out["warnings"].append(f"{requested} is not in {base['provider']}'s model list for this key; "
                                   f"sending it anyway, without a lifecycle check.")
        out["model"], out["basis"] = requested, "requested"
        return out
    if not out["model"]:
        kind = f"{base['line']} model" if base.get("line") else "model in the job's family"
        raise RouterError(f"no active, generally available {kind} at least {MIN_GA_DAYS} days old with the "
                          f"required capabilities is visible to this key")
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
                       cache_path=args.cache, anthropic_version=args.anthropic_version, registry=registry)
    except RouterError as exc:
        print(json.dumps({"error": exc.reason}))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
