"""The connector catalogue says who runs each endpoint, and no URL carries a secret.

The 2026-11-05 security review (finding 13): `.mcp.json.connectors-reference` said every listed
connector is reached "via the provider's official endpoint", yet it lists third-party gateways
(Pipedream, Composio, Zapier, Make), vendor-run ad services that are not the ad platform
(synter-media-ai, ryze-ai-google-ads on a Cloud Run host) and a community-maintained server
(northbeam-mcp-selfhosted), several of which can write to ad accounts. The make-com entry put its
token in the URL path. Since 3.42.0 every entry has an `_operator`, the summary no longer claims
every endpoint is official, and Make's token goes in an Authorization header.

Stdlib only.
"""
from __future__ import annotations

import json
import re
import unittest

from _helpers import PLUGIN_ROOT

CATALOG = PLUGIN_ROOT / ".mcp.json.connectors-reference"
OPERATOR_KINDS = ("vendor:", "vendor code, self-hosted:", "third-party gateway:", "third-party:",
                  "community, self-hosted:")
NOT_THE_PLATFORM = {"composio-generic", "zapier", "make-com", "synter-media-ai", "ryze-ai-google-ads",
                    "northbeam-mcp-selfhosted"}
SECRET_IN_URL = re.compile(r"token|secret|api[_-]?key|password", re.I)


def catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def entries() -> dict:
    return {k: v for k, v in catalog()["mcpServers_reference"].items() if isinstance(v, dict) and "url" in v}


class TestConnectorOperators(unittest.TestCase):
    def test_every_entry_names_its_operator(self):
        bad = {k: v.get("_operator") for k, v in entries().items()
               if not str(v.get("_operator", "")).startswith(OPERATOR_KINDS)}
        self.assertEqual(bad, {})

    def test_gateways_and_third_parties_are_not_called_vendor(self):
        names = NOT_THE_PLATFORM | {k for k in entries() if k.startswith("pipedream-")}
        bad = [k for k in sorted(names) if entries()[k]["_operator"].startswith("vendor")]
        self.assertEqual(bad, [])

    def test_no_claim_that_every_endpoint_is_official(self):
        text = json.dumps(catalog()["_cowork_compatibility_summary"])
        self.assertNotIn("via the provider's official endpoint", text)

    def test_no_url_carries_a_secret(self):
        bad = {k: v["url"] for k, v in entries().items() if SECRET_IN_URL.search(v["url"])}
        self.assertEqual(bad, {}, "put tokens in a header, not in the URL")
        make = entries()["make-com"]
        self.assertEqual(make["headers"]["Authorization"], "Bearer ${MAKE_MCP_TOKEN}")

    def test_guard_can_fail(self):
        self.assertTrue(SECRET_IN_URL.search("https://eu1.make.com/mcp/u/<MCP_TOKEN>"))
        self.assertFalse(SECRET_IN_URL.search("https://eu1.make.com/mcp"))
        self.assertFalse("third-party gateway: x".startswith("vendor"))


if __name__ == "__main__":
    unittest.main()
