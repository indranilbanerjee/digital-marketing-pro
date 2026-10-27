#!/usr/bin/env python3
"""
refresh_models.py — Poll provider APIs and report drift against the registry.

Reads model_registry.json, calls the provider list endpoints where available,
and prints:
  • Models in the provider catalog that are NOT in the registry (additions to triage)
  • Models in the registry marked "current" that the provider no longer lists
  • Models in the registry marked "deprecated" that the provider has stopped serving
  • A simple summary + next_review_due reminder

By default this is REPORT-ONLY. Pass --bump-timestamp to update last_updated
to today after a manual review pass. The script never silently rewrites model
entries; curation is a human decision.

Requires (per provider) one or more of:
  ANTHROPIC_API_KEY   — calls https://api.anthropic.com/v1/models
  OPENAI_API_KEY      — calls https://api.openai.com/v1/models
  GEMINI_API_KEY      — calls https://generativelanguage.googleapis.com/v1beta/models
  EVOLINK_API_KEY     — calls https://direct.evolink.ai/v1/models

Every list is read to its last page (Anthropic's default page is 20 models, Google's 50), and
each key goes only in its provider's header: never in a URL, where proxies and server logs
keep it, and never in the output. The Anthropic, OpenAI and Google readers are the model
router's own (scripts/model_router.py), so both tools list models the same way. A refused
call is reported by its HTTP status alone, because providers echo part of a rejected key in
their error messages.

Usage:
    python refresh_models.py            # report drift
    python refresh_models.py --json     # machine-readable
    python refresh_models.py --bump-timestamp  # set last_updated to today
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resolve_model import _find_registry, get_registry  # noqa: E402
from model_router import FetchError, fetch_anthropic, fetch_google, fetch_openai  # noqa: E402

EVOLINK_MODELS_URL = "https://direct.evolink.ai/v1/models"
TIMEOUT_S = 15


def list_anthropic(urlopen=None) -> set[str] | None:
    """Live Anthropic models, every page. The router's reader also lists retired models (with
    their lifecycle), so those are left out here: a retired model is not live."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    models = fetch_anthropic(key, "2023-06-01", timeout=TIMEOUT_S, urlopen=urlopen)
    return {m["id"] for m in models if m.get("lifecycle") != "retired"}


def list_openai(urlopen=None) -> set[str] | None:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return None
    return {m["id"] for m in fetch_openai(key, timeout=TIMEOUT_S, urlopen=urlopen)}


def list_gemini(urlopen=None) -> set[str] | None:
    """Every page, the key in the x-goog-api-key header (never `?key=` in the URL)."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    return {m["name"].replace("models/", "", 1) for m in fetch_google(key, timeout=TIMEOUT_S, urlopen=urlopen)}


def list_evolink(urlopen=None) -> set[str] | None:
    """Evolink's docs (index read 2026-10-27) do not describe this endpoint. It answers in
    OpenAI's shape, so it is read the same way: one page, or more while has_more and
    last_id say there is another."""
    key = os.environ.get("EVOLINK_API_KEY")
    if not key:
        return None
    opener = urlopen or urllib.request.urlopen
    ids: set[str] = set()
    after = None
    for _ in range(20):
        url = EVOLINK_MODELS_URL + ("?" + urllib.parse.urlencode({"after": after}) if after else "")
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
        try:
            with opener(req, timeout=TIMEOUT_S) as resp:
                page = json.loads(resp.read().decode("utf-8-sig"))
        except urllib.error.HTTPError as exc:
            raise FetchError("http", f"HTTP {exc.code}", exc.code) from None  # the body may echo the key
        except (OSError, ValueError) as exc:
            raise FetchError("network", type(exc).__name__) from None
        if not isinstance(page, dict) or not isinstance(page.get("data"), list):
            raise FetchError("schema", "the model list had no data array")
        ids |= {m["id"] for m in page["data"] if isinstance(m, dict) and isinstance(m.get("id"), str)}
        after = page.get("has_more") and page.get("last_id")
        if not after:
            break
    return ids


def diff(registry_ids: set[str], live_ids: set[str]) -> dict[str, list[str]]:
    return {
        "missing_from_registry": sorted(live_ids - registry_ids),
        "missing_from_live": sorted(registry_ids - live_ids),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Report model-registry drift")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--bump-timestamp",
        action="store_true",
        help="Set last_updated to today (use after a manual curation pass)",
    )
    args = parser.parse_args()

    reg = get_registry()
    reg_path = _find_registry()
    by_vendor: dict[str, set[str]] = {}
    for m in reg.get("models", []):
        by_vendor.setdefault(m.get("vendor", ""), set()).add(m.get("id"))

    report: dict[str, dict] = {
        "registry_path": str(reg_path),
        "registry_last_updated": reg.get("last_updated"),
        "registry_next_review_due": reg.get("next_review_due"),
    }

    for vendor, fetcher in (
        ("anthropic", list_anthropic),
        ("openai", list_openai),
        ("google", list_gemini),
        ("evolink", list_evolink),
    ):
        try:
            live = fetcher()
        except FetchError as exc:
            # kind plus HTTP status (and Google's status name) only: never a provider's message.
            report[vendor] = {"status": f"skipped (fetch failed: {exc.kind}: {exc.detail})"}
            continue
        if live is None:
            report[vendor] = {"status": "skipped (no API key)"}
            continue
        d = diff(by_vendor.get(vendor, set()), live)
        report[vendor] = {
            "status": "checked",
            "live_count": len(live),
            "registry_count": len(by_vendor.get(vendor, set())),
            **d,
        }

    if args.bump_timestamp:
        reg["last_updated"] = date.today().isoformat()
        reg_path.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
        report["timestamp_bumped"] = reg["last_updated"]

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"Registry: {report['registry_path']}")
        print(f"Last updated: {report['registry_last_updated']}  "
              f"(next review due: {report['registry_next_review_due']})")
        if "timestamp_bumped" in report:
            print(f"  -> timestamp bumped to {report['timestamp_bumped']}")
        for v in ("anthropic", "openai", "google", "evolink"):
            r = report.get(v, {})
            print(f"\n{v.upper()}: {r.get('status')}")
            if r.get("status") == "checked":
                if r["missing_from_registry"]:
                    print(f"  NEW (not in registry, may need to add):")
                    for m in r["missing_from_registry"]:
                        print(f"    + {m}")
                if r["missing_from_live"]:
                    print(f"  STALE (in registry, not in provider list):")
                    for m in r["missing_from_live"]:
                        print(f"    - {m}")
                if not r["missing_from_registry"] and not r["missing_from_live"]:
                    print("  no drift")
    return 0


if __name__ == "__main__":
    sys.exit(main())
