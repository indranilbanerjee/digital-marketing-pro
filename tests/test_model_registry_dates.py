"""The model registry's dates and statuses must agree with each other and with today.

The failures this prevents (all found in the 2026-10-04 registry on 2026-10-27):
  * latest-fast-anthropic pointed at Claude Haiku 4.5 three weeks after Haiku 5.5
    shipped, with a note saying no Haiku 5.x existed;
  * gemini-2.5-flash-image was marked "retired 2026-10-02": that was its RELEASE date
    (its shutdown is 2027-03-15);
  * Gemini 2.5 was marked deprecated with a 2026-10-16 shutdown the vendor page no
    longer showed;
  * veo-3.0 entries fell forward to a preview id that had itself shut down.

Rules (dates are ISO strings; DMP_TODAY=YYYY-MM-DD freezes "today" for planting):
  1. A `current`/`supported` entry with a `shutdown_date` on or before today is wrong:
     mark it retired. A `deprecated` entry past its `shutdown_date`: same.
  2. A `current`/`supported` entry past its `tentative_retirement` ("not sooner than")
     must carry `retirement_checked` on or after that date and at most RECHECK_DAYS old.
  3. No alias may point at a deprecated or retired id, or at one whose `shutdown_date`
     is within SHUTDOWN_WARN_DAYS.
  4. Every deprecated/retired entry's `replacement_id` exists and is current or supported.
  5. A retired entry is dropped DROP_AFTER_DAYS after its shutdown date.
  6. `next_review_due` is not in the past.
  7. Kinds no vendor list endpoint can discover (text-to-speech, speech-to-text) are PINS:
     each entry carries `pinned_on` and `pin_expires`, at most PIN_MAX_DAYS apart, and
     fails once `pin_expires` passes, so someone re-reads the vendor page and re-pins.
The weekly dated-checks job runs this file.
"""
from __future__ import annotations

import json
import os
import unittest
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REGISTRY = REPO / "scripts" / "model_registry.json"

RECHECK_DAYS = 30
SHUTDOWN_WARN_DAYS = 30
DROP_AFTER_DAYS = 120
LIVE = {"current", "supported"}
PINNED_TIERS = {"text-to-speech", "speech-to-text"}
PIN_MAX_DAYS = 92


def today() -> date:
    frozen = os.environ.get("DMP_TODAY")
    return date.fromisoformat(frozen) if frozen else date.today()


def _d(value):
    return date.fromisoformat(value[:10]) if value else None


def registry_problems(reg: dict, on: date) -> list[str]:
    out = []
    models = {m["id"]: m for m in reg["models"]}
    for mid, m in models.items():
        status = m.get("status", "current")
        shut, floor, checked = _d(m.get("shutdown_date")), _d(m.get("tentative_retirement")), _d(m.get("retirement_checked"))
        if status in LIVE | {"deprecated"} and shut and shut <= on:
            out.append(f"{mid}: {status} but shut down {shut}; mark it retired")
        if status in LIVE and floor and floor < on:
            if not checked or checked < floor:
                out.append(f"{mid}: past its retirement floor {floor} with no retirement_checked on or after it")
            elif (on - checked).days > RECHECK_DAYS:
                out.append(f"{mid}: retirement floor {floor} passed; last checked {checked}, over {RECHECK_DAYS} days ago")
        if status in {"deprecated", "retired"}:
            rep = m.get("replacement_id")
            if not rep or rep not in models:
                out.append(f"{mid}: {status} with replacement {rep!r} missing from the registry")
            elif models[rep].get("status", "current") not in LIVE:
                out.append(f"{mid}: falls forward to {rep}, which is {models[rep].get('status')}")
        if status == "retired" and shut and (on - shut).days > DROP_AFTER_DAYS:
            out.append(f"{mid}: retired {shut}, over {DROP_AFTER_DAYS} days ago; drop it")
        pinned, expires = _d(m.get("pinned_on")), _d(m.get("pin_expires"))
        if m.get("tier") in PINNED_TIERS and not (pinned and expires):
            out.append(f"{mid}: {m['tier']} is a pinned kind; give it pinned_on and pin_expires")
        elif expires and expires < on:
            out.append(f"{mid}: pin expired {expires}; re-read {m.get('docs_url', 'the vendor page')} and re-pin")
        elif pinned and expires and (expires - pinned).days > PIN_MAX_DAYS:
            out.append(f"{mid}: pin runs {(expires - pinned).days} days; at most {PIN_MAX_DAYS}")
    for alias, target in reg.get("aliases", {}).items():
        m = models.get(target)
        if m is None:
            out.append(f"alias {alias}: target {target} missing")
            continue
        if m.get("status", "current") not in LIVE:
            out.append(f"alias {alias}: points at {target}, which is {m.get('status')}")
        shut = _d(m.get("shutdown_date"))
        if shut and shut - on <= timedelta(days=SHUTDOWN_WARN_DAYS):
            out.append(f"alias {alias}: {target} shuts down {shut}; repoint it")
    due = _d(reg.get("next_review_due"))
    if not due or due < on:
        out.append(f"next_review_due {reg.get('next_review_due')!r} has passed; review the registry")
    return out


class TestRegistryDates(unittest.TestCase):

    def test_registry_is_consistent_today(self):
        reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
        problems = registry_problems(reg, today())
        self.assertEqual(problems, [], "\n  " + "\n  ".join(problems))

    def test_plants_from_the_2026_10_04_registry(self):
        old = {
            "next_review_due": "2026-11-01",
            "aliases": {"latest-fast-anthropic": "claude-haiku-4-5-20251001",
                        "latest-image-balanced-google": "gemini-3.1-flash-image"},
            "models": [
                # Haiku 4.5: floor passed, nobody re-checked
                {"id": "claude-haiku-4-5-20251001", "status": "current", "tentative_retirement": "2026-10-15"},
                # Nano Banana 2 deprecated on 2026-10-06 but still the alias target
                {"id": "gemini-3.1-flash-image", "status": "deprecated", "replacement_id": "gemini-nano-banana-2.1"},
                {"id": "gemini-nano-banana-2.1", "status": "current"},
                # veo-3.0 falling forward to a retired preview
                {"id": "veo-3.1-generate-preview", "status": "retired", "shutdown_date": "2026-10-22",
                 "replacement_id": "veo-3.1-generate-001"},
                {"id": "veo-3.1-generate-001", "status": "current"},
                {"id": "veo-3.0-generate-001", "status": "retired", "shutdown_date": "2026-06-30",
                 "replacement_id": "veo-3.1-generate-preview"},
                # deprecated with a shutdown that passed
                {"id": "gemini-2.5-flash", "status": "deprecated", "shutdown_date": "2026-10-16",
                 "replacement_id": "gemini-nano-banana-2.1"},
            ],
        }
        problems = registry_problems(old, date(2026, 11, 20))
        joined = "\n".join(problems)
        for expected in ("claude-haiku-4-5-20251001: past its retirement floor",
                         "alias latest-image-balanced-google: points at gemini-3.1-flash-image",
                         "veo-3.0-generate-001: falls forward to veo-3.1-generate-preview",
                         "gemini-2.5-flash: deprecated but shut down",
                         "veo-3.0-generate-001: retired 2026-06-30, over",
                         "next_review_due"):
            self.assertIn(expected, joined)

    def test_recheck_and_shutdown_windows(self):
        reg = {"next_review_due": "2027-01-01", "aliases": {"a": "x"},
               "models": [{"id": "x", "status": "current", "shutdown_date": "2026-11-20"},
                          {"id": "y", "status": "supported", "tentative_retirement": "2026-10-15",
                           "retirement_checked": "2026-10-27"}]}
        self.assertEqual(registry_problems(reg, date(2026, 10, 1)), [])
        late = "\n".join(registry_problems(reg, date(2026, 11, 30)))
        self.assertIn("alias a: x shuts down", late)
        self.assertIn("y: retirement floor 2026-10-15 passed; last checked 2026-10-27", late)


RECORD_FAIL_DAYS = 45


def record_problems(hints: dict, on: date) -> list[str]:
    """The router's hand-read lifecycle records (scripts/model_hints.json 'deprecations') go
    stale like any pin: the router warns after 30 days, this weekly check fails after 45."""
    out = []
    for provider, record in (hints.get("deprecations") or {}).items():
        age = (on - date.fromisoformat(record["read_on"])).days
        if age > RECORD_FAIL_DAYS:
            out.append(f"deprecations.{provider} read {record['read_on']}, {age} days ago; re-read {record['source']}")
    return out


class TestRouterRecords(unittest.TestCase):

    def test_deprecation_records_are_fresh(self):
        hints = json.loads((REPO / "scripts" / "model_hints.json").read_text(encoding="utf-8"))
        problems = record_problems(hints, today())
        self.assertEqual(problems, [], "\n  " + "\n  ".join(problems))

    def test_plant(self):
        hints = {"deprecations": {"openai": {"read_on": "2026-10-27", "source": "https://x"}}}
        self.assertEqual(record_problems(hints, date(2026, 12, 11)), [])
        self.assertIn("46 days ago", "\n".join(record_problems(hints, date(2026, 12, 12))))


class TestSpeechPins(unittest.TestCase):
    """Speech kinds were hardcoded in CutForge (gpt-4o-mini-tts, whisper-1, saarika:v2.5), and all
    three were deprecated by 2026-10-27 with nothing in the suite to say so. No list endpoint
    tells a speech model from a chat model, so these entries are pins that expire."""

    def setUp(self):
        self.reg = json.loads(REGISTRY.read_text(encoding="utf-8"))

    def test_every_speech_kind_has_an_alias_per_vendor(self):
        for kind in ("tts", "stt"):
            for vendor in ("openai", "elevenlabs", "sarvam"):
                self.assertIn(f"latest-{kind}-{vendor}", self.reg["aliases"])

    def test_speech_aliases_resolve_to_their_kind(self):
        models = {m["id"]: m for m in self.reg["models"]}
        tier = {"tts": "text-to-speech", "stt": "speech-to-text"}
        for alias, target in self.reg["aliases"].items():
            kind = alias.split("-")[1]
            if kind in tier:
                self.assertEqual(models[target]["tier"], tier[kind], alias)

    def test_plants(self):
        base = {"next_review_due": "2027-06-01", "aliases": {}}
        unpinned = dict(base, models=[{"id": "t", "status": "current", "tier": "text-to-speech"}])
        self.assertIn("t: text-to-speech is a pinned kind",
                      "\n".join(registry_problems(unpinned, date(2026, 10, 27))))
        pinned = dict(base, models=[{"id": "t", "status": "current", "tier": "speech-to-text",
                                     "pinned_on": "2026-10-27", "pin_expires": "2027-01-25"}])
        self.assertEqual(registry_problems(pinned, date(2027, 1, 25)), [])
        self.assertIn("t: pin expired 2027-01-25",
                      "\n".join(registry_problems(pinned, date(2027, 1, 26))))
        forever = dict(base, models=[dict(pinned["models"][0], pin_expires="2099-01-01")])
        self.assertIn("at most 92",
                      "\n".join(registry_problems(forever, date(2026, 10, 27))))


class TestCuratorDocMatchesRegistry(unittest.TestCase):
    """docs/MODEL-CURATOR.md's alias table said Haiku 4.5, Gemini 3 Pro and "Veo 3.1 preview"
    for three months after the registry moved on. It must name each alias's live target."""

    ROW = __import__("re").compile(r"^\| `([a-z0-9.-]+)` \| `([^`]+)`")

    def doc_aliases(self, text: str) -> dict:
        return {m.group(1): m.group(2) for line in text.splitlines() if (m := self.ROW.match(line))}

    def test_alias_table_matches_registry(self):
        reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
        doc = self.doc_aliases((REPO / "docs" / "MODEL-CURATOR.md").read_text(encoding="utf-8"))
        self.assertEqual(doc, reg["aliases"])

    def test_worked_examples_name_live_targets(self):
        # 3.37.1's examples still said claude-sonnet-4-6 was the default and the substitute,
        # and check() on Sonnet 4.5 was shown returning claude-sonnet-4-6 until 3.38.0.
        import re
        reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
        models = {m["id"]: m for m in reg["models"]}
        text = (REPO / "docs" / "MODEL-CURATOR.md").read_text(encoding="utf-8")
        substitutes = re.findall(r"WARNING \((?:openai|anthropic)\): (\S+) is deprecated, using (\S+) instead", text)
        substitutes += re.findall(r'check\("([^"]+)"\)` returns `\("deprecated", "([^"]+)"\)', text)
        self.assertTrue(substitutes)
        for old, new in substitutes:
            self.assertEqual(models[old].get("replacement_id"), new, old)
        # A router warning names a deprecated model's retirement date and the replacement: from
        # the registry for Anthropic, from the hint book's deprecations record for OpenAI.
        record = json.loads((REPO / "scripts" / "model_hints.json").read_text(encoding="utf-8"))
        record = record["deprecations"]["openai"]["models"]
        kept = re.findall(r"WARNING \((anthropic|openai)\): (\S+) is deprecated and retires (\d{4}-\d{2}-\d{2}); "
                          r"the router would choose (\S+)\.", text)
        self.assertEqual({k[0] for k in kept}, {"anthropic", "openai"})
        for provider, old, when, new in kept:
            if provider == "anthropic":
                got = (models[old]["status"], models[old].get("shutdown_date"), models[old].get("replacement_id"))
                self.assertEqual(got, ("deprecated", when, new), old)
            else:
                self.assertEqual((record[old]["shutdown"], record[old]["replacement"]), (when, new), old)

    def test_drift_is_caught(self):
        stale = "| `latest-fast-anthropic` | `claude-haiku-4-5-20251001` (Claude Haiku 4.5) |\n"
        self.assertNotEqual(self.doc_aliases(stale)["latest-fast-anthropic"], "claude-haiku-5-5")


class TestCheckParamsScope(unittest.TestCase):
    """API version 2026-10-21 rejects temperature/top_p/top_k on every Anthropic model."""

    def test_scan_flags_any_claude_target(self):
        import subprocess
        import sys
        import tempfile
        code = 'c.messages.create(model="claude-haiku-5-5", max_tokens=10, temperature=0.2)\n'
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
        try:
            proc = subprocess.run([sys.executable, str(REPO / "scripts" / "resolve_model.py"),
                                   "--check-params", f.name, "--json"],
                                  capture_output=True, text=True, timeout=60)
        finally:
            os.unlink(f.name)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["targets_anthropic"])
        self.assertEqual(payload["findings"][0]["param"], "temperature")


if __name__ == "__main__":
    unittest.main()
