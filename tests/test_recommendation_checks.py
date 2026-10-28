"""Every audit recommendation carries a metric, an expected direction and a check-by date, and the
continuous-improvement loop checks it when due (borrow 2 of the 2026-10-27 ecosystem review).

Before 3.40.0 none of the four audit skills (seo, aeo, landing-page, campaign) said how anyone
would know a recommendation worked, and nothing came back to check it.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "recommendation-tracker.py"
HEADER = "| Recommendation | Metric | Expected direction | Check by |"
AUDITS = ["seo-audit", "aeo-audit", "landing-page-audit", "campaign-audit"]


class TestSkills(unittest.TestCase):

    def test_every_audit_has_the_table_and_records_it(self):
        for name in AUDITS:
            text = (REPO / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn(HEADER, text, name)
            self.assertIn(f"recommendation-tracker.py\" --brand {{slug}} --action add --source {name}", text, name)
            # every example row under the header fills all four columns
            rows = text.split(HEADER, 1)[1].split("\n")[2:3]
            self.assertTrue(rows and rows[0].count("|") == 5 and "|  |" not in rows[0], name)

    def test_the_loop_checks_what_fell_due(self):
        text = (REPO / "skills/continuous-improvement-loop/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("recommendation-tracker.py\" --brand {slug} --action due", text)
        self.assertIn("--action close", text)


class TestTracker(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        home = self.tmp / "home"
        self.env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PLUGIN_DATA", "PLUGIN_DATA")}
        self.env.update(HOME=str(home), USERPROFILE=str(home), CLAUDE_MARKETING_HOME=str(home / ".claude-marketing"))
        subprocess.run([sys.executable, str(REPO / "scripts" / "setup.py"), "--create-brand", "Acme"],
                       capture_output=True, env=self.env, timeout=120)

    def run_tracker(self, *args):
        proc = subprocess.run([sys.executable, str(SCRIPT), "--brand", "acme", *args], capture_output=True,
                              text=True, encoding="utf-8", env=self.env, timeout=60)
        return proc.returncode, json.loads(proc.stdout)

    def test_add_due_close(self):
        rows = [{"recommendation": "Fix broken links", "metric": "crawl errors", "direction": "down", "check_by": "2099-01-15"},
                {"recommendation": "Shorten form", "metric": "completion rate", "direction": "up", "check_by": "2099-06-01"}]
        code, out = self.run_tracker("--action", "add", "--source", "seo-audit", "--data", json.dumps(rows))
        self.assertEqual((code, out["count"]), (0, 2), out)
        code, due = self.run_tracker("--action", "due", "--as-of", "2099-02-01")
        self.assertEqual([r["metric"] for r in due["due"]], ["crawl errors"])
        code, closed = self.run_tracker("--action", "close", "--id", due["due"][0]["id"], "--observed", "3",
                                        "--outcome", "worked")
        self.assertEqual((code, closed["recommendation"]["status"]), (0, "closed"))
        code, due = self.run_tracker("--action", "due", "--as-of", "2099-02-01")
        self.assertEqual(due["count"], 0)

    def test_incomplete_rows_are_refused(self):
        for row, word in (({"recommendation": "x", "direction": "up", "check_by": "2099-01-01"}, "metric"),
                          ({"recommendation": "x", "metric": "m", "direction": "sideways", "check_by": "2099-01-01"}, "direction"),
                          ({"recommendation": "x", "metric": "m", "direction": "up", "check_by": "2020-01-01"}, "past"),
                          ({"recommendation": "x", "metric": "m", "direction": "up"}, "check_by")):
            code, out = self.run_tracker("--action", "add", "--data", json.dumps([row]))
            self.assertEqual(code, 2, out)
            self.assertIn(word, out["error"])


if __name__ == "__main__":
    unittest.main()
