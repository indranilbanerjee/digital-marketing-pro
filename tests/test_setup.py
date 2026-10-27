"""setup.py — env-aware workspace, brand creation + slug, atomic writes, exit codes."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _helpers import run_script  # type: ignore[import-not-found]


class SetupBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name)

    def setup(self, *args):
        return run_script("setup.py", *args, marketing_home=self.home)


class TestBrandCreation(SetupBase):
    def test_create_brand_uses_slug(self):
        proc = self.setup("--create-brand", "Acme & Co")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # H5: single slug rule → "acme-co", not "acme-&-co"
        self.assertTrue((self.home / "brands" / "acme-co" / "profile.json").exists())

    def test_active_brand_written(self):
        self.setup("--create-brand", "Acme Corp")
        active = self.home / "brands" / "_active-brand.json"
        self.assertTrue(active.exists())
        self.assertEqual(json.loads(active.read_text(encoding="utf-8"))["active_slug"], "acme-corp")

    def test_profile_written_atomically_no_tmp(self):
        self.setup("--create-brand", "Acme Corp")
        self.assertFalse((self.home / "brands" / "acme-corp" / "profile.json.tmp").exists())

    def test_env_aware_workspace(self):
        # Brand must land under the CLAUDE_MARKETING_HOME workspace, not ~.
        self.setup("--create-brand", "Zeta")
        self.assertTrue((self.home / "brands" / "zeta").exists())


class TestSwitchAndExit(SetupBase):
    def test_switch_unknown_brand_exits_nonzero(self):
        # H4: a failed switch must propagate a non-zero exit code.
        proc = self.setup("--switch-brand", "does-not-exist")
        self.assertNotEqual(proc.returncode, 0)

    def test_switch_existing_brand_ok(self):
        self.setup("--create-brand", "Acme Corp")
        proc = self.setup("--switch-brand", "acme-corp")
        self.assertEqual(proc.returncode, 0)

    def test_check_brand_when_none_is_informational(self):
        # --check-brand with no brand is informational (exit 0), not a hard error.
        proc = self.setup("--check-brand")
        self.assertEqual(proc.returncode, 0)


class TestNoPython3InSource(unittest.TestCase):
    def test_setup_source_uses_python_not_python3(self):
        src = (Path(__file__).resolve().parent.parent / "scripts" / "setup.py").read_text(encoding="utf-8")
        self.assertNotIn("python3 ", src)


class TestPythonVersionNotice(SetupBase):
    """Python 3.10 reached end of life on 2026-10-01. setup.py says so on stderr, without
    failing or changing stdout, and promises no release: Cowork's VM ran 3.10.12, so DMP
    moves to 3.11 only once Cowork does."""

    def _module(self):
        import importlib.util
        import sys
        scripts = Path(__file__).resolve().parent.parent / "scripts"
        sys.path.insert(0, str(scripts))
        spec = importlib.util.spec_from_file_location("dmp_setup", scripts / "setup.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_warns_on_3_10_only(self):
        mod = self._module()
        notice = mod.python_version_notice((3, 10, 14, "final", 0))
        self.assertIn("3.11", notice)
        self.assertIn("Cowork", notice)
        self.assertIn("still runs on it", notice)
        self.assertNotRegex(notice, r"3\.3\d\.\d|will require|requires Python")
        self.assertTrue(notice.startswith("PYTHON_WARNING:"))
        self.assertIsNone(mod.python_version_notice((3, 11, 0, "final", 0)))
        self.assertIsNone(mod.python_version_notice((3, 13, 1, "final", 0)))

    def test_running_python_is_reported_correctly(self):
        import sys
        proc = self.setup("--init")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("PYTHON_WARNING", proc.stdout)
        self.assertEqual("PYTHON_WARNING" in proc.stderr, sys.version_info[:2] < (3, 11))


if __name__ == "__main__":
    unittest.main()
