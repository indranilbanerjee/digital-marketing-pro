"""A recheck or review date in a script or doc fails a test once it passes; it is never just printed.

scripts/gsc-ai-performance.py carried "recheck_after": "2026-09-01" in the output of --api and
nothing failed when the date passed (found 2026-10-27). This scans the scripts, their JSON files
and the docs for machine-readable stamps (recheck_after, review_by, re_verify_by, as a key or a
constant) and for "recheck after / review by YYYY-MM-DD" in prose, and fails on any date that is
today or earlier. Files with their own dated tests (the model registry, platform_specs.json,
compliance-rules.md) are read by those. DMP_TODAY=YYYY-MM-DD freezes today.
"""
from __future__ import annotations

import os
import re
import unittest
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STAMP = re.compile(r"""["']?(recheck_after|review_by|re_verify_by|RECHECK_AFTER|REVIEW_BY)["']?\s*[:=]\s*["'](\d{4}-\d{2}-\d{2})["']""")
PROSE = re.compile(r"(?i)\b(re-?check after|review by|re-?verify by)\s+(\d{4}-\d{2}-\d{2})")
OWN_TESTS = {"model_registry.json", "platform_specs.json", "compliance-rules.md"}
SCAN = ["scripts/*.py", "scripts/*.json", "skills/**/*.md", "docs/*.md", "README.md", "agents/*.md", "commands/*.md"]


def today() -> date:
    frozen = os.environ.get("DMP_TODAY")
    return date.fromisoformat(frozen) if frozen else date.today()


def passed_stamps(root: Path, on: date) -> list[str]:
    out = []
    for path in sorted({p for pattern in SCAN for p in root.glob(pattern)}):
        if path.name in OWN_TESTS:
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            for rx in (STAMP, PROSE):
                for m in rx.finditer(line):
                    due = date.fromisoformat(m.group(2))
                    if due <= on:
                        out.append(f"{path.relative_to(root)}:{n}: {m.group(1)} {due} has passed; "
                                   f"do the check, then move the date")
    return out


class TestReviewDates(unittest.TestCase):

    def test_no_recheck_date_has_passed(self):
        problems = passed_stamps(REPO, today())
        self.assertEqual(problems, [], "\n  " + "\n  ".join(problems))

    def test_the_gsc_stamp_is_read(self):
        text = (REPO / "scripts" / "gsc-ai-performance.py").read_text(encoding="utf-8")
        self.assertTrue(STAMP.search(text), "the scan must see gsc-ai-performance.py's recheck_after")

    def test_plant(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "scripts").mkdir()
            Path(tmp, "scripts", "x.py").write_text('    "recheck_after": "2026-09-01",\nRECHECK_AFTER = "2027-01-01"\n',
                                                    encoding="utf-8")
            Path(tmp, "README.md").write_text("Review by 2026-10-01 before relying on it.\n", encoding="utf-8")
            got = passed_stamps(Path(tmp), date(2026, 10, 28))
        self.assertEqual(len(got), 2, got)


if __name__ == "__main__":
    unittest.main()
