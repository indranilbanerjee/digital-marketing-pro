"""One definition per AI-visibility metric, with its formula, and every reporting surface points at it.

Before 3.40.0 the skills reported mention rate, citation rate, share of voice and a visibility score
without one shared definition, and "accuracy score" had no formula at all. The rule from the
2026-10-27 audit: no score is reported without its formula.
"""
from __future__ import annotations

import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GLOSSARY = "skills/context-engine/ai-visibility-metrics.md"
METRICS = ["Mention rate", "Citation rate", "Share of model", "Share of AI voice", "Sentiment", "AI Visibility Score"]
REPORTERS = ["skills/aeo-audit/SKILL.md", "skills/geo-monitor/SKILL.md", "skills/share-of-voice/SKILL.md",
             "skills/campaign-audit/SKILL.md", "skills/aeo-geo/ai-visibility-audit.md", "skills/aeo-geo/SKILL.md",
             "skills/analytics-insights/SKILL.md", "agents/competitive-intel.md"]


class TestMetricGlossary(unittest.TestCase):

    def test_each_metric_has_a_formula(self):
        text = (REPO / GLOSSARY).read_text(encoding="utf-8")
        for metric in METRICS:
            i = text.index(f"### {metric}")
            j = text.find("\n### ", i + 4)
            self.assertIn("**Formula:**", text[i:j if j > 0 else None], metric)
        self.assertIn("never reported without its formula", text)

    def test_every_reporter_points_at_the_glossary(self):
        missing = [f for f in REPORTERS if GLOSSARY not in (REPO / f).read_text(encoding="utf-8")]
        self.assertEqual(missing, [])

    def test_the_checker_reports_its_formula(self):
        src = (REPO / "scripts" / "ai-visibility-checker.py").read_text(encoding="utf-8")
        self.assertIn('"mention_rate_formula"', src)
        self.assertIn(GLOSSARY, src)

    def test_no_score_without_a_formula(self):
        self.assertNotIn("Establish KPIs: citation rate, accuracy score,", (REPO / "skills/aeo-geo/SKILL.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
