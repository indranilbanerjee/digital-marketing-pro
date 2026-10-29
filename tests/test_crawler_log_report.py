"""scripts/crawler-log-report.py: what AI crawlers did, from the site's own logs (3.41.0).

The 2026-10-27 ecosystem review's borrow 3, built the way Brain A asked: robots.txt says what a
crawler may fetch and the logs say what it did, but a user-agent string proves nothing, so each
request is checked against the vendor's published addresses, which change weekly and so are
downloaded (--refresh-ranges, the only network call) into a dated local cache, never shipped.
The logs hold visitors' IP addresses (personal data under GDPR and the DPDP Act): they stay on
the machine, the report prints no full address and cuts query strings. The checks below plant
each failure: a spoofed crawler, a missing list, a partial list, a redirect, a broken download,
an address or an email in the output, a network call during a report.
"""
from __future__ import annotations

import gzip
import io
import json
import os
import re
import sys
import tempfile
import unittest
import urllib.error
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _helpers import PLUGIN_ROOT, import_script, run_script  # noqa: E402

crl = import_script("crawler-log-report.py", "crawler_log_report")
TABLE = json.loads((PLUGIN_ROOT / "scripts" / "crawler_ranges.json").read_text(encoding="utf-8"))
WARN_DAYS = 30

LISTS = {
    "https://openai.com/searchbot.json": {"creationTime": "2026-10-01T00:00:00", "prefixes": [{"ipv4Prefix": "20.42.10.176/28"}]},
    "https://openai.com/gptbot.json": {"creationTime": "2026-10-01T00:00:00", "prefixes": [{"ipv4Prefix": "52.230.152.0/24"}]},
    "https://claude.com/crawling/bots.json": {"creationTime": "2026-10-20T00:00:00Z",
                                              "prefixes": [{"ipv4Prefix": "216.73.216.0/22"}, {"ipv6Prefix": "2600:1f28:365:80b0::/60"}]},
}
DEFAULT_LIST = {"creationTime": "2026-10-01T00:00:00", "prefixes": [{"ipv4Prefix": "192.0.2.0/24"}]}

UA = {
    "search": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-SearchBot/1.3; +https://openai.com/searchbot",
    "gpt": "Mozilla/5.0 (compatible; GPTBot/1.2; +https://openai.com/gptbot)",
    "claude": "Mozilla/5.0 (compatible; ClaudeBot/1.0; +claudebot@anthropic.com)",
    "google_agent": "Mozilla/5.0 (compatible; Google-Agent)",
    "browser": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0",
}


def combined(ip, path, status, ua, when="28/Oct/2026:10:00:00 +0000"):
    return f'{ip} - - [{when}] "GET {path} HTTP/1.1" {status} 512 "-" "{ua}"'


LOG = "\n".join([
    combined("20.42.10.180", "/products/anvil?email=jane@example.com&token=abc", 200, UA["search"]),
    combined("20.42.10.181", "/robots.txt", 200, UA["search"]),
    combined("203.0.113.9", "/pricing", 200, UA["gpt"]),           # GPTBot, not from OpenAI's list
    combined("203.0.113.77", "/pricing", 200, UA["gpt"]),
    combined("216.73.216.10", "/missing", 404, UA["claude"]),
    combined("2600:1f28:365:80b1::5", "/", 200, UA["claude"]),       # IPv6, inside the /60
    'shop.example.com 52.230.152.4 - - [28/Oct/2026:11:00:00 +0000] "GET /a HTTP/1.1" 200 1 "-" "' + UA["gpt"] + '"',
    combined("198.51.100.7", "/", 200, UA["browser"]),
    "this is not a request",
]) + "\n"


def fake_get(url, timeout):
    return json.dumps(LISTS.get(url, DEFAULT_LIST)).encode("utf-8")


class _Isolated(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        env = {"CLAUDE_MARKETING_HOME": str(root / "cmh"), "HOME": str(root / "home"), "USERPROFILE": str(root / "home")}
        self.env = mock.patch.dict(os.environ, env)
        self.env.start()
        os.environ.pop("CLAUDE_PLUGIN_DATA", None)
        os.environ.pop("PLUGIN_DATA", None)
        self.root = root
        self.log = root / "access.log"
        self.log.write_text(LOG, encoding="utf-8")

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def refresh(self, getter=fake_get):
        with mock.patch.object(crl, "_http_get", side_effect=getter):
            return crl.refresh_ranges(TABLE)

    def report(self, logs=None, fmt="auto"):
        def no_network(*a, **k):
            raise AssertionError("a report must not touch the network")
        with mock.patch.object(crl, "_http_get", side_effect=no_network):
            return crl.build_report(logs or [self.log], fmt, 10, TABLE, crl.load_cache())

    def by_token(self, report):
        return {r["token"]: r for r in report["crawlers"]}


class TestTable(unittest.TestCase):

    def test_every_list_and_crawler_has_a_source_and_a_review_date_ahead(self):
        frozen = os.environ.get("DMP_TODAY")
        today = date.fromisoformat(frozen) if frozen else date.today()
        problems = []
        for name, entry in TABLE["lists"].items():
            if not entry["url"].startswith("https://") or not entry["docs_url"].startswith("https://"):
                problems.append(f"list {name}: url and docs_url must be https")
            if date.fromisoformat(entry["review_by"]) - today <= timedelta(days=WARN_DAYS):
                problems.append(f"list {name}: review_by {entry['review_by']} is within {WARN_DAYS} days; re-read {entry['docs_url']}")
        for row in TABLE["crawlers"]:
            for name in row["lists"]:
                if name not in TABLE["lists"]:
                    problems.append(f"{row['token']}: no list named {name}")
                elif TABLE["lists"][name]["vendor"] != row["vendor"]:
                    problems.append(f"{row['token']}: list {name} is {TABLE['lists'][name]['vendor']}'s, not {row['vendor']}'s")
            if date.fromisoformat(row["review_by"]) - today <= timedelta(days=WARN_DAYS):
                problems.append(f"{row['token']}: review_by {row['review_by']} is within {WARN_DAYS} days")
        self.assertEqual(problems, [], "\n  " + "\n  ".join(problems))

    def test_every_crawler_the_audit_names_is_counted(self):
        # The agent-readiness audit's crawler table and this report must not drift apart. Two tokens
        # there are robots.txt controls with no user agent of their own, so no log line carries them.
        skill = (PLUGIN_ROOT / "skills" / "agent-readiness-audit" / "SKILL.md").read_text(encoding="utf-8")
        audited = set(re.findall(r"^\|\s*`([A-Za-z-]+)`\s*\|", skill, re.M)) - {"Google-Extended", "Applebot-Extended"}
        counted = {row["token"] for row in TABLE["crawlers"]}
        self.assertEqual(sorted(audited - counted), [])

    def test_no_token_hides_another(self):
        # A token that is a substring of an earlier one would never be reached.
        tokens = [row["token"].lower() for row in TABLE["crawlers"]]
        clashes = [(a, b) for i, a in enumerate(tokens) for b in tokens[i + 1:] if a in b]
        self.assertEqual(clashes, [])


class TestReport(_Isolated):

    def test_without_the_lists_nothing_is_called_genuine(self):
        report = self.report()
        self.assertEqual(report["crawler_requests"]["verified"], 0)
        self.assertEqual(report["crawler_requests"]["spoofed"], 0)
        self.assertEqual(report["crawler_requests"]["unverified"], report["crawler_requests"]["requests"])
        self.assertTrue(report["ranges"]["lists_missing"])
        self.assertIn("--refresh-ranges", " ".join(report["findings"]))

    def test_verified_spoofed_ipv6_and_vhost(self):
        self.refresh()
        rows = self.by_token(self.report())
        self.assertEqual((rows["OAI-SearchBot"]["verified"], rows["OAI-SearchBot"]["spoofed"]), (2, 0))
        self.assertEqual((rows["GPTBot"]["verified"], rows["GPTBot"]["spoofed"]), (1, 2))
        self.assertEqual(rows["GPTBot"]["spoofing_networks"], [{"network": "203.0.113.0/24", "requests": 2}])
        self.assertEqual(rows["ClaudeBot"]["verified"], 2)  # one IPv4, one IPv6
        self.assertEqual(rows["ClaudeBot"]["status"], {"2xx": 1, "4xx": 1})
        self.assertEqual(rows["OAI-SearchBot"]["robots_txt_fetches"], 1)
        self.assertEqual(rows["OAI-SearchBot"]["first_seen"], "2026-10-28T10:00:00Z")
        self.assertNotIn("Chrome", json.dumps(rows))
        self.assertTrue(any("GPTBot from addresses OpenAI does not publish" in f for f in self.report()["findings"]))

    def test_a_partial_list_set_never_calls_a_request_spoofed(self):
        # Google-Agent may come from any of three Google lists; with only one downloaded, an address
        # outside it is unknown, not spoofed.
        self.refresh()
        cache = crl.load_cache()
        for name in ("google-user-triggered-fetchers-google", "google-user-triggered-fetchers"):
            cache["lists"].pop(name)
        crl._common.atomic_write_json(crl.cache_path(), cache)
        self.log.write_text(combined("198.18.0.1", "/", 200, UA["google_agent"]) + "\n", encoding="utf-8")
        row = self.by_token(self.report())["Google-Agent"]
        self.assertEqual((row["verified"], row["spoofed"], row["unverified"]), (0, 0, 1))

    def test_no_full_address_or_query_string_reaches_the_output(self):
        self.refresh()
        text = json.dumps(self.report())
        for ip in ("20.42.10.180", "203.0.113.9", "216.73.216.10", "2600:1f28:365:80b1::5", "52.230.152.4", "198.51.100.7"):
            self.assertNotIn(ip, text)
        self.assertNotIn("jane@example.com", text)
        self.assertNotIn("token=abc", text)
        self.assertIn('"/products/anvil"', text)

    def test_json_lines_and_gzip(self):
        self.refresh()
        lines = [{"ClientIP": "20.42.10.177", "ClientRequestUserAgent": UA["search"], "ClientRequestURI": "/x?q=1",
                  "EdgeResponseStatus": 200, "EdgeStartTimestamp": 1793181600000000000},
                 {"ip": "203.0.113.5", "user_agent": UA["gpt"], "path": "/y", "status": "503", "time": "2026-10-28T09:00:00Z"}]
        gz = self.root / "cf.jsonl.gz"
        with gzip.open(gz, "wt", encoding="utf-8") as fh:
            fh.write("\n".join(json.dumps(x) for x in lines) + "\n")
        rows = self.by_token(self.report([gz], "jsonl"))
        self.assertEqual(rows["OAI-SearchBot"]["verified"], 1)
        self.assertEqual(rows["OAI-SearchBot"]["top_paths"], [{"path": "/x", "requests": 1}])
        self.assertEqual(rows["GPTBot"]["spoofed"], 1)

    def test_stale_lists_are_flagged(self):
        self.refresh()
        cache = crl.load_cache()
        old = (date.today() - timedelta(days=40)).isoformat() + "T00:00:00Z"
        for entry in cache["lists"].values():
            entry["fetched_on"] = old
        crl._common.atomic_write_json(crl.cache_path(), cache)
        report = self.report()
        self.assertTrue(report["ranges"]["stale"])
        self.assertTrue(any("days old" in f for f in report["findings"]))

    def test_a_byte_order_mark_and_odd_bytes_are_read(self):
        self.refresh()
        self.log.write_bytes(b"\xef\xbb\xbf" + combined("20.42.10.180", "/caf\xe9", 200, UA["search"]).encode("latin-1") + b"\n")
        self.assertEqual(self.by_token(self.report())["OAI-SearchBot"]["verified"], 1)


class TestRefresh(_Isolated):

    def test_the_cache_holds_every_list_with_its_date(self):
        result = self.refresh()
        self.assertEqual(result["failed"], [])
        self.assertEqual(len(result["fetched"]), len(TABLE["lists"]))
        cache = json.loads(crl.cache_path().read_text(encoding="utf-8"))
        self.assertTrue(str(crl.cache_path()).startswith(os.environ["CLAUDE_MARKETING_HOME"]))
        self.assertTrue(all(e["fetched_on"] and e["prefixes"] for e in cache["lists"].values()))

    def test_a_failed_list_keeps_its_last_good_copy(self):
        self.refresh()
        good = crl.load_cache()["lists"]["anthropic-bots"]

        def broken(url, timeout):
            if url == "https://claude.com/crawling/bots.json":
                raise urllib.error.HTTPError(url, 302, "Found", {"Location": "https://elsewhere.example/x.json"}, io.BytesIO())
            return fake_get(url, timeout)

        result = self.refresh(broken)
        self.assertEqual([f["list"] for f in result["failed"]], ["anthropic-bots"])
        self.assertIn("not followed", result["failed"][0]["error"])
        self.assertEqual(crl.load_cache()["lists"]["anthropic-bots"]["prefixes"], good["prefixes"])

    def test_a_broken_download_is_a_failure_not_an_empty_list(self):
        for body in (b"<html>blocked</html>", b'{"prefixes": []}', b'{"prefixes": [{"ipv4Prefix": "not-an-ip"}]}'):
            with self.subTest(body=body):
                result = self.refresh(lambda url, timeout, b=body: b)
                self.assertEqual(result["fetched"], [])
                self.assertIn("error", result)
                self.assertFalse(crl.cache_path().exists())

    def test_a_non_https_list_is_never_fetched(self):
        table = json.loads(json.dumps(TABLE))
        table["lists"] = {"x": {"url": "http://openai.com/searchbot.json", "vendor": "OpenAI"}}
        calls = []
        with mock.patch.object(crl, "_http_get", side_effect=lambda url, timeout: calls.append(url)):
            result = crl.refresh_ranges(table)
        self.assertEqual(calls, [])
        self.assertIn("https", result["failed"][0]["error"])

    def test_the_fetch_follows_no_redirect(self):
        handler = crl._NoRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 302, "Found", {}, "https://elsewhere.example/"))


class TestCli(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.env = {"HOME": str(self.home), "USERPROFILE": str(self.home)}

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args):
        return run_script("crawler-log-report.py", *args, marketing_home=self.home / "cmh", env=self.env)

    def test_exit_codes(self):
        self.assertEqual(self.run_cli().returncode, 2)
        self.assertEqual(self.run_cli("--log", "-").returncode, 2)
        self.assertEqual(self.run_cli("--log", "x.log", "--top", "0").returncode, 2)
        self.assertEqual(self.run_cli("--help").returncode, 0)
        missing = self.run_cli("--log", str(self.home / "nope.log"))
        self.assertEqual(missing.returncode, 1)
        self.assertIn("no such log file", json.loads(missing.stdout)["error"])

    def test_a_report_runs_offline(self):
        log = self.home / "a.log"
        log.write_text(LOG, encoding="utf-8")
        proc = self.run_cli("--log", str(log))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out["crawler_requests"]["unverified"], out["crawler_requests"]["requests"])


class TestDocs(unittest.TestCase):

    def test_privacy_names_the_one_network_call_and_the_local_logs(self):
        text = (PLUGIN_ROOT / "PRIVACY.md").read_text(encoding="utf-8")
        self.assertIn("crawler-log-report.py", text)
        self.assertIn("--refresh-ranges", text)
        self.assertIn("never leave", text)

    def test_the_audit_skill_points_at_the_report(self):
        text = (PLUGIN_ROOT / "skills" / "agent-readiness-audit" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("crawler-log-report.py", text)
        self.assertIn("--refresh-ranges", text)


if __name__ == "__main__":
    unittest.main()
