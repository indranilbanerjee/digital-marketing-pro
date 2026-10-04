"""Connective and participial opener detection must not fire on ordinary words.

Found 2026-10-04 while extracting the standalone humanizer: the scan matched
connectives with a bare prefix (so "so" fired on "Sometimes", "Soon",
"Something", "Software") and counted any first word ending in "-ing" as a
participle ("During", "Spring", "Something"). Five plain human sentences
scored 60% connective and 60% participial openers.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location("ai_tell_scan_openers", SCRIPTS / "ai-tell-scan.py")
tm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tm)

HUMAN = ("Sometimes it rains in the valley. Soon it stops and the fields dry. "
         "Something changes every season. During the night we slept well. "
         "Spring arrived early that year.")
AI_ISH = ("Moreover, the results matter. So, we must act. Furthermore, the data shows growth. "
          "Leveraging these insights, teams can win. In fact, nothing else compares.")


def metrics(text):
    sentences = tm._split_sentences(text)
    _, counts = tm.scan_sentences(sentences)
    n = max(1, len(sentences))
    return {"connective_openers_pct": round(100.0 * counts["connective_openers"] / n, 1),
            "participial_openers_pct": round(100.0 * counts["participial_openers"] / n, 1)}


class TestOpenerMatching(unittest.TestCase):
    def test_plain_human_sentences_do_not_fire(self):
        m = metrics(HUMAN)
        self.assertEqual(m["connective_openers_pct"], 0.0)
        self.assertEqual(m["participial_openers_pct"], 0.0)

    def test_real_connectives_and_participles_still_fire(self):
        m = metrics(AI_ISH)
        self.assertEqual(m["connective_openers_pct"], 80.0)
        self.assertEqual(m["participial_openers_pct"], 20.0)

    def test_matcher_units(self):
        rx = tm._connective_matcher(["so", "in fact", "however"])
        for s in ("So, we act.", "so the plan", "In fact, yes", "In   fact it works", "However, no"):
            self.assertTrue(rx.match(s), s)
        for s in ("Sometimes it rains", "Soon", "Software ships", "Infact", "Howevermuch"):
            self.assertFalse(rx.match(s), s)
        self.assertTrue(tm._is_participial_opener("Leveraging data, we win"))
        self.assertTrue(tm._is_participial_opener("Being a founder, I know"))
        for s in ("During the night", "Something changed", "Spring came", "Ring the bell", ""):
            self.assertFalse(tm._is_participial_opener(s), s)


if __name__ == "__main__":
    unittest.main()
