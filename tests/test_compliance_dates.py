"""Compliance dates live in one dated table, every jurisdiction carries a Verified stamp,
and neither may go stale.

The failure this prevents: compliance-rules.md said India's DPDP Rules were "notified by
MeitY 3 Jan 2025" (that was the consultation draft) and that the Consent Manager framework
was "now live" (it opens on 13 Nov 2026); it listed UK PECR fines as GBP 500,000 eight
months after they rose to the UK GDPR maximum, and California's 2023 penalty amounts.
Nothing in the repo knew any of those dates.

So:
  * The "Dated obligations" table at the top of compliance-rules.md lists each dated
    change with a source and a status. A row still marked `upcoming` once its date has
    passed FAILS, so someone updates the section it points to. A future row marked
    `in force` also fails.
  * Every Section 1 jurisdiction has a `| **Verified** |` row: an ISO date (warn after
    WARN_DAYS, fail after FAIL_DAYS) or "pending re-check", allowed only until
    PENDING_UNTIL.
  * Known-wrong claims stay gone (each was in the 3.36.0 text).
These tests go red as time passes; the weekly dated-checks job runs them.
DMP_TODAY=YYYY-MM-DD freezes "today" for planting.
"""
from __future__ import annotations

import os
import re
import unittest
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RULES = REPO / "skills" / "context-engine" / "compliance-rules.md"

WARN_DAYS = 180
FAIL_DAYS = 365
PENDING_UNTIL = date(2027, 1, 31)
STATUSES = {"upcoming", "in force"}

ROW = re.compile(r"^\| (\d{4}-\d{2}-\d{2}) \| ([^|]+) \| ([^|]+) \| ([^|]+) \| ([^|]+) \| ([^|]+) \|$")
SECTION = re.compile(r"^### (1\.\d+b?) ")
VERIFIED = re.compile(r"^\| \*\*Verified\*\* \| (.+) \|$")
STAMP_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})\b")

# (claim that must stay gone, why)
RETIRED_CLAIMS = (
    ("notified by MeitY 3 Jan 2025", "3 Jan 2025 was the DPDP consultation draft; the Rules are G.S.R. 846(E) of 13 Nov 2025"),
    ("is now live under Rule 4", "DPDP Consent Manager registration opens 13 Nov 2026"),
    ("phased commencement through 2025-2026", "DPDP phasing runs to 13 May 2027"),
    ("PECR: up to GBP 500,000. ICO", "PECR fines follow the UK GDPR higher maximum since 5 Feb 2026"),
    ("$2,500 per unintentional violation", "CCPA amounts are CPI-adjusted ($2,663 / $7,988) since 1 Jan 2025"),
    ("high-risk system obligations 2 Aug 2027", "the Digital Omnibus on AI moved high-risk dates to 2 Dec 2027 / 2 Aug 2028"),
    ("Vermont (VDPA, 2025)", "Vermont's law (S.71) is reported effective 1 Jan 2028"),
)


def today() -> date:
    frozen = os.environ.get("DMP_TODAY")
    return date.fromisoformat(frozen) if frozen else date.today()


def dated_rows(text: str) -> list[tuple]:
    start = text.index("## Dated obligations")
    end = text.index("\n---", start)
    return [m.groups() for line in text[start:end].splitlines() if (m := ROW.match(line.strip()))]


def table_problems(text: str, on: date) -> list[str]:
    out = []
    sections = {m.group(1) for line in text.splitlines() if (m := SECTION.match(line))}
    rows = dated_rows(text)
    if not rows:
        return ["the Dated obligations table has no rows"]
    for day, place, what, section, source, status in rows:
        status, section = status.strip(), section.strip()
        when = date.fromisoformat(day)
        if status not in STATUSES:
            out.append(f"{day} {place.strip()}: status {status!r} not in {sorted(STATUSES)}")
        elif status == "upcoming" and when <= on:
            out.append(f"{day} {place.strip()}: the date has passed. Update section {section} for "
                       f"\"{what.strip()[:60]}\" and mark the row `in force`")
        elif status == "in force" and when > on:
            out.append(f"{day} {place.strip()}: marked `in force` before its date")
        if section not in sections:
            out.append(f"{day} {place.strip()}: section {section} does not exist")
        if not source.strip():
            out.append(f"{day} {place.strip()}: no source")
    return out


def stamp_problems(text: str, on: date) -> tuple[list[str], list[str]]:
    """(failures, warnings) for the Verified stamp of every Section 1 jurisdiction."""
    fails, warns = [], []
    body = text[text.index("## Section 1"):text.index("## Section 2")]
    current, stamped = None, {}
    for line in body.splitlines():
        if m := SECTION.match(line):
            current = m.group(1)
            stamped.setdefault(current, None)
        elif current and (v := VERIFIED.match(line.strip())):
            stamped[current] = v.group(1).strip()
    for section, stamp in stamped.items():
        if stamp is None:
            fails.append(f"section {section}: no | **Verified** | row")
        elif d := STAMP_DATE.match(stamp):
            age = (on - date.fromisoformat(d.group(1))).days
            if age > FAIL_DAYS:
                fails.append(f"section {section}: verified {d.group(1)}, {age} days ago; re-check it")
            elif age > WARN_DAYS:
                warns.append(f"section {section}: verified {d.group(1)}, {age} days ago")
        elif stamp.startswith("pending re-check"):
            if on > PENDING_UNTIL:
                fails.append(f"section {section}: still pending re-check after {PENDING_UNTIL}")
        else:
            fails.append(f"section {section}: Verified must start with a date or 'pending re-check'")
    return fails, warns


class TestComplianceDates(unittest.TestCase):

    def setUp(self):
        self.text = RULES.read_text(encoding="utf-8")

    def test_dated_table_is_current(self):
        problems = table_problems(self.text, today())
        self.assertEqual(problems, [], "\n  " + "\n  ".join(problems))

    def test_every_jurisdiction_has_a_fresh_stamp(self):
        fails, warns = stamp_problems(self.text, today())
        for w in warns:
            print(f"[compliance-dates] re-check soon: {w}")
        self.assertEqual(fails, [], "\n  " + "\n  ".join(fails))

    def test_retired_claims_stay_gone(self):
        found = [f"{claim!r}: {why}" for claim, why in RETIRED_CLAIMS if claim in self.text]
        self.assertEqual(found, [], "\n  " + "\n  ".join(found))

    def test_dated_rows_name_the_deadlines(self):
        days = {r[0] for r in dated_rows(self.text)}
        for must in ("2026-11-13", "2026-11-25", "2026-12-02", "2027-05-13"):
            self.assertIn(must, days)


class TestGuardsCanFail(unittest.TestCase):
    """Plants: each check must reject the failure it exists for."""

    TEXT = ("## Dated obligations\n\n| Date | J | W | S | Src | St |\n|---|---|---|---|---|---|\n"
            "| 2026-11-13 | India | Rule 4 | 1.11 | G.S.R. 846(E) | upcoming |\n"
            "| 2027-05-13 | India | core | 1.11 | G.S.R. 846(E) | in force |\n\n---\n"
            "## Section 1\n\n### 1.11 India — DPDPA\n\n| Field | Detail |\n|---|---|\n"
            "| **Verified** | 2025-01-01: old |\n\n### 1.12 Japan — APPI\n\n| Field | Detail |\n"
            "| **Law** | APPI |\n\n### 1.13 South Korea — PIPA\n\n"
            "| **Verified** | pending re-check: x |\n\n## Section 2\n")

    def test_passed_date_and_early_in_force_fail(self):
        problems = table_problems(self.TEXT, date(2026, 11, 20))
        self.assertTrue(any("2026-11-13" in p and "has passed" in p for p in problems), problems)
        self.assertTrue(any("2027-05-13" in p and "before its date" in p for p in problems), problems)
        self.assertEqual(table_problems(self.TEXT.replace("| in force |", "| upcoming |"),
                                        date(2026, 10, 27)), [])

    def test_stale_missing_and_overdue_stamps_fail(self):
        fails, _ = stamp_problems(self.TEXT, date(2027, 2, 15))
        joined = "\n".join(fails)
        self.assertIn("1.11", joined)              # 2025-01-01 is over a year old
        self.assertIn("1.12: no", joined)          # no Verified row
        self.assertIn("1.13: still pending", joined)  # pending past PENDING_UNTIL

    def test_retired_claims_are_caught(self):
        old = ("| **Law** | ... Rules 2025 (notified by MeitY 3 Jan 2025; phased commencement through 2025-2026). |\n"
               "| **Penalty Range** | UK GDPR: up to GBP 17.5 million or 4% of global turnover. PECR: up to GBP 500,000. ICO enforcement. |")
        self.assertEqual(sum(1 for claim, _ in RETIRED_CLAIMS if claim in old), 3)


if __name__ == "__main__":
    unittest.main()
