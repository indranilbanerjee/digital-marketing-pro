"""scripts/model_router.py: pick a model by job from the provider's live list, never by name.

Brain A's build order for the router proof (_shared/PLAN-2026-10-27-model-router.md) was
FIXTURES FIRST: the deprecated-with-retires_at, retired, preview-only and 401 cases were
planted as failing tests before any selection code existed. The fixtures in
tests/fixtures/model_router/ are the documented shape of GET /v1/models; their ids and
dates are test data.

What each case pins:
  * deprecated, retiring next week, and asked for by name: warn and keep running;
  * retired and asked for by name: fail closed (exit 2), naming the replacement;
  * a preview id, or one under 14 days old, is never chosen;
  * a rejected key or an empty list: fail with the reason (exit 2), before any call;
  * a timeout, or a list without lifecycle fields: the shipped default, tagged offline;
  * a corrupted cache is rebuilt; a fresh cache means no network call;
  * MODEL_ROUTER_OFFLINE=1 never calls out;
  * the cache keys on the credential NAME and holds chosen ids only;
  * the same list on the same day always gives the same answer (a snapshot).
Stdlib only; no test touches the network.
"""
from __future__ import annotations

import copy
import importlib.util
import io
import json
import os
import random
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
from contextlib import redirect_stderr
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "model_router"
sys.path.insert(0, str(SCRIPTS))
import model_router as mr  # noqa: E402

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
KEY = "sk-ant-test-0000-not-a-real-key"
CRED = "ANTHROPIC_API_KEY"
JOB = "ai-visibility.probe"
HINTS = {
    "schema": 1,
    "jobs": {
        JOB: {"provider": "anthropic", "line": "sonnet", "capabilities": [],
              "default_alias": "latest-balanced-anthropic",
              "source": "https://platform.claude.com/docs/en/api/models/list", "read_on": "2026-10-27"},
        "test.fast": {"provider": "anthropic", "line": "haiku", "capabilities": [],
                      "default_alias": "latest-fast-anthropic",
                      "source": "https://platform.claude.com/docs/en/api/models/list", "read_on": "2026-10-27"},
    },
}


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def models() -> list:
    return copy.deepcopy(fixture("anthropic_models.json")["data"])


def with_change(mid: str, **fields) -> list:
    out = models()
    for m in out:
        if m["id"] == mid:
            m.update(fields)
    return out


class Fetch:
    """A recorded list, served without the network; counts how often it was asked."""

    def __init__(self, data=None, error=None):
        self.data, self.error, self.calls, self.versions = data, error, 0, []

    def __call__(self, api_key, anthropic_version):
        self.calls += 1
        self.versions.append(anthropic_version)
        assert api_key == KEY
        if self.error:
            raise self.error
        return copy.deepcopy(self.data if self.data is not None else models())


class RouterCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cache = self.tmp / "model-router-cache.json"
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))

    def route(self, fetch, job=JOB, requested=None, now=NOW, env=None, default="claude-sonnet-5-5"):
        err = io.StringIO()
        with redirect_stderr(err):
            result = mr.route(job, HINTS, provider="anthropic", credential_name=CRED, api_key=KEY,
                              default_model=default, requested=requested, fetch=fetch,
                              cache_path=self.cache, now=now, anthropic_version="2023-06-01",
                              env=env if env is not None else {})
        self.stderr = err.getvalue()
        return result


class TestPlantedCases(RouterCase):
    """The four cases Brain A asked for first."""

    def test_deprecated_retiring_next_week_warns_and_keeps_running(self):
        r = self.route(Fetch(), requested="claude-sonnet-4-5-20250929", now=datetime(2026, 11, 23, tzinfo=timezone.utc))
        self.assertEqual(r["model"], "claude-sonnet-4-5-20250929")
        self.assertEqual(r["basis"], "requested")
        self.assertEqual(r["replacement"], "claude-sonnet-5-5")
        joined = " ".join(r["warnings"])
        self.assertIn("deprecated", joined)
        self.assertIn("2026-11-30", joined)
        self.assertIn("claude-sonnet-5-5", joined)

    def test_retired_fails_closed_naming_the_replacement(self):
        fetch = Fetch(with_change("claude-sonnet-4-5-20250929", lifecycle="retired"))
        with self.assertRaises(mr.RouterError) as ctx:
            self.route(fetch, requested="claude-sonnet-4-5-20250929")
        self.assertEqual(ctx.exception.exit_code, 2)
        self.assertIn("retired", str(ctx.exception))
        self.assertIn("claude-sonnet-5-5", str(ctx.exception))

    def test_preview_newest_is_skipped(self):
        data = models() + [dict(models()[1], id="claude-sonnet-6-preview", display_name="Claude Sonnet 6 Preview",
                                created_at="2026-10-01T00:00:00Z")]
        r = self.route(Fetch(data))
        self.assertEqual(r["model"], "claude-sonnet-5-5")

    def test_too_new_to_promote_is_skipped(self):
        data = models() + [dict(models()[1], id="claude-sonnet-6", display_name="Claude Sonnet 6",
                                created_at=(NOW - timedelta(days=3)).isoformat().replace("+00:00", "Z"))]
        r = self.route(Fetch(data))
        self.assertEqual(r["model"], "claude-sonnet-5-5")

    def test_rejected_key_fails_with_the_reason_exit_2(self):
        body = json.dumps(fixture("anthropic_401.json")).encode()

        def opener(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, io.BytesIO(body))

        fetch = lambda key, ver: mr.fetch_anthropic(key, ver, urlopen=opener)  # noqa: E731
        with self.assertRaises(mr.RouterError) as ctx:
            self.route(fetch)
        self.assertEqual(ctx.exception.exit_code, 2)
        self.assertIn("401", str(ctx.exception))
        self.assertIn("authentication_error", str(ctx.exception))
        self.assertNotIn(KEY, str(ctx.exception))


class TestFailureModes(RouterCase):

    def test_empty_list_fails_exit_2(self):
        with self.assertRaises(mr.RouterError) as ctx:
            self.route(Fetch(fixture("anthropic_empty.json")["data"]))
        self.assertEqual(ctx.exception.exit_code, 2)
        self.assertIn("no models", str(ctx.exception))

    def test_timeout_uses_the_default_tagged_offline(self):
        def opener(req, timeout=None):
            raise TimeoutError("timed out")

        fetch = lambda key, ver: mr.fetch_anthropic(key, ver, urlopen=opener)  # noqa: E731
        r = self.route(fetch, default="claude-sonnet-5-5")
        self.assertEqual((r["model"], r["basis"], r["offline"]), ("claude-sonnet-5-5", "offline", True))
        self.assertIn("timeout", r["reason"])

    def test_a_list_without_lifecycle_is_not_trusted(self):
        data = models()
        for m in data:
            m.pop("lifecycle")
        r = self.route(Fetch(data), default="claude-sonnet-5-5")
        self.assertEqual((r["basis"], r["offline"]), ("offline", True))
        self.assertIn("lifecycle", r["reason"])

    def test_offline_with_no_default_fails(self):
        with self.assertRaises(mr.RouterError):
            self.route(Fetch(), env={"MODEL_ROUTER_OFFLINE": "1"}, default=None)

    def test_a_key_value_is_never_accepted_as_the_credential_name(self):
        with self.assertRaises(mr.RouterError) as ctx:
            mr.route(JOB, HINTS, provider="anthropic", credential_name=KEY, api_key=KEY,
                     default_model="x", fetch=Fetch(), cache_path=self.cache, now=NOW, env={})
        self.assertNotIn(KEY, str(ctx.exception))

    def test_cli_never_echoes_a_key_given_as_the_name(self):
        import subprocess
        proc = subprocess.run([sys.executable, str(SCRIPTS / "model_router.py"), "--hints",
                               str(SCRIPTS / "model_hints.json"), "--job", JOB, "--provider", "anthropic",
                               "--credential-name", KEY], capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn(KEY, proc.stdout + proc.stderr)

    def test_unknown_job_fails(self):
        with self.assertRaises(mr.RouterError):
            self.route(Fetch(), job="no.such.job")


class TestCache(RouterCase):

    def test_fresh_cache_means_no_call_and_one_call_serves_every_job(self):
        fetch = Fetch()
        self.assertEqual(self.route(fetch)["basis"], "live")
        again = self.route(fetch, now=NOW + timedelta(days=6))
        fast = self.route(fetch, job="test.fast", now=NOW + timedelta(days=6))
        self.assertEqual(fetch.calls, 1)
        self.assertEqual((again["basis"], again["model"]), ("cache", "claude-sonnet-5-5"))
        self.assertEqual((fast["basis"], fast["model"]), ("cache", "claude-haiku-5-5"))

    def test_stale_cache_lists_again(self):
        fetch = Fetch()
        self.route(fetch)
        self.route(fetch, now=NOW + timedelta(days=mr.TTL_DAYS, seconds=1))
        self.assertEqual(fetch.calls, 2)

    def test_corrupted_cache_is_rebuilt(self):
        self.cache.write_text("{not json", encoding="utf-8")
        fetch = Fetch()
        r = self.route(fetch)
        self.assertEqual((fetch.calls, r["model"]), (1, "claude-sonnet-5-5"))
        self.assertTrue(any("rebuilt" in w for w in r["warnings"]))
        json.loads(self.cache.read_text(encoding="utf-8"))

    def test_offline_env_never_calls_out(self):
        fetch = Fetch()
        r = self.route(fetch, env={"MODEL_ROUTER_OFFLINE": "1"})
        self.assertEqual((fetch.calls, r["basis"], r["offline"], r["model"]), (0, "offline", True, "claude-sonnet-5-5"))

    def test_cache_holds_the_credential_name_and_chosen_ids_only(self):
        self.route(Fetch(), requested="claude-sonnet-4-5-20250929")
        text = self.cache.read_text(encoding="utf-8")
        self.assertNotIn(KEY, text)
        cache = json.loads(text)
        for key, entry in cache["entries"].items():
            self.assertTrue(key.endswith("|" + CRED), key)
            self.assertLessEqual(set(entry), mr.CACHE_FIELDS, key)
        for banned in ("capabilities", "display_name", "data", "max_input_tokens"):
            self.assertNotIn(f'"{banned}"', text)

    def test_the_list_call_uses_the_generation_calls_version(self):
        fetch = Fetch()
        self.route(fetch)
        self.assertEqual(fetch.versions, ["2023-06-01"])


class TestSelection(RouterCase):

    def test_capability_requirements_filter(self):
        hints = copy.deepcopy(HINTS)
        hints["jobs"][JOB]["capabilities"] = ["pdf_input"]
        data = with_change("claude-sonnet-5-5", capabilities=dict(models()[1]["capabilities"], pdf_input={"supported": False}))
        r = mr.route(JOB, hints, provider="anthropic", credential_name=CRED, api_key=KEY, default_model="x",
                     fetch=Fetch(data), cache_path=None, now=NOW, env={})
        self.assertEqual(r["model"], "claude-sonnet-4-6")

    def test_determinism_snapshot(self):
        want = fixture("snapshot_ai_visibility_probe.json")
        self.assertEqual(self.route(Fetch()), want)
        shuffled = models()
        random.Random(7).shuffle(shuffled)
        self.cache.unlink()
        self.assertEqual(self.route(Fetch(shuffled)), want)


class TestNaturalExperiment(RouterCase):
    """Sonnet 4.5 retires 2026-11-30: warn before, fail closed after, float unaffected; no registry edit."""

    def test_before_and_after(self):
        before = datetime(2026, 11, 23, tzinfo=timezone.utc)
        after = datetime(2026, 12, 1, tzinfo=timezone.utc)
        r = self.route(Fetch(), requested="claude-sonnet-4-5-20250929", now=before)
        self.assertEqual(r["model"], "claude-sonnet-4-5-20250929")
        self.assertTrue(r["warnings"])
        self.cache.unlink()
        retired = with_change("claude-sonnet-4-5-20250929", lifecycle="retired")
        with self.assertRaises(mr.RouterError):
            self.route(Fetch(retired), requested="claude-sonnet-4-5-20250929", now=after)
        self.assertEqual(self.route(Fetch(retired), now=after)["model"], "claude-sonnet-5-5")


class TestFetchAnthropic(unittest.TestCase):

    def test_pages_headers_and_query(self):
        seen = []
        pages = [fixture("anthropic_models_page1.json"), fixture("anthropic_models_page2.json")]

        class Resp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def opener(req, timeout=None):
            seen.append(req)
            return Resp(json.dumps(pages[len(seen) - 1]).encode())

        got = mr.fetch_anthropic(KEY, "2023-06-01", urlopen=opener)
        self.assertEqual([m["id"] for m in got], [m["id"] for m in models()])
        first = urllib.parse.urlsplit(seen[0].full_url)
        self.assertEqual((first.scheme, first.netloc, first.path), ("https", "api.anthropic.com", "/v1/models"))
        query = urllib.parse.parse_qs(first.query)
        self.assertEqual(query["limit"], ["1000"])
        self.assertEqual(sorted(query["lifecycle[]"]), ["active", "deprecated", "retired"])
        self.assertEqual(urllib.parse.parse_qs(urllib.parse.urlsplit(seen[1].full_url).query)["after_id"],
                         ["claude-opus-5-5"])
        self.assertEqual(seen[0].get_header("X-api-key"), KEY)
        self.assertEqual(seen[0].get_header("Anthropic-version"), "2023-06-01")


class TestHintBook(unittest.TestCase):

    def test_dmp_hint_book_is_valid(self):
        hints = json.loads((SCRIPTS / "model_hints.json").read_text(encoding="utf-8"))
        self.assertEqual(mr.validate_hints(hints), [])
        self.assertIn(JOB, hints["jobs"])

    def test_a_rule_without_its_source_or_date_is_rejected(self):
        bad = copy.deepcopy(HINTS)
        del bad["jobs"][JOB]["read_on"]
        bad["jobs"]["test.fast"]["source"] = ""
        problems = "\n".join(mr.validate_hints(bad))
        self.assertIn(f"{JOB}: read_on", problems)
        self.assertIn("test.fast: source", problems)


class TestCheckerUsesTheRouter(unittest.TestCase):

    def load_checker(self):
        spec = importlib.util.spec_from_file_location("ai_visibility_checker", SCRIPTS / "ai-visibility-checker.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_route_anthropic_live_and_offline(self):
        checker = self.load_checker()
        with tempfile.TemporaryDirectory() as home:
            old = {k: os.environ.get(k) for k in ("CLAUDE_MARKETING_HOME", "MODEL_ROUTER_OFFLINE")}
            os.environ["CLAUDE_MARKETING_HOME"] = home
            os.environ.pop("MODEL_ROUTER_OFFLINE", None)
            try:
                with redirect_stderr(io.StringIO()):
                    live = checker.route_anthropic(None, KEY, "2023-06-01", fetch=Fetch(), now=NOW)
                    os.environ["MODEL_ROUTER_OFFLINE"] = "1"
                    off = checker.route_anthropic(None, KEY, "2023-06-01", fetch=Fetch(), now=NOW)
            finally:
                for k, v in old.items():
                    os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
            self.assertEqual((live["model"], live["basis"]), ("claude-sonnet-5-5", "live"))
            self.assertTrue(off["offline"])
            self.assertTrue((Path(home) / "model-router-cache.json").exists())


class TestPrivacyDocsTruth(unittest.TestCase):

    def test_privacy_names_the_list_call_and_its_limits(self):
        text = (REPO / "PRIVACY.md").read_text(encoding="utf-8")
        for needed in ("/v1/models", "MODEL_ROUTER_OFFLINE", f"once every {mr.TTL_DAYS} days",
                       "never the key", "model-router-cache.json"):
            self.assertIn(needed, text)


class TestParity(unittest.TestCase):
    """One file, byte-identical wherever it is copied (the hero-sync pattern)."""

    def test_sibling_copies_are_identical(self):
        mine = (SCRIPTS / "model_router.py").read_bytes()
        copies = [p for p in (REPO.parent / name / "scripts" / "model_router.py"
                              for name in ("contentforge", "socialforge", "CutForge")) if p.exists()]
        for p in copies:
            self.assertEqual(p.read_bytes(), mine, f"{p} differs from DMP's model_router.py")
        if not copies:
            self.skipTest("no sibling copy checked out yet")


if __name__ == "__main__":
    unittest.main()
