"""Descriptions keep the words real requests use.

In the blind SEO-door eval (2026-10-27; evals/routing-heldout/ on the pilot branch), today's
plugin missed six held-out requests across four skills. Each time, no SEO skill fired at all,
so the cause was missing vocabulary, not sibling confusion:
  * keyword-cluster: "sort this list of queries into themes, one hub page per theme";
  * seo-drift: two Search Console exports from two dates;
  * seo-plan: a long-term organic plan for the year;
  * technical-seo: client-side JavaScript rendering, and LCP / INP fixes for developers.
3.38.1 added those words, inside the Stage-2 limits (tests/test_description_density.py). This
test keeps a later trim from dropping them. It measures nothing about routing: that set is
spent, and a new routing score needs a fresh blind set.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parent.parent / "skills"
REQUIRED = {
    "keyword-cluster": ("queries", "topic hubs", "spoke pages"),
    "seo-drift": ("exports", "Search Console", "two dates"),
    "seo-plan": ("organic", "12-month", "year"),
    "technical-seo": ("rendering", "SSR", "prerender", "LCP", "INP"),
}


def description(text: str) -> str:
    return re.search(r'(?m)^description:\s*"(.*)"\s*$', text).group(1)


def missing(desc: str, words) -> list:
    return [w for w in words if w.lower() not in desc.lower()]


class TestBlindEvalVocabulary(unittest.TestCase):

    def test_descriptions_keep_the_words(self):
        for name, words in REQUIRED.items():
            desc = description((SKILLS / name / "SKILL.md").read_text(encoding="utf-8"))
            self.assertEqual(missing(desc, words), [], name)

    def test_plant_the_3_38_0_wording(self):
        old = {"keyword-cluster": "Cluster keywords into pillar and spoke pages by SERP overlap via script.",
               "seo-drift": "Compare two SEO snapshots by script: gainers, losers, drift classes.",
               "seo-plan": "Build a 12-month SEO plan that scores four pillars and phases the roadmap.",
               "technical-seo": "Technical SEO reference for deep fixes: Web Vitals, JS SEO, migrations, schema."}
        for name, desc in old.items():
            self.assertTrue(missing(desc, REQUIRED[name]), name)


if __name__ == "__main__":
    unittest.main()
