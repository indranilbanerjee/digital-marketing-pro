"""competitor-scraper.py identifies itself and obeys robots.txt per RFC 9309.

Until v3.33.0 it sent a random browser User-Agent on every request, which hid
it from the robots.txt rules a site owner writes for it, and it treated an
unreachable robots.txt as permission. These tests need no network: the
robots decision is a pure function of the response.

Stdlib only.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "competitor-scraper.py"
_spec = importlib.util.spec_from_file_location("competitor_scraper", SCRIPT)
cs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cs)

URL = "https://example.com/pricing"


class TestHonestUserAgent(unittest.TestCase):
    def test_user_agent_names_the_scraper_and_the_project(self):
        self.assertIn(cs.CRAWLER_NAME, cs.USER_AGENT)
        self.assertIn("github.com/indranilbanerjee/digital-marketing-pro", cs.USER_AGENT)

    def test_no_browser_user_agent_is_sent(self):
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("Mozilla/5.0", src)
        self.assertNotIn("random.choice(USER_AGENTS)", src)


class TestRobotsVerdict(unittest.TestCase):
    def test_unreachable_robots_means_disallow(self):
        self.assertFalse(cs.robots_verdict(None, "", URL)[0])
        self.assertFalse(cs.robots_verdict(503, "", URL)[0])

    def test_missing_robots_means_allow(self):
        self.assertTrue(cs.robots_verdict(404, "", URL)[0])

    def test_star_group_applies(self):
        self.assertFalse(cs.robots_verdict(200, "User-agent: *\nDisallow: /pricing\n", URL)[0])
        self.assertTrue(cs.robots_verdict(200, "User-agent: *\nDisallow: /admin\n", URL)[0])

    def test_own_token_group_wins_over_star(self):
        text = (f"User-agent: {cs.CRAWLER_NAME}\nDisallow: /\n\n"
                "User-agent: *\nAllow: /\n")
        self.assertFalse(cs.robots_verdict(200, text, URL)[0])

    def test_allow_line_is_honoured(self):
        text = "User-agent: *\nAllow: /pricing\nDisallow: /\n"
        self.assertTrue(cs.robots_verdict(200, text, URL)[0])


if __name__ == "__main__":
    unittest.main()
