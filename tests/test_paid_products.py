"""scripts/paid_products.json is where an ad product waits until a page about it has been read.

The 2026-10-27 trends audit (finding 28) listed products a media plan could lean on that the paid
hub never named (Meta Andromeda and Opportunity score, Google campaign total budgets, AI Max for
Shopping and AI Brief, TikTok GMV Max and the 2026-10-05 Advertising Week products, LinkedIn
Qualified Leads Optimization, Pinterest Performance+), and finding 30 the X ad-text rules. Many of
them rest on press reports, because the vendor pages do not load from India. The checks:
  * every row carries platform, product, kind, status, availability, since, source_url,
    source_date, verified_on, review_by and note; status is read or reported, availability one of
    live, beta, rolling_out, announced;
  * a reported row says so in its note, and a read row points at a page, not a site root;
  * no review_by is within 30 days (DMP_TODAY=YYYY-MM-DD freezes today; the weekly dated job runs it);
  * the paid-advertising skill reads the file and says what a reported or not-live row means;
  * a product the file lists as reported or announced is never called available in the paid hub.
"""
from __future__ import annotations

import json
import os
import re
import unittest
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FILE = REPO / "scripts" / "paid_products.json"
SKILL = REPO / "skills" / "paid-advertising" / "SKILL.md"
WARN_DAYS = 30
FIELDS = ("platform", "product", "kind", "status", "availability", "since", "source_url", "source_date",
          "verified_on", "review_by", "note")
STATUSES = {"read", "reported"}
AVAILABILITY = {"live", "beta", "rolling_out", "announced"}


def today() -> date:
    frozen = os.environ.get("DMP_TODAY")
    return date.fromisoformat(frozen) if frozen else date.today()


def load() -> list[dict]:
    return json.loads(FILE.read_text(encoding="utf-8"))["products"]


def row_problems(rows: list[dict], on: date) -> list[str]:
    out = []
    seen = set()
    for row in rows:
        where = f"{row.get('platform')}/{row.get('product')}"
        missing = [k for k in FIELDS if k not in row]
        if missing:
            out.append(f"{where}: missing {', '.join(missing)}")
            continue
        if (row["platform"], row["product"]) in seen:
            out.append(f"{where}: listed twice")
        seen.add((row["platform"], row["product"]))
        if row["status"] not in STATUSES:
            out.append(f"{where}: status {row['status']!r} is not one of {sorted(STATUSES)}")
        if row["availability"] not in AVAILABILITY:
            out.append(f"{where}: availability {row['availability']!r} is not one of {sorted(AVAILABILITY)}")
        if not str(row["source_url"]).startswith("https://"):
            out.append(f"{where}: source_url must be an https URL")
        if row["status"] == "read" and not re.match(r"https://[^/]+/.+", row["source_url"]):
            out.append(f"{where}: a read row points at the page read, not a site root")
        if row["status"] == "reported" and not row["note"].startswith("REPORTED"):
            out.append(f"{where}: a reported row's note starts with REPORTED, so a reader sees it")
        if row["verified_on"] is None:
            out.append(f"{where}: verified_on is empty; a row is added only after its source was read")
        for k in ("since", "source_date", "verified_on"):
            if row[k] is not None:
                date.fromisoformat(row[k])
        due = date.fromisoformat(row["review_by"])
        if due - on <= timedelta(days=WARN_DAYS):
            out.append(f"{where}: review_by {due} is within {WARN_DAYS} days; re-read {row['source_url']} "
                       f"and update status, availability, verified_on and review_by")
    return out


class TestPaidProducts(unittest.TestCase):

    def test_every_row_has_provenance_and_a_review_date_ahead(self):
        problems = row_problems(load(), today())
        self.assertEqual(problems, [], "\n  " + "\n  ".join(problems))

    def test_the_paid_skill_reads_the_file(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("scripts/paid_products.json", text)
        for words in ("reported", "announced", "ad account"):
            self.assertIn(words, text, f"paid-advertising/SKILL.md no longer says what a {words!r} row means")

    def test_unconfirmed_products_are_not_called_available(self):
        # A product that is announced or rests on a press report must not be stated as available in
        # the paid hub's prose; the file holds it until a page is read.
        unconfirmed = [r["product"] for r in load()
                       if r["status"] == "reported" or r["availability"] in {"announced", "rolling_out"}]
        problems = []
        for path in sorted((REPO / "skills" / "paid-advertising").glob("*.md")):
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                for product in unconfirmed:
                    if product in line and re.search(r"\b(now available|available now|generally available|is live)\b",
                                                     line, re.I):
                        problems.append(f"{path.relative_to(REPO)}:{n}: calls {product!r} available")
        self.assertEqual(problems, [], "\n  " + "\n  ".join(problems))

    def test_plants(self):
        good = {"platform": "x", "product": "P", "kind": "k", "status": "read", "availability": "live", "since": None,
                "source_url": "https://example.com/page", "source_date": None, "verified_on": "2026-10-29",
                "review_by": "2026-12-31", "note": "n"}
        self.assertEqual(row_problems([good], date(2026, 11, 30)), [])
        self.assertIn("within 30 days", row_problems([good], date(2026, 12, 1))[0])
        bad = [dict(good, product="O", status="rumoured"), dict(good, product="Q", status="reported"),
               dict(good, product="R", source_url="https://example.com/"), dict(good, product="S", verified_on=None),
               dict(good, product="T", availability="soon"), good]
        got = row_problems(bad + [dict(good)], date(2026, 11, 1))
        self.assertEqual(len(got), 6, got)  # status, REPORTED note, site root, no verified_on, availability, twice


if __name__ == "__main__":
    unittest.main()
