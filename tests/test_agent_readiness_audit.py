"""agent-readiness-audit.py — can AI agents and AI crawlers use a site?

Every test runs OFFLINE on inline fixtures; the one fetch test swaps
urllib's opener for a fixture server, and a separate test proves that
without --fetch the script never touches the network.

Each class guards one check, and each was proven able to fail by a planted
mutation of the script (see the release notes for the plant list): first-match
instead of longest-match robots rules, @graph ignored, the visible-text floor
disabled, required feed attributes not counted, ACP required fields skipped,
WebMCP absence counted as a failure, the exit code pinned to 0, and an llms.txt
recommendation slipped into the output.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _helpers import import_script, run_json


def _public_dns():
    """acme.example resolves to a public address, so the URL guard lets the
    (mocked) fetch through; no real DNS lookup happens in these tests."""
    return mock.patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 443))])

ara = import_script("agent-readiness-audit.py", module_name="agent_readiness_audit")

ROBOTS_OPEN = """\
User-agent: *
Disallow: /cart/
"""

ROBOTS_BLOCKS_SEARCH = """\
User-agent: OAI-SearchBot
User-agent: PerplexityBot
Disallow: /

User-agent: GPTBot
Disallow: /

User-agent: *
Allow: /
"""

ROBOTS_TRAINING_BLOCKED = """\
User-agent: GPTBot
User-agent: ClaudeBot
User-agent: Google-Extended
User-agent: Applebot-Extended
Disallow: /

User-agent: *
Disallow:
"""

HTML_GOOD = """<!doctype html><html lang="en"><head><title>Acme Anvil</title>
<script type="application/ld+json">
{"@context":"https://schema.org","@graph":[
 {"@type":"Organization","name":"Acme","url":"https://acme.example"},
 {"@type":"Product","name":"Acme Anvil","image":"https://acme.example/a.jpg",
  "offers":{"@type":"Offer","price":"119.99","priceCurrency":"USD",
            "availability":"https://schema.org/InStock"}}]}
</script></head>
<body><main><h1>Acme Anvil</h1>
<p>The Acme Anvil is a forged steel anvil for hobby and professional smiths. It weighs
55 kg, ships flat-packed on a pallet and comes with a ten-year warranty against cracks.
Price: 119.99 USD. In stock and ready to ship from our Ohio warehouse within two days.</p>
<img src="a.jpg" alt="Acme Anvil on a workbench">
<form toolname="checkStock" tooldescription="Check stock for a product SKU" action="/stock">
<label for="sku">SKU</label><input id="sku" name="sku"
 toolparamdescription="The product SKU to look up"><button type="submit">Check</button></form>
</main></body></html>"""

HTML_SPA_SHELL = """<!doctype html><html lang="en"><head><title>Shop</title></head>
<body><div id="root"></div><noscript>You need to enable JavaScript to run this app.</noscript>
<script src="/static/js/main.js"></script></body></html>"""

HTML_BAD_JSONLD = """<html lang="en"><head>
<script type="application/ld+json">{"@type": "Organization", "name": "Acme",}</script>
</head><body><main><h1>About Acme</h1><p>""" + ("Acme makes anvils. " * 30) + """</p></main></body></html>"""

HTML_PRODUCT_NO_OFFER = """<html lang="en"><head>
<script type="application/ld+json">[{"@type":"Organization","name":"Acme"},
{"@type":"Product","name":"Widget","image":"w.jpg"}]</script>
</head><body><main><h1>Widget</h1><p>""" + ("A very good widget for every workshop. " * 12) + """</p></main></body></html>"""

FEED_TSV = (
    "id\ttitle\tdescription\tlink\timage_link\tavailability\tprice\tbrand\t"
    "native_commerce(checkout_eligibility)\tquestion_and_answer\n"
    "A1\tAnvil\tForged anvil\thttps://a.example/a1\thttps://a.example/a1.jpg\tin_stock\t119.99 USD\tAcme\tTRUE\tQ: weight? A: 55 kg\n"
    "A2\tHammer\tForging hammer\thttps://a.example/a2\thttps://a.example/a2.jpg\tin_stock\t\tAcme\tFALSE\t\n"
    "A3\tTongs\tTongs\thttps://a.example/a3\thttps://a.example/a3.jpg\tsold out\t19.00 USD\tAcme\tmaybe\t\n"
)

FEED_TSV_CLEAN = (
    "id\ttitle\tdescription\tlink\timage_link\tavailability\tprice\tbrand\n"
    "A1\tAnvil\tForged anvil\thttps://a.example/a1\thttps://a.example/a1.jpg\tin_stock\t119.99 USD\tAcme\n"
)

FEED_XML = """<?xml version="1.0"?>
<rss xmlns:g="http://base.google.com/ns/1.0" version="2.0"><channel>
<item><g:id>A1</g:id><title>Anvil</title><description>Forged anvil</description>
<link>https://a.example/a1</link><g:image_link>https://a.example/a1.jpg</g:image_link>
<g:availability>in_stock</g:availability><g:price>119.99 USD</g:price><g:brand>Acme</g:brand>
<g:native_commerce><g:checkout_eligibility>TRUE</g:checkout_eligibility></g:native_commerce>
<g:popularity_rank>5</g:popularity_rank></item>
</channel></rss>"""

ACP_JSONL_OK = "\n".join(json.dumps(r) for r in [
    {"item_id": "A1", "title": "Anvil", "description": "Forged", "url": "https://a.example/a1",
     "brand": "Acme", "seller_name": "Acme", "image_url": "https://a.example/a1.jpg",
     "availability": "in_stock", "price": "119.99 USD", "is_eligible_search": True},
])
ACP_JSONL_MISSING = json.dumps({"item_id": "A1", "title": "Anvil", "description": "Forged",
                                "url": "https://a.example/a1", "brand": "Acme",
                                "image_url": "https://a.example/a1.jpg",
                                "availability": "in_stock", "price": "119.99 USD"})


class _Tmp(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.dir = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def write(self, name: str, text: str) -> str:
        p = self.dir / name
        p.write_text(text, encoding="utf-8")
        return str(p)

    def audit(self, *args):
        return run_json("agent-readiness-audit.py", *args)

    @staticmethod
    def check(report: dict, cid: str) -> dict:
        return next(c for c in report["checks"] if c["id"] == cid)


class TestRobotsMatching(unittest.TestCase):
    """RFC 9309 semantics — the plant (first-match instead of longest-match)
    flipped test_longest_match_wins and test_allow_wins_a_tie."""

    def test_longest_match_wins(self):
        g = ara.parse_robots("User-agent: *\nDisallow: /shop\nAllow: /shop/public\n")
        self.assertTrue(ara.is_allowed(g, "GPTBot", "/shop/public/x")[0])
        self.assertFalse(ara.is_allowed(g, "GPTBot", "/shop/private")[0])

    def test_allow_wins_a_tie(self):
        g = ara.parse_robots("User-agent: *\nDisallow: /page\nAllow: /page\n")
        self.assertTrue(ara.is_allowed(g, "ClaudeBot", "/page")[0])

    def test_named_group_overrides_star(self):
        g = ara.parse_robots("User-agent: *\nDisallow: /\n\nUser-agent: OAI-SearchBot\nAllow: /\n")
        self.assertTrue(ara.is_allowed(g, "OAI-SearchBot", "/")[0])
        self.assertFalse(ara.is_allowed(g, "PerplexityBot", "/")[0])

    def test_token_match_is_case_insensitive_and_groups_merge(self):
        g = ara.parse_robots("user-agent: gptbot\nDisallow: /a\n\nUser-Agent: GPTBot\nDisallow: /b\n")
        self.assertFalse(ara.is_allowed(g, "GPTBot", "/a")[0])
        self.assertFalse(ara.is_allowed(g, "GPTBot", "/b")[0])

    def test_wildcards_and_end_anchor(self):
        g = ara.parse_robots("User-agent: *\nDisallow: /*.pdf$\nDisallow: /tmp*/\n")
        self.assertFalse(ara.is_allowed(g, "ClaudeBot", "/files/guide.pdf")[0])
        self.assertTrue(ara.is_allowed(g, "ClaudeBot", "/files/guide.pdf?x=1")[0])
        self.assertFalse(ara.is_allowed(g, "ClaudeBot", "/tmp123/x")[0])

    def test_empty_disallow_allows_everything(self):
        g = ara.parse_robots("User-agent: *\nDisallow:\n")
        self.assertTrue(ara.is_allowed(g, "GPTBot", "/anything")[0])

    def test_no_robots_rules_means_allowed(self):
        self.assertTrue(ara.is_allowed([], "Claude-User", "/")[0])

    def test_crawler_list_covers_the_verified_tokens(self):
        tokens = {b["token"] for b in ara.AI_CRAWLERS}
        for t in ("GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot",
                  "Claude-User", "PerplexityBot", "Perplexity-User", "Google-Extended",
                  "Applebot-Extended", "OAI-AdsBot"):
            self.assertIn(t, tokens)
        for b in ara.AI_CRAWLERS:
            self.assertTrue(b["source"].startswith("https://"), b["token"])


class TestRobotsVerdicts(_Tmp):
    def test_blocking_answer_engines_fails(self):
        rep, code = self.audit("--robots", self.write("r.txt", ROBOTS_BLOCKS_SEARCH))
        c = self.check(rep, "robots_ai_crawlers")
        self.assertEqual(c["status"], "fail")
        self.assertEqual(code, 1)
        joined = " ".join(c["findings"])
        self.assertIn("OAI-SearchBot", joined)
        self.assertIn("PerplexityBot", joined)
        self.assertNotIn("GPTBot", joined, "training bots are policy, not a failure, by default")

    def test_training_blocks_are_policy_by_default(self):
        rep, code = self.audit("--robots", self.write("r.txt", ROBOTS_TRAINING_BLOCKED))
        c = self.check(rep, "robots_ai_crawlers")
        self.assertEqual(c["status"], "pass")
        self.assertEqual(code, 0)
        gpt = next(b for b in c["crawlers"] if b["token"] == "GPTBot")
        self.assertEqual(gpt["verdict"], "blocked")

    def test_training_policy_allow_turns_blocks_into_failures(self):
        rep, code = self.audit("--robots", self.write("r.txt", ROBOTS_TRAINING_BLOCKED),
                               "--training-policy", "allow")
        self.assertEqual(self.check(rep, "robots_ai_crawlers")["status"], "fail")
        self.assertEqual(code, 1)

    def test_partial_block_on_a_tested_path(self):
        rep, _ = self.audit("--robots", self.write("r.txt", ROBOTS_OPEN), "--path", "/cart/")
        c = self.check(rep, "robots_ai_crawlers")
        bot = next(b for b in c["crawlers"] if b["token"] == "OAI-SearchBot")
        self.assertEqual(bot["verdict"], "partially_blocked")
        self.assertEqual(c["status"], "fail")

    def test_user_fetchers_carry_the_vendor_robots_caveat(self):
        rep, _ = self.audit("--robots", self.write("r.txt", ROBOTS_OPEN))
        c = self.check(rep, "robots_ai_crawlers")
        for token in ("ChatGPT-User", "Perplexity-User"):
            bot = next(b for b in c["crawlers"] if b["token"] == token)
            self.assertIn("robots", bot["note"].lower())


class TestStructuredData(_Tmp):
    """Plant: ignoring @graph made test_graph_is_walked fail."""

    def test_graph_is_walked(self):
        rep, _ = self.audit("--html", self.write("p.html", HTML_GOOD))
        c = self.check(rep, "structured_data")
        self.assertEqual(c["present"], {"Product": True, "Offer": True,
                                        "Organization": True, "FAQPage": False})
        self.assertEqual(c["status"], "pass")

    def test_unparseable_jsonld_fails(self):
        rep, code = self.audit("--html", self.write("p.html", HTML_BAD_JSONLD))
        c = self.check(rep, "structured_data")
        self.assertEqual(c["status"], "fail")
        self.assertEqual(code, 1)
        self.assertIn("unparseable", c["findings"][0])

    def test_product_without_offers_warns(self):
        rep, code = self.audit("--html", self.write("p.html", HTML_PRODUCT_NO_OFFER))
        c = self.check(rep, "structured_data")
        self.assertEqual(c["status"], "warn")
        self.assertEqual(code, 0, "a warning alone must not fail the run")

    def test_ai_note_says_markup_is_not_required_for_ai(self):
        rep, _ = self.audit("--html", self.write("p.html", HTML_GOOD))
        self.assertIn("isn't required for generative AI search",
                      " ".join(self.check(rep, "structured_data")["notes"]))


class TestNoJsRender(_Tmp):
    """Plant: disabling the visible-text floor made test_spa_shell_fails fail."""

    def test_spa_shell_fails(self):
        rep, code = self.audit("--html", self.write("s.html", HTML_SPA_SHELL))
        c = self.check(rep, "no_js_render")
        self.assertEqual(c["status"], "fail")
        self.assertEqual(code, 1)
        self.assertTrue(c["pages"][0]["noscript_says_enable_js"])
        self.assertIn("root", c["pages"][0]["spa_shell_markers"])

    def test_server_rendered_page_passes(self):
        rep, _ = self.audit("--html", self.write("p.html", HTML_GOOD), "--expect", "Acme Anvil")
        self.assertEqual(self.check(rep, "no_js_render")["status"], "pass")

    def test_missing_expected_text_fails(self):
        rep, _ = self.audit("--html", self.write("p.html", HTML_GOOD), "--expect", "Titanium Hammer")
        c = self.check(rep, "no_js_render")
        self.assertEqual(c["status"], "fail")
        self.assertEqual(c["pages"][0]["missing_expected"], ["Titanium Hammer"])

    def test_text_inside_scripts_does_not_count(self):
        html = "<html><body><script>" + ("var s='lots of text';" * 200) + "</script></body></html>"
        p = ara.parse_html(html)
        self.assertEqual(p.visible_text(), "")

    def test_unclosed_head_does_not_hide_the_body(self):
        p = ara.parse_html("<html><head><title>x</title><meta charset=utf-8><body><p>Hello world</p>")
        self.assertEqual(p.visible_text(), "Hello world")


class TestAccessibilityBasics(_Tmp):
    def test_issues_warn_never_fail(self):
        html = ('<html><body><main><h1>x</h1><img src="a.png"><input name="q">'
                '<button></button><p>' + "text " * 80 + "</p></main></body></html>")
        rep, code = self.audit("--html", self.write("a.html", html))
        c = self.check(rep, "accessibility_basics")
        self.assertEqual(c["status"], "warn")
        joined = " ".join(c["findings"])
        for needle in ("lang", "alt", "label", "accessible name"):
            self.assertIn(needle, joined)


class TestMerchantFeed(_Tmp):
    """Plant: not counting required attributes made test_missing_required_fails fail."""

    def test_missing_required_fails(self):
        rep, code = self.audit("--feed", self.write("f.tsv", FEED_TSV))
        c = self.check(rep, "merchant_feed")
        self.assertEqual(c["status"], "fail")
        self.assertEqual(code, 1)
        self.assertEqual(c["required_missing"]["price"], 1)
        joined = " ".join(c["findings"])
        self.assertIn("[availability]", joined)
        self.assertIn("not TRUE/FALSE", joined)

    def test_native_commerce_and_conversational_attributes(self):
        rep, _ = self.audit("--feed", self.write("f.tsv", FEED_TSV))
        c = self.check(rep, "merchant_feed")
        self.assertEqual(c["native_commerce"]["products_opted_in"], 1)
        self.assertIn("United States, Canada and Australia", c["native_commerce"]["note"])
        self.assertAlmostEqual(c["conversational_attributes_coverage_pct"]["question_and_answer"], 33.3)

    def test_xml_feed_with_nested_native_commerce(self):
        rep, code = self.audit("--feed", self.write("f.xml", FEED_XML))
        c = self.check(rep, "merchant_feed")
        self.assertEqual(c["format"], "xml")
        self.assertEqual(c["status"], "pass")
        self.assertEqual(c["native_commerce"]["products_opted_in"], 1)
        self.assertEqual(c["conversational_attributes_coverage_pct"]["popularity_rank"], 100.0)
        self.assertEqual(code, 0)

    def test_clean_feed_passes(self):
        rep, code = self.audit("--feed", self.write("f.tsv", FEED_TSV_CLEAN))
        self.assertEqual(self.check(rep, "merchant_feed")["status"], "pass")
        self.assertEqual(code, 0)


class TestAcpFeed(_Tmp):
    """Plant: skipping the ACP required-field check made test_missing_field_fails fail."""

    def test_optional_and_skipped_when_absent(self):
        rep, _ = self.audit("--robots", self.write("r.txt", ROBOTS_OPEN))
        c = self.check(rep, "acp_feed")
        self.assertEqual(c["status"], "skipped")
        self.assertTrue(c["optional"])

    def test_complete_jsonl_passes(self):
        rep, _ = self.audit("--acp-feed", self.write("o.jsonl", ACP_JSONL_OK))
        c = self.check(rep, "acp_feed")
        self.assertEqual((c["status"], c["format"], c["eligible_search"]), ("pass", "jsonl", 1))

    def test_missing_field_fails(self):
        rep, code = self.audit("--acp-feed", self.write("o.jsonl", ACP_JSONL_MISSING))
        c = self.check(rep, "acp_feed")
        self.assertEqual(c["status"], "fail")
        self.assertEqual(c["required_missing"]["seller_name"], 1)
        self.assertEqual(code, 1)


class TestWebMcpIsExperimental(_Tmp):
    """Plant: counting WebMCP absence as a failure made test_absence_never_fails fail."""

    def test_detects_declarative_tool(self):
        rep, _ = self.audit("--html", self.write("p.html", HTML_GOOD), "--webmcp")
        c = self.check(rep, "webmcp")
        self.assertEqual(c["status"], "info")
        self.assertTrue(c["experimental"])
        self.assertEqual(c["declarative_forms"][0]["toolname"], "checkStock")
        self.assertEqual(c["toolparamdescription_fields"], 1)
        self.assertIn("origin trial", c["status_note"])

    def test_absence_never_fails(self):
        rep, code = self.audit("--html", self.write("p.html", HTML_PRODUCT_NO_OFFER), "--webmcp")
        self.assertEqual(self.check(rep, "webmcp")["status"], "info")
        self.assertEqual(code, 0)

    def test_skipped_unless_requested(self):
        rep, _ = self.audit("--html", self.write("p.html", HTML_GOOD))
        self.assertEqual(self.check(rep, "webmcp")["status"], "skipped")


class TestNoLlmsTxtForGoogle(_Tmp):
    """Plant: adding an 'add llms.txt' recommendation made this fail."""

    def test_never_recommends_llms_txt_and_says_why(self):
        rep, _ = self.audit("--robots", self.write("r.txt", ROBOTS_BLOCKS_SEARCH),
                            "--html", self.write("s.html", HTML_SPA_SHELL),
                            "--feed", self.write("f.tsv", FEED_TSV))
        self.assertTrue(rep["recommendations"], "fixture should produce recommendations")
        for r in rep["recommendations"]:
            self.assertNotIn("llms", r.lower())
        self.assertIn("Google Search itself doesn't use them", rep["notes"][0])


class TestCliContract(_Tmp):
    """Exit codes 0/1/2 + JSON. Plant: pinning the exit code to 0 made
    test_failure_exits_1 fail."""

    def test_clean_run_exits_0(self):
        rep, code = self.audit("--robots", self.write("r.txt", ROBOTS_OPEN),
                               "--html", self.write("p.html", HTML_GOOD))
        self.assertEqual(code, 0)
        self.assertEqual(rep["verdict"], "ready")

    def test_failure_exits_1(self):
        _, code = self.audit("--html", self.write("s.html", HTML_SPA_SHELL))
        self.assertEqual(code, 1)

    def test_nothing_to_audit_exits_2(self):
        rep, code = self.audit()
        self.assertEqual(code, 2)
        self.assertIn("nothing to audit", rep["error"])

    def test_missing_file_exits_2(self):
        rep, code = self.audit("--robots", str(self.dir / "nope.txt"))
        self.assertEqual(code, 2)
        self.assertIn("not found", rep["error"])

    def test_bad_flag_exits_2(self):
        _, code = self.audit("--training-policy", "sometimes")
        self.assertEqual(code, 2)

    def test_fetch_requires_site(self):
        rep, code = self.audit("--fetch")
        self.assertEqual(code, 2)


class _FakeResp:
    def __init__(self, body: str, status: int = 200):
        self.status = status
        self._body = body.encode("utf-8")
        self.headers = mock.Mock()
        self.headers.get_content_charset.return_value = "utf-8"

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestFetchIsOptIn(unittest.TestCase):
    def test_offline_run_never_touches_the_network(self):
        with tempfile.TemporaryDirectory() as td:
            robots = Path(td) / "r.txt"
            robots.write_text(ROBOTS_OPEN, encoding="utf-8")
            # fetch() swallows exceptions by design, so record calls instead
            # of raising — a raise would be eaten and the test could not fail.
            with mock.patch.object(ara, "_http_open") as urlopen:
                with mock.patch("sys.stdout"):
                    code = ara.main(["--robots", str(robots), "--site", "https://acme.example"])
        urlopen.assert_not_called()
        self.assertEqual(code, 0)

    def test_fetch_reads_robots_and_pages(self):
        served = {"https://acme.example/robots.txt": ROBOTS_BLOCKS_SEARCH,
                  "https://acme.example": HTML_GOOD}

        def fake_urlopen(req, timeout=15):
            return _FakeResp(served[req.full_url])

        with mock.patch.object(ara, "_http_open", side_effect=fake_urlopen), _public_dns():
            args = ara.build_parser().parse_args(["--site", "https://acme.example", "--fetch"])
            rep = ara.run_audit(args)
        self.assertEqual(len(rep["fetched"]), 2)
        self.assertEqual(self.check_status(rep, "robots_ai_crawlers"), "fail")
        self.assertEqual(self.check_status(rep, "structured_data"), "pass")

    def test_robots_404_means_allow_all(self):
        def fake_urlopen(req, timeout=15):
            if req.full_url.endswith("/robots.txt"):
                raise ara.urllib.error.HTTPError(req.full_url, 404, "nf", {}, None)
            return _FakeResp(HTML_GOOD)

        with mock.patch.object(ara, "_http_open", side_effect=fake_urlopen), _public_dns():
            args = ara.build_parser().parse_args(["--site", "https://acme.example", "--fetch"])
            rep = ara.run_audit(args)
        self.assertEqual(self.check_status(rep, "robots_ai_crawlers"), "pass")

    def _robots_unreachable(self, failure):
        def fake_urlopen(req, timeout=15):
            if req.full_url.endswith("/robots.txt"):
                raise failure(req.full_url)
            return _FakeResp(HTML_GOOD)

        with mock.patch.object(ara, "_http_open", side_effect=fake_urlopen), _public_dns():
            args = ara.build_parser().parse_args(["--site", "https://acme.example", "--fetch"])
            rep = ara.run_audit(args)
        return next(c for c in rep["checks"] if c["id"] == "robots_ai_crawlers")

    def test_robots_5xx_means_complete_disallow(self):
        check = self._robots_unreachable(
            lambda url: ara.urllib.error.HTTPError(url, 503, "unavailable", {}, None))
        self.assertEqual(check["status"], "fail")
        self.assertIn("RFC 9309", check["findings"][0])
        self.assertTrue(all(b["verdict"] == "blocked" for b in check["crawlers"]))

    def test_robots_network_error_means_complete_disallow(self):
        check = self._robots_unreachable(lambda url: ara.urllib.error.URLError("refused"))
        self.assertEqual(check["status"], "fail")
        self.assertIn("could not be read", check["findings"][0])

    @staticmethod
    def check_status(rep, cid):
        return next(c for c in rep["checks"] if c["id"] == cid)["status"]


if __name__ == "__main__":
    unittest.main()
