"""A script that reports an error exits non-zero, and printed commands paste into any shell.

A fresh-install smoke test (2026-10-12, recheck of 3.35.6) found scripts that print an error
result and exit 0, the class connector_executor fixed in 3.35.4: utm-generator (a missing CSV,
reported under "results"; and a CSV where every row failed), tech-seo-auditor and
local-seo-checker (errors followed by an explicit sys.exit(0)). A sweep found the same in
ad-budget-pacer, link-profile-analyzer, review-response-drafter, budget-optimizer,
roi-calculator, clv-calculator, content-repurposer, connector-status, drive-sync-state,
brand-voice-scorer, content-scorer and output-validator. Now: 2 for a bad argument (as
argparse does), 1 for a failure such as a missing file or an empty input, and utm-generator
3 for a partial batch. The documented missing-package fallbacks ("fallback": true) keep 0.

It also found that _common.script_command() output failed in Git Bash (Claude Code's Bash
tool on Windows): bash strips backslashes, so C:\\Python313\\python.exe became
"C:Python313python.exe: command not found". Commands now use forward slashes.
"""
from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _helpers import SCRIPTS_DIR  # noqa: E402

sys.path.insert(0, str(SCRIPTS_DIR))
import _common  # noqa: E402

NOTE = _common.POWERSHELL_NOTE


def run(script, *args, env_extra=None, prelude=None):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    env.update(env_extra or {})
    cmd = [sys.executable, str(SCRIPTS_DIR / script), *args]
    if prelude:
        cmd = [sys.executable, "-c", prelude, str(SCRIPTS_DIR / script), *args]
    with tempfile.TemporaryDirectory() as tmp:
        env.setdefault("CLAUDE_MARKETING_HOME", tmp)
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env, cwd=tmp, timeout=120)
    try:
        out = json.loads(p.stdout)
    except ValueError:
        out = None
    return p.returncode, out, p.stdout + p.stderr


class TestCommandsPasteIntoBashAndPowerShell(unittest.TestCase):
    def test_shape_without_a_space_in_the_interpreter(self):
        with mock.patch.object(_common.sys, "executable", r"C:\Python313\python.exe"):
            cmd = _common.script_command("setup.py", "--check-deps")
            pip = _common.install_command(["nltk"])
        path = (SCRIPTS_DIR / "setup.py").resolve().as_posix()
        self.assertEqual(cmd, f'C:/Python313/python.exe "{path}" --check-deps')
        self.assertEqual(pip, "C:/Python313/python.exe -m pip install nltk==3.10.3")
        self.assertNotIn("\\", cmd + pip)

    def test_shape_with_a_space_in_the_interpreter(self):
        with mock.patch.object(_common.sys, "executable", r"C:\Program Files\Python313\python.exe"):
            cmd = _common.script_command("setup.py", "--check-deps")
        path = (SCRIPTS_DIR / "setup.py").resolve().as_posix()
        self.assertEqual(cmd, f'"C:/Program Files/Python313/python.exe" "{path}" --check-deps{NOTE}')

    @staticmethod
    def bash():
        if os.name == "nt":
            for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramW6432", "")):
                cand = Path(base) / "Git" / "bin" / "bash.exe" if base else None
                if cand and cand.exists():
                    return str(cand)
            return None  # System32\bash.exe is WSL, which cannot run a Windows interpreter path
        return shutil.which("bash")

    def test_the_printed_command_runs_in_bash_from_another_folder(self):
        bash = self.bash()
        if not bash:
            self.skipTest("no Git Bash / bash on this machine")
        cmd = _common.script_command("utm-generator.py", "--help")
        with tempfile.TemporaryDirectory() as tmp:
            p = subprocess.run([bash, "-c", cmd], capture_output=True, text=True, cwd=tmp, timeout=60)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("Exit status", p.stdout)

    def test_the_powershell_note_does_not_break_bash(self):
        bash = self.bash()
        if not bash:
            self.skipTest("no Git Bash / bash on this machine")
        with mock.patch.object(_common.sys, "executable", r"C:\Program Files\Python313\python.exe"):
            cmd = _common.script_command("setup.py", "--check-deps")
        p = subprocess.run([bash, "-n", "-c", cmd], capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, "the note is a comment to bash: " + p.stderr)

    def test_the_inline_copy_in_connector_registry_matches(self):
        code, _, text = run("_connector_registry.py")
        line = next(ln for ln in text.splitlines() if ln.startswith("Usage: "))
        self.assertNotIn("\\", line)
        self.assertIn(f'"{(SCRIPTS_DIR / "_connector_registry.py").resolve().as_posix()}" self-test', line)


CSV = "base_url,source,medium,campaign\n{}\n{}\n"
GOOD = "https://example.com/a,news,email,spring"
BAD = "http://,news,email,spring"


class TestUtmGeneratorExitStatus(unittest.TestCase):
    def csv(self, *rows):
        tmp = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8", newline="")
        tmp.write("base_url,source,medium,campaign\n" + "\n".join(rows) + "\n")
        tmp.close()
        self.addCleanup(os.unlink, tmp.name)
        return tmp.name

    def test_missing_csv_is_a_top_level_error_exit_1(self):
        code, out, _ = run("utm-generator.py", "--csv", "no-such-file.csv")
        self.assertEqual(code, 1)
        self.assertIn("File not found", out["error"])
        self.assertEqual(out["results"], [])

    def test_every_row_failing_exits_1(self):
        code, out, _ = run("utm-generator.py", "--csv", self.csv(BAD, BAD))
        self.assertEqual(code, 1, out)
        self.assertEqual(out["summary"], {"rows": 2, "built": 0, "failed": 2})
        self.assertIn("every row failed", out["error"])

    def test_some_rows_failing_exits_3_and_all_good_exits_0(self):
        code, out, _ = run("utm-generator.py", "--csv", self.csv(GOOD, BAD))
        self.assertEqual((code, out["summary"]["failed"]), (3, 1))
        self.assertNotIn("error", out)
        code, out, _ = run("utm-generator.py", "--csv", self.csv(GOOD, GOOD))
        self.assertEqual((code, out["summary"]["failed"]), (0, 0))

    def test_an_invalid_single_url_exits_1(self):
        code, out, _ = run("utm-generator.py", "--base-url", "http://", "--source", "a", "--medium", "b",
                           "--campaign", "c")
        self.assertEqual(code, 1, out)


NO_NLTK = ("import sys, types, runpy\n"
           "nltk = types.ModuleType('nltk'); nltk.data = types.SimpleNamespace(find=lambda *a, **k: None)\n"
           "nltk.download = lambda *a, **k: True\n"
           "tok = types.ModuleType('nltk.tokenize'); tok.sent_tokenize = lambda t: [t]; tok.word_tokenize = str.split\n"
           "nltk.tokenize = tok; sys.modules.update({'nltk': nltk, 'nltk.tokenize': tok, 'textstat': types.ModuleType('textstat')})\n"
           "sys.argv = sys.argv[1:]\nrunpy.run_path(sys.argv[0], run_name='__main__')\n")


class TestErrorResultsExitNonZero(unittest.TestCase):
    """(script, args, expected exit, text the error must contain)."""
    CASES = [
        ("tech-seo-auditor.py", ["--file", "no-such-file.txt"], 1, "File not found"),
        ("tech-seo-auditor.py", [], 2, "Provide at least one URL"),
        ("local-seo-checker.py", ["--file", "x.json"], 2, "Provide --nap"),
        ("local-seo-checker.py", ["--nap", '{"name": "A"}', "--file", "no-such-file.json"], 1, "File not found"),
        ("local-seo-checker.py", ["--nap", "{bad"], 2, "--nap is not valid JSON"),
        ("ad-budget-pacer.py", ["--budget", "-5", "--period-days", "30", "--days-elapsed", "3",
                                "--spend-to-date", "1"], 2, "positive number"),
        ("link-profile-analyzer.py", [], 2, "Provide either --links"),
        ("link-profile-analyzer.py", ["--file", "no-such-file.json"], 1, "File not found"),
        ("review-response-drafter.py", ["--review", "   ", "--rating", "4"], 1, "cannot be empty"),
        ("budget-optimizer.py", ["--total-budget", "1000", "--file", "no-such-file.json"], 1, "File not found"),
        ("budget-optimizer.py", ["--total-budget", "1000"], 2, "Provide either --channels"),
        ("roi-calculator.py", ["--file", "no-such-file.json"], 1, "File not found"),
        ("clv-calculator.py", ["--margin", "0"], 2, "margin must be"),
        ("content-repurposer.py", ["--content-type", "blog", "--title", "T", "--key-points", "{bad"], 2,
         "--key-points is not valid JSON"),
        ("connector-status.py", ["--action", "check", "--name", "no-such-connector"], 1, "Unknown connector"),
        ("drive-sync-state.py", ["--action", "profile-drive-state"], 1, "--brand required"),
        ("output-validator.py", ["--action", "check-format", "--text", "   "], 1, "No content provided"),
    ]

    def test_each_error_result_exits_non_zero(self):
        for script, args, expected, text in self.CASES:
            with self.subTest(script=script, args=args):
                code, out, raw = run(script, *args)
                self.assertEqual(code, expected, raw[-600:])
                self.assertIn(text, json.dumps(out) if out is not None else raw)

    def test_scorers_exit_4_on_empty_text(self):
        # Empty text is "nothing to score" (exit 4, as the other empty cases); before 3.40.0 it was
        # exit 1, and an empty --text (not just blank) crashed on the missing --file.
        with tempfile.TemporaryDirectory() as home:
            brand = Path(home) / "brands" / "acme"
            brand.mkdir(parents=True)
            (brand / "profile.json").write_text(json.dumps({"brand_name": "Acme"}), encoding="utf-8")
            for script, args in (("brand-voice-scorer.py", ["--brand", "acme", "--text", "   "]),
                                 ("content-scorer.py", ["--text", "   ", "--type", "blog"])):
                with self.subTest(script=script):
                    code, out, raw = run(script, *args, prelude=NO_NLTK, env_extra={"CLAUDE_MARKETING_HOME": home})
                    self.assertEqual(code, 4, raw[-600:])
                    self.assertIn("nothing to score", out["error"])

    def test_the_missing_package_fallback_keeps_exit_0(self):
        blocker = ("import importlib.abc, runpy, sys\n"
                   "class B(importlib.abc.MetaPathFinder):\n"
                   "    def find_spec(self, n, p=None, t=None):\n"
                   "        if n.split('.')[0] == 'textstat': raise ImportError(n)\n"
                   "sys.meta_path.insert(0, B()); sys.argv = sys.argv[1:]\n"
                   "runpy.run_path(sys.argv[0], run_name='__main__')\n")
        code, out, _ = run("readability-analyzer.py", "--text", "Hello.", prelude=blocker)
        self.assertEqual((code, out["fallback"]), (0, True), "CONTRIBUTING convention 3: a fallback is not a failure")


def error_stmt(stmt):
    """True for a statement that prints/returns a dict literal with an "error" key (not a fallback)."""
    if not isinstance(stmt, ast.Expr):
        return False
    for node in ast.walk(stmt):
        if isinstance(node, ast.Dict):
            keys = [getattr(k, "value", None) for k in node.keys]
            if "error" in keys and "fallback" not in keys:
                return True
    return False


def stops(stmt):
    """True if a statement ends the run with a non-zero status (or hands off to _common.finish)."""
    for node in ast.walk(stmt):
        if isinstance(node, ast.Raise):
            return True
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Constant) \
                and type(node.value.value) is int and node.value.value != 0:
            return True
        if isinstance(node, ast.Call):
            name = getattr(node.func, "attr", getattr(node.func, "id", ""))
            if name == "finish":
                return True
            if name == "exit" and node.args and not (isinstance(node.args[0], ast.Constant)
                                                     and node.args[0].value in (0, None)):
                return True
    return False


def unstopped_error_prints(tree):
    """In each main(), error prints that no later statement (in their block or an enclosing one) stops."""
    out = []
    for fn in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "main"):
        def visit(block, after):
            for i, stmt in enumerate(block):
                rest = block[i + 1:] + after
                if error_stmt(stmt) and not stops(stmt) and not any(stops(s) for s in rest):
                    out.append(stmt.lineno)
                for field in ("body", "orelse", "finalbody"):
                    inner = getattr(stmt, field, None)
                    if isinstance(inner, list) and inner and isinstance(inner[0], ast.stmt):
                        visit(inner, rest)
                for handler in getattr(stmt, "handlers", []) or []:
                    visit(handler.body, rest)
        visit(fn.body, [])
    return out


class TestNoScriptWaitsForInput(unittest.TestCase):
    """Claude Code's Bash tool gives a script an open stdin pipe that never ends, and on Windows a
    stdin redirected from NUL reports isatty() as True, so input(), getpass() or a bare
    sys.stdin.read() blocks forever (a sibling plugin's credential setup hung this way,
    2026-10-12). No DMP script reads stdin or prompts today; if one ever must, it reads stdin
    only behind an explicit flag and prompts only behind a flag and a real console."""

    @staticmethod
    def waits(tree):
        out = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", getattr(node.func, "id", ""))
                if name in ("input", "getpass", "raw_input", "FileType"):
                    out.append(node.lineno)
                if name == "open" and node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == 0:
                    out.append(node.lineno)
            if isinstance(node, ast.Attribute) and node.attr in ("stdin", "__stdin__") \
                    and getattr(node.value, "id", "") == "sys":
                out.append(node.lineno)
        return sorted(set(out))

    def test_no_script_reads_stdin_or_prompts(self):
        bad = []
        for p in sorted(SCRIPTS_DIR.glob("*.py")):
            bad += [f"{p.name}:{ln}" for ln in self.waits(ast.parse(p.read_text(encoding="utf-8-sig")))]
        self.assertEqual(bad, [], "\n  ".join(bad))

    def test_plant(self):
        tree = ast.parse("key = input('API key: ')\nimport getpass\ns = getpass.getpass()\n"
                         "data = sys.stdin.read()\nf = open(0)\n")
        self.assertEqual(self.waits(tree), [1, 3, 4, 5])

    def test_scripts_exit_with_an_open_stdin_pipe(self):
        """The Bash tool's situation, reproduced: stdin is a pipe nobody writes to or closes."""
        for script, args in (("tech-seo-auditor.py", []), ("local-seo-checker.py", []),
                             ("utm-generator.py", []), ("connector-status.py", ["--action", "check"])):
            with self.subTest(script=script):
                proc = subprocess.Popen([sys.executable, str(SCRIPTS_DIR / script), *args], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                try:
                    code = proc.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    self.fail(f"{script} waited for input on an open stdin pipe")
                finally:
                    for stream in (proc.stdin, proc.stdout, proc.stderr):
                        stream.close()
                self.assertNotEqual(code, 0, "missing arguments are an error")


class TestNoErrorFallsThroughToExitZero(unittest.TestCase):
    """Light check: in every script's main(), a printed error dict is followed by a non-zero exit."""

    def test_every_main(self):
        bad = []
        for p in sorted(SCRIPTS_DIR.glob("*.py")):
            bad += [f"{p.name}:{ln}" for ln in unstopped_error_prints(ast.parse(p.read_text(encoding="utf-8-sig")))]
        self.assertEqual(bad, [], "an error is printed and the script can still exit 0:\n  " + "\n  ".join(bad))

    def test_plant(self):
        caught = unstopped_error_prints(ast.parse(
            "def main():\n"
            "    if x:\n"
            "        json.dump({'error': 'File not found'}, sys.stdout)\n"
            "        print()\n"
            "        sys.exit(0)\n"
            "    if y:\n"
            "        print(json.dumps({'error': 'bad'}))\n"
            "        return\n"
            "    print(json.dumps({'error': 'nltk missing', 'fallback': True}))\n"
            "    sys.exit(0)\n"))
        self.assertEqual(caught, [3, 7], "both error exits are flagged; the fallback is not")
        fine = unstopped_error_prints(ast.parse(
            "def main():\n"
            "    if not brand:\n"
            "        if as_json:\n"
            "            print(json.dumps({'error': 'no brand'}))\n"
            "        else:\n"
            "            print('no brand')\n"
            "        return 1\n"))
        self.assertEqual(fine, [], "a non-zero return after the if/else counts")


if __name__ == "__main__":
    unittest.main()
