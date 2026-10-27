"""A model in both a hint-book deprecations record and the shipped registry must agree on its lifecycle.

Offline, the router reads both and the stricter one wins (3.39.1), so a disagreement never
sends a dead model. It still means one of the two files is wrong. On 2026-10-27 the registry
listed gpt-5.1 as "current" while the openai record, read from OpenAI's deprecations page
that day, shuts it down on 2027-04-01 with gpt-6-sol as the replacement.

For every id in both a record (hints["deprecations"][provider]["models"]) and the registry,
when the record says the model is deprecated, redirected or shut down (read the way the router
reads it, through model_router._record_verdict):
  1. the registry status is retired if the record says shut down, deprecated otherwise; never
     current or supported;
  2. the registry shutdown_date is the record's shutdown date (or both are absent);
  3. the registry's replacement for the backend the record describes (model_router.PROVIDER_BACKEND:
     the Gemini API for Google's page) is the record's replacement (Google's redirects_to first).
     That is replacement_by_backend[backend] when the entry has one, replacement_id otherwise.
     A row naming two, "a or b", accepts either;
  4. an OpenAI row's announced date is the registry deprecation_date.
A record row with no deprecation in it (a Google row with only a release date) is not checked:
the registry may know of a deprecation from another source, such as Google's changelog.
Ids only in a record stay out of the registry, since the router reads the record offline
(docs/MODEL-CURATOR.md). DMP_TODAY=YYYY-MM-DD freezes "today", as in test_model_registry_dates.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))

import model_router  # noqa: E402

HINTS = SCRIPTS / "model_hints.json"
REGISTRY = SCRIPTS / "model_registry.json"


def today() -> date:
    frozen = os.environ.get("DMP_TODAY")
    return date.fromisoformat(frozen) if frozen else date.today()


def _d(value):
    return date.fromisoformat(value[:10]) if value else None


def shared_ids(hints: dict, registry: dict) -> list[tuple[str, str]]:
    ids = {m["id"] for m in registry.get("models", [])}
    return sorted((provider, mid) for provider, record in (hints.get("deprecations") or {}).items()
                  for mid in (record.get("models") or {}) if mid in ids)


def disagreements(hints: dict, registry: dict, on: date) -> list[str]:
    out = []
    models = {m["id"]: m for m in registry.get("models", [])}
    for provider, mid in shared_ids(hints, registry):
        record = hints["deprecations"][provider]
        said = model_router._record_verdict(provider, record, mid, on)
        if said is None or said["kind"] == "known":
            continue
        entry, row = models[mid], record["models"][mid]
        source = f"the {provider} record (read {record.get('read_on')})"
        want = "retired" if said["kind"] == "retired" else "deprecated"
        status = entry.get("status", "current")
        if status != want:
            out.append(f"{mid}: {source} says {said['kind']}, the registry says {status}; make it {want}")
        if _d(entry.get("shutdown_date")) != said["shutdown"]:
            out.append(f"{mid}: registry shutdown_date {entry.get('shutdown_date')!r}, "
                       f"{source} {said['shutdown'] and said['shutdown'].isoformat()!r}")
        options = [r.strip() for r in (said["replacement"] or "").split(" or ") if r.strip()]
        backend = model_router.PROVIDER_BACKEND.get(provider)
        replacement = model_router.registry_replacement(entry, backend)
        if options and replacement not in options:
            field = (f"replacement_by_backend[{backend!r}]" if backend in (entry.get("replacement_by_backend") or {})
                     else "replacement_id")
            out.append(f"{mid}: registry {field} {replacement!r}, {source} {' or '.join(options)!r}")
        if row.get("announced") and entry.get("deprecation_date") != row["announced"]:
            out.append(f"{mid}: registry deprecation_date {entry.get('deprecation_date')!r}, "
                       f"{source} announced {row['announced']!r}")
    return out


def _openai(**rows) -> dict:
    return {"deprecations": {"openai": {"source": "https://developers.openai.com/api/docs/deprecations",
                                        "read_on": "2026-10-27", "models": rows}}}


def _google(**rows) -> dict:
    return {"deprecations": {"google": {"source": "https://ai.google.dev/gemini-api/docs/deprecations",
                                        "read_on": "2026-10-27", "models": rows}}}


GPT51 = {"announced": "2026-10-01", "shutdown": "2027-04-01", "replacement": "gpt-6-sol"}
GPT51_FIXED = {"id": "gpt-5.1", "status": "deprecated", "deprecation_date": "2026-10-01",
               "shutdown_date": "2027-04-01", "replacement_id": "gpt-6-sol"}
ON = date(2026, 10, 27)


class TestShippedFilesAgree(unittest.TestCase):

    def setUp(self):
        self.hints = json.loads(HINTS.read_text(encoding="utf-8-sig"))
        self.registry = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))

    def test_the_record_and_the_registry_agree_today(self):
        problems = disagreements(self.hints, self.registry, today())
        self.assertEqual(problems, [], "\n  " + "\n  ".join(problems))

    def test_there_is_something_to_compare(self):
        # An empty overlap would pass the test above without checking anything.
        self.assertIn(("openai", "gpt-5.1"), shared_ids(self.hints, self.registry))


class TestPlants(unittest.TestCase):

    def test_the_3_39_1_registry_lists_gpt_5_1_as_current(self):
        registry = {"models": [{"id": "gpt-5.1", "vendor": "evolink", "status": "current"}]}
        got = disagreements(_openai(**{"gpt-5.1": GPT51}), registry, ON)
        self.assertEqual(got, [
            "gpt-5.1: the openai record (read 2026-10-27) says deprecated, the registry says current; make it deprecated",
            "gpt-5.1: registry shutdown_date None, the openai record (read 2026-10-27) '2027-04-01'",
            "gpt-5.1: registry replacement_id None, the openai record (read 2026-10-27) 'gpt-6-sol'",
            "gpt-5.1: registry deprecation_date None, the openai record (read 2026-10-27) announced '2026-10-01'",
        ])

    def test_agreement_is_quiet(self):
        self.assertEqual(disagreements(_openai(**{"gpt-5.1": GPT51}), {"models": [GPT51_FIXED]}, ON), [])

    def test_supported_is_not_deprecated_either(self):
        registry = {"models": [{**GPT51_FIXED, "status": "supported"}]}
        got = disagreements(_openai(**{"gpt-5.1": GPT51}), registry, ON)
        self.assertEqual(len(got), 1)
        self.assertIn("the registry says supported; make it deprecated", got[0])

    def test_a_different_date_or_replacement(self):
        registry = {"models": [{**GPT51_FIXED, "shutdown_date": "2027-05-01", "replacement_id": "gpt-6.1-sol"}]}
        got = "\n".join(disagreements(_openai(**{"gpt-5.1": GPT51}), registry, ON))
        self.assertIn("registry shutdown_date '2027-05-01'", got)
        self.assertIn("registry replacement_id 'gpt-6.1-sol'", got)

    def test_past_the_openai_shutdown_the_registry_says_retired(self):
        got = disagreements(_openai(**{"gpt-5.1": GPT51}), {"models": [GPT51_FIXED]}, date(2027, 4, 2))
        self.assertEqual(len(got), 1)
        self.assertIn("says retired, the registry says deprecated; make it retired", got[0])

    def test_record_only_ids_are_not_asked_for(self):
        hints = _openai(**{"gpt-5.1": GPT51, "gpt-5.1-2025-11-13": GPT51})
        self.assertEqual(disagreements(hints, {"models": [GPT51_FIXED]}, ON), [])

    def test_google_redirect_and_shut_down_rows(self):
        hints = _google(**{
            "gemini-3.5-flash": {"released": "2026-05-19", "redirects_to": "gemini-3.6-flash"},
            "gemini-2.0-flash": {"released": "2025-02-05", "shutdown": "2026-06-01", "shut_down": True,
                                 "replacement": "gemini-3.6-flash"},
        })
        registry = {"models": [
            {"id": "gemini-3.5-flash", "status": "deprecated", "shutdown_date": "2026-11-01",
             "replacement_id": "gemini-3.7-flash"},
            {"id": "gemini-2.0-flash", "status": "deprecated", "shutdown_date": "2026-06-01",
             "replacement_id": "gemini-3.6-flash"},
        ]}
        got = "\n".join(disagreements(hints, registry, ON))
        self.assertIn("gemini-2.0-flash: the google record (read 2026-10-27) says retired, the registry says deprecated", got)
        self.assertIn("gemini-3.5-flash: registry shutdown_date '2026-11-01', the google record (read 2026-10-27) None", got)
        self.assertIn("gemini-3.5-flash: registry replacement_id 'gemini-3.7-flash', the google record (read 2026-10-27) 'gemini-3.6-flash'", got)

    def test_the_veo_preview_is_compared_on_the_gemini_api(self):
        # SocialForge's Google record with the 3.39.1 registry entry, which held one replacement_id
        # (Vertex AI's veo-3.1-generate-001) for an id the Gemini API retired.
        hints = _google(**{"veo-3.1-generate-preview": {"released": "2025-10-15", "shutdown": "2026-10-22",
                                                        "shut_down": True, "replacement": "gemini-omni-1.1-flash"}})
        old = {"id": "veo-3.1-generate-preview", "status": "retired", "shutdown_date": "2026-10-22",
               "replacement_id": "veo-3.1-generate-001"}
        self.assertEqual(disagreements(hints, {"models": [old]}, ON), [
            "veo-3.1-generate-preview: registry replacement_id 'veo-3.1-generate-001', "
            "the google record (read 2026-10-27) 'gemini-omni-1.1-flash'"])
        new = {**old, "replacement_by_backend": {"gemini-api": "gemini-omni-1.1-flash", "vertex": "veo-3.1-generate-001"}}
        self.assertEqual(disagreements(hints, {"models": [new]}, ON), [])
        wrong = {**old, "replacement_by_backend": {"gemini-api": "veo-3.1-generate-001"}}
        self.assertIn("registry replacement_by_backend['gemini-api'] 'veo-3.1-generate-001'",
                      disagreements(hints, {"models": [wrong]}, ON)[0])

    def test_google_two_replacements_and_rows_without_a_deprecation(self):
        hints = _google(**{
            "gemini-2.5-flash-preview-tts": {"released": "2025-05-20", "shutdown": "2026-11-17",
                                             "replacement": "gemini-3.8-flash-tts or gemini-3.8-flash-lite-tts"},
            "gemini-3.1-flash-image": {"released": "2026-05-28", "replacement": "gemini-nano-banana-2.1"},
        })
        registry = {"models": [
            {"id": "gemini-2.5-flash-preview-tts", "status": "deprecated", "shutdown_date": "2026-11-17",
             "replacement_id": "gemini-3.8-flash-lite-tts"},
            # Deprecated in Google's changelog, with no row on the deprecations page: not a disagreement.
            {"id": "gemini-3.1-flash-image", "status": "deprecated", "replacement_id": "gemini-nano-banana-2.1"},
        ]}
        self.assertEqual(disagreements(hints, registry, ON), [])


if __name__ == "__main__":
    unittest.main()
