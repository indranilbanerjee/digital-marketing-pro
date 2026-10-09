"""Every missing-package message prints the exact, tested install command.

Before 3.35.2 the README said a missing package "prints the exact pinned install
command", but only embed-c2pa.py did: six other messages said `pip install nltk`,
`pip install textstat` or `pip install requests beautifulsoup4`, requirements.txt
used `>=` ranges, ai-visibility-checker.py ignored a missing SDK and blamed the
API key, and utm-generator.py named the QR packages without a command. Now one
table (_common.PINNED_DEPENDENCIES) pins every optional package, requirements.txt
lists the same pins, setup.py installs from the table, and every message prints
_common.install_command(). These tests keep all four equal and run each script
with its package blocked to read the message it actually prints.
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _helpers import PLUGIN_ROOT, SCRIPTS_DIR, import_script  # noqa: E402

sys.path.insert(0, str(SCRIPTS_DIR))
import _common  # noqa: E402

REQUIREMENTS = SCRIPTS_DIR / "requirements.txt"

# Import name -> distribution name, where they differ.
DIST_FOR_IMPORT = {"bs4": "beautifulsoup4", "PIL": "pillow", "c2pa": "c2pa-python"}
# Pinned but never imported by name: used through another pinned package.
INDIRECT = {"pillow": "qrcode's PNG image backend (utm-generator.py --qr)"}

RUNNER = (
    "import importlib.abc, json, os, runpy, sys, types\n"
    "blocked = set(json.loads(os.environ['DMP_BLOCK']))\n"
    "for _n in json.loads(os.environ.get('DMP_STUB', '[]')):\n"
    "    sys.modules[_n] = types.ModuleType(_n)\n"
    "class _Block(importlib.abc.MetaPathFinder):\n"
    "    def find_spec(self, name, path=None, target=None):\n"
    "        if name.split('.')[0] in blocked:\n"
    "            raise ImportError(name)\n"
    "        return None\n"
    "sys.meta_path.insert(0, _Block())\n"
    "sys.argv = sys.argv[1:]\n"
    "runpy.run_path(sys.argv[0], run_name='__main__')\n"
)


def requirement_pins(text: str) -> dict:
    pins, bad = {}, []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        m = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9._-]*)==(\d+(?:\.\d+)*)", line)
        if not m:
            bad.append(line)
            continue
        pins[m.group(1).lower().replace("_", "-")] = m.group(2)
    if bad:
        raise AssertionError(f"requirements.txt lines that are not exact pins: {bad}")
    return pins


def third_party_imports() -> dict:
    """Top-level non-stdlib, non-local imports in scripts/*.py -> files."""
    local = {p.stem for p in SCRIPTS_DIR.glob("*.py")}
    found: dict = {}
    for path in sorted(SCRIPTS_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module.split(".")[0]]
            else:
                continue
            for name in names:
                if name in sys.stdlib_module_names or name in local or name.startswith("_"):
                    continue
                found.setdefault(name, set()).add(path.name)
    return found


class TestOneTable(unittest.TestCase):
    def test_table_pins_are_exact(self):
        for name, version in _common.PINNED_DEPENDENCIES.items():
            self.assertRegex(version, r"^\d+(\.\d+)+$", name)
            self.assertEqual(name, name.lower().replace("_", "-"), "table keys are normalised names")

    def test_requirements_txt_equals_the_table(self):
        self.assertEqual(requirement_pins(REQUIREMENTS.read_text(encoding="utf-8")),
                         _common.PINNED_DEPENDENCIES)

    def test_guard_rejects_a_range_or_a_drifted_pin(self):
        with self.assertRaises(AssertionError):
            requirement_pins("nltk>=3.8\n")
        drifted = REQUIREMENTS.read_text(encoding="utf-8").replace("nltk==3.10.3", "nltk==3.9.1")
        self.assertNotEqual(requirement_pins(drifted), _common.PINNED_DEPENDENCIES)

    def test_setup_installs_exact_pins_from_the_table(self):
        setup = import_script("setup.py", module_name="setup_pins_test")
        expected = {f"{k}=={v}" for k, v in _common.PINNED_DEPENDENCIES.items()}
        for dep in setup.FULL_DEPS:
            self.assertIn(dep, expected, f"setup.py installs {dep!r}, which is not an exact table pin")
        self.assertTrue(set(setup.LITE_DEPS) <= set(setup.FULL_DEPS))

    def test_every_third_party_import_is_pinned_and_every_pin_is_used(self):
        imports = third_party_imports()
        self.assertTrue(imports, "found no third-party imports; the scan is broken")
        used = set()
        for name, files in imports.items():
            dist = DIST_FOR_IMPORT.get(name, name).lower()
            used.add(dist)
            self.assertIn(dist, _common.PINNED_DEPENDENCIES,
                          f"{name} (imported by {sorted(files)}) has no pin in _common.PINNED_DEPENDENCIES")
        self.assertEqual(set(_common.PINNED_DEPENDENCIES) - used - set(INDIRECT), set(),
                         "pins that no script imports")

    def test_install_command_is_pinned(self):
        cmd = _common.install_command(["nltk", "Pillow", "beautifulsoup4>=4"])
        self.assertTrue(cmd.endswith("-m pip install nltk==3.10.3 pillow==12.3.0 beautifulsoup4==4.15.0"), cmd)
        with self.assertRaises(ValueError):
            _common.pinned_specs(["left-pad"])


class TestNoUnpinnedInstallText(unittest.TestCase):
    """No script or user-facing doc tells anyone to `pip install <name>` without a pin."""
    UNPINNED = re.compile(r"pip install\s+((?:[A-Za-z][^\s`'\")]*[ \t]*)+)")

    def offenders(self, text):
        hits = []
        for m in self.UNPINNED.finditer(text):
            for word in m.group(1).split():
                if not word[0].isalpha():
                    break
                if "==" not in word:
                    hits.append(m.group(0).strip())
                    break
        return hits

    def test_guard_catches_an_unpinned_command(self):
        self.assertEqual(self.offenders("Run: pip install nltk textstat"), ["pip install nltk textstat"])
        self.assertEqual(self.offenders("python -m pip install nltk==3.10.3 textstat==0.7.13"), [])
        self.assertEqual(self.offenders("pip install -r scripts/requirements.txt"), [])

    @staticmethod
    def live_files():
        files = sorted(SCRIPTS_DIR.glob("*.py"))
        for pattern in ("*.md", "docs/**/*.md", "skills/**/*.md", "commands/*.md", "agents/*.md"):
            files += sorted(PLUGIN_ROOT.glob(pattern))
        return [f for f in files if f.name != "CHANGELOG.md"]  # history, not instructions

    def test_scripts_and_docs_name_only_pinned_installs(self):
        wrong = []
        for f in self.live_files():
            for hit in self.offenders(f.read_text(encoding="utf-8")):
                wrong.append(f"{f.relative_to(PLUGIN_ROOT).as_posix()}: {hit}")
        self.assertEqual(wrong, [])

    def test_a_version_named_in_prose_is_the_pinned_one(self):
        spec = re.compile(r"\b([A-Za-z][A-Za-z0-9._-]*)(==|>=|~=)(\d+(?:\.\d+)+)")
        seen, wrong = 0, []
        for f in self.live_files():
            for m in spec.finditer(f.read_text(encoding="utf-8")):
                name = m.group(1).lower().replace("_", "-")
                if name not in _common.PINNED_DEPENDENCIES:
                    continue
                seen += 1
                if m.group(2) != "==" or m.group(3) != _common.PINNED_DEPENDENCIES[name]:
                    wrong.append(f"{f.relative_to(PLUGIN_ROOT).as_posix()}: {m.group(0)} "
                                 f"(pinned: {name}=={_common.PINNED_DEPENDENCIES[name]})")
        self.assertGreater(seen, 0, "no version found in prose; the scan is broken")
        self.assertEqual(wrong, [])


class TestMessagesPrintThePinnedCommand(unittest.TestCase):
    """Run each script with its package blocked and read what it prints."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        root = Path(cls._tmp.name)
        cls.env = dict(os.environ)
        for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA"):
            cls.env[key] = str(root / "home")
        cls.env["CLAUDE_MARKETING_HOME"] = str(root / "cm")
        cls.env["NLTK_DATA"] = str(root / "nltk_data")
        cls.env.pop("ANTHROPIC_API_KEY", None)
        cls.env["PYTHONIOENCODING"] = "utf-8"
        brand = root / "cm" / "brands" / "pin-test"
        brand.mkdir(parents=True)
        (brand / "profile.json").write_text(json.dumps({"brand_name": "Pin Test", "brand_slug": "pin-test"}),
                                            encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def run_blocked(self, script, args, block, stub=(), extra_env=None):
        env = dict(self.env, DMP_BLOCK=json.dumps(list(block)), DMP_STUB=json.dumps(list(stub)))
        env.update(extra_env or {})
        proc = subprocess.run([sys.executable, "-c", RUNNER, str(SCRIPTS_DIR / script), *args],
                              capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)
        return proc.stdout + proc.stderr

    def assertPrints(self, out, packages):
        cmd = _common.install_command(packages)
        self.assertTrue(cmd in out or json.dumps(cmd)[1:-1] in out,
                        f"expected the pinned command\n  {cmd}\nin output:\n{out[-1500:]}")

    def test_brand_voice_scorer_nltk(self):
        out = self.run_blocked("brand-voice-scorer.py", ["--brand", "pin-test", "--text", "Hello."], ["nltk"])
        self.assertPrints(out, ["nltk"])

    def test_content_scorer_textstat(self):
        out = self.run_blocked("content-scorer.py", ["--text", "Hello.", "--type", "blog"], ["textstat", "nltk"])
        self.assertPrints(out, ["textstat"])

    def test_content_scorer_nltk(self):
        out = self.run_blocked("content-scorer.py", ["--text", "Hello.", "--type", "blog"], ["nltk"],
                               stub=["textstat"])
        self.assertPrints(out, ["nltk"])

    def test_readability_analyzer_textstat(self):
        out = self.run_blocked("readability-analyzer.py", ["--text", "Hello."], ["textstat"])
        self.assertPrints(out, ["textstat"])

    def test_competitor_scraper_requests_and_bs4(self):
        out = self.run_blocked("competitor-scraper.py", ["--url", "https://example.com"], ["requests", "bs4"])
        self.assertPrints(out, ["requests", "beautifulsoup4"])

    def test_dm_status_lists_the_missing_packages(self):
        blocked = ["nltk", "textstat", "requests", "bs4", "qrcode", "PIL"]
        out = self.run_blocked("dm-status.py", ["--brand", "pin-test", "--section", "deps"], blocked)
        self.assertPrints(out, ["nltk", "textstat", "requests", "beautifulsoup4", "qrcode", "Pillow"])

    def test_setup_check_deps(self):
        setup = import_script("setup.py", module_name="setup_pins_test2")
        out = self.run_blocked("setup.py", ["--check-deps"], ["nltk", "textstat"])
        self.assertIn("DEPS_MISSING", out)
        self.assertPrints(out, setup.LITE_DEPS)

    def test_utm_generator_qr(self):
        out = self.run_blocked("utm-generator.py", ["--base-url", "https://example.com", "--source", "news",
                                                    "--medium", "email", "--campaign", "q4", "--qr"], ["qrcode"])
        self.assertPrints(out, ["qrcode", "pillow"])

    def test_ai_visibility_checker_names_the_missing_sdk_not_the_key(self):
        out = self.run_blocked("ai-visibility-checker.py",
                               ["--brand", "pin-test", "--mode", "api", "--queries", "best crm"],
                               ["openai", "anthropic"], extra_env={"OPENAI_API_KEY": "sk-test-not-real"})
        self.assertPrints(out, ["openai"])
        self.assertNotIn("No AI API keys found", out)


if __name__ == "__main__":
    unittest.main()
