"""A connector proves itself with one read-only GET (borrow 4 of the 2026-10-27 ecosystem review).

Before 3.40.0 action-doctor checked only that a credential was present; nothing showed the key
worked. probe() makes one GET with no body to a read endpoint, never writes, and says plainly when
a connector (OAuth or the host's MCP connection) can't be tested from code.
"""
from __future__ import annotations

import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import connector_executor as ce  # noqa: E402


class Resp(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestProbe(unittest.TestCase):

    def capture(self, body=b'{"ok": true, "results": [{"id": 1}]}', error=None):
        seen = []

        def opener(req, timeout):
            seen.append(req)
            if error:
                raise error
            return Resp(body)
        return seen, opener

    def test_every_live_connector_has_a_get_probe(self):
        live = sorted(k for k, v in ce.EXECUTE_PROFILES.items() if not v.get("oauth_only"))
        self.assertEqual(sorted(ce.PROBES), live)
        for name in live:
            env = {ce.EXECUTE_PROFILES[name]["env_var"]: "key-us6"}
            seen, opener = self.capture()
            out = ce.probe(name, env=env, urlopen=opener)
            self.assertEqual(out["status"], "ok", name)
            req = seen[0]
            self.assertEqual(req.get_method(), "GET", name)
            self.assertIsNone(req.data, name)
            self.assertTrue(req.full_url.startswith("https://"), name)
            self.assertNotIn("key-us6", json.dumps(out), name)  # the key never comes back

    def test_mcp_path_connectors_say_they_cannot_be_probed(self):
        oauth = next(k for k, v in ce.EXECUTE_PROFILES.items() if v.get("oauth_only"))
        out = ce.probe(oauth, env={})
        self.assertEqual(out["status"], "not_probeable")
        self.assertIn("can't test it", out["message"])

    def test_missing_key_refused_key_and_slack_not_ok(self):
        self.assertEqual(ce.probe("hubspot", env={})["status"], "not_configured")
        _, opener = self.capture(error=urllib.error.HTTPError("u", 401, "no", {}, io.BytesIO(b"")))
        out = ce.probe("hubspot", env={"HUBSPOT_PRIVATE_APP_TOKEN": "x"}, urlopen=opener)
        self.assertEqual((out["status"], out["http_status"]), ("failed", 401))
        _, opener = self.capture(body=b'{"ok": false, "error": "invalid_auth"}')
        self.assertEqual(ce.probe("slack", env={"SLACK_BOT_TOKEN": "x"}, urlopen=opener)["status"], "failed")

    def test_docs(self):
        self.assertIn("--action probe", (REPO / "PRIVACY.md").read_text(encoding="utf-8"))
        skill = (REPO / "skills/connect/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("--action probe --name <connector>", skill)
        self.assertIn("not_probeable", skill)


if __name__ == "__main__":
    unittest.main()
