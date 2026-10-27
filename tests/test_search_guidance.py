"""Search and AI-crawler guidance that the 2026-10-27 review found missing stays in place.

Each fact here was read at its primary source on 2026-10-27; the skill text cites it.
  * The agent-readiness skill's crawler table lists exactly the tokens the script audits
    (Google-Agent and Google-GeminiNotebook were missing; Google retired Google-NotebookLM
    in August 2026).
  * Cloudflare's 15 Sep 2026 change: "Block" now also stops Googlebot, Bingbot and
    Applebot, so a readiness or technical-SEO audit that reads only robots.txt can miss
    a site that has delisted itself.
  * Bing's Topics Portfolio (13 Oct 2026) is the first first-party citation-gap list.
  * Google's Search generative AI control is "not used as a ranking or inclusion signal"
    elsewhere in Search and does not affect training; opting out also drops the
    Preferred Sources badge in AI features.
Stdlib only.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS = REPO / "skills"
sys.path.insert(0, str(REPO / "scripts"))

ROW = re.compile(r"^\|\s*`([A-Za-z-]+)`\s*\|")


def skill(name: str) -> str:
    return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")


def crawler_tokens(text: str) -> set[str]:
    start = text.index("### AI crawler tokens")
    end = text.index("\n## ", start)
    return {m.group(1) for line in text[start:end].splitlines() if (m := ROW.match(line))}


# (skill, phrase that must stay, why)
REQUIRED = (
    ("agent-readiness-audit", "Block on pages with ads", "Cloudflare block modes reach search crawlers since 15 Sep 2026"),
    ("agent-readiness-audit", "Disallow AI Training", "Cloudflare's no-training option keeps search crawlers"),
    ("tech-seo-audit", "Block** removes the site from search", "Cloudflare Block delists the site"),
    ("geo-monitor", "Topics Portfolio", "Bing's citation-gap view (13 Oct 2026)"),
    ("aeo-audit", "Top Opportunity Queries", "seed probes from Bing's first-party gap list"),
    ("aeo-geo", "isn't used as a ranking or inclusion signal", "Google's wording on the Search generative AI control"),
    ("aeo-geo", "https://www.google.com/preferences/source?q=", "the Preferred Sources deep link"),
    ("gsc-ai-performance", "Search generative AI control", "the control's real name"),
)


def missing(texts: dict[str, str]) -> list[str]:
    return [f"{name}: lost {phrase!r} ({why})" for name, phrase, why in REQUIRED
            if phrase not in texts[name]]


class TestSearchGuidance(unittest.TestCase):

    def test_crawler_table_matches_the_script(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("ara_tokens", REPO / "scripts" / "agent-readiness-audit.py")
        ara = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ara)
        self.assertEqual(crawler_tokens(skill("agent-readiness-audit")),
                         {b["token"] for b in ara.AI_CRAWLERS})

    def test_guidance_is_present(self):
        texts = {name: skill(name) for name, _, _ in REQUIRED}
        problems = missing(texts)
        self.assertEqual(problems, [], "\n  " + "\n  ".join(problems))

    def test_no_skill_names_the_retired_notebooklm_token_as_current(self):
        offenders = []
        for p in SKILLS.rglob("*.md"):
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if "Google-NotebookLM" in line and not re.search(r"replac|retired|former|supported until", line, re.I):
                    offenders.append(f"{p.relative_to(REPO)}:{n}")
        self.assertEqual(offenders, [])

    def test_plants(self):
        old_table = ("### AI crawler tokens\n\n| `OAI-SearchBot` | OpenAI |\n| `Google-Extended` | Google |\n\n## Inputs\n")
        self.assertEqual(crawler_tokens(old_table), {"OAI-SearchBot", "Google-Extended"})
        blank = {name: "" for name, _, _ in REQUIRED}
        self.assertEqual(len(missing(blank)), len(REQUIRED))


if __name__ == "__main__":
    unittest.main()
