"""Guards for the October 2026 AI-surface work (items #9, #10, #11, #18).

Three kinds of guard live here:

1. Catalog transport + access (#10). MCP spec 2026-07-28 classifies the old
   HTTP+SSE transport as Deprecated; a catalog entry on an /sse URL must carry
   an explicit _transport_status flag. The shipped .mcp.json must stay empty.
   The official ad/CRM servers must carry access level, source and check date,
   and the registry must agree with the catalog on access.
2. Resolver write safety (#10). A read-only connector (google-ads-mcp) must
   never be chosen for a write action; launch manifests must say new ad
   objects are created PAUSED behind the approval gate; MCP-only connectors
   must never be fired from Python.
3. Honesty statements (#9, #11, #18). The sentences that stop a deliverable
   from inventing a metric (no AI-Overview clicks/CTR/queries; GA4's AI
   Assistant channel excludes Google's AI surfaces) or from presenting
   secondary-sourced ChatGPT Ads rollout facts as confirmed.

Plants that proved each guard fires are listed in the release notes:
replicate's flag removed, asana reverted to /sse, an entry added to
.mcp.json, registry google-ads-mcp flipped to read-write, the resolver's
read-only filter removed, AD_OBJECT_CREATE_STATUS set to ACTIVE, the
"top queries (if available" line restored, and a CPM figure inserted.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import _connector_registry as registry  # noqa: E402  # type: ignore[import-not-found]
import connector_executor  # noqa: E402  # type: ignore[import-not-found]
import connector_resolver  # noqa: E402  # type: ignore[import-not-found]

CATALOG = ROOT / ".mcp.json.connectors-reference"
OFFICIAL = {
    "meta-ads": ("https://mcp.facebook.com/ads", "read-write"),
    "google-ads-mcp": (None, "read-only"),
    "amazon-ads-mcp": (None, "read-write"),
    "hubspot": ("https://mcp.hubspot.com", "read-write"),
}


def _catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))["mcpServers_reference"]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


class TestCatalogTransport(unittest.TestCase):
    def test_sse_endpoints_must_be_flagged(self):
        unflagged = []
        for name, entry in _catalog().items():
            if not isinstance(entry, dict):
                continue
            path = entry.get("url", "").split("?", 1)[0].rstrip("/")
            if path.endswith("/sse"):
                if "FLAGGED" not in entry.get("_transport_status", ""):
                    unflagged.append(name)
        self.assertEqual(unflagged, [],
                         "catalog entries on the deprecated HTTP+SSE transport without a "
                         f"_transport_status flag: {unflagged}")

    def test_migrated_entries_use_streamable_http_urls(self):
        cat = _catalog()
        self.assertEqual(cat["asana"]["url"], "https://mcp.asana.com/v2/mcp")
        self.assertEqual(cat["webflow"]["url"], "https://mcp.webflow.com/mcp")
        self.assertFalse(cat["make-com"]["url"].endswith("/sse"))

    def test_shipped_mcp_json_stays_empty(self):
        # .mcp.json is gitignored, so an installed copy has none at all — which
        # connects nothing. A local one must still be empty, and the ignore rule
        # is what keeps any local edit out of every install.
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn(".mcp.json", [ln.strip() for ln in gitignore],
                      ".mcp.json must stay gitignored so no install ever ships servers")
        path = ROOT / ".mcp.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data.get("mcpServers"), {},
                             ".mcp.json must ship with zero auto-connecting MCP servers")

    def test_official_servers_are_sourced_and_access_labelled(self):
        cat = _catalog()
        for name, (url, access) in OFFICIAL.items():
            entry = cat[name]
            if url:
                self.assertEqual(entry["url"], url, name)
            self.assertEqual(entry.get("_access"), access, name)
            self.assertTrue(entry.get("_source", "").startswith("https://"), name)
            self.assertEqual(entry.get("_checked"), "2026-10-04", name)
        for name in ("meta-ads", "amazon-ads-mcp"):
            policy = cat[name]["_write_policy"]
            self.assertIn("PAUSED", policy + cat["_section_official_ad_platform_mcps"], name)
            self.assertIn("approval gate", policy.lower() + cat["_section_official_ad_platform_mcps"].lower())

    def test_registry_agrees_with_catalog_on_access(self):
        cat = _catalog()
        for name in OFFICIAL:
            info = registry.find_connector(name)
            self.assertIsNotNone(info, f"{name} missing from _connector_registry")
            self.assertEqual(info.get("access"), cat[name]["_access"], name)
        self.assertTrue(registry.is_read_only("google-ads-mcp"))
        self.assertFalse(registry.is_read_only("meta-ads"))
        self.assertFalse(registry.is_read_only("slack"), "no access field means not read-only")


class TestResolverWriteSafety(unittest.TestCase):
    def _resolve(self, action, configured, **kw):
        with mock.patch.object(connector_resolver, "_load_mcp_json",
                               return_value={n: {} for n in configured}):
            return connector_resolver.resolve_action(action, "acme-test", **kw)

    def test_read_only_connector_never_chosen_for_write(self):
        spec = connector_resolver.ACTION_SPECS["launch-ads"]
        with mock.patch.dict(spec, {"candidate_connectors": lambda kw: ["google-ads-mcp"]}):
            res = self._resolve("launch-ads", ["google-ads-mcp"])
        self.assertEqual(res["status"], "stub_unconfigured")
        self.assertEqual(res["candidate_status"][0]["status"], "skipped_read_only")

    def test_read_only_connector_serves_reads(self):
        res = self._resolve("inventory", ["google-ads-mcp"], channel="google_ads")
        self.assertEqual(res["status"], "manifest_ready")
        self.assertEqual(res["chosen_connector"], "google-ads-mcp")
        self.assertIsNone(res["manifest"]["http_request"])
        self.assertIn("search", res["manifest"]["mcp_tool_hint"])

    def test_launch_manifest_is_paused_and_gated(self):
        res = self._resolve("launch-ads", ["meta-ads"])
        self.assertEqual(res["chosen_connector"], "meta-ads")
        m = res["manifest"]
        self.assertEqual(m["create_status"], "PAUSED")
        self.assertTrue(m["approval_required"])
        self.assertIn("typed yes", m["approval_gate"])
        self.assertIsNone(m["http_request"])
        self.assertIn("never delete", m["mcp_tool_hint"])

    def test_per_platform_connector_still_wins_when_configured(self):
        env = {v: "x" for v in registry.find_connector("google-ads")["env_vars"]}
        with mock.patch.dict("os.environ", env):
            res = self._resolve("inventory", ["google-ads", "google-ads-mcp"], channel="google_ads")
        self.assertEqual(res["chosen_connector"], "google-ads")
        self.assertEqual(res["other_configured_connectors"], ["google-ads-mcp"])

    def test_executor_never_fires_mcp_only_connectors(self):
        with mock.patch.object(connector_resolver, "_load_mcp_json",
                               return_value={"meta-ads": {}}), \
             mock.patch.object(connector_executor.urllib.request, "urlopen") as urlopen:
            res = connector_executor.execute_action("launch-ads", "acme-test",
                                                    confirm=True, log_to_tracker=False)
        urlopen.assert_not_called()
        self.assertFalse(res["execute_attempted"])
        self.assertIn("MCP path", res["execute_blocked_reason"])


class TestHonestAiMeasurement(unittest.TestCase):
    def test_gsc_report_limits_are_stated(self):
        t = _read("skills/gsc-ai-performance/SKILL.md")
        self.assertIn("no Queries dimension", t)
        self.assertIn("support.google.com/webmasters/answer/16984139", t)
        self.assertRegex(t, r"\*\*Does not exist\*\* in Search Console")
        self.assertNotIn("top queries (if available", t,
                         "the generative AI report has no Queries dimension")

    def test_ga4_blind_spot_is_stated_with_primary_source(self):
        for rel in ("skills/analytics-insights/SKILL.md", "skills/gsc-ai-performance/SKILL.md"):
            t = _read(rel)
            self.assertIn("support.google.com/analytics/answer/9756891", t, rel)
            self.assertRegex(t, r"(?i)exclud\w* Google's AI Overviews and AI Mode", rel)

    def test_first_party_ai_sources_are_wired(self):
        a = _read("skills/analytics-insights/SKILL.md")
        g = _read("skills/geo-monitor/SKILL.md")
        bing = "blogs.bing.com/search/2026/6/New-AI-Visibility-Insights-in-Bing-Webmaster-Tools"
        for t in (a, g):
            self.assertIn(bing, t)
            self.assertIn("support.google.com/merchants/answer/17117204", t)
        self.assertIn("does not expose competitor domains", g)
        self.assertIn("No first-party citation report exists", g)


class TestAdsInAiAnswersSourcing(unittest.TestCase):
    def test_secondary_rollout_claims_are_labelled(self):
        t = _read("skills/paid-advertising/ads-in-ai-answers.md")
        self.assertIn("developers.openai.com/ads", t)
        self.assertIn("blog.google/products/ads-commerce/google-marketing-live-search-ads", t)
        i = t.index("31 European markets")
        self.assertIn("secondary", t[max(0, i - 600):i].lower(),
                      "country rollout must sit under the secondary-sourced label")

    def test_no_invented_prices(self):
        for rel in ("skills/paid-advertising/ads-in-ai-answers.md", "skills/media-plan/SKILL.md"):
            t = _read(rel)
            self.assertIsNone(re.search(r"[$€£]\s?\d", t), f"{rel}: currency figure in AI-ads guidance")
            self.assertIsNone(re.search(r"(?i)\bCPM\s+(of|is|around|~)\s*\d", t), rel)

    def test_since_august_section_extended_not_duplicated(self):
        t = _read("skills/paid-advertising/SKILL.md")
        self.assertEqual(t.count("## Since August 2026"), 1)
        self.assertIn("ads-in-ai-answers.md", t)


class TestMeridian2x(unittest.TestCase):
    def test_versions_and_open_item_documented(self):
        m = _read("skills/analytics-insights/mmm-framework.md")
        a = _read("agents/marketing-scientist.md")
        for t in (m, a):
            self.assertIn("github.com/google/meridian/blob/main/CHANGELOG.md", t)
            self.assertIn("v2.0.0", t)
            self.assertIn("v2.1.0", t)
            self.assertIn("CalibrationSpec", t)
            self.assertIn("JAX", t)
            self.assertIn("sample_prior", t)


if __name__ == "__main__":
    unittest.main()
