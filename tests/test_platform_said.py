"""No "platform said" sentence or percentage without a source and a date, or "reported".

Findings 5, 6, 23 and 29 of the 2026-10-27 trends audit were sentences that read like a Google or
LinkedIn statement and had no primary behind them ("Google's March 2026 core update demoted FAQ
schema", "links penalised ~60%"). Over the stats-bearing files the audit named (the README's AEO
and platform-changes sections, google-seo-reference.md, the platform-updates section of
execution-workflows.md), any line that says a vendor said, announced, confirmed or reported
something, or that states a percentage, must carry a source (a URL or a vendor domain) and a date,
or say "reported", "vendor study" or "opinion".
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VENDOR = r"(?:Google|LinkedIn|Meta|OpenAI|TikTok|Instagram|YouTube|Microsoft|Apple|Anthropic|Pinterest|Amazon)"
CLAIM = re.compile(VENDOR + r"(?:'s)?[^.\n]{0,60}\b(?:said|says|states|stated|announced|confirmed|reported|reports)\b"
                   r"|\d+(?:\.\d+)?%")
SOURCE = re.compile(r"https?://|www\.|\b[a-z0-9-]+\.(?:com|google|org|io|net|ai|gov|eu)\b")
DATE = re.compile(r"\b20\d{2}-\d{2}(?:-\d{2})?\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* 20\d{2}\b"
                  r"|\b\d{1,2} (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* 20\d{2}\b")
HEDGE = re.compile(r"(?i)\b(?:reported|vendor stud(?:y|ies)|opinion|planning prior|illustrative)\b")
FILES = {  # file -> heading test for the part checked (None: the whole file)
    "README.md": lambda h: h.startswith("## ") and ("what changed in 2026" in h or "2026 platform changes" in h),
    "skills/context-engine/google-seo-reference.md": None,
    "skills/context-engine/execution-workflows.md": lambda h: h.startswith("### ") and "platform updates" in h,
}


def checked_lines(text: str, heading_test):
    if heading_test is None:
        yield from enumerate(text.splitlines(), 1)
        return
    on = False
    for n, line in enumerate(text.splitlines(), 1):
        if line.startswith("#"):
            on = heading_test(line)
        elif on:
            yield n, line


def unsourced(name: str, text: str, heading_test) -> list[str]:
    return [f"{name}:{n}: {line.strip()[:120]}" for n, line in checked_lines(text, heading_test)
            if CLAIM.search(line) and not HEDGE.search(line) and not (SOURCE.search(line) and DATE.search(line))]


class TestPlatformSaid(unittest.TestCase):

    def test_claims_carry_a_source_and_a_date(self):
        problems = []
        for rel, heading_test in FILES.items():
            problems += unsourced(rel, (REPO / rel).read_text(encoding="utf-8"), heading_test)
        self.assertEqual(problems, [], "\n  " + "\n  ".join(problems))

    def test_plants_from_3_39_1(self):
        old = ("- **LinkedIn (March 2026 algorithm shift):** external links and engagement bait penalized ~60%.\n"
               "Schema strategy refresh — Google's March 2026 core update demoted FAQ schema, Google announced.\n"
               "Google said it (support.google.com/x, 2026-07-10).\n"
               "Vendor studies put it near 50% (vendor study).\n")
        got = unsourced("x.md", old, None)
        self.assertEqual(len(got), 2, got)


if __name__ == "__main__":
    unittest.main()
