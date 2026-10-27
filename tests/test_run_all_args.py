"""tests/run_all.py runs only on the flags it knows.

A fresh-install test's `python tests/run_all.py --help` probe used to run the whole suite
(747 tests, with the real HOME), because run_all ignored every argument it did
not recognise. Now --help prints the usage and exits 0, and any unknown argument
prints the usage to stderr and exits 2 without loading a single test.
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

import run_all  # noqa: E402


class TestRunAllArguments(unittest.TestCase):

    def test_unknown_flag_exits_2_without_running(self):
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = run_all.main(["--bogus"])
        self.assertEqual(code, 2)
        self.assertIn("unknown argument(s): --bogus", err.getvalue())
        self.assertIn("--dated", err.getvalue())
        self.assertNotIn("Ran ", out.getvalue() + err.getvalue())

    def test_help_prints_usage_and_exits_0(self):
        proc = subprocess.run([sys.executable, str(TESTS / "run_all.py"), "--help"],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("--dated", proc.stdout)
        self.assertNotIn("Ran ", proc.stdout + proc.stderr)

    def test_known_flags_are_accepted(self):
        self.assertEqual(run_all.KNOWN_FLAGS, {"-v", "--dated"})


if __name__ == "__main__":
    unittest.main()
