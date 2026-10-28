"""A connector's key goes only to its own vendor (3.40.0).

Before 3.40.0, _mailchimp_dc_url took everything after the key's last "-" as the data centre and
put it in the host: MAILCHIMP_API_KEY="abc-evil.example/x?" built
https://evil.example/x?.api.mailchimp.com/3.0/ping, and urllib sent the Basic-auth key to
evil.example. The same shape waited in PIPEDRIVE_COMPANY_DOMAIN (a subdomain) and
SALESFORCE_INSTANCE_URL (a whole base URL). And urllib copies ordinary headers to whatever host a
redirect names, so a 302 could carry any key elsewhere: in the executor, the model router and
refresh_models alike.

Now each host piece from credential or env text is validated, the finished URL's host must be on
the vendor's domain, nothing is sent otherwise, and headers are unredirected.
"""
from __future__ import annotations

import ast
import io
import json
import os
import re
import sys
import unittest
import urllib.parse
import urllib.request
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import connector_executor as ce  # noqa: E402

EVIL_KEY = "abc123-evil.example/x?"


class Resp(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def recorder():
    calls = []

    def opener(req, timeout=30):
        calls.append(req)
        return Resp(b'{"health_status": "ok"}')
    return calls, opener


class TestMailchimpKey(unittest.TestCase):

    def test_probe_refuses_an_evil_key_and_sends_nothing(self):
        calls, opener = recorder()
        out = ce.probe("mailchimp", env={"MAILCHIMP_API_KEY": EVIL_KEY}, urlopen=opener)
        self.assertEqual(calls, [])
        self.assertEqual(out["status"], "failed")
        self.assertIs(out["sent"], False)
        self.assertIn("data centre", out["message"])
        self.assertNotIn("evil", json.dumps(out))

    def test_executor_refuses_an_evil_key_and_sends_nothing(self):
        manifest = {"method": "GET", "url": "https://{MAILCHIMP_DC}.api.mailchimp.com/3.0/automations"}
        with mock.patch.object(ce.urllib.request, "urlopen") as urlopen:
            out = ce.execute_manifest(manifest, env={"MAILCHIMP_API_KEY": EVIL_KEY}, connector="mailchimp")
        urlopen.assert_not_called()
        self.assertEqual(out["status"], "error")
        self.assertIs(out["sent"], False)
        self.assertNotIn("evil", json.dumps(out))

    def test_an_evil_mailchimp_dc_variable_is_refused(self):
        manifest = {"method": "GET", "url": "https://{MAILCHIMP_DC}.api.mailchimp.com/3.0/automations"}
        env = {"MAILCHIMP_API_KEY": "abc123-us21", "MAILCHIMP_DC": "evil.example/x?"}
        with mock.patch.object(ce.urllib.request, "urlopen") as urlopen:
            out = ce.execute_manifest(manifest, env=env, connector="mailchimp")
        urlopen.assert_not_called()
        self.assertEqual(out["status"], "error")
        self.assertIn("MAILCHIMP_DC", out["error"])

    def test_a_real_key_still_reaches_its_data_centre(self):
        calls, opener = recorder()
        out = ce.probe("mailchimp", env={"MAILCHIMP_API_KEY": "abc123-us21"}, urlopen=opener)
        self.assertEqual(out["status"], "ok", out)
        self.assertEqual(len(calls), 1)
        self.assertEqual(urllib.parse.urlsplit(calls[0].full_url).hostname, "us21.api.mailchimp.com")
        built = ce.build_request({"method": "GET", "url": "https://{MAILCHIMP_DC}.api.mailchimp.com/3.0/automations"},
                                 env={"MAILCHIMP_API_KEY": "abc123-us21"}, connector="mailchimp")
        self.assertEqual(built["status"], "built", built)
        self.assertTrue(built["url"].startswith("https://us21.api.mailchimp.com/"))

    def test_malformed_keys_are_refused(self):
        for key in ("abc123", "abc-", "abc-US21", "abc-us21.evil", "abc-us21/", "abc-u1", "abc-usxx"):
            calls, opener = recorder()
            with self.subTest(key=key):
                out = ce.probe("mailchimp", env={"MAILCHIMP_API_KEY": key}, urlopen=opener)
                self.assertEqual((out["status"], calls), ("failed", []))


class TestHostPieces(unittest.TestCase):
    """Pipedrive and Salesforce run through MCP today (oauth_only). The checks wait for the day
    they get an execute profile; the profile is patched in here to prove the path."""

    def build(self, connector, env_var, url, env):
        profile = {"env_var": env_var, "auth": "bearer", "auth_header": "Authorization"}
        with mock.patch.dict(ce.EXECUTE_PROFILES, {connector: profile}):
            return ce.build_request({"method": "GET", "url": url}, env=env, connector=connector)

    def test_pipedrive_company_domain(self):
        url = "https://{PIPEDRIVE_COMPANY_DOMAIN}.pipedrive.com/api/v1/workflows"
        for bad in ("evil.example/x?", "acme.evil.example#", "acme@evil.example", "-acme", "ACME", ""):
            with self.subTest(bad=bad):
                out = self.build("pipedrive", "PIPEDRIVE_API_TOKEN", url,
                                 {"PIPEDRIVE_API_TOKEN": "t", "PIPEDRIVE_COMPANY_DOMAIN": bad})
                self.assertNotEqual(out["status"], "built", out)
        out = self.build("pipedrive", "PIPEDRIVE_API_TOKEN", url,
                         {"PIPEDRIVE_API_TOKEN": "t", "PIPEDRIVE_COMPANY_DOMAIN": "acme-co"})
        self.assertEqual(out["url"], "https://acme-co.pipedrive.com/api/v1/workflows")

    def test_salesforce_instance_url(self):
        url = "{SALESFORCE_INSTANCE_URL}/services/data/v60.0/sobjects/Campaign/"
        for bad in ("https://evil.example", "http://acme.my.salesforce.com", "https://acme.my.salesforce.com@evil.example",
                    "https://evil.example/x?.salesforce.com", "https://acme.my.salesforce.com/x",
                    "https://acme.my.salesforce.com:8443", "https://salesforce.com.evil.example"):
            with self.subTest(bad=bad):
                out = self.build("salesforce", "SALESFORCE_ACCESS_TOKEN", url,
                                 {"SALESFORCE_ACCESS_TOKEN": "t", "SALESFORCE_INSTANCE_URL": bad})
                self.assertEqual(out["status"], "error", out)
                self.assertIs(out["sent"], False)
        out = self.build("salesforce", "SALESFORCE_ACCESS_TOKEN", url,
                         {"SALESFORCE_ACCESS_TOKEN": "t", "SALESFORCE_INSTANCE_URL": "https://acme.my.salesforce.com/"})
        self.assertEqual(out["url"], "https://acme.my.salesforce.com/services/data/v60.0/sobjects/Campaign/")

    def test_final_host_check(self):
        for connector, url in (("mailchimp", "https://evil.example/x?.api.mailchimp.com/3.0/ping"),
                               ("mailchimp", "http://us21.api.mailchimp.com/3.0/ping"),
                               ("pipedrive", "https://acme.pipedrive.com.evil.example/api"),
                               ("salesforce", "https://user@evil.example/.salesforce.com")):
            with self.subTest(url=url), self.assertRaises(ce.HostRefused):
                ce._check_vendor_host(connector, url)
        ce._check_vendor_host("mailchimp", "https://us21.api.mailchimp.com/3.0/ping")


class TestEveryHostFromTextIsGuarded(unittest.TestCase):
    """Sweep: a URL template whose host holds a placeholder must name a checked piece and a
    vendor domain from VENDOR_HOSTS, so a new one can't ship unguarded."""

    HOST_IN_URL = re.compile(r"""https?://([^/"'\s]*\{\w+\}[^/"'\s]*)""")  # a placeholder in the host
    BASE_FROM_VAR = re.compile(r"""["']url["']\s*:\s*f?["']\{(\w+)\}""")  # the whole base from a variable

    def problems(self, name: str, text: str) -> tuple[list, list]:
        found, problems = [], []
        for host in self.HOST_IN_URL.findall(text):
            found.append(host)
            names = re.findall(r"\{(\w+)\}", host)
            literal = re.sub(r"\{\w+\}", "", host)
            if not all(n in ce.HOST_PIECES or n == "dc" for n in names) or literal not in ce.VENDOR_HOSTS.values():
                problems.append(f"{name}: {host}")
        for var in self.BASE_FROM_VAR.findall(text):
            found.append(var)
            if var not in ce.HOST_PIECES:
                problems.append(f"{name}: url from {{{var}}}")
        return found, problems

    def test_sweep(self):
        found, problems = [], []
        for path in sorted((REPO / "scripts").glob("*.py")):
            f, p = self.problems(path.name, path.read_text(encoding="utf-8"))
            found += f
            problems += p
        self.assertEqual(problems, [], "\n  " + "\n  ".join(problems))
        self.assertGreaterEqual(len(found), 5, found)  # mailchimp x2, pipedrive, salesforce x2

    def test_sweep_catches_plants(self):
        planted = ('"url": "https://{ZOHO_REGION}.zohoapis.com/crm/v5/x",\n'
                   '"url": "{SHOPIFY_STORE_URL}/admin/api/products.json",\n'
                   '"url": "https://{MAILCHIMP_DC}.evil.example/3.0/ping",\n')
        self.assertEqual(len(self.problems("plant", planted)[1]), 3)


class TestRedirectsCarryNoKey(unittest.TestCase):

    def test_send_request_headers_are_unredirected(self):
        built = ce.build_request({"method": "GET", "url": "https://api.sendgrid.com/v3/scopes",
                                  "headers": {"Authorization": "Bearer {SENDGRID_API_KEY}"}},
                                 env={"SENDGRID_API_KEY": "SG.secret"}, connector="sendgrid")
        seen = []
        with mock.patch.object(ce.urllib.request, "urlopen",
                               side_effect=lambda req, timeout: seen.append(req) or Resp(b"{}")):
            ce.send_request(built)
        self.assertEqual(len(seen), 1)
        req = seen[0]
        self.assertEqual(req.get_header("Authorization"), "Bearer SG.secret")
        self.assertNotIn("Authorization", req.headers)  # ordinary headers are what a redirect copies
        follow = urllib.request.HTTPRedirectHandler().redirect_request(
            req, None, 302, "Found", {}, "https://evil.example/")
        self.assertNotIn("Authorization", dict(follow.header_items()))

    def test_probe_headers_are_unredirected(self):
        calls, opener = recorder()
        ce.probe("sendgrid", env={"SENDGRID_API_KEY": "SG.secret"}, urlopen=opener)
        follow = urllib.request.HTTPRedirectHandler().redirect_request(
            calls[0], None, 302, "Found", {}, "https://evil.example/")
        self.assertNotIn("Authorization", dict(follow.header_items()))


class TestKeysNeverFollowARedirect(unittest.TestCase):
    """Every script that sends a key with urllib keeps it off a redirect, and a static guard keeps
    it that way: a urllib request that sets a credential header must use add_unredirected_header."""

    CRED_NAMES = {"authorization", "x-api-key", "x-goog-api-key", "api-key", "xi-api-key"}
    CRED_VALUE = re.compile(r"(?i)\b(?:bearer|basic)\b")

    def violations(self, name: str, source: str) -> list:
        def lit(node):
            return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None

        def risky(key_node, value_node) -> bool:
            key = lit(key_node) if key_node is not None else None
            bits = [n.value for n in ast.walk(value_node) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
            return key is None or key.lower() in self.CRED_NAMES or any(self.CRED_VALUE.search(b) for b in bits)

        out = []
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            fname = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if fname == "add_header" and len(node.args) >= 2 and risky(node.args[0], node.args[1]):
                out.append(f"{name}:{node.lineno}: add_header with a credential (or unknown) header")
            if fname == "Request":
                headers = [kw.value for kw in node.keywords if kw.arg == "headers"] + node.args[2:3]
                for h in headers:
                    if not isinstance(h, ast.Dict):
                        out.append(f"{name}:{node.lineno}: Request(headers=...) not a literal")
                    elif any(risky(k, v) for k, v in zip(h.keys, h.values)):
                        out.append(f"{name}:{node.lineno}: Request(headers=...) with a credential header")
        return out

    def test_scripts_keep_keys_off_redirects(self):
        problems = []
        for path in sorted((REPO / "scripts").glob("*.py")):
            problems += self.violations(path.name, path.read_text(encoding="utf-8"))
        self.assertEqual(problems, [], "\n  " + "\n  ".join(problems))

    def test_guard_catches_plants(self):
        planted = (
            "req.add_header('Authorization', 'Bearer ' + key)\n"
            "for name, value in headers.items():\n    req.add_header(name, value)\n"
            "urllib.request.Request(url, headers={'x-api-key': key})\n"
            "urllib.request.Request(url, headers=hdrs)\n"
            "urllib.request.Request(url, None, {'xi-api-key': key})\n"
            "req.add_header('User-Agent', 'dmp')\n"
            "req.add_unredirected_header('Authorization', f'Bearer {key}')\n"
            "urllib.request.Request(url, headers={'Accept': 'application/json'})\n"
        )
        self.assertEqual(len(self.violations("plant", planted)), 5)

    def test_refresh_models_evolink_key_stays_off_the_redirect(self):
        import refresh_models as rm
        sent = []

        def opener(req, timeout=None):
            sent.append(req)
            return Resp(b'{"data": [{"id": "evo-one"}], "has_more": false}')
        with mock.patch.dict(os.environ, {"EVOLINK_API_KEY": "evo-secret"}):
            self.assertEqual(rm.list_evolink(urlopen=opener), {"evo-one"})
        self.assertEqual(sent[0].get_header("Authorization"), "Bearer evo-secret")
        follow = urllib.request.HTTPRedirectHandler().redirect_request(
            sent[0], None, 302, "Found", {}, "https://evil.example/")
        self.assertNotIn("evo-secret", json.dumps(dict(follow.header_items())))


if __name__ == "__main__":
    unittest.main()
