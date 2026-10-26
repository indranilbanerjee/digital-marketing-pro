"""Run every test_*.py in this directory. Exit non-zero on failure.

Stdlib-only. No pytest needed.

Usage:
    python tests/run_all.py
    python tests/run_all.py -v             # verbose
    python tests/run_all.py --dated        # only the tests that go red as time passes

--dated is what .github/workflows/dated-checks.yml runs every week: a quiet
repo never runs push-only tests, so an API sunset, a stale stamp or a stale
allowlist entry would otherwise pass unnoticed until the next release.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent

# Tests whose verdict depends on today's date (API sunsets, provenance stamps,
# re-verification ages).
DATED_TESTS = ("test_api_versions", "test_benchmark_provenance", "test_npx_allowlist")

sys.path.insert(0, str(TESTS_DIR))


def main() -> int:
    loader = unittest.TestLoader()
    if "--dated" in sys.argv:
        suite = loader.loadTestsFromNames(DATED_TESTS)
    else:
        suite = loader.discover(start_dir=str(TESTS_DIR), pattern="test_*.py",
                                top_level_dir=str(TESTS_DIR))
    verbosity = 2 if "-v" in sys.argv else 1
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
