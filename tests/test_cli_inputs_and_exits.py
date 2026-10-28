"""Command-line inputs that crashed, and results that exited 0 with an error in them.

From an outside audit and fuzz run of 3.39.1 and customer journeys on an installed copy, all planted
before the fix:
  * F1: a JSON option holding null, a list or a string where an object (or a list of strings or
    numbers) was expected ended 15 scripts in AttributeError or TypeError.
  * F3: --text "" sent four text scorers to a missing --file (TypeError).
  * F5: an empty or 20,000-character path, or JSON where a path goes, ended in OSError.
  * M4/F6: clv-calculator, email-subject-tester and revenue-simulator printed an error and exited 0.
  * M5: brand-voice-scorer scored neutral text 100 "Excellent" against a profile with no voice targets.
  * L3: build_skills_index.py with no arguments rewrote the index inside the installed plugin.
  * L5: connector_resolver and _connector_registry answered any argument with usage, exit 0.
  * T-M1: Git Bash rewrote --path /products/ into C:/Program Files/Git/products/ and the audit said ready.
  * T-M2: ai-visibility-checker --list-models exited 2 on its own.
  * T-M3: a run whose every request failed reported "0.0%" mention rate with exit 0.
  * M8: the visible output folder ignored a OneDrive-moved Documents folder.
  * T-L3: --out into a folder that doesn't exist yet crashed seo_drift.
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


def _load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Sandbox(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        home = self.tmp / "home"
        home.mkdir()
        self.env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PLUGIN_DATA", "PLUGIN_DATA")}
        self.env.update(HOME=str(home), USERPROFILE=str(home), CLAUDE_MARKETING_HOME=str(home / ".claude-marketing"))
        self.run_script("setup.py", "--create-brand", "Acme")

    def run_script(self, script, *args):
        proc = subprocess.run([sys.executable, str(SCRIPTS / script), *args], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=180, env=self.env, cwd=str(self.tmp))
        return proc.returncode, proc.stdout + proc.stderr


class TestJsonOptions(Sandbox):
    """F1: each option reaches _common.json_arg, which names it and exits 2."""

    CASES = [  # script, base args, option, bad values
        ("approval-manager.py", ["--brand", "acme", "--action", "create-approval"], "--data", ["null", "[]", '"x"']),
        ("campaign-tracker.py", ["--brand", "acme", "--action", "save-campaign"], "--data", ["null", "[]", '"x"']),
        ("credential-manager.py", ["--action", "create-profile"], "--data", ["null", "[]", '"x"']),
        ("crm-sync.py", ["--brand", "acme", "--action", "prepare-contact"], "--data", ["null", "[]", '"x"']),
        ("execution-tracker.py", ["--brand", "acme", "--action", "log-execution"], "--data", ["null", "[]", '"x"']),
        ("memory-manager.py", ["--brand", "acme", "--action", "prepare-store"], "--data", ["null", "[]", '"x"']),
        ("quality-tracker.py", ["--brand", "acme", "--action", "log-eval"], "--data", ["null", "[]", '"x"']),
        ("report-generator.py", ["--brand", "acme", "--action", "generate-report"], "--data", ["null", "[]", '"x"']),
        ("team-manager.py", ["--brand", "acme", "--action", "add-member"], "--data", ["null", "[]", '"x"']),
        ("narrative-mapper.py", ["--brand", "acme", "--action", "map-landscape"], "--data", ["null", "[]", '"x"']),
        ("local-seo-checker.py", [], "--nap", ["null", "[]", '"x"']),
        ("revenue-simulator.py", ["--action", "simulate"], "--scenarios", ["null", '"x"', "5"]),
        ("content-repurposer.py", ["--content-type", "blog", "--title", "T"], "--key-points", ["null", "{}", "[[1]]"]),
        ("ad-budget-pacer.py", ["--budget", "1000", "--period-days", "30", "--days-elapsed", "10",
                                "--spend-to-date", "300"], "--daily-spend", ["null", "{}", "[[1]]"]),
    ]

    def test_wrong_shapes_name_the_option(self):
        for script, base, option, bad in self.CASES:
            for value in bad:
                with self.subTest(script=script, value=value):
                    code, out = self.run_script(script, *base, option, value)
                    self.assertNotIn("Traceback", out)
                    self.assertEqual(code, 2, out)
                    self.assertRegex(out, rf"{option} (must be a JSON|item \d+ must be)")

    def test_engagement_state_fact_and_hypothesis(self):
        self.run_script("engagement-state.py", "init", "--brand", "acme", "--id", "e1")
        for command, option in (("add-stone-fact", "--fact-json"), ("add-opinion", "--hypothesis-json")):
            for value in ("null", "[]", '"x"'):
                code, out = self.run_script("engagement-state.py", command, "--brand", "acme", "--id", "e1", option, value)
                self.assertNotIn("Traceback", out)
                self.assertEqual(code, 2, out)
                self.assertIn(f"{option} must be a JSON object", out)

    def test_email_subjects_must_be_strings(self):
        code, out = self.run_script("email-subject-tester.py", "--subjects", "[1, 2]")
        self.assertEqual(code, 2, out)
        self.assertNotIn("Traceback", out)

    def test_the_helper(self):
        with mock.patch.object(sys, "exit", side_effect=SystemExit) as ex, mock.patch("builtins.print"):
            self.assertEqual(_common.json_arg('{"a": 1}', "--x"), {"a": 1})
            self.assertEqual(_common.json_arg('["a"]', "--x", list, str), ["a"])
            for value, kwargs in (("true", {}), ("[1]", {"expect": list, "items": str}), ("{", {})):
                with self.assertRaises(SystemExit):
                    _common.json_arg(value, "--x", **kwargs)
            self.assertEqual(ex.call_args.args, (2,))


class TestErrorPayloadsExitNonZero(Sandbox):
    """M4/F6, plus a guard: a script's main that ends by printing its result decides the exit code."""

    def test_the_three_scripts(self):
        for args in (["clv-calculator.py"], ["clv-calculator.py", "--model", "contractual", "--monthly-revenue", "100",
                                               "--churn-rate", "5"],
                     ["email-subject-tester.py", "--subjects", '[""]'],
                     ["revenue-simulator.py", "--action", "simulate", "--scenarios", "{}"]):
            with self.subTest(args=args):
                code, out = self.run_script(*args)
                self.assertIn('"error"', out)
                self.assertNotEqual(code, 0, out)

    def test_every_main_that_prints_its_result_sets_the_exit_code(self):
        import ast
        loose = []
        for path in sorted(SCRIPTS.glob("*.py")):
            src = path.read_text(encoding="utf-8-sig")
            tree = ast.parse(src)
            mains = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"]
            if not mains:
                continue
            last = ast.get_source_segment(src, mains[0].body[-1]) or ""
            if ("json.dump(output" in last or "json.dumps(output" in last or "json.dumps(result" in last
                    or "json.dump(result" in last) and "exit" not in last:
                loose.append(path.name)
        # These print results that never carry an error key: the two tell scanners' reports,
        # detect_surface's classification, and embed-c2pa's success record (it exits earlier on
        # every error).
        exempt = {"ai-tell-scan.py", "structural-tell-scan.py", "detect_surface.py", "embed-c2pa.py"}
        self.assertEqual(sorted(set(loose) - exempt), [])


class TestTextScorers(Sandbox):
    """F3, M5, L6."""

    def test_empty_text_is_nothing_to_score(self):
        runs = [("hallucination-detector.py", ["--action", "detect"]), ("content-scorer.py", ["--type", "blog"]),
                ("readability-analyzer.py", []), ("brand-voice-scorer.py", ["--brand", "acme"])]
        for script, base in runs:
            with self.subTest(script=script):
                code, out = self.run_script(script, *base, "--text", "")
                self.assertNotIn("Traceback", out)
                if '"fallback": true' in out:  # a missing package is reported first, exit 0
                    continue
                self.assertEqual(code, 4, out)
                self.assertIn("nothing to score", out)

    def test_options_are_checked_before_packages(self):
        for script in ("brand-voice-scorer.py", "content-scorer.py", "readability-analyzer.py"):
            code, out = self.run_script(script, "--no-such-option")
            self.assertEqual(code, 2, f"{script}: {out}")

    def test_no_voice_targets_no_score(self):
        bvs = _load("brand-voice-scorer")
        result = bvs.score_content("We build simple invoicing software. It is fast and friendly.",
                                   {"brand_name": "Acme", "voice": {"tone": "plain"}})
        self.assertIsNone(result["overall_score"])
        self.assertEqual(result["error"], "no_voice_profile")

    def test_missing_nltk_data_is_one_line(self):
        if importlib.util.find_spec("nltk") is None:
            self.skipTest("nltk not installed")
        import nltk
        with mock.patch.object(nltk, "download", return_value=False), \
                mock.patch("nltk.tokenize.sent_tokenize", side_effect=LookupError("punkt_tab")), \
                mock.patch.object(nltk.data, "find", side_effect=LookupError("x")), \
                mock.patch("builtins.print") as out, self.assertRaises(SystemExit) as ctx:
            _common.load_nltk_tokenizers("review by hand")
        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("nltk_data_missing", out.call_args.args[0])


class TestPathsAndFolders(Sandbox):
    """F5, T-M1, T-L3, M8."""

    def test_agent_readiness_paths(self):
        code, out = self.run_script("agent-readiness-audit.py", "--path", "C:/Program Files/Git/products/", "--format", "json")
        self.assertEqual(code, 2, out)
        self.assertIn("MSYS_NO_PATHCONV=1", out)
        robots = self.tmp / "robots.txt"
        robots.write_text("User-agent: *\nDisallow: /products/\n", encoding="utf-8")
        code, out = self.run_script("agent-readiness-audit.py", "--robots", str(robots), "--path", "//products/",
                                    "--format", "json")
        self.assertIn("/products/", out)
        self.assertNotIn("Program Files", out)
        for args in (["--html", ""], ["--html", "x" * 20000], ["--acp-feed", '{"a": 1}']):
            code, out = self.run_script("agent-readiness-audit.py", *args, "--format", "json")
            self.assertEqual(code, 2, f"{args[0]}: {out[:200]}")
            self.assertNotIn("Traceback", out)

    def test_empty_keyword_file(self):
        code, out = self.run_script("keyword_cluster.py", "--keywords", "")
        self.assertEqual(code, 2, out)
        self.assertNotIn("Traceback", out)

    def test_out_into_a_new_folder(self):
        base, cur = self.tmp / "base.csv", self.tmp / "cur.csv"
        rows = "query,page,clicks,impressions,ctr,position\nanvil,/a,10,100,0.1,3\n"
        base.write_text(rows, encoding="utf-8")
        cur.write_text(rows, encoding="utf-8")
        out_file = self.tmp / "not" / "yet" / "drift.json"
        code, out = self.run_script("seo_drift.py", "--baseline", str(base), "--current", str(cur), "--out", str(out_file))
        self.assertNotIn("Traceback", out)
        self.assertTrue(out_file.is_file(), out)

    def test_long_names_are_refused_not_oserrors(self):
        self.assertFalse(_common.is_safe_component("x" * 201))
        self.assertTrue(_common.is_safe_component("x" * 200))

    def test_documents_folder_follows_explorer(self):
        moved = self.tmp / "OneDrive" / "Documents"
        moved.mkdir(parents=True)
        with mock.patch.object(_common, "_registry_documents", return_value=moved):
            self.assertEqual(_common.documents_dir(), moved)
        with mock.patch.object(_common, "_registry_documents", return_value=self.tmp / "missing"), \
                mock.patch.object(Path, "home", return_value=self.tmp):
            self.assertEqual(_common.documents_dir(), self.tmp / "Documents")
        publisher = _load("output-publisher")
        with mock.patch.object(_common, "_registry_documents", return_value=moved), \
                mock.patch.dict(os.environ, {"DIGITAL_MARKETING_PRO_PUBLISH_DIR": ""}):
            self.assertEqual(publisher.get_visible_publish_dir("acme"), moved / "DigitalMarketingPro" / "acme")


class TestCliBasics(Sandbox):
    """L3, L5, T-M2, T-M3."""

    def test_build_skills_index_defaults_to_check(self):
        before = (REPO / "skills-index.json").read_bytes()
        code, out = self.run_script("build_skills_index.py")
        self.assertIn(code, (0, 1), out)
        self.assertEqual((REPO / "skills-index.json").read_bytes(), before)  # nothing written
        self.assertNotIn("Wrote", out)  # identical bytes alone would pass even if it rewrote the file

    def test_connector_modules_refuse_unknown_arguments(self):
        for script in ("connector_resolver.py", "_connector_registry.py"):
            for args in (["--bogus"], ["bogus-cmd"], []):
                code, _ = self.run_script(script, *args)
                self.assertEqual(code, 2, f"{script} {args}")
            self.assertEqual(self.run_script(script, "--help")[0], 0)

    def test_list_models_alone(self):
        code, out = self.run_script("ai-visibility-checker.py", "--list-models")
        self.assertEqual(code, 0, out)

    def test_all_failed_requests_report_no_rate(self):
        import types
        checker = _load("ai-visibility-checker")

        class Completions:
            def create(self, **kw):
                raise ConnectionError("Connection error.")

        fake = types.ModuleType("openai")
        fake.DefaultHttpxClient = lambda **kw: kw
        fake.OpenAI = lambda api_key, http_client: types.SimpleNamespace(chat=types.SimpleNamespace(completions=Completions()))
        env = {"OPENAI_API_KEY": "sk-test-not-a-key"}
        with mock.patch.dict(sys.modules, {"openai": fake}), mock.patch.dict(os.environ, env), \
                mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}), \
                mock.patch.object(checker, "route_openai", return_value={"model": "test-model"}), \
                mock.patch.object(checker, "_report"):
            out = checker.run_api_mode("Acme", ["q1", "q2", "q3"])
        self.assertEqual((out["answered"], out["errors"], out["mention_rate"]), (0, 3, None))
        self.assertIn("every request failed (3 of 3)", out["error"])


if __name__ == "__main__":
    unittest.main()
