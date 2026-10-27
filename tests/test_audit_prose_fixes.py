"""Prose that contradicted the scripts, found by the 3.39.1 audits (each fails on 18433b9's text).

  * M3: roi-calculator was described as "multi-touch attribution across 5 models"; its weights only
    label channels by input order and move no revenue.
  * M9: "GPT-5.6 family as of July 2026" sat in a script and two guides while the registry's own
    aliases point elsewhere.
  * L1: a guide named `setup.py --switch-credentials`, which doesn't exist.
  * L2: brand-setup told the agent to hand-edit _active-brand.json.
  * L9: two skills recommended Veo 3.1 without saying the Gemini API doesn't serve it.
  * T-L2: client-report passed "the report JSON" to format-slack, and report-generator dropped a
    summary without a word.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"


def read(rel):
    return (REPO / rel).read_text(encoding="utf-8")


def live_text():
    for pattern in ("skills/**/*.md", "agents/*.md", "commands/*.md", "docs/*.md", "README.md", "AGENTS.md"):
        for path in REPO.glob(pattern):
            yield path, path.read_text(encoding="utf-8")


class TestRoiAttribution(unittest.TestCase):

    def test_the_output_says_what_the_weights_are(self):
        proc = subprocess.run([sys.executable, str(SCRIPTS / "roi-calculator.py"), "--channels",
                               '[{"name":"a","spend":10,"conversions":1,"revenue":30},'
                               '{"name":"b","spend":10,"conversions":1,"revenue":20}]', "--attribution", "linear"],
                              capture_output=True, text=True, timeout=60)
        out = json.loads(proc.stdout)
        self.assertIn("order of the channels in the input", out["attribution_note"])
        self.assertIn("unchanged", out["attribution_note"])

    def test_no_doc_calls_it_multi_touch(self):
        bad = [f"{p.relative_to(REPO)}" for p, t in live_text()
               for line in t.splitlines() if "roi-calculator" in line and "multi-touch" in line.lower()]
        self.assertEqual(bad, [])


class TestStaleNamesAndCommands(unittest.TestCase):

    def test_no_dated_model_family(self):
        hits = [str(p.relative_to(REPO)) for p, t in live_text() if "GPT-5.6 family" in t]
        hits += [p.name for p in SCRIPTS.glob("*.py") if "GPT-5.6 family" in p.read_text(encoding="utf-8")]
        self.assertEqual(hits, [])

    def test_no_switch_credentials_flag(self):
        self.assertEqual([str(p.relative_to(REPO)) for p, t in live_text() if "--switch-credentials" in t], [])
        self.assertIn('"switch-profile"', read("scripts/credential-manager.py"))

    def test_brand_switching_goes_through_the_script(self):
        skill = read("skills/brand-setup/SKILL.md")
        self.assertNotIn("3. Update `~/.claude-marketing/brands/_active-brand.json`", skill)
        self.assertIn("--switch-brand BRAND_SLUG", skill)

    def test_video_guidance_names_both_backends(self):
        for rel in ("skills/ad-creative/SKILL.md", "skills/creative-testing-framework/SKILL.md"):
            text = read(rel)
            self.assertNotIn("Veo 3.1", text, rel)
            self.assertIn("latest-video-gemini-api", text, rel)
            self.assertIn("latest-video-google", text, rel)


class TestClientReport(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        home = self.tmp / "home"
        self.env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PLUGIN_DATA", "PLUGIN_DATA")}
        self.env.update(HOME=str(home), USERPROFILE=str(home), CLAUDE_MARKETING_HOME=str(home / ".claude-marketing"))
        subprocess.run([sys.executable, str(SCRIPTS / "setup.py"), "--create-brand", "Acme"], capture_output=True,
                       env=self.env, timeout=120)

    def run_rg(self, *args):
        proc = subprocess.run([sys.executable, str(SCRIPTS / "report-generator.py"), "--brand", "acme", *args],
                              capture_output=True, text=True, encoding="utf-8", env=self.env, timeout=60)
        return proc.returncode, json.loads(proc.stdout)

    def test_summary_is_kept_and_unknown_keys_are_named(self):
        code, out = self.run_rg("--action", "generate-report", "--data", json.dumps(
            {"report_type": "monthly-review", "period": "2026-10", "summary": "Leads up 12%.",
             "metrics": {"leads": 120}, "title": "October", "sections": []}))
        self.assertEqual(code, 0, out)
        self.assertIn("## Executive Summary", out["markdown"])
        self.assertIn("Leads up 12%.", out["markdown"])
        self.assertEqual(out["ignored_keys"], ["sections", "title"])
        code, slack = self.run_rg("--action", "format-slack", "--id", out["report_id"])
        self.assertEqual(code, 0, slack)

    def test_the_skill_shows_the_two_steps(self):
        skill = read("skills/client-report/SKILL.md")
        self.assertNotIn("passing the report JSON via `--data '{report_json}'`", skill)
        self.assertIn("--action format-slack --id {report_id}", skill)


class TestMetadataText(unittest.TestCase):

    def test_no_bare_none(self):
        proc = subprocess.run([sys.executable, str(SCRIPTS / "plugin-metadata.py"), "--section", "version",
                               "--format", "text"], capture_output=True, text=True, timeout=60)
        self.assertNotRegex(proc.stdout, r": None$|: None\n")


if __name__ == "__main__":
    unittest.main()
