"""Platform API versions live in one dated table, and the table must not rot.

The failure this prevents: Meta Marketing API v24.0 sat hard-coded at four
call sites while its sunset (10 Nov 2026) approached, and nothing in the repo
knew the date. LinkedIn's /rest/adCampaignsV2 left the versioned docs the
same way, and skill prose told readers to "target v24.2" and "move
integrations to 202609" while the code sent 202606.

So:
  * scripts/connector_resolver.py API_VERSIONS holds every pinned version with
    its sunset date, the vendor page that states it, and the day someone last
    read that page.
  * A version within SUNSET_WARN_DAYS of its sunset FAILS the suite.
  * A row not re-read for VERIFY_MAX_DAYS FAILS the suite, so an undated
    sunset ("TBD") still gets looked at.
  * No manifest hard-codes a version; every one comes from the table.
  * Prose that names a target version must point at API_VERSIONS and agree
    with it.

These tests are SUPPOSED to go red as time passes; the weekly scheduled CI job
(.github/workflows/dated-checks.yml) runs them so a quiet repo finds out too.
DMP_TODAY=YYYY-MM-DD freezes "today" for planting.
"""
from __future__ import annotations

import os
import re
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))

import connector_resolver as cr  # noqa: E402

SUNSET_WARN_DAYS = 30
VERIFY_MAX_DAYS = 120

# Folders the model is never sent to, plus history that is allowed to name
# old versions (CHANGELOG records what was true at the time).
SKIP_DIRS = {".git", "tests", "research", "evals", "node_modules", "__pycache__"}
SKIP_FILES = {"CHANGELOG.md"}
PROSE_SUFFIXES = {".md", ".json", ".example", ".connectors-reference", ".yaml", ".yml"}

VERSION = r"(?<![\w.])\**`?(v\d{2}(?:\.\d+)?|20\d{4})\b"
# "target v26", "pins Google Ads API v26", "move integrations to 202610" ...
TARGET_BEFORE = re.compile(
    r"\b(?:target(?:s|ing)?|pins?|pinned(?: to)?|stable target|"
    r"(?:move|upgrade|migrate) (?:integrations|clients) to)\b[^\n]{0,80}?" + VERSION, re.I)
# ... and "v24.2 remains DMP's stable target".
TARGET_AFTER = re.compile(VERSION + r"\**`?[^\n]{0,40}?\b(?:remains|is)\b[^\n]{0,30}?\btarget\b", re.I)

PLATFORM_WORDS = [  # LinkedIn before Meta: both say "Marketing API"
    ("linkedin", re.compile(r"LinkedIn", re.I)),
    ("google_ads", re.compile(r"Google Ads|googleads", re.I)),
    ("tiktok", re.compile(r"TikTok", re.I)),
    ("klaviyo", re.compile(r"Klaviyo", re.I)),
    ("x_ads", re.compile(r"\bX Ads\b|ads-api\.twitter", re.I)),
    ("meta", re.compile(r"\bMeta\b|Graph API|(?<!LinkedIn )(?<!TikTok )Marketing API|facebook",
                        re.I)),
]
FILE_PLATFORM = {"google-ads.md": "google_ads", "meta-ads.md": "meta",
                 "linkedin-ads.md": "linkedin", "tiktok-ads.md": "tiktok"}


def today() -> date:
    frozen = os.environ.get("DMP_TODAY")
    return date.fromisoformat(frozen) if frozen else date.today()


def sunset_problems(table: dict, on: date) -> list[str]:
    out = []
    for name, row in table.items():
        if not row.get("sunset"):
            continue
        sunset = date.fromisoformat(row["sunset"])
        if on >= sunset - timedelta(days=SUNSET_WARN_DAYS):
            out.append(f"{name} {row['version']} sunsets {row['sunset']} "
                       f"({(sunset - on).days} days): move to a newer version, "
                       f"see {row['source']}")
    return out


def verification_problems(table: dict, on: date) -> list[str]:
    out = []
    for name, row in table.items():
        for field in ("version", "source", "sunset_basis"):
            if not row.get(field):
                out.append(f"{name}: missing {field}")
        verified = row.get("verified_on")
        if verified is None:
            if not row.get("verify_note"):
                out.append(f"{name}: verified_on is None and no verify_note says why")
            continue
        age = (on - date.fromisoformat(verified)).days
        if age > VERIFY_MAX_DAYS:
            out.append(f"{name}: last read {verified} ({age} days ago); re-read {row['source']}")
    return out


def _normal(v: str) -> str:
    v = v.lower().lstrip("v")
    return v[:-2] if v.endswith(".0") else v


def _platform(line: str, end: int, path: Path) -> str | None:
    best, best_pos = None, -1
    head = line[:end]
    for name, rx in PLATFORM_WORDS:
        for m in rx.finditer(head):
            if m.start() > best_pos:
                best, best_pos = name, m.start()
    return best or FILE_PLATFORM.get(path.name)


def prose_target_problems(root: Path, table: dict) -> list[str]:
    out = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in PROSE_SUFFIXES:
            continue
        rel = path.relative_to(root)
        if path.name in SKIP_FILES or set(rel.parts) & SKIP_DIRS:
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for n, line in enumerate(text.splitlines(), 1):
            for rx in (TARGET_BEFORE, TARGET_AFTER):
                for m in rx.finditer(line):
                    platform = _platform(line, m.end(), path)
                    if platform is None:
                        continue
                    named = m.group(1)
                    want = table[platform]["version"]
                    if "API_VERSIONS" not in line:
                        out.append(f"{rel}:{n}: names target {named} for {platform} without "
                                   f"pointing at API_VERSIONS (currently {want})")
                    elif _normal(named) != _normal(want):
                        out.append(f"{rel}:{n}: says {named} for {platform}; "
                                   f"API_VERSIONS has {want}")
    return out


HARDCODED = [
    re.compile(r"graph\.facebook\.com/v\d"),
    re.compile(r"googleads\.googleapis\.com/v\d"),
    re.compile(r"\"LinkedIn-Version\":\s*\"\d"),
    re.compile(r"open_api/v\d"),
    re.compile(r"ads-api\.twitter\.com/\d"),
    re.compile(r"\"revision\":\s*\"\d"),
]


def hardcoded_problems(source: str) -> list[str]:
    body = source.split("META_GRAPH_BASE =", 1)[-1]  # everything after the table
    out = [f"hard-coded version: {m.group(0)}"
           for rx in HARDCODED for m in rx.finditer(body)]
    if "adCampaignsV2" in source:
        out.append("LinkedIn /rest/adCampaignsV2 is not in the versioned docs; "
                   "use /rest/adAccounts/{id}/adCampaigns")
    if "developer-token" in source or "DEVELOPER_TOKEN" in source:
        out.append("Google Ads developer tokens were sunset on 9 Sep 2026; "
                   "drop the header and the variable")
    return out


class TestApiVersionTable(unittest.TestCase):

    def test_no_version_within_30_days_of_sunset(self):
        problems = sunset_problems(cr.API_VERSIONS, today())
        self.assertEqual(problems, [], "\n  " + "\n  ".join(problems))

    def test_every_row_was_read_recently(self):
        problems = verification_problems(cr.API_VERSIONS, today())
        self.assertEqual(problems, [], "\n  " + "\n  ".join(problems))

    def test_sunset_check_catches_meta_v24(self):
        """The plant: v24.0 with its real sunset fails on 2026-10-27."""
        old = {"meta": {"version": "v24.0", "sunset": "2026-11-10", "sunset_basis": "x",
                        "source": "s", "verified_on": "2026-10-04"}}
        self.assertTrue(sunset_problems(old, date(2026, 10, 27)))
        self.assertEqual(sunset_problems(old, date(2026, 10, 10)), [])

    def test_staleness_check_catches_an_unread_row(self):
        stale = {"x": {"version": "1", "sunset": None, "sunset_basis": "x",
                       "source": "s", "verified_on": "2026-01-01"}}
        self.assertTrue(verification_problems(stale, date(2026, 10, 27)))
        unexplained = {"x": {"version": "1", "sunset": None, "sunset_basis": "x",
                             "source": "s", "verified_on": None}}
        self.assertTrue(verification_problems(unexplained, date(2026, 10, 27)))


def deadline_problems(table: dict, resolver_source: str, on: date) -> list[str]:
    """A vendor deadline that retires endpoints: fail 30 days ahead while a template
    still calls an affected path. Once no template does, the row is informational."""
    out = []
    body = resolver_source.split("META_GRAPH_BASE =", 1)[-1]
    for name, row in table.items():
        for d in row.get("deadlines", []):
            when = date.fromisoformat(d["date"])
            used = [p for p in d.get("affected_paths", []) if f'+ "{p}"' in body]
            if used and on >= when - timedelta(days=SUNSET_WARN_DAYS):
                out.append(f"{name}: {', '.join(used)} still used; {d['what']} on {d['date']}")
    return out


class TestVendorDeadlines(unittest.TestCase):

    def test_no_template_uses_an_endpoint_near_its_cutoff(self):
        source = (SCRIPTS / "connector_resolver.py").read_text(encoding="utf-8")
        problems = deadline_problems(cr.API_VERSIONS, source, today())
        self.assertEqual(problems, [], "\n  " + "\n  ".join(problems))

    def test_tiktok_cutoff_is_recorded(self):
        tiktok = cr.API_VERSIONS["tiktok"]
        self.assertEqual(tiktok["deadlines"][0]["date"], "2027-01-01")
        self.assertIn("/campaign/create/", tiktok["deadlines"][0]["affected_paths"])

    def test_plant_a_legacy_create_template(self):
        table = {"tiktok": {"deadlines": [{"date": "2027-01-01", "what": "legacy create ends",
                                           "affected_paths": ["/campaign/create/"]}]}}
        source = 'META_GRAPH_BASE = "x"\n"url": TIKTOK_BASE + "/campaign/create/",\n'
        self.assertTrue(deadline_problems(table, source, date(2026, 12, 5)))
        self.assertEqual(deadline_problems(table, source, date(2026, 11, 1)), [])

    def test_launch_template_targets_upgraded_smart_plus(self):
        launch = cr._manifest_launch_ads("tiktok-ads", "b", {})["http_request"]
        self.assertTrue(launch["url"].endswith("/smart_plus/campaign/status/update/"))
        self.assertTrue(launch["legacy_flow_url"].endswith("/campaign/status/update/"))


class TestManifestsUseTheTable(unittest.TestCase):

    def test_no_hardcoded_versions_in_resolver(self):
        source = (SCRIPTS / "connector_resolver.py").read_text(encoding="utf-8")
        problems = hardcoded_problems(source)
        self.assertEqual(problems, [], "\n  " + "\n  ".join(problems))

    def test_hardcoded_check_catches_the_old_templates(self):
        old = ('META_GRAPH_BASE = "x"\n"url": "https://graph.facebook.com/v24.0/act_1/campaigns"\n'
               '"url": "https://api.linkedin.com/rest/adCampaignsV2"\n'
               '"developer-token": "{GOOGLE_ADS_DEVELOPER_TOKEN}"\n')
        self.assertEqual(len(hardcoded_problems(old)), 3)

    def test_built_manifests_carry_table_versions(self):
        v = cr.API_VERSIONS
        inv = {c: cr._manifest_inventory(c, "b", {"channel": "x"})["http_request"]
               for c in ("google-ads", "meta-marketing", "linkedin-marketing", "tiktok-ads",
                         "twitter-x")}
        self.assertIn("/" + v["google_ads"]["version"] + "/", inv["google-ads"]["url"])
        self.assertNotIn("developer-token", inv["google-ads"]["headers"])
        self.assertIn("/" + v["meta"]["version"] + "/", inv["meta-marketing"]["url"])
        self.assertEqual(inv["linkedin-marketing"]["headers"]["LinkedIn-Version"],
                         v["linkedin"]["version"])
        self.assertIn("/rest/adAccounts/{LINKEDIN_AD_ACCOUNT_ID}/adCampaigns",
                      inv["linkedin-marketing"]["url"])
        self.assertIn("/" + v["tiktok"]["version"] + "/", inv["tiktok-ads"]["url"])
        self.assertIn("/" + v["x_ads"]["version"] + "/", inv["twitter-x"]["url"])
        launch = cr._manifest_launch_ads("linkedin-marketing", "b", {})["http_request"]
        self.assertTrue(launch["url"].endswith("/adAccounts/{LINKEDIN_AD_ACCOUNT_ID}"
                                               "/adCampaigns/{campaign_id}"))
        self.assertEqual(launch["headers"]["X-RestLi-Method"], "PARTIAL_UPDATE")
        posts = cr._manifest_cadence("meta-graph", "b", {})["http_request"]
        self.assertIn("/" + v["meta"]["version"] + "/", posts["url"])
        for gone in ("post_impressions", "post_engaged_users"):  # deprecated above v25 / undocumented
            self.assertNotIn(gone, posts["params"]["fields"])
        flows = cr._manifest_automations("klaviyo", "b", {"channel": "email"})["http_request"]
        self.assertEqual(flows["headers"]["revision"], v["klaviyo"]["version"])


class TestProseAgreesWithTheTable(unittest.TestCase):

    def test_target_versions_in_prose_match_the_table(self):
        problems = prose_target_problems(REPO, cr.API_VERSIONS)
        self.assertEqual(problems, [], "\n  " + "\n  ".join(problems))

    def test_prose_check_catches_the_old_wording(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "skills").mkdir()
            (root / "skills" / "google-ads.md").write_text(
                "target **v24.2** (released 24 June 2026)\n"
                "**v24.2 remains DMP's deliberate stable target**\n", encoding="utf-8")
            (root / "skills" / "SKILL.md").write_text(
                "**LinkedIn Marketing API:** move integrations to `202609`.\n"
                "Google Ads: target the version in API_VERSIONS (currently v25).\n"
                "Google Ads: target the version in API_VERSIONS (currently v26).\n",
                encoding="utf-8")
            table = {"google_ads": {"version": "v26"}, "linkedin": {"version": "202610"},
                     "meta": {"version": "v26.0"}}
            problems = prose_target_problems(root, table)
        self.assertEqual(len(problems), 4, problems)
        self.assertTrue(any("202609 for linkedin" in p for p in problems), problems)


class TestScheduledJob(unittest.TestCase):
    """The dated tests only help if something runs them on a quiet repo."""

    def test_weekly_workflow_runs_the_dated_tests(self):
        wf = (REPO / ".github" / "workflows" / "dated-checks.yml").read_text(encoding="utf-8")
        self.assertRegex(wf, r"schedule:\s*\n\s*- cron: \"[^\"]+\"")
        self.assertIn("python tests/run_all.py --dated", wf)
        self.assertIn("issues: write", wf)
        self.assertIn("gh issue create", wf)

    def test_dated_list_names_real_test_modules(self):
        import run_all
        self.assertIn("test_api_versions", run_all.DATED_TESTS)
        for name in run_all.DATED_TESTS:
            self.assertTrue((REPO / "tests" / f"{name}.py").is_file(), name)


if __name__ == "__main__":
    unittest.main()
