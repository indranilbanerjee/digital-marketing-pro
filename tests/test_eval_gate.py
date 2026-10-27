"""The scored quality gate (eval-runner.py) applies the brand's settings and stops on CRITICAL issues.

From the Tester's installed-copy audit of 3.39.1 (planted before the fix):
  * T-H1: _load_eval_config returned the manager's whole {"brand", "config"} reply and looked up
    "minimum_dimension_scores" (the writer's key is "minimum_scores") and weights.full/quick/
    compliance (the writer stores one flat map). Every lookup missed, so set-auto-reject 60 with a
    composite of 57.0 gave auto_rejected false, and no minimum ever fired.
  * T-H2: hallucination-detector reported critical_flags 1 (a placeholder URL); eval-runner kept only
    the score and returned rc 0 with no issue list. check/SKILL.md promises BLOCKED.
  * T-M7: with textstat and nltk missing, run-quick graded A+ from the hallucination dimension alone.
  * T-M5: --schema list and an unknown schema were swallowed ("Non-zero exit (1): "); a missing
    --file said "No content provided".
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _common  # noqa: E402

CLEAN = ("Spreadsheets are a good place to start. Most small teams track invoices in one, then move to "
         "dedicated software when the volume grows. Pick a tool your accountant already knows.\n")
# The Tester's draft. The detector marks a placeholder URL critical in a call to action ("Buy now at").
PLACEHOLDER = ("Our miracle formula cures diabetes in 30 days, guaranteed. 76% of buyers prefer Sehat. "
               "Buy now at https://your-site.com/buy or write to info@example.com.\n")


def _load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Gate(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.ws = self.tmp / "home" / ".claude-marketing"
        self.env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PLUGIN_DATA", "PLUGIN_DATA")}
        self.env.update(HOME=str(self.tmp / "home"), USERPROFILE=str(self.tmp / "home"),
                        CLAUDE_MARKETING_HOME=str(self.ws))
        patcher = mock.patch.dict(os.environ, {"CLAUDE_MARKETING_HOME": str(self.ws)})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.run_script("setup.py", "--create-brand", "Sehat Pharma")
        self.brand = "sehat-pharma"

    def run_script(self, script, *args):
        proc = subprocess.run([sys.executable, str(SCRIPTS / script), *args], capture_output=True, text=True,
                              encoding="utf-8", timeout=180, env=self.env, cwd=str(self.tmp))
        return proc.returncode, proc.stdout, proc.stderr

    def write(self, name, text):
        p = self.tmp / name
        p.write_text(text, encoding="utf-8")
        return str(p)

    def eval_json(self, *args):
        code, out, err = self.run_script("eval-runner.py", *args)
        return code, json.loads(out), err


class TestBrandSettingsReachTheRunner(Gate):
    """T-H1: every key the eval-config writer stores is the key the runner reads."""

    def test_round_trip(self):
        mgr = ["--brand", self.brand]
        self.assertEqual(self.run_script("eval-config-manager.py", "--action", "set-auto-reject", *mgr,
                                         "--threshold", "77")[0], 0)
        self.assertEqual(self.run_script("eval-config-manager.py", "--action", "set-threshold", *mgr,
                                         "--dimension", "hallucination", "--threshold", "88")[0], 0)
        self.assertEqual(self.run_script("eval-config-manager.py", "--action", "set-weights", *mgr,
                                         "--weights", '{"hallucination": 0.9}')[0], 0)
        runner = _load("eval-runner")
        config = runner._load_eval_config(self.brand)
        keys = _common.EVAL_CONFIG_KEYS
        self.assertEqual(config[keys["auto_reject"]], 77)
        self.assertEqual(config[keys["minimums"]]["default"]["hallucination"], 88)
        self.assertEqual(config[keys["weights"]]["hallucination"], 0.9)
        self.assertNotIn("config", config)  # the manager's reply is unwrapped

        scores = {"hallucination-detector.py": {"hallucination_score": 70, "critical_flags": 0},
                  "content-scorer.py": {"overall_score": 90}, "readability-analyzer.py": {"readability_score": 90}}

        def fake(script, args):
            return True, scores[script], None
        with mock.patch.object(runner, "_run_script", side_effect=fake):
            out = runner._run_eval(["hallucination", "content_quality", "readability"],
                                   runner._brand_weights(runner.QUICK_EVAL_WEIGHTS, config), CLEAN, self.brand,
                                   None, None, "general", "quick", False, config)
        self.assertLess(out["composite_score"], 77)
        self.assertTrue(out["auto_rejected"])
        self.assertEqual(out["decision"], "BLOCKED")
        self.assertEqual([a["dimension"] for a in out["dimension_alerts"]], ["hallucination"])
        self.assertEqual(out["dimensions"]["hallucination"]["status"], "below_minimum")
        weights = out["weights_used"]
        self.assertGreater(weights["hallucination"], weights["content_quality"] * 5)  # the 0.9 emphasis applies

    def test_shipped_defaults_are_enforced(self):
        # Untouched config: minimum_scores.default.hallucination is 60 and the auto-reject line 40.
        runner = _load("eval-runner")
        config = runner._load_eval_config(self.brand)
        with mock.patch.object(runner, "_run_script",
                               return_value=(True, {"hallucination_score": 57, "critical_flags": 0}, None)):
            out = runner._run_eval(["hallucination"], {"hallucination": 1.0}, CLEAN, self.brand, None, None,
                                   "general", "quick", False, config)
        self.assertEqual(out["dimensions"]["hallucination"]["status"], "below_minimum")
        self.assertEqual(out["decision"], "WARN")

    def test_the_cli_rejects_below_the_brand_line(self):
        self.run_script("eval-config-manager.py", "--action", "set-auto-reject", "--brand", self.brand,
                        "--threshold", "100")
        code, out, _ = self.eval_json("--action", "run-quick", "--file", self.write("d.md", CLEAN + "76% of teams agree."),
                                      "--brand", self.brand)
        self.assertTrue(out["auto_rejected"], out)
        self.assertEqual((out["decision"], code), ("BLOCKED", 3))


class TestCriticalIssuesBlock(Gate):
    """T-H2: a CRITICAL flag from any dimension reaches the output and blocks."""

    def test_placeholder_url(self):
        for action in ("run-quick", "run-compliance", "run-full"):
            code, out, _ = self.eval_json("--action", action, "--file", self.write("p.md", PLACEHOLDER))
            self.assertEqual(out["decision"], "BLOCKED", action)
            self.assertEqual(code, 3, action)
            critical = [i for i in out["issues"] if i["severity"] == "critical"]
            self.assertTrue(any("your-site.com" in i["value"] for i in critical), out["issues"])
            self.assertTrue(all(i["dimension"] == "hallucination" for i in critical))

    def test_clean_text_has_no_critical_issue(self):
        code, out, _ = self.eval_json("--action", "run-quick", "--file", self.write("c.md", CLEAN))
        self.assertNotEqual(out["decision"], "BLOCKED", out)
        self.assertEqual(code, 0)

    def test_the_skill_promises_only_what_the_scripts_check(self):
        skill = (REPO / "skills" / "check" / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("missing required disclaimer for a regulated industry", skill)
        self.assertNotIn("zero external dependencies", skill)
        self.assertNotIn("All scripts use stdlib only", skill)


class TestPartialEvals(Gate):
    """T-M7: a dimension that should have run and didn't makes the result partial."""

    def test_one_dimension_never_grades_a_plus(self):
        runner = _load("eval-runner")

        def fake(script, args):
            if script == "hallucination-detector.py":
                return True, {"hallucination_score": 100, "critical_flags": 0}, None
            return False, {"fallback": True, "message": "textstat not installed"}, f"{script} ran in fallback mode"
        with mock.patch.object(runner, "_run_script", side_effect=fake):
            out = runner._run_eval(["hallucination", "content_quality", "readability"], dict(runner.QUICK_EVAL_WEIGHTS),
                                   CLEAN, None, None, None, "general", "quick", False, runner._load_eval_config(None))
        self.assertTrue(out["partial"])
        self.assertEqual(sorted(out["missing_dimensions"]), ["content_quality", "readability"])
        self.assertEqual(out["grade"], "incomplete")
        self.assertEqual(out["decision"], "WARN")

    def test_two_of_three_caps_the_grade(self):
        runner = _load("eval-runner")

        def fake(script, args):
            if script == "readability-analyzer.py":
                return False, {}, "readability-analyzer.py failed"
            return True, {"hallucination_score": 100, "overall_score": 100, "critical_flags": 0}, None
        with mock.patch.object(runner, "_run_script", side_effect=fake):
            out = runner._run_eval(["hallucination", "content_quality", "readability"], dict(runner.QUICK_EVAL_WEIGHTS),
                                   CLEAN, None, None, None, "general", "quick", False, runner._load_eval_config(None))
        self.assertTrue(out["partial"])
        self.assertEqual(out["grade"], "B")
        self.assertEqual(out["grade_capped_from"], "A+")

    def test_not_applicable_dimensions_do_not_make_it_partial(self):
        # No evidence file and no schema: those dimensions don't apply; nothing failed.
        runner = _load("eval-runner")
        with mock.patch.object(runner, "_run_script",
                               return_value=(True, {"hallucination_score": 95, "overall_score": 95,
                                                    "verification_score": 95, "critical_flags": 0}, None)):
            out = runner._run_eval(list(runner.FULL_EVAL_WEIGHTS), dict(runner.FULL_EVAL_WEIGHTS), CLEAN, None,
                                   None, None, "general", "full", False, runner._load_eval_config(None))
        self.assertFalse(out["partial"])
        self.assertIn("claim_verification", out["skipped_dimensions"])


class TestHonestErrors(Gate):
    """T-M5."""

    def test_schema_list_lists(self):
        code, out, _ = self.eval_json("--action", "run-full", "--file", self.write("c.md", CLEAN), "--schema", "list")
        self.assertEqual(code, 0)
        self.assertIn("blog_post", out["schemas"])

    def test_an_unknown_schema_is_an_error(self):
        code, out, _ = self.eval_json("--action", "run-full", "--file", self.write("c.md", CLEAN), "--schema", "bogus")
        self.assertEqual(code, 2)
        self.assertIn("bogus", out["error"])
        self.assertIn("blog_post", out["valid_schemas"])

    def test_a_missing_file_says_so(self):
        code, out, _ = self.eval_json("--action", "run-quick", "--file", str(self.tmp / "nope.md"))
        self.assertEqual(code, 2)
        self.assertIn("not found", out["error"])

    def test_a_failing_dimension_says_why(self):
        code, out, _ = self.eval_json("--action", "run-full", "--file", self.write("c.md", CLEAN), "--brand", "no-such-brand")
        reason = out["dimensions"]["brand_voice"]["reason"]
        self.assertNotRegex(reason, r"^Non-zero exit \(\d\): $")
        if importlib.util.find_spec("nltk") is not None:  # without nltk the scorer stops before the brand
            self.assertIn("no-such-brand", reason)
        else:
            self.assertIn("NLTK", reason)


if __name__ == "__main__":
    unittest.main()
