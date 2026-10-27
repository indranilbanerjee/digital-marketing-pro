#!/usr/bin/env python3
"""model_router.py: choose a model by JOB from the provider's own live list, never by name.

WHY
---
A model id written into a plugin is a claim about the day it was written. The registry
(scripts/model_registry.json) made that claim reviewable; this module stops depending on it
for the decision. A job names a provider and a model LINE (for Anthropic, `line` is a field
of GET /v1/models: "do not infer a line from the id"). At run time the router lists the
models this key can use and picks the newest one in that line that is:
  * `active` (not deprecated, not retired);
  * generally available: no preview/exp/beta/alpha/rc id, no dated OpenAI-style snapshot;
  * at least MIN_GA_DAYS old (a brand-new release is never promoted on day one);
  * equipped with every capability the job's rule requires.
The registry stays as the hint book's fallback: offline, the caller's shipped default is
used and the answer is tagged "offline".

A model asked for by name is kept if it is active; kept with a warning if it is deprecated
(naming the retirement date and the model the router would pick); and refused, exit 2, if it
is retired, naming that replacement. Nothing is swapped silently.

LIMITS (the plan's rules 5, 8 and 10)
-------------------------------------
* Discovery happens only when a job needs a model and the cache is stale: never at install
  or import. One list call per provider and credential per TTL_DAYS serves every job in the
  hint book.
* The cache is keyed by provider, job and credential NAME (an environment variable name),
  never the key. It stores the chosen ids, their lifecycle dates and counts; never the list.
* The key goes only to its own vendor (ANTHROPIC_MODELS_URL), with the same
  anthropic-version header as the caller's generation call.
* MODEL_ROUTER_OFFLINE=1 makes no call at all.
* Deterministic: the same list on the same day gives the same answer. Learning from
  approvals belongs to a server, not to this file.

This file is copied byte for byte into each plugin that uses it; a parity test in each repo
keeps the copies identical. Stdlib only, Python 3.10+.

CLI (prints one JSON object; exit 0 chosen, 2 refused or bad input):
    python model_router.py --hints FILE --job JOB --provider anthropic \\
        --credential-name ANTHROPIC_API_KEY [--requested ID] [--default-model ID] \\
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
TIMEOUT_S = 10.0
OFFLINE_ENV = "MODEL_ROUTER_OFFLINE"
ANTHROPIC_MODELS_URL = "https://api.anthropic.com/v1/models"
LIFECYCLES = ("active", "deprecated", "retired")
NON_GA = re.compile(r"(?:^|[-_.])(?:preview|exp|experimental|beta|alpha|rc\d*)(?:$|[-_.])", re.I)
DATED_SNAPSHOT = re.compile(r"-\d{4}-\d{2}-\d{2}$")
CREDENTIAL_NAME = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
CACHE_FIELDS = frozenset({"model", "lifecycle", "retires_at", "line", "replacement",
                          "discovered_at", "source", "counts"})
RULE_REQUIRED = ("provider", "line", "source", "read_on")
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


class RouterError(Exception):
    """The router refuses: the caller must not send a request. exit_code is for CLIs."""

    def __init__(self, reason: str, exit_code: int = 2):
        super().__init__(reason)
        self.reason, self.exit_code = reason, exit_code


class FetchError(Exception):
    """A list call failed. kind: auth | http | unavailable | timeout | network | schema."""

    def __init__(self, kind: str, detail: str):
        super().__init__(f"{kind}: {detail}")
        self.kind, self.detail = kind, detail


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(stamp) -> datetime | None:
    """RFC 3339 to an aware datetime; Python 3.10's fromisoformat takes no 'Z'."""
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


# --- the Anthropic adapter ---------------------------------------------------------------

def fetch_anthropic(api_key: str, anthropic_version: str | None, *, timeout: float = TIMEOUT_S,
                    urlopen=None) -> list:
    """Every model this key can see, retired ones included, across pages."""
    opener = urlopen or urllib.request.urlopen
    out: list = []
    after, with_lifecycle = None, True
    for _ in range(20):
        params = [("limit", "1000")]
        if with_lifecycle:
            params += [("lifecycle[]", stage) for stage in LIFECYCLES]
        if after:
            params.append(("after_id", after))
        req = urllib.request.Request(ANTHROPIC_MODELS_URL + "?" + urllib.parse.urlencode(params), method="GET")
        req.add_header("x-api-key", api_key)
        if anthropic_version:
            req.add_header("anthropic-version", anthropic_version)
        try:
            with opener(req, timeout=timeout) as resp:
                page = json.loads(resp.read().decode("utf-8-sig"))
        except urllib.error.HTTPError as exc:
            detail = _scrub(f"HTTP {exc.code} {_error_text(exc)}".strip(), api_key)
            if exc.code == 400 and with_lifecycle and not out:
                # An API version without the lifecycle filter: list without it (retired
                # models then go unlisted, and a retired id asked for by name reads as unlisted).
                with_lifecycle = False
                continue
            if exc.code in (401, 403):
                raise FetchError("auth", detail) from None
            if exc.code == 429 or exc.code >= 500:
                raise FetchError("unavailable", detail) from None
            raise FetchError("http", detail) from None
        except (TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            kind = "timeout" if isinstance(reason, TimeoutError) or "timed out" in str(reason) else "network"
            raise FetchError(kind, _scrub(str(reason), api_key)) from None
        except ValueError:
            raise FetchError("schema", "the model list was not JSON") from None
        if not isinstance(page, dict) or not isinstance(page.get("data"), list):
            raise FetchError("schema", "the model list had no data array")
        out.extend(m for m in page["data"] if isinstance(m, dict) and isinstance(m.get("id"), str))
        if not page.get("has_more") or not page.get("last_id"):
            return out
        after = page["last_id"]
    return out


def _error_text(exc: urllib.error.HTTPError) -> str:
    try:
        body = json.loads(exc.read().decode("utf-8-sig"))
        err = body.get("error", {})
        return f"{err.get('type', '')}: {str(err.get('message', ''))[:200]}".strip(": ")
    except Exception:
        return ""


ADAPTERS = {"anthropic": fetch_anthropic}


# --- selection ---------------------------------------------------------------------------

def _non_ga(model_id: str) -> bool:
    return bool(NON_GA.search(model_id) or DATED_SNAPSHOT.search(model_id))


def _has_capabilities(model: dict, required) -> bool:
    for path in required or ():
        node = model.get("capabilities")
        for part in path.split("."):
            node = node.get(part) if isinstance(node, dict) else None
        if not (isinstance(node, dict) and node.get("supported") is True):
            return False
    return True


def choose(listed: list, line: str, capabilities, now: datetime) -> tuple:
    """(best model dict or None, counts) for one line."""
    in_line = [m for m in listed if m.get("line") == line]
    floor = now - timedelta(days=MIN_GA_DAYS)
    eligible = [m for m in in_line
                if m.get("lifecycle") == "active" and not _non_ga(m["id"])
                and (_parse(m.get("created_at")) or EPOCH) <= floor
                and _has_capabilities(m, capabilities)]
    eligible.sort(key=lambda m: (_parse(m.get("created_at")) or EPOCH, m["id"]), reverse=True)
    counts = {"listed": len(listed), "in_line": len(in_line), "eligible": len(eligible)}
    return (eligible[0] if eligible else None), counts


def validate_hints(hints) -> list:
    """Problems with a hint book; every rule carries its source and the date it was read."""
    if not isinstance(hints, dict) or hints.get("schema") != 1 or not isinstance(hints.get("jobs"), dict):
        return ["hint book must be {\"schema\": 1, \"jobs\": {...}}"]
    out = []
    for job, rule in sorted(hints["jobs"].items()):
        if not isinstance(rule, dict):
            out.append(f"{job}: rule must be an object")
            continue
        for field in RULE_REQUIRED:
            if not isinstance(rule.get(field), str) or not rule[field].strip():
                out.append(f"{job}: {field} missing")
        if isinstance(rule.get("source"), str) and rule["source"] and not rule["source"].startswith("https://"):
            out.append(f"{job}: source must be an https URL")
        if isinstance(rule.get("read_on"), str) and rule["read_on"]:
            try:
                date.fromisoformat(rule["read_on"])
            except ValueError:
                out.append(f"{job}: read_on must be YYYY-MM-DD")
        caps = rule.get("capabilities", [])
        if not isinstance(caps, list) or not all(isinstance(c, str) for c in caps):
            out.append(f"{job}: capabilities must be a list of names")
    return out


# --- cache -------------------------------------------------------------------------------

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


# --- the route ---------------------------------------------------------------------------

def route(job: str, hints: dict, *, provider: str, credential_name: str, api_key: str,
          default_model: str | None, requested: str | None = None, fetch=None, cache_path=None,
          now: datetime | None = None, anthropic_version: str | None = None, env=None) -> dict:
    """The model to send for `job`, with where the answer came from. Raises RouterError."""
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
    if rule["provider"] != provider or provider not in ADAPTERS:
        raise RouterError(f"job {job!r} is for {rule['provider']!r}; no {provider!r} adapter here")
    base = {"job": job, "provider": provider, "line": rule["line"], "model_requested": requested,
            "replacement": None, "router": ROUTER, "reason": None, "warnings": []}

    if str(env.get(OFFLINE_ENV, "")).strip().lower() in ("1", "true", "yes"):
        return _offline(base, requested or default_model, f"{OFFLINE_ENV} is set")

    cache, cache_warning = _load_cache(cache_path)
    if cache_warning:
        base["warnings"].append(cache_warning)
    entries = cache["entries"]
    listed_key = f"{provider}|listed|{credential_name}"
    job_key = f"{provider}|job:{job}|{credential_name}"
    model_key = f"{provider}|model:{requested}|{credential_name}" if requested else None
    if _fresh(entries.get(listed_key), now) and job_key in entries and (not model_key or model_key in entries):
        return _answer(base, entries, job_key, model_key, "cache")

    why = "cache unreadable" if cache_warning else ("cache stale" if listed_key in entries else "no cache")
    print(f"model-router: listing {provider} models for {credential_name} ({why})", file=sys.stderr)
    try:
        listed = (fetch or ADAPTERS[provider])(api_key, anthropic_version)
    except FetchError as exc:
        if exc.kind in ("auth", "http"):
            raise RouterError(f"{provider} refused the model-list call ({_scrub(exc.detail, api_key)}); "
                              f"check {credential_name}") from None
        return _offline(base, requested or default_model,
                        f"{provider} model list unavailable ({exc.kind}: {_scrub(exc.detail, api_key)})")
    if not listed:
        raise RouterError(f"{provider} returned no models for {credential_name}; check the key's access")
    if any("lifecycle" not in m for m in listed):
        return _offline(base, requested or default_model,
                        "the model list has no lifecycle field, so deprecation cannot be checked")

    source, stamp = ADAPTER_SOURCE[provider], _iso(now)
    for key in [k for k in entries if k.startswith(f"{provider}|") and k.endswith(f"|{credential_name}")]:
        del entries[key]
    entries[listed_key] = {"discovered_at": stamp, "source": source, "counts": {"listed": len(listed)}}
    for name, other in hints["jobs"].items():
        if other["provider"] != provider:
            continue
        best, counts = choose(listed, other["line"], other.get("capabilities"), now)
        entries[f"{provider}|job:{name}|{credential_name}"] = {
            "model": best["id"] if best else None, "lifecycle": best.get("lifecycle") if best else None,
            "retires_at": best.get("retires_at") if best else None, "line": other["line"],
            "discovered_at": stamp, "source": source, "counts": counts}
    if requested:
        found = next((m for m in listed if m["id"] == requested), None)
        line = (found or {}).get("line") or rule["line"]
        replacement, _ = choose(listed, line, rule.get("capabilities"), now)
        entries[model_key] = {"model": requested, "lifecycle": (found or {}).get("lifecycle", "unlisted"),
                              "retires_at": (found or {}).get("retires_at"), "line": line,
                              "replacement": replacement["id"] if replacement else None,
                              "discovered_at": stamp, "source": source}
    _save_cache(cache_path, cache)
    return _answer(base, entries, job_key, model_key, "live")


ADAPTER_SOURCE = {"anthropic": ANTHROPIC_MODELS_URL}


def _offline(base: dict, model: str | None, reason: str) -> dict:
    if not model:
        raise RouterError(f"no model for job {base['job']!r}: {reason}, and there is no shipped default")
    return {**base, "model": model, "basis": "offline", "offline": True, "reason": reason,
            "source": "shipped-default", "discovered_at": None, "counts": None}


def _answer(base: dict, entries: dict, job_key: str, model_key: str | None, basis: str) -> dict:
    chosen = entries[job_key]
    out = {**base, "model": chosen.get("model"), "basis": basis, "offline": False,
           "source": chosen.get("source"), "discovered_at": chosen.get("discovered_at"),
           "counts": chosen.get("counts"), "warnings": list(base["warnings"])}
    if model_key:
        asked = entries[model_key]
        requested, replacement = asked["model"], asked.get("replacement")
        out["replacement"] = replacement
        instead = replacement or "a current model"
        if asked.get("lifecycle") == "retired":
            raise RouterError(f"{requested} is retired: requests naming it fail. Use {instead}, the newest "
                              f"active {asked.get('line')} model this key can use.")
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
        raise RouterError(f"no active, generally available {base['line']} model at least {MIN_GA_DAYS} days "
                          f"old with the required capabilities is visible to this key")
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Choose a model by job from the provider's live list.")
    p.add_argument("--hints", required=True, type=Path, help="the plugin's hint book (JSON)")
    p.add_argument("--job", required=True)
    p.add_argument("--provider", required=True, choices=sorted(ADAPTERS))
    p.add_argument("--credential-name", required=True, help="environment variable that holds the key")
    p.add_argument("--requested", help="a model asked for by name")
    p.add_argument("--default-model", help="the shipped default, used offline")
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
        key = os.environ.get(args.credential_name, "")
        if not key and str(os.environ.get(OFFLINE_ENV, "")).strip().lower() not in ("1", "true", "yes"):
            raise RouterError(f"{args.credential_name} is not set")
        result = route(args.job, hints, provider=args.provider, credential_name=args.credential_name,
                       api_key=key, default_model=args.default_model, requested=args.requested,
                       cache_path=args.cache, anthropic_version=args.anthropic_version)
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": f"cannot read the hint book: {exc}"}))
        return 2
    except RouterError as exc:
        print(json.dumps({"error": exc.reason}))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
