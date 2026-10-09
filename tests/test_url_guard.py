"""The fetch scripts only ever request public http(s) addresses, on every hop.

Hermes review (smaller notes): tech-seo-auditor used the default opener (so
file:// worked) and followed redirects by hand without checks;
competitor-scraper let requests follow redirects; agent-readiness-audit fetched
--page URLs unchecked. Now every hop goes through `_common.public_url_error`
(or agent-readiness-audit's standalone copy, which must agree with it):
http/https only, and the host must resolve only to public addresses.

DNS is mocked: no test here resolves a real name.

Stdlib only (the competitor-scraper case is skipped without `requests`).
"""
from __future__ import annotations

import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _helpers import SCRIPTS_DIR, import_script  # noqa: E402

sys.path.insert(0, str(SCRIPTS_DIR))
import _common  # noqa: E402

ara = import_script("agent-readiness-audit.py", module_name="ara_url_guard")
tsa = import_script("tech-seo-auditor.py", module_name="tsa_url_guard")

HOSTS = {
    "public.example": "93.184.216.34",
    "loop.example": "127.0.0.1",
    "lan.example": "10.0.0.5",
    "lan2.example": "192.168.1.20",
    "meta.example": "169.254.169.254",
    "cgnat.example": "100.64.0.1",
    "v6loop.example": "::1",
    "v6local.example": "fe80::1",
}


def fake_getaddrinfo(host, port, *a, **kw):
    ip = HOSTS.get(host, host)  # bare IP literals resolve to themselves
    fam = 10 if ":" in ip else 2
    return [(fam, 1, 6, "", (ip, port))]


def dns():
    return mock.patch("socket.getaddrinfo", side_effect=fake_getaddrinfo)


class TestRule(unittest.TestCase):
    CASES = {
        "https://public.example/page": True,
        "http://public.example:8080/x": True,
        "https://loop.example/": False,
        "http://lan.example/": False,
        "http://lan2.example/": False,
        "http://meta.example/latest/meta-data/": False,
        "http://cgnat.example/": False,
        "http://v6loop.example/": False,
        "http://v6local.example/": False,
        "http://127.0.0.1/": False,
        "http://169.254.169.254/": False,
        "file:///etc/passwd": False,
        "ftp://public.example/": False,
        "gopher://public.example/": False,
        "https:///nohost": False,
    }

    def test_rule_table(self):
        with dns():
            for url, ok in self.CASES.items():
                with self.subTest(url=url):
                    self.assertEqual(_common.public_url_error(url) is None, ok, _common.public_url_error(url))

    def test_standalone_copy_agrees(self):
        with dns():
            for url in self.CASES:
                with self.subTest(url=url):
                    self.assertEqual(_common.public_url_error(url) is None, ara._public_url_error(url) is None)


def _redirect_to(location):
    def raise_redirect(*a, **kw):
        raise urllib.error.HTTPError("https://public.example/", 302, "Found", {"Location": location}, None)
    return raise_redirect


class TestTechSeoAuditor(unittest.TestCase):
    def test_private_first_hop_is_refused_before_any_request(self):
        with dns(), mock.patch("urllib.request.build_opener") as build:
            url, status, hops, headers, body, ttfb, err = tsa.follow_redirects("http://lan.example/", 5)
        build.assert_not_called()
        self.assertIsNone(status)
        self.assertIn("non-public", err)

    def test_file_scheme_is_refused(self):
        with mock.patch("urllib.request.build_opener") as build:
            err = tsa.follow_redirects("file:///etc/hosts", 5)[-1]
        build.assert_not_called()
        self.assertIn("http", err)

    def test_redirect_to_metadata_is_refused(self):
        opener = mock.Mock()
        opener.open.side_effect = _redirect_to("http://meta.example/latest/meta-data/")
        with dns(), mock.patch("urllib.request.build_opener", return_value=opener):
            url, status, hops, headers, body, ttfb, err = tsa.follow_redirects("https://public.example/", 5)
        self.assertEqual(opener.open.call_count, 1, "the private hop must not be requested")
        self.assertIn("non-public", err)
        self.assertEqual(hops[0]["to"], "http://meta.example/latest/meta-data/")


class TestAgentReadinessFetch(unittest.TestCase):
    def test_private_and_file_urls_are_refused(self):
        with dns(), mock.patch.object(ara, "_http_open") as opened:
            for url in ("http://lan.example/", "file:///etc/hosts", "http://169.254.169.254/"):
                with self.subTest(url=url):
                    code, body, err = ara.fetch(url)
                    self.assertIsNone(code)
                    self.assertTrue(err)
        opened.assert_not_called()

    def test_redirect_hop_to_private_is_refused(self):
        with dns(), mock.patch.object(ara, "_http_open", side_effect=_redirect_to("http://loop.example/admin")) as o:
            code, body, err = ara.fetch("https://public.example/")
        self.assertEqual(o.call_count, 1)
        self.assertIn("non-public", err)


class TestCompetitorScraper(unittest.TestCase):
    def setUp(self):
        try:
            import requests  # noqa: F401
        except ImportError:
            self.skipTest("requests not installed (competitor-scraper's optional dependency)")
        self.cs = import_script("competitor-scraper.py", module_name="cs_url_guard")

    def test_redirect_hop_to_private_is_refused(self):
        first = mock.Mock(status_code=302, headers={"Location": "http://lan.example/internal"})
        with dns(), mock.patch.object(self.cs.requests, "get", return_value=first) as get:
            with self.assertRaises(self.cs.UnsafeURL):
                self.cs.get_public("https://public.example/", timeout=5, headers={})
        self.assertEqual(get.call_count, 1)
        self.assertFalse(get.call_args.kwargs.get("allow_redirects", True), "requests must not follow redirects itself")

    def test_private_target_is_refused_without_a_request(self):
        with dns(), mock.patch.object(self.cs.requests, "get") as get:
            with self.assertRaises(self.cs.UnsafeURL):
                self.cs.get_public("http://loop.example/", timeout=5, headers={})
        get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
