"""scripts/refresh_models.py: every page of every list, and no key anywhere but its header.

Through 3.39.0's first commits the drift report built the Gemini call as `.../models?key=<key>`
(proxies and server logs keep URLs) and read only the first page of every list: Anthropic's
default page is 20 models and Google's 50, so a model on page two was reported STALE ("in
registry, not in provider list"). Planted before the fix, through a recording opener:
  * the Gemini key travels only in the x-goog-api-key header: in no URL, no error text and
    nothing printed;
  * Anthropic is read by has_more/last_id and Google by nextPageToken, every page (two-page
    fixtures); OpenAI's list is one page, and Evolink, whose docs do not describe the endpoint,
    is read the same way, following has_more/last_id if it ever sends them;
  * a refused call (HTTP 400, 401, 403) is reported without any part of the key, even when the
    provider's error body echoes part of it.
Stdlib only; no test touches the network.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import unittest
import urllib.error
import urllib.parse
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "model_router"
sys.path.insert(0, str(SCRIPTS))
import refresh_models as rm  # noqa: E402

KEYS = {  # test values; no six-character run is shared, so a leak names the right key
    "ANTHROPIC_API_KEY": "ak-Qw7Zp2Yx9AnthMv31Tz",
    "OPENAI_API_KEY": "ok-Lm4Xc8Tq0OpaiBv72Wn",
    "GEMINI_API_KEY": "gk-Rt5Vb3Ws6GemnNc54Pq",
    "EVOLINK_API_KEY": "ek-Hn6Ys1Pd2EvolJr85Kx",
}
EVOLINK = {"object": "list", "data": [{"id": "evo-image-one", "object": "model"},
                                      {"id": "evo-video-two", "object": "model"}]}


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def pieces(secret: str, size: int = 6) -> list:
    """Every run of `size` characters of a key: a printed fragment counts as a leak."""
    return [secret[i:i + size] for i in range(len(secret) - size + 1)]


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Recorder:
    """Serves recorded pages per host, in order, and keeps every request."""

    PAGES = {
        "api.anthropic.com": ["anthropic_models_page1.json", "anthropic_models_page2.json"],
        "generativelanguage.googleapis.com": ["google_models_page1.json", "google_models_page2.json"],
        "api.openai.com": ["openai_models.json"],
        "direct.evolink.ai": [EVOLINK],
    }

    def __init__(self, refuse=None):
        self.requests, self.refuse = [], refuse or {}

    def __call__(self, req, timeout=None):
        self.requests.append(req)
        host = urllib.parse.urlsplit(req.full_url).netloc
        if host in self.refuse:
            code, body = self.refuse[host]
            raise urllib.error.HTTPError(req.full_url, code, "refused", {}, io.BytesIO(json.dumps(body).encode()))
        seen = sum(1 for r in self.requests if urllib.parse.urlsplit(r.full_url).netloc == host)
        page = self.PAGES[host][min(seen, len(self.PAGES[host])) - 1]
        return Resp(json.dumps(fixture(page) if isinstance(page, str) else page).encode())

    def to(self, host: str) -> list:
        return [r for r in self.requests if urllib.parse.urlsplit(r.full_url).netloc == host]


def run_main(recorder, env=None) -> tuple:
    out, err = io.StringIO(), io.StringIO()
    clean = {k: v for k, v in os.environ.items() if k not in KEYS}
    with mock.patch.dict(os.environ, {**clean, **(KEYS if env is None else env)}, clear=True), \
            mock.patch("urllib.request.urlopen", recorder), mock.patch.object(sys, "argv", ["refresh_models.py", "--json"]), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = rm.main()
    return code, out.getvalue(), err.getvalue()


class TestGeminiKeyStaysInItsHeader(unittest.TestCase):

    def test_the_key_is_in_the_header_and_in_no_url(self):
        rec = Recorder()
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": KEYS["GEMINI_API_KEY"]}):
            got = rm.list_gemini(urlopen=rec)
        self.assertTrue(rec.requests)
        for req in rec.requests:
            self.assertNotIn(KEYS["GEMINI_API_KEY"], req.full_url)
            self.assertNotIn("key", urllib.parse.parse_qs(urllib.parse.urlsplit(req.full_url).query))
            self.assertEqual(req.get_header("X-goog-api-key"), KEYS["GEMINI_API_KEY"])
        self.assertIn("gemini-3.8-flash", got)

    def test_nothing_printed_carries_any_key(self):
        rec = Recorder()
        code, out, err = run_main(rec)
        self.assertEqual(code, 0)
        report = json.loads(out)
        for vendor in ("anthropic", "openai", "google", "evolink"):
            self.assertEqual(report[vendor]["status"], "checked", report[vendor])
        for name, secret in KEYS.items():
            for bit in pieces(secret):
                self.assertNotIn(bit, out + err, f"part of {name} printed")
                for req in rec.requests:
                    self.assertNotIn(bit, req.full_url, f"part of {name} in a URL")


class TestEveryPage(unittest.TestCase):

    def test_anthropic_reads_every_page(self):
        rec = Recorder()
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": KEYS["ANTHROPIC_API_KEY"]}):
            got = rm.list_anthropic(urlopen=rec)
        both = fixture("anthropic_models_page1.json")["data"] + fixture("anthropic_models_page2.json")["data"]
        self.assertEqual(len(rec.to("api.anthropic.com")), 2)
        self.assertEqual(got, {m["id"] for m in both if m.get("lifecycle") != "retired"})
        self.assertIn("claude-sonnet-4-6", got)  # on page two only
        self.assertNotIn("claude-3-5-haiku-20241022", got)  # retired: listed, but not live
        self.assertEqual(rec.requests[0].get_header("X-api-key"), KEYS["ANTHROPIC_API_KEY"])

    def test_google_reads_every_page(self):
        rec = Recorder()
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": KEYS["GEMINI_API_KEY"]}):
            got = rm.list_gemini(urlopen=rec)
        both = fixture("google_models_page1.json")["models"] + fixture("google_models_page2.json")["models"]
        self.assertEqual(len(rec.to("generativelanguage.googleapis.com")), 2)
        self.assertEqual(got, {m["name"].replace("models/", "") for m in both})
        self.assertIn("gemini-embedding-2", got)  # on page two only
        second = urllib.parse.parse_qs(urllib.parse.urlsplit(rec.requests[1].full_url).query)
        self.assertEqual(second["pageToken"], ["Cg10ZXN0LXBhZ2UtdHdv"])

    def test_openai_and_evolink_read_one_page_unless_told_there_is_more(self):
        rec = Recorder()
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": KEYS["OPENAI_API_KEY"],
                                          "EVOLINK_API_KEY": KEYS["EVOLINK_API_KEY"]}):
            openai, evolink = rm.list_openai(urlopen=rec), rm.list_evolink(urlopen=rec)
        self.assertEqual(openai, {m["id"] for m in fixture("openai_models.json")["data"]})
        self.assertEqual(evolink, {"evo-image-one", "evo-video-two"})
        self.assertEqual((len(rec.to("api.openai.com")), len(rec.to("direct.evolink.ai"))), (1, 1))
        self.assertEqual(rec.to("direct.evolink.ai")[0].get_header("Authorization"), f"Bearer {KEYS['EVOLINK_API_KEY']}")

        paged = Recorder()
        paged.PAGES = dict(Recorder.PAGES, **{"direct.evolink.ai": [
            {"object": "list", "data": [{"id": "evo-image-one"}], "has_more": True, "last_id": "evo-image-one"},
            {"object": "list", "data": [{"id": "evo-video-two"}], "has_more": False}]})
        with mock.patch.dict(os.environ, {"EVOLINK_API_KEY": KEYS["EVOLINK_API_KEY"]}):
            self.assertEqual(rm.list_evolink(urlopen=paged), {"evo-image-one", "evo-video-two"})
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(paged.requests[1].full_url).query)
        self.assertEqual(query["after"], ["evo-image-one"])

    def test_a_list_cut_at_the_page_cap_is_skipped_not_short(self):
        """21 pages, each saying there is another: a short list would report models STALE."""
        endless = Recorder()
        endless.PAGES = dict(Recorder.PAGES, **{"direct.evolink.ai": [
            {"object": "list", "data": [{"id": f"evo-model-{n}"}], "has_more": True, "last_id": f"evo-model-{n}"}
            for n in range(1, 30)]})
        code, out, _ = run_main(endless, env={"EVOLINK_API_KEY": KEYS["EVOLINK_API_KEY"]})
        status = json.loads(out)["evolink"]["status"]
        self.assertTrue(status.startswith("skipped (fetch failed: schema:"), status)
        self.assertIn("pages", status)
        self.assertEqual(len(endless.to("direct.evolink.ai")), 20)

    def test_page_two_counts_in_the_drift_report(self):
        code, out, _ = run_main(Recorder(), env={k: KEYS[k] for k in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY")})
        report = json.loads(out)
        # claude-sonnet-4-6 is in the shipped registry and only on page two: it was reported STALE.
        self.assertEqual(report["anthropic"]["live_count"], 5)
        self.assertNotIn("claude-sonnet-4-6", report["anthropic"]["missing_from_live"])
        # gemini-embedding-2 is not in the registry and only on page two: it was never reported NEW.
        self.assertEqual(report["google"]["live_count"], len(fixture("google_models.json")["models"]))
        self.assertIn("gemini-embedding-2", report["google"]["missing_from_registry"])


class TestRefusedCalls(unittest.TestCase):

    def test_a_refusal_is_reported_without_any_part_of_the_key(self):
        echo = {"error": {"message": f"Incorrect API key provided: {KEYS['OPENAI_API_KEY'][:7]}...{KEYS['OPENAI_API_KEY'][-4:]}",
                          "type": "invalid_request_error", "code": "invalid_api_key"}}
        refuse = {
            "api.anthropic.com": (401, {"type": "error", "error": {"type": "authentication_error",
                                                                   "message": f"invalid x-api-key {KEYS['ANTHROPIC_API_KEY'][:9]}"}}),
            "api.openai.com": (401, echo),
            "generativelanguage.googleapis.com": (400, fixture("google_400.json")),
            "direct.evolink.ai": (403, {"error": {"message": f"key {KEYS['EVOLINK_API_KEY']} is disabled"}}),
        }
        code, out, err = run_main(Recorder(refuse=refuse))
        self.assertEqual(code, 0)
        report = json.loads(out)
        for vendor, status in (("anthropic", "401"), ("openai", "401"), ("google", "400"), ("evolink", "403")):
            self.assertTrue(report[vendor]["status"].startswith("skipped (fetch failed"), report[vendor])
            self.assertIn(status, report[vendor]["status"])
        for name, secret in KEYS.items():
            for bit in pieces(secret):
                self.assertNotIn(bit, out + err, f"part of {name} printed")

    def test_no_key_is_still_skipped_quietly(self):
        code, out, _ = run_main(Recorder(), env={})
        report = json.loads(out)
        self.assertEqual(report["google"]["status"], "skipped (no API key)")


if __name__ == "__main__":
    unittest.main()
