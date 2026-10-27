"""Defects found by running the content engine end to end, not by reading it.

A full `brand-setup` → `content-engine` run on a fresh brand produced all twelve
working files and then surfaced a set of contract problems that no unit test
could see, because each one is about what an instruction MEANS rather than
whether code executes:

  * `brand_voice_match` asked for "<= 1.5 point deviation" while
    `brand-voice-scorer.py` emits `distance` bounded at 1.0 — read literally the
    gate could never fail. That is the same hollow-gate defect as a gate with no
    measurement behind it, and it had been sitting in the scorecard passing
    everything.
  * `seo_complete` required ">= 3 internal links" with no exemption. A
    pre-launch brand's first article cannot link internally to anything, so the
    gate was unsatisfiable rather than strict. Its "all images have alt text"
    criterion also passed vacuously at zero images.
  * `validate-profile` demanded `voice.*`, `target_jurisdictions` and
    `guardrails.*` as BLOCKERs, none of which `brand-setup` creates — so a
    freshly created brand failed the plugin's own validator. `content-engine`
    and `brand-voice-scorer.py` both read the generator's keys, which makes the
    validator the outlier.
  * The remediation message inverted its own diagnosis: copy scoring humor 0.00
    against a target of 0.20 was told it "reads as too serious" AND that the
    brand "calls for more serious tone". Following it moves the score further
    out of tolerance.
  * Two instructions both wrote to `05-scans.json`, one "save" and one "append";
    appending a second JSON document to a file holding one yields invalid JSON.

Stdlib only.
"""
from __future__ import annotations

import importlib.util
import re
import sys
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS = REPO / "skills"
CONTENT_ENGINE = (SKILLS / "content-engine" / "SKILL.md").read_text(encoding="utf-8")
VALIDATE = (SKILLS / "validate-profile" / "SKILL.md").read_text(encoding="utf-8")


def _load(name, filename):
    """Load a script as a module. brand-voice-scorer.py exits at import when NLTK is missing,
    and the suite is stdlib-only, so on a clean machine a stub stands in: these tests call
    its pure scoring functions, never the tokenisers."""
    stubbed = {}
    if importlib.util.find_spec("nltk") is None:
        nltk = types.ModuleType("nltk")
        nltk.data = types.SimpleNamespace(find=lambda *a, **k: None)
        nltk.download = lambda *a, **k: True
        tok = types.ModuleType("nltk.tokenize")
        tok.sent_tokenize, tok.word_tokenize = (lambda t: [t]), str.split
        nltk.tokenize = tok
        stubbed = {"nltk": nltk, "nltk.tokenize": tok}
        sys.modules.update(stubbed)
    try:
        spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / filename)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        for key in stubbed:
            sys.modules.pop(key, None)
    return mod


class TestGatesAreStatedInTheUnitTheyAreMeasuredIn(unittest.TestCase):
    def test_voice_gate_uses_the_scorer_scale(self):
        """`distance` is bounded at 1.0, so a threshold of 1.5 is unreachable."""
        # The old wording is quoted in the cell's own explanation, so match the
        # OPERATIVE phrasing rather than any mention of it.
        self.assertNotIn("shows ≤ 1.5 point deviation", CONTENT_ENGINE,
                         "the voice gate is stated in a unit the scorer never emits")
        self.assertIn("`distance` ≤ 0.15", CONTENT_ENGINE,
                      "state the gate in the 0-1 unit brand-voice-scorer.py returns")

    def test_the_stated_threshold_matches_what_the_scorer_flags_at(self):
        """If these two ever diverge, the scorecard and the script disagree about
        the same document. Read the scorer's own threshold rather than trusting
        the number in the doc."""
        src = (REPO / "scripts" / "brand-voice-scorer.py").read_text(encoding="utf-8")
        m = re.search(r"if dist > ([0-9.]+):", src)
        self.assertIsNotNone(m, "could not find the scorer's flagging threshold")
        self.assertIn(f"`distance` ≤ {m.group(1)}", CONTENT_ENGINE,
                      f"scorer flags above {m.group(1)}; the gate must say the same number")

    def test_a_distance_of_1_5_is_not_even_reachable(self):
        scorer = _load("dmp_voice_scorer", "brand-voice-scorer.py")
        self.assertLessEqual(scorer.dimension_distance(0.0, 1.0), 1.0)
        self.assertLessEqual(scorer.dimension_distance(1.0, 0.0), 1.0)


class TestUnsatisfiableCriteriaHaveAnExplicitNotApplicable(unittest.TestCase):
    def test_internal_links_has_a_no_site_exemption(self):
        self.assertIn("N/A (no site)", CONTENT_ENGINE,
                      "a brand with no website cannot link internally; the gate needs an N/A")

    def test_alt_text_does_not_pass_vacuously_at_zero_images(self):
        self.assertIn("N/A (no images)", CONTENT_ENGINE,
                      "0 of 0 images with alt text is a pass that verifies nothing")

    def test_a_bare_not_applicable_is_still_a_failure(self):
        self.assertIn("a bare `N/A` is a FAIL", CONTENT_ENGINE,
                      "N/A must name its reason or it becomes a way to skip any gate")


class TestTheGeneratorAndTheValidatorAgree(unittest.TestCase):
    """A freshly created brand must pass the plugin's own validator. It did not:
    the generator writes `brand_voice` / `target_markets` and no `guardrails`,
    while the validator demanded `voice.*`, `target_jurisdictions` and
    `guardrails.*` as BLOCKERs."""

    def test_validator_accepts_the_key_the_generator_writes_for_voice(self):
        self.assertIn("`brand_voice`", VALIDATE,
                      "validator must accept the voice key brand-setup actually writes")

    def test_validator_accepts_the_key_the_generator_writes_for_markets(self):
        self.assertIn("`target_markets`", VALIDATE,
                      "validator must accept the market key brand-setup actually writes")

    def test_missing_guardrails_is_not_a_blocker_for_unregulated_brands(self):
        self.assertIn("WARNING otherwise", VALIDATE,
                      "brand-setup does not create guardrails, so a plain brand would "
                      "always fail a BLOCKER it cannot satisfy at setup time")

    def test_generator_still_writes_what_the_validator_now_expects(self):
        """Guard on the guard: if brand-setup's schema changes, this fails rather
        than letting the two drift apart again in the other direction."""
        setup_src = (REPO / "scripts" / "setup.py").read_text(encoding="utf-8")
        for key in ('"brand_name"', '"brand_voice"', '"target_markets"', '"industry"'):
            self.assertIn(key, setup_src, f"generator no longer writes {key}")


class TestRemediationPointsTowardTheTarget(unittest.TestCase):
    def test_advice_is_the_opposite_of_how_the_content_reads(self):
        scorer = _load("dmp_voice_scorer_2", "brand-voice-scorer.py")
        # Content far too serious (0.0) against a target that wants some humor.
        devs = scorer.generate_deviations(
            {"humor": {"actual": 0.0, "distance": 0.30}},
            {"voice_dimensions": {"humor": 0.30}})
        self.assertTrue(devs, "a 0.30 distance should be flagged")
        msg = devs[0]["message"].lower()
        self.assertIn("too serious", msg, "diagnosis should say how it currently reads")
        self.assertNotIn("more serious", msg,
                         "the remedy must not repeat the diagnosis — following it "
                         "would move the score further out of tolerance")

    def test_the_other_direction_too(self):
        scorer = _load("dmp_voice_scorer_3", "brand-voice-scorer.py")
        devs = scorer.generate_deviations(
            {"humor": {"actual": 0.9, "distance": 0.70}},
            {"voice_dimensions": {"humor": 0.2}})
        msg = devs[0]["message"].lower()
        self.assertNotIn("more playful", msg)


class TestScanOutputHasOneWellDefinedShape(unittest.TestCase):
    def test_no_instruction_appends_a_second_json_document(self):
        self.assertNotIn("Append the scan JSON to **`05-scans.json`**", CONTENT_ENGINE,
                         "appending a second JSON document produces a file json.load rejects")

    def test_the_keyed_shape_is_specified(self):
        self.assertIn('"surface"', CONTENT_ENGINE)
        self.assertIn('"structure"', CONTENT_ENGINE)

    def test_the_file_appears_in_the_output_convention(self):
        m = re.search(r"05-scans\.json\s+\S", CONTENT_ENGINE)
        self.assertIsNotNone(
            m, "05-scans.json is mandated by two sections but was missing from the file list")

    def test_windows_encoding_pitfall_is_documented(self):
        self.assertIn("PYTHONIOENCODING=utf-8", CONTENT_ENGINE,
                      "the documented redirect writes cp1252 on Windows and the em-dash "
                      "in the advisory note then breaks json.load")


class TestBrandCreationIsNotSilentlyGlobal(unittest.TestCase):
    SETUP = (REPO / "scripts" / "setup.py").read_text(encoding="utf-8")

    def test_slug_is_settable_from_the_cli(self):
        """create_brand() always accepted a slug and the CLI never exposed it,
        so anyone needing a specific slug had to import the module. The slug is
        the storage directory name, so this was not optional."""
        self.assertIn('"--slug"', self.SETUP)
        self.assertIn("slug=args.slug", self.SETUP)

    def test_repointing_the_active_brand_is_announced_with_a_way_back(self):
        self.assertIn("ACTIVE_BRAND_CHANGED", self.SETUP,
                      "creating a brand silently repointed every skill at it")
        self.assertIn("--switch-brand", self.SETUP, "say how to undo it")
        self.assertIn('"previous_slug"', self.SETUP,
                      "_active-brand.json stored one value with no history")


if __name__ == "__main__":
    unittest.main()
