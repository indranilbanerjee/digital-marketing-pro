"""JSON options travel through a file or stdin, never single-quoted inside a shell command.

The 2026-11-05 security review (finding 4): the docs told the model to run commands such as
`competitor-tracker.py ... --data '{baseline_json}'`, where the baseline holds titles and ad copy
scraped from competitor sites. A title such as `Plans'; curl ... | sh; echo '` closes the quoting
and the rest runs as shell; even an innocent `O'Brien` breaks the command. No script accepted the
JSON from a file or stdin.

Since 3.42.0 every JSON option (and the free-text --text / --content options) accepts `@<path>`
and `-` (stdin) through _common.arg_text, and every shipped doc writes the JSON with the Write tool
and passes `--data "@{data_file}"`. check_skill_contracts.py fails on `--flag '{` or `--flag '[` in
any shipped markdown outside CHANGELOG.md.

Stdlib only.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _helpers import PLUGIN_ROOT, SCRIPTS_DIR, import_script, run_json, run_script

HOSTILE_TITLE = "Plans'; touch PWNED #"


class TestArgText(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(SCRIPTS_DIR))
        import _common
        cls.c = _common

    def test_inline_file_and_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "p.json"
            f.write_bytes(("﻿" + json.dumps({"title": HOSTILE_TITLE})).encode("utf-8"))
            self.assertEqual(self.c.json_arg("@" + str(f), "--data"), {"title": HOSTILE_TITLE})
            self.assertEqual(self.c.json_text("@" + str(f)), {"title": HOSTILE_TITLE})
            self.assertEqual(self.c.arg_text('{"a": 1}'), '{"a": 1}')
            self.assertIsNone(self.c.arg_text(None))
            import contextlib
            import io
            with self.assertRaises(SystemExit) as cm, contextlib.redirect_stdout(io.StringIO()) as out:
                self.c.arg_text("@" + str(Path(tmp) / "missing.json"), "--data")
            self.assertIn("cannot read", out.getvalue())
            self.assertEqual(cm.exception.code, 2)

    def test_free_text_keeps_a_literal_at(self):
        self.assertEqual(self.c.arg_text("@acme thanks for the shout-out", "--text", text=True),
                         "@acme thanks for the shout-out")

    def test_resolve_file_options(self):
        import argparse
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "c.json"
            f.write_text('["a", "b"]', encoding="utf-8")
            ns = argparse.Namespace(channels="@" + str(f), other="x", none=None)
            self.c.resolve_file_options(ns, ("channels", "other", "none", "absent"))
            self.assertEqual((ns.channels, ns.other, ns.none), ('["a", "b"]', "x", None))


class TestHostileTextStaysData(unittest.TestCase):
    """A scraped title with a single quote is stored byte for byte, and nothing runs."""

    def _brand(self, home: Path):
        brand = home / "brands" / "acme"
        brand.mkdir(parents=True)
        (brand / "profile.json").write_text(json.dumps({"brand_name": "Acme", "brand_slug": "acme"}),
                                            encoding="utf-8")
        return brand

    def test_data_from_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            brand = self._brand(home)
            payload = home / "payload.json"
            payload.write_text(json.dumps({"title": HOSTILE_TITLE}), encoding="utf-8")
            data, code = run_json("competitor-tracker.py", "--brand", "acme", "--action", "save-baseline",
                                  "--competitor", "Rival", "--url", "https://rival.example",
                                  "--data", "@" + str(payload), marketing_home=home, cwd=tmp)
            self.assertEqual(code, 0, data)
            stored = json.loads((brand / "competitors" / "rival" / "baseline.json").read_text(encoding="utf-8"))
            self.assertEqual(stored["data"]["title"], HOSTILE_TITLE)
            self.assertFalse((home / "PWNED").exists())

    def test_data_from_stdin(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            brand = self._brand(home)
            proc = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "competitor-tracker.py"), "--brand", "acme", "--action",
                 "save-baseline", "--competitor", "Rival", "--url", "https://rival.example", "--data", "-"],
                input=json.dumps({"title": HOSTILE_TITLE}), capture_output=True, text=True, cwd=tmp,
                env={**__import__("os").environ, "CLAUDE_MARKETING_HOME": str(home)}, timeout=60)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            stored = json.loads((brand / "competitors" / "rival" / "baseline.json").read_text(encoding="utf-8"))
            self.assertEqual(stored["data"]["title"], HOSTILE_TITLE)
            self.assertFalse((home / "PWNED").exists())

    def test_executor_data_from_file(self):
        """The live-write executor reads its --data from a file too (dry run: nothing is sent)."""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self._brand(home)
            payload = home / "plan.json"
            payload.write_text(json.dumps({"plan": {"kickoff_message": HOSTILE_TITLE}}), encoding="utf-8")
            data, code = run_json("connector_executor.py", "--action", "internal-kickoff", "--brand", "acme",
                                  "--data", "@" + str(payload), marketing_home=home, cwd=tmp)
            self.assertNotIn("invalid JSON", json.dumps(data))
            self.assertFalse((home / "PWNED").exists())


class TestNoInlineJsonInDocs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lint = import_script("check_skill_contracts.py", "check_skill_contracts_for_json")

    def test_shipped_markdown_is_clean(self):
        found = self.lint.lint_inline_json()
        self.assertEqual([f"{f['file']}: {f['snippet']}" for f in found], [])

    def test_guard_can_fail(self):
        sites = self.lint.inline_json_sites(
            "ok --data \"@{data_file}\"\nbad `x.py --data '{\"a\":1}'`\nbad2 --channels '[1]'\n")
        self.assertEqual([n for n, _ in sites], [2, 3])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "skills" / "x").mkdir(parents=True)
            (root / "skills" / "x" / "SKILL.md").write_text("run `a.py --data '{\"k\": 1}'`\n", encoding="utf-8")
            (root / "CHANGELOG.md").write_text("history: --data '{\"k\": 1}'\n", encoding="utf-8")
            found = self.lint.lint_inline_json(root)
            self.assertEqual([f["file"] for f in found], ["skills/x/SKILL.md"])

    def test_contract_checker_passes(self):
        proc = run_script("check_skill_contracts.py")
        self.assertEqual(proc.returncode, 0, proc.stdout[-2000:])


class TestNoDirectJsonLoadsOfOptions(unittest.TestCase):
    def test_scripts_route_json_options_through_common(self):
        bad = []
        for p in sorted(SCRIPTS_DIR.glob("*.py")):
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if re.search(r"json\.loads\(args\.[a-z_]+\b(?!\.read_text)", line):
                    bad.append(f"{p.name}:{n}")
        self.assertEqual(bad, [], "parse JSON options with _common.json_arg / json_text so @file and - work")


if __name__ == "__main__":
    unittest.main()
