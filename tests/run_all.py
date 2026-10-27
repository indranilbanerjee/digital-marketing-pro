"""Run every test_*.py in this directory. Exit non-zero on failure.

Stdlib-only. No pytest needed.

Usage:
    python tests/run_all.py
    python tests/run_all.py -v             # verbose
    python tests/run_all.py --dated        # only the tests that go red as time passes
    python tests/run_all.py --help         # this text

Any other argument prints this text and exits 2 without running anything (a
mistyped flag used to run the whole suite against the real HOME).

--dated is what .github/workflows/dated-checks.yml runs every week: a quiet
repo never runs push-only tests, so an API sunset, a stale stamp or a stale
allowlist entry would otherwise pass unnoticed until the next release.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent

# Tests whose verdict depends on today's date (API sunsets, compliance dates, provenance
# stamps, re-verification ages).
DATED_TESTS = ("test_api_versions", "test_benchmark_provenance", "test_compliance_dates",
               "test_model_registry_dates", "test_npx_allowlist", "test_registry_record_agreement")

sys.path.insert(0, str(TESTS_DIR))


KNOWN_FLAGS = {"-v", "--dated"}
HELP_FLAGS = {"-h", "--help"}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if any(a in HELP_FLAGS for a in args):
        print(__doc__.strip())
        return 0
    unknown = [a for a in args if a not in KNOWN_FLAGS]
    if unknown:
        print(f"run_all.py: unknown argument(s): {' '.join(unknown)}\n", file=sys.stderr)
        print(__doc__.strip(), file=sys.stderr)
        return 2
    loader = unittest.TestLoader()
    if "--dated" in args:
        suite = loader.loadTestsFromNames(DATED_TESTS)
    else:
        suite = loader.discover(start_dir=str(TESTS_DIR), pattern="test_*.py",
                                top_level_dir=str(TESTS_DIR))
    verbosity = 2 if "-v" in args else 1
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
