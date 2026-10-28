"""Facts corrected by the 2026-10-27 trends audit stay corrected.

Each stale phrasing below shipped in 3.39.1 and was wrong against a primary source read that day
(the source is named next to the corrected text in the docs). The REQUIRED rows are the corrected
statements; the two behaviour tests cover the scripts that scored email opens.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
LIVE = ["README.md", "AGENTS.md", "docs/*.md", "skills/**/*.md", "agents/*.md", "commands/*.md", "scripts/*.py"]

STALE = {  # phrase -> why it is wrong
    "TCF 2.2 compliance": "TCF 2.3; the 2.2 transition ended 2026-02-28",
    "Required for ads in EEA": "EU user consent policy covers the EEA, the UK and Switzerland",
    "25% open rate = perfect": "opens are inflated by Apple Mail Privacy Protection; not scored",
    "5-15% open-rate lift": "an open-rate claim with no source",
    "Last-click within Google Ads": "Google Ads defaults to data-driven for most conversion actions",
    "default last-click reporting": "Google Ads defaults to data-driven",
    "Depth Score": "no LinkedIn statement exists",
    "penalized ~60%": "no LinkedIn statement exists",
    "E-E-A-T evaluation now extends to ALL competitive queries": "Google said no such thing",
    "March 2026 core update demoted": "Google issued no guidance for that update",
    "Wave of manual actions targeting AI-generated content": "no Google source",
    "45% reduction in low-quality": "that figure is the March 2024 core update estimate",
    "Schema Markup for AI Citation": "no schema is required for generative AI search",
    "Structured Data for AI Citation": "no schema is required for generative AI search",
    "(FAQ, HowTo, Product schema) increases chance": "no schema is required for generative AI search",
    "883M MAU": "OpenAI: more than 1.2 billion weekly users (October 2026)",
    "image-only formats": "Threads ads include carousels, video, catalog and app ads",
    "no video, no carousels yet": "Threads ads include carousels, video, catalog and app ads",
    "permanent 550 rejections": "Gmail ramped up from November 2025: temporary, then permanent rejections",
    "Spam threshold tightened to <0.10%": "the ceiling is 0.3%, 0.1% recommended",
    "within 24 hours (required)": "Gmail 48 hours, Yahoo 2 days",
    "rolling out through 2025 for senders": "Outlook.com enforced from 5 May 2025",
    "released 9 February 2026": "C2PA 2.3 is December 2025, announced February 2026",
    "None of these auto-embed C2PA": "Adobe Firefly attaches Content Credentials",
    "Similar Segments | Auto-generated": "Google retired Similar Segments on 2023-05-01",
    "Lookalike Audiences | Similar professionals": "LinkedIn discontinued Lookalike Audiences on 2024-02-29",
    "GA4 provides assisted conversion data natively": "a Universal Analytics term",
    "300+ conversions/month": "Google publishes no fixed minimum for data-driven attribution",
    "1,000+ conversions/month": "Google publishes no fixed minimum for data-driven attribution",
    "conversion events configured, consent-mode state": "GA4 calls them key events",
    "AI Mode became the default": "AI Overviews remain the default; AI Mode is a separate tab",
    "default for opted-in users since I/O": "AI Overviews remain the default; AI Mode is a separate tab",
    "days away": "Article 50 has applied since 2 August 2026",
    "before EU AI Act enforcement on 2 Aug 2026": "Article 50 has applied since 2 August 2026",
    "Run this checklist before 2 August 2026": "Article 50 has applied since 2 August 2026",
    "no web browsing by default": "Claude has web search with citations (user-enabled)",
}
REQUIRED = [  # (file, phrase)
    ("skills/analytics-insights/privacy-first-measurement.md", "ad_user_data = denied"),
    ("skills/analytics-insights/privacy-first-measurement.md", "ad_personalization = denied"),
    ("skills/analytics-insights/privacy-first-measurement.md", "the EEA, the UK and Switzerland"),
    ("skills/funnel-architect/attribution-models.md", "The Data-driven model is the default attribution model for most conversion actions"),
    ("skills/aeo-geo/SKILL.md", "AI Overviews remain the default search surface"),
    ("skills/paid-advertising/ads-in-ai-answers.md", "More than 1.2 billion people use ChatGPT each week"),
    ("skills/c2pa-metadata/SKILL.md", "C2PA 2.5 is the current specification"),
    ("skills/context-engine/platform-specs.md", "#### Idea Pin (retired)"),
]


def _live_files():
    return sorted({p for pattern in LIVE for p in REPO.glob(pattern)})


class TestTrendFacts(unittest.TestCase):

    def test_stale_phrasings_are_gone(self):
        hits = []
        for path in _live_files():
            text = path.read_text(encoding="utf-8-sig")
            for phrase, why in STALE.items():
                if phrase in text:
                    hits.append(f"{path.relative_to(REPO)}: '{phrase}' ({why})")
        self.assertEqual(hits, [], "\n  " + "\n  ".join(hits))

    def test_corrected_statements_are_present(self):
        missing = [f"{f}: {phrase}" for f, phrase in REQUIRED
                   if phrase not in (REPO / f).read_text(encoding="utf-8")]
        self.assertEqual(missing, [])

    def test_ai_mode_is_stated_once(self):
        canon = "Google AI Mode has more than one billion monthly users"
        hits = [p for p in _live_files() if canon in p.read_text(encoding="utf-8-sig")]
        self.assertEqual([p.relative_to(REPO).as_posix() for p in hits], ["skills/aeo-geo/SKILL.md"])


class TestOpensAreNotScored(unittest.TestCase):

    def run_json(self, script, *args):
        proc = subprocess.run([sys.executable, str(SCRIPTS / script), *args], capture_output=True, text=True,
                              encoding="utf-8", timeout=60)
        return json.loads(proc.stdout)

    def test_campaign_health_scores_complaints_not_opens(self):
        out = self.run_json("campaign-health-monitor.py", "--action", "health-score", "--campaign-id", "c1",
                            "--campaign-type", "retention", "--metrics",
                            json.dumps({"open_rate": 60, "complaint_rate": 0.35, "ctr_current": 2, "ctr_baseline": 2}))
        factors = [f["factor"] for f in out["contributing_factors"]]
        self.assertNotIn("open_rate", factors)
        self.assertIn("complaint_rate", factors)
        self.assertEqual(out["top_issue"], "spam-complaints")
        self.assertIn("Apple Mail Privacy Protection", out["open_rate_note"])

    def test_send_time_ranks_by_clicks_when_the_log_has_them(self):
        from datetime import datetime, timedelta, timezone
        base = datetime(2026, 9, 7, tzinfo=timezone.utc)
        rows = []
        for week in range(10):
            # Tuesday 10:00 wins on opens, Thursday 14:00 on clicks
            for day, hour, opens, clicks in ((1, 10, 2000, 50), (3, 14, 900, 300)):
                ts = base + timedelta(days=week * 7 + day, hours=hour)
                rows.append({"sent_at": ts.isoformat(), "opens": opens, "clicks": clicks, "recipients": 5000})
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
            json.dump(rows, fh)
        try:
            out = self.run_json("send-time-optimizer.py", "--industry", "saas", "--audience-type", "b2b",
                                "--history", fh.name)
        finally:
            os.unlink(fh.name)
        top = out["recommendations"][0]
        self.assertEqual(top["day"], "Thursday")
        self.assertIn("click_rate", top)


if __name__ == "__main__":
    unittest.main()
