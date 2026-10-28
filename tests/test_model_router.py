"""scripts/model_router.py: pick a model by job from the provider's live list, never by name.

The router proof was built FIXTURES FIRST: the deprecated-with-retires_at, retired,
preview-only and 401 cases were planted as failing tests before any selection code existed. The fixtures in
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
import urllib.request
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
JOB = "ai-visibility.probe.anthropic"
OAI_KEY = "sk-test-0000-not-a-real-openai-key"
OAI_CRED = "OPENAI_API_KEY"
OAI_JOB = "ai-visibility.probe.openai"
SOL = r"^gpt-(?P<version>\d+(?:\.\d+)*)-sol$"
HINTS = {
    "schema": 1,
    "jobs": {
        JOB: {"provider": "anthropic", "line": "sonnet", "capabilities": [],
              "default_alias": "latest-balanced-anthropic",
              "source": "https://platform.claude.com/docs/en/api/models/list", "read_on": "2026-10-27"},
        "test.fast": {"provider": "anthropic", "line": "haiku", "capabilities": [],
                      "default_alias": "latest-fast-anthropic",
                      "source": "https://platform.claude.com/docs/en/api/models/list", "read_on": "2026-10-27"},
        OAI_JOB: {"provider": "openai", "family": SOL, "default_alias": "latest-balanced-openai",
                  "source": "https://developers.openai.com/api/docs/models", "read_on": "2026-10-27"},
    },
    "deprecations": {
        "openai": {
            "source": "https://developers.openai.com/api/docs/deprecations", "read_on": "2026-10-27",
            "models": {
                "gpt-4o-2024-08-06": {"announced": "2026-10-14", "shutdown": "2027-01-14", "replacement": "gpt-6-luna"},
                "gpt-5.1": {"announced": "2026-10-01", "shutdown": "2027-04-01", "replacement": "gpt-6-sol"},
                "o3": {"announced": "2026-06-11", "shutdown": "2026-12-11", "replacement": "gpt-5.6-sol"},
            },
        },
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
    """The four cases planted first."""

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
        want = fixture("snapshot_anthropic_probe.json")
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


def oai_models() -> list:
    return copy.deepcopy(fixture("openai_models.json")["data"])


def oai_with(extra=(), **changes) -> list:
    out = oai_models()
    for m in out:
        m.update(changes.get(m["id"], {}))
    return out + [dict(e) for e in extra]


def created(day: datetime) -> int:
    return int(day.timestamp())


class OAIFetch(Fetch):
    def __call__(self, api_key, anthropic_version):
        self.calls += 1
        assert api_key == OAI_KEY
        if self.error:
            raise self.error
        return copy.deepcopy(self.data if self.data is not None else oai_models())


class OpenAICase(RouterCase):
    def oai(self, fetch, requested=None, now=NOW, hints=None, default="gpt-6.1-sol", env=None):
        err = io.StringIO()
        with redirect_stderr(err):
            return mr.route(OAI_JOB, hints or HINTS, provider="openai", credential_name=OAI_CRED, api_key=OAI_KEY,
                            default_model=default, requested=requested, fetch=fetch, cache_path=self.cache,
                            now=now, env=env if env is not None else {})


class TestOpenAIPresenceOnly(OpenAICase):
    """OpenAI's list gives ids, created, owned_by and an optional shutdown_date: selection is by
    family rule over ids, lifecycle from that date and the agent-read deprecations record."""

    def test_float_picks_the_highest_version_in_the_family(self):
        r = self.oai(OAIFetch())
        self.assertEqual((r["model"], r["basis"], r["family"]), ("gpt-6.1-sol", "live", SOL))

    def test_preview_and_too_new_are_skipped(self):
        data = oai_with([{"id": "gpt-6.2-sol-preview", "object": "model", "created": created(NOW - timedelta(days=30)),
                          "owned_by": "openai", "shutdown_date": None},
                         {"id": "gpt-6.2-sol", "object": "model", "created": created(NOW - timedelta(days=3)),
                          "owned_by": "openai", "shutdown_date": None}])
        self.assertEqual(self.oai(OAIFetch(data))["model"], "gpt-6.1-sol")

    def test_fine_tunes_and_dated_snapshots_are_never_picked(self):
        loose = copy.deepcopy(HINTS)
        loose["jobs"][OAI_JOB]["family"] = r"^(?:ft:)?gpt-(?P<version>\d+(?:\.\d+)*)-sol.*$"
        data = oai_with([{"id": "ft:gpt-7-sol:acme-corp::zzz", "object": "model",
                          "created": created(NOW - timedelta(days=60)), "owned_by": "user-org-acme"}])
        r = self.oai(OAIFetch(data), hints=loose)
        self.assertEqual(r["model"], "gpt-6.1-sol")

    def test_a_shutdown_date_in_the_list_takes_a_model_out_of_selection(self):
        data = oai_with(**{"gpt-6.1-sol": {"shutdown_date": "2027-06-01"}})
        self.assertEqual(self.oai(OAIFetch(data))["model"], "gpt-6-sol")

    def test_deprecated_by_the_list_warns_and_keeps(self):
        r = self.oai(OAIFetch(), requested="gpt-4o-2024-08-06")
        self.assertEqual((r["model"], r["basis"], r["replacement"]), ("gpt-4o-2024-08-06", "requested", "gpt-6-luna"))
        self.assertIn("2027-01-14", " ".join(r["warnings"]))

    def test_deprecated_by_the_record_only_warns_and_keeps(self):
        r = self.oai(OAIFetch(), requested="gpt-5.1")
        self.assertEqual((r["model"], r["replacement"]), ("gpt-5.1", "gpt-6-sol"))
        self.assertIn("2027-04-01", " ".join(r["warnings"]))
        # Before 3.39.0 this said "the router would choose gpt-6-sol"; the router's own pick is gpt-6.1-sol.
        self.assertIn("deprecations page names gpt-6-sol", " ".join(r["warnings"]))

    def test_past_its_shutdown_it_is_refused_naming_the_replacement(self):
        with self.assertRaises(mr.RouterError) as ctx:
            self.oai(OAIFetch(), requested="gpt-4o-2024-08-06", now=datetime(2027, 1, 15, tzinfo=timezone.utc))
        self.assertIn("gpt-6-luna", str(ctx.exception))
        self.cache.unlink()
        gone = [m for m in oai_models() if m["id"] != "o3"]
        with self.assertRaises(mr.RouterError) as ctx:
            self.oai(OAIFetch(gone), requested="o3", now=datetime(2026, 12, 12, tzinfo=timezone.utc))
        self.assertIn("gpt-5.6-sol", str(ctx.exception))

    def test_a_fine_tune_follows_its_base_model_and_is_never_cached(self):
        r = self.oai(OAIFetch(), requested="ft:gpt-4o-2024-08-06:acme-corp::def456")
        self.assertEqual(r["model"], "ft:gpt-4o-2024-08-06:acme-corp::def456")
        self.assertIn("2027-01-14", " ".join(r["warnings"]))
        self.oai(OAIFetch(), requested="ft:gpt-6.1-sol:acme-corp::abc123")
        self.assertNotIn("acme", self.cache.read_text(encoding="utf-8"))
        self.assertNotIn("ft:", self.cache.read_text(encoding="utf-8"))

    def test_a_stale_deprecations_record_is_named(self):
        stale = copy.deepcopy(HINTS)
        stale["deprecations"]["openai"]["read_on"] = "2026-08-01"
        r = self.oai(OAIFetch(), hints=stale)
        self.assertTrue(any("deprecations" in w and "developers.openai.com" in w for w in r["warnings"]), r["warnings"])

    def test_rejected_key_empty_and_timeout(self):
        body = json.dumps(fixture("openai_401.json")).encode()

        def refuse(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, io.BytesIO(body))

        with self.assertRaises(mr.RouterError) as ctx:
            self.oai(lambda k, v: mr.fetch_openai(k, v, urlopen=refuse))
        self.assertIn("401", str(ctx.exception))
        self.assertNotIn("sk-test", str(ctx.exception))
        with self.assertRaises(mr.RouterError):
            self.oai(OAIFetch(fixture("openai_empty.json")["data"]))

        def slow(req, timeout=None):
            raise TimeoutError("timed out")

        r = self.oai(lambda k, v: mr.fetch_openai(k, v, urlopen=slow))
        self.assertEqual((r["basis"], r["offline"], r["model"]), ("offline", True, "gpt-6.1-sol"))

    def test_determinism_snapshot(self):
        want = fixture("snapshot_openai_probe.json")
        self.assertEqual(self.oai(OAIFetch()), want)
        shuffled = oai_models()
        random.Random(3).shuffle(shuffled)
        self.cache.unlink()
        self.assertEqual(self.oai(OAIFetch(shuffled)), want)

    def test_fetch_openai_request(self):
        seen = []

        class Resp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def opener(req, timeout=None):
            seen.append(req)
            return Resp(json.dumps(fixture("openai_models.json")).encode())

        got = mr.fetch_openai(OAI_KEY, None, urlopen=opener)
        self.assertEqual(len(got), 13)
        url = urllib.parse.urlsplit(seen[0].full_url)
        self.assertEqual((url.scheme, url.netloc, url.path), ("https", "api.openai.com", "/v1/models"))
        self.assertEqual(seen[0].get_header("Authorization"), f"Bearer {OAI_KEY}")
        self.assertIsNone(seen[0].get_header("X-api-key"))


G_KEY = "g-test-0000-not-a-real-google-key"
G_CRED = "GEMINI_API_KEY"
G_JOB = "test.vision.google"
FLASH = r"^gemini-(?P<version>\d+(?:\.\d+)*)-flash$"
G_DEPRECATIONS = "https://ai.google.dev/gemini-api/docs/deprecations"
GHINTS = copy.deepcopy(HINTS)
GHINTS["jobs"][G_JOB] = {"provider": "google", "family": FLASH, "capabilities": ["generateContent"],
                         "default_alias": "latest-vision-google",
                         "source": "https://ai.google.dev/gemini-api/docs/models", "read_on": "2026-10-27"}
# Rows copied from the deprecations page as read 2026-10-27 (shutdown dates there are the EARLIEST
# possible; the page greys out the models already shut down, recorded here as shut_down).
GHINTS["deprecations"]["google"] = {
    "source": G_DEPRECATIONS, "read_on": "2026-10-27",
    "models": {
        "gemini-3.8-flash": {"released": "2026-09-02"},
        "gemini-3.8-flash-tts": {"released": "2026-09-22"},
        "gemini-3.7-flash": {"released": "2026-08-13", "redirects_to": "gemini-3.8-flash"},
        "gemini-3.6-flash": {"released": "2026-07-21"},
        "gemini-3.5-flash": {"released": "2026-05-19", "redirects_to": "gemini-3.6-flash"},
        "gemini-3.5-flash-lite": {"released": "2026-07-21"},
        "gemini-3.5-transcribe": {"released": "2026-08"},
        "gemini-3.1-flash-lite": {"released": "2026-05-07", "shutdown": "2027-05-07",
                                  "replacement": "gemini-3.5-flash-lite"},
        "gemini-3-flash-preview": {"released": "2025-12-17", "replacement": "gemini-3.6-flash"},
        "gemini-3.1-flash-tts-preview": {"released": "2026-02-26", "shutdown": "2026-11-17",
                                         "replacement": "gemini-3.8-flash-tts or gemini-3.8-flash-lite-tts"},
        "gemini-2.5-flash": {"released": "2025-06-17"},
        "gemini-2.0-flash": {"released": "2025-02-05", "shutdown": "2026-06-01", "shut_down": True,
                             "replacement": "gemini-3.6-flash"},
    },
}


def g_models() -> list:
    return copy.deepcopy(fixture("google_models.json")["models"])


def g_entry(mid: str, methods=("generateContent", "countTokens")) -> dict:
    return {"name": f"models/{mid}", "baseModelId": mid, "version": "001", "displayName": mid,
            "supportedGenerationMethods": list(methods)}


class GFetch(Fetch):
    def __call__(self, api_key, anthropic_version):
        self.calls += 1
        assert api_key == G_KEY
        if self.error:
            raise self.error
        return copy.deepcopy(self.data if self.data is not None else g_models())


class GoogleCase(RouterCase):
    def g(self, fetch, requested=None, now=NOW, hints=None, default="gemini-3.6-flash", env=None, registry=None):
        err = io.StringIO()
        with redirect_stderr(err):
            return mr.route(G_JOB, hints or GHINTS, provider="google", credential_name=G_CRED, api_key=G_KEY,
                            default_model=default, requested=requested, fetch=fetch, cache_path=self.cache,
                            now=now, env=env if env is not None else {}, registry=registry)


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestGooglePresenceOnly(GoogleCase):
    """Google's models.list gives names ("models/<id>"), versions, token limits and the generation
    methods each model supports, but no lifecycle and no release date, and previews, experimental
    ids and moving "latest" aliases are mixed in. Selection is by family rule over ids with the
    job's methods required; lifecycle AND release dates come from the deprecations record an
    agent read from Google's page. Planted before the adapter existed."""

    def test_float_picks_the_highest_version_with_the_required_method(self):
        r = self.g(GFetch())
        self.assertEqual((r["model"], r["basis"], r["family"], r["provider"]),
                         ("gemini-3.8-flash", "live", FLASH, "google"))

    def test_generate_content_is_required_from_the_list(self):
        data = g_models()
        for m in data:
            if m["baseModelId"] == "gemini-3.8-flash":
                m["supportedGenerationMethods"] = ["bidiGenerateContent", "countTokens"]
        self.assertEqual(self.g(GFetch(data))["model"], "gemini-3.6-flash")

    def test_a_redirected_endpoint_is_never_picked_and_warns_when_asked_for(self):
        data = [m for m in g_models() if m["baseModelId"] != "gemini-3.8-flash"]
        self.assertEqual(self.g(GFetch(data))["model"], "gemini-3.6-flash")
        self.cache.unlink()
        r = self.g(GFetch(), requested="gemini-3.5-flash")
        self.assertEqual((r["model"], r["basis"], r["replacement"]), ("gemini-3.5-flash", "requested", "gemini-3.6-flash"))
        joined = " ".join(r["warnings"])
        self.assertIn("routes", joined)
        self.assertIn("gemini-3.6-flash", joined)

    def test_previews_exp_latest_and_dated_ids_are_never_picked(self):
        loose = copy.deepcopy(GHINTS)
        loose["jobs"][G_JOB]["family"] = r"^gemini-(?P<version>\d+(?:\.\d+)*)-flash(?:-.+)?$"
        names = ("gemini-3.9-flash-preview", "gemini-3.9-flash-exp", "gemini-3.9-flash-latest",
                 "gemini-3.9-flash-preview-11-2026", "gemini-3.9-flash-11-2026", "gemini-3.9-flash-11-05")
        for name in names:
            loose["deprecations"]["google"]["models"][name] = {"released": "2026-09-01"}
        data = [m for m in g_models() if not m["baseModelId"].endswith(("-tts", "-lite"))]
        data += [g_entry(n) for n in names]
        self.assertEqual(self.g(GFetch(data), hints=loose)["model"], "gemini-3.8-flash")

    def test_too_new_by_the_records_release_date_is_skipped(self):
        newer = copy.deepcopy(GHINTS)
        newer["deprecations"]["google"]["models"]["gemini-3.9-flash"] = {"released": "2026-10-20"}
        r = self.g(GFetch(g_models() + [g_entry("gemini-3.9-flash")]), hints=newer)
        self.assertEqual(r["model"], "gemini-3.8-flash")
        self.assertEqual(r["warnings"], [])

    def test_a_listed_model_missing_from_the_record_is_held_back_and_named(self):
        r = self.g(GFetch(g_models() + [g_entry("gemini-3.9-flash")]))
        self.assertEqual(r["model"], "gemini-3.8-flash")
        held = [w for w in r["warnings"] if "release date" in w]
        self.assertEqual(len(held), 1, r["warnings"])
        self.assertIn(G_DEPRECATIONS, held[0])
        cached = self.g(GFetch(error=AssertionError("a fresh cache must not call out")))
        self.assertEqual(cached["warnings"], r["warnings"])

    def test_a_month_only_release_date_counts_from_the_months_last_day(self):
        loose = copy.deepcopy(GHINTS)
        loose["jobs"][G_JOB]["family"] = r"^gemini-(?P<version>\d+(?:\.\d+)*)-transcribe$"
        loose["deprecations"]["google"]["models"]["gemini-3.5-transcribe"] = {"released": "2026-10"}
        data = [g_entry("gemini-3.5-transcribe")]
        with self.assertRaises(mr.RouterError):
            self.g(GFetch(data), hints=loose, now=datetime(2026, 11, 10, tzinfo=timezone.utc))
        self.cache.unlink()
        r = self.g(GFetch(data), hints=loose, now=datetime(2026, 11, 15, tzinfo=timezone.utc))
        self.assertEqual(r["model"], "gemini-3.5-transcribe")

    def test_deprecated_by_the_record_warns_and_keeps(self):
        r = self.g(GFetch(), requested="gemini-3.1-flash-lite")
        self.assertEqual((r["model"], r["basis"], r["replacement"]),
                         ("gemini-3.1-flash-lite", "requested", "gemini-3.5-flash-lite"))
        joined = " ".join(r["warnings"])
        self.assertIn("2027-05-07", joined)
        # The replacement is the page's recommendation, not the router's pick (that would be 3.8 Flash).
        self.assertIn("deprecations page names gemini-3.5-flash-lite", joined)
        self.assertNotIn("the router would choose", joined)

    def test_shut_down_on_the_page_is_refused_naming_the_replacement(self):
        with self.assertRaises(mr.RouterError) as ctx:
            self.g(GFetch(), requested="gemini-2.0-flash")
        self.assertEqual(ctx.exception.exit_code, 2)
        self.assertTrue(str(ctx.exception).startswith("gemini-2.0-flash is retired"), str(ctx.exception))
        self.assertIn("Use gemini-3.6-flash, the replacement google's deprecations page names", str(ctx.exception))
        self.assertNotIn("newest", str(ctx.exception))

    def test_past_the_earliest_shutdown_date_but_still_served_warns_not_refuses(self):
        """Google's dates are the earliest possible shutdown; the page greys out what is really off."""
        later = datetime(2026, 11, 20, tzinfo=timezone.utc)
        r = self.g(GFetch(), requested="gemini-3.1-flash-tts-preview", now=later)
        self.assertEqual(r["model"], "gemini-3.1-flash-tts-preview")
        joined = " ".join(r["warnings"])
        self.assertIn("2026-11-17", joined)
        self.assertIn("any time", joined)

    def test_a_models_prefix_on_a_requested_id_is_understood(self):
        r = self.g(GFetch(), requested="models/gemini-3.1-flash-lite")
        self.assertIn("2027-05-07", " ".join(r["warnings"]))

    def test_rejected_key_empty_list_and_timeout(self):
        body = json.dumps(fixture("google_400.json")).encode()

        def refuse(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {}, io.BytesIO(body))

        with self.assertRaises(mr.RouterError) as ctx:
            self.g(lambda k, v: mr.fetch_google(k, v, urlopen=refuse))
        self.assertEqual(ctx.exception.exit_code, 2)
        self.assertIn("400", str(ctx.exception))
        self.assertIn("INVALID_ARGUMENT", str(ctx.exception))
        self.assertNotIn(G_KEY, str(ctx.exception))
        with self.assertRaises(mr.RouterError) as ctx:
            self.g(lambda k, v: mr.fetch_google(k, v, urlopen=lambda req, timeout=None: Resp(
                json.dumps(fixture("google_empty.json")).encode())))
        self.assertIn("no models", str(ctx.exception))

        def slow(req, timeout=None):
            raise TimeoutError("timed out")

        r = self.g(lambda k, v: mr.fetch_google(k, v, urlopen=slow))
        self.assertEqual((r["basis"], r["offline"], r["model"]), ("offline", True, "gemini-3.6-flash"))

    def test_offline_checks_the_shipped_registry(self):
        # A model only the registry knows (the record has no gemini-1.5 rows), so the registry speaks.
        registry = {"models": [{"id": "gemini-1.5-flash", "status": "retired", "shutdown_date": "2025-09-24",
                                "replacement_id": "gemini-3.6-flash"}]}
        with self.assertRaises(mr.RouterError) as ctx:
            self.g(GFetch(), requested="gemini-1.5-flash", env={"MODEL_ROUTER_OFFLINE": "1"}, registry=registry)
        self.assertTrue(str(ctx.exception).startswith("gemini-1.5-flash is retired"), str(ctx.exception))
        self.assertIn("shipped registry", str(ctx.exception))
        self.assertIn("gemini-3.6-flash", str(ctx.exception))

    def test_cache_holds_the_credential_name_and_chosen_ids_only(self):
        self.g(GFetch())
        text = self.cache.read_text(encoding="utf-8")
        self.assertIn(G_CRED, text)
        self.assertNotIn(G_KEY, text)
        self.assertNotIn("gemini-embedding-2", text)

    def test_determinism_snapshot(self):
        want = fixture("snapshot_google_probe.json")
        self.assertEqual(self.g(GFetch()), want)
        shuffled = g_models()
        random.Random(5).shuffle(shuffled)
        self.cache.unlink()
        self.assertEqual(self.g(GFetch(shuffled)), want)

    def test_the_key_goes_in_a_header_never_the_url(self):
        seen = []
        pages = [fixture("google_models_page1.json"), fixture("google_models_page2.json")]

        def opener(req, timeout=None):
            seen.append(req)
            return Resp(json.dumps(pages[len(seen) - 1]).encode())

        got = mr.fetch_google(G_KEY, None, urlopen=opener)
        self.assertEqual([m["name"] for m in got], [m["name"] for m in g_models()])
        self.assertEqual(len(seen), 2)
        for req in seen:
            url = urllib.parse.urlsplit(req.full_url)
            self.assertEqual((url.scheme, url.netloc, url.path),
                             ("https", "generativelanguage.googleapis.com", "/v1beta/models"))
            self.assertNotIn("key", urllib.parse.parse_qs(url.query))
            self.assertNotIn(G_KEY, req.full_url)
            self.assertEqual(req.get_header("X-goog-api-key"), G_KEY)
            self.assertIsNone(req.get_header("Authorization"))
        self.assertEqual(urllib.parse.parse_qs(urllib.parse.urlsplit(seen[0].full_url).query)["pageSize"], ["1000"])
        self.assertEqual(urllib.parse.parse_qs(urllib.parse.urlsplit(seen[1].full_url).query)["pageToken"],
                         ["Cg10ZXN0LXBhZ2UtdHdv"])

    def test_the_hint_book_and_record_rules_for_google(self):
        self.assertEqual(mr.validate_hints(GHINTS), [])
        bad = copy.deepcopy(GHINTS)
        bad["jobs"][G_JOB]["capabilities"] = []
        bad["jobs"]["test.google.line"] = {"provider": "google", "line": "flash", "capabilities": ["generateContent"],
                                           "source": "https://ai.google.dev/gemini-api/docs/models",
                                           "read_on": "2026-10-27"}
        record = bad["deprecations"]["google"]["models"]
        record["gemini-3.8-flash"] = {"released": "September 2, 2026"}
        record["gemini-3.6-flash"] = {"released": "2026-07-21", "shutdown_on": "2027-01-01"}
        record["gemini-3.7-flash"] = {"released": "2026-08-13", "redirects_to": ""}
        record["gemini-2.0-flash"] = {"shut_down": True, "replacement": "gemini-3.6-flash"}
        record["gemini-9-flash"] = {}
        problems = "\n".join(mr.validate_hints(bad))
        for expected in (f"{G_JOB}: google jobs must name the generation methods",
                         "test.google.line: google lists no model lines",
                         "deprecations.google.gemini-3.8-flash: released must be YYYY-MM-DD or YYYY-MM",
                         "deprecations.google.gemini-3.6-flash: unknown field shutdown_on",
                         "deprecations.google.gemini-3.7-flash: redirects_to",
                         "deprecations.google.gemini-2.0-flash: shut_down needs its shutdown date",
                         "deprecations.google.gemini-9-flash: empty"):
            self.assertIn(expected, problems)


REGISTRY = {
    "aliases": {"latest-balanced-anthropic": "claude-sonnet-5-5"},
    "models": [
        {"id": "claude-sonnet-4-5-20250929", "status": "deprecated", "shutdown_date": "2026-11-30",
         "replacement_id": "claude-sonnet-5-5"},
        {"id": "claude-sonnet-5-5", "status": "current"},
        {"id": "claude-3-5-haiku-20241022", "status": "retired", "shutdown_date": "2026-02-19",
         "replacement_id": "claude-haiku-5-5"},
    ],
}


class TestOfflineLifecycle(RouterCase):
    """With no live list (MODEL_ROUTER_OFFLINE, a timeout, provider trouble), a model asked for by
    name is checked against the shipped registry: the same contract as the live path. Found from
    an installed copy: offline, a requested Sonnet 4.5 came back with no warning at all."""

    def offline(self, requested, now=NOW, registry=REGISTRY, fetch=None, env=None):
        err = io.StringIO()
        with redirect_stderr(err):
            return mr.route(JOB, HINTS, provider="anthropic", credential_name=CRED, api_key=KEY,
                            default_model="claude-sonnet-5-5", requested=requested, fetch=fetch or Fetch(),
                            cache_path=self.cache, now=now, env={"MODEL_ROUTER_OFFLINE": "1"} if env is None else env,
                            registry=registry)

    def test_deprecated_warns_naming_the_date_and_replacement(self):
        r = self.offline("claude-sonnet-4-5-20250929")
        self.assertEqual((r["model"], r["basis"], r["replacement"]),
                         ("claude-sonnet-4-5-20250929", "offline", "claude-sonnet-5-5"))
        joined = " ".join(r["warnings"])
        for needed in ("deprecated", "2026-11-30", "claude-sonnet-5-5"):
            self.assertIn(needed, joined)

    def test_an_undated_alias_matches_its_one_dated_snapshot(self):
        r = self.offline("claude-sonnet-4-5")
        self.assertIn("2026-11-30", " ".join(r["warnings"]))
        self.assertIn("claude-sonnet-4-5-20250929", " ".join(r["warnings"]))

    def test_past_its_shutdown_it_is_refused(self):
        with self.assertRaises(mr.RouterError) as ctx:
            self.offline("claude-sonnet-4-5-20250929", now=datetime(2026, 12, 1, tzinfo=timezone.utc))
        self.assertEqual(ctx.exception.exit_code, 2)
        self.assertIn("claude-sonnet-5-5", str(ctx.exception))
        with self.assertRaises(mr.RouterError):
            self.offline("claude-3-5-haiku-20241022")

    def test_a_list_timeout_takes_the_same_check(self):
        r = self.offline("claude-sonnet-4-5-20250929", env={},
                         fetch=Fetch(error=mr.FetchError("timeout", "timed out")))
        self.assertEqual(r["basis"], "offline")
        self.assertIn("2026-11-30", " ".join(r["warnings"]))

    def test_an_id_the_registry_does_not_know_is_named(self):
        r = self.offline("claude-imaginary-9")
        self.assertTrue(any("not in the shipped registry" in w for w in r["warnings"]), r["warnings"])

    def test_without_a_registry_nothing_changes(self):
        self.assertEqual(self.offline("claude-sonnet-4-5-20250929", registry=None)["warnings"], [])

    def test_cli_resolves_default_alias_and_checks_the_requested_id(self):
        import subprocess
        env = dict(os.environ, MODEL_ROUTER_OFFLINE="1")
        base = [sys.executable, str(SCRIPTS / "model_router.py"), "--hints", str(SCRIPTS / "model_hints.json"),
                "--job", JOB, "--provider", "anthropic", "--credential-name", CRED]
        live_registry = json.loads((SCRIPTS / "model_registry.json").read_text(encoding="utf-8"))
        proc = subprocess.run(base, capture_output=True, text=True, timeout=60, env=env)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["model"], live_registry["aliases"]["latest-balanced-anthropic"])
        reg = self.tmp / "registry.json"
        reg.write_text(json.dumps(REGISTRY), encoding="utf-8")
        proc = subprocess.run(base + ["--registry", str(reg), "--requested", "claude-sonnet-4-5"],
                              capture_output=True, text=True, timeout=60, env=env)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("2026-11-30", " ".join(json.loads(proc.stdout)["warnings"]))
        proc = subprocess.run(base + ["--registry", str(reg), "--requested", "claude-3-5-haiku-20241022"],
                              capture_output=True, text=True, timeout=60, env=env)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("claude-haiku-5-5", proc.stdout)


class TestOfflineRecord(unittest.TestCase):
    """Without the live list, a named model is checked against the hint book's deprecations
    record as well as the shipped registry: the record ships beside the router and is local
    data, not a call. Found from an installed copy: offline, a requested gemini-2.0-flash
    (shut_down in the record) was sent with only "not in the shipped registry", and
    gemini-3.5-flash warned as deprecated without saying its endpoint redirects. The stricter
    source wins and the message names it. Planted before the change (they fail on b71cd44)."""

    LATER = datetime(2026, 12, 12, tzinfo=timezone.utc)

    def go(self, provider, requested, registry=None, now=NOW, env=None, fetch=None, hints=None, **kw):
        job, cred, key, default = {"google": (G_JOB, G_CRED, G_KEY, "gemini-3.6-flash"),
                                   "openai": (OAI_JOB, OAI_CRED, OAI_KEY, "gpt-6.1-sol")}[provider]
        with redirect_stderr(io.StringIO()):
            return mr.route(job, hints or GHINTS, provider=provider, credential_name=cred, api_key=key,
                            default_model=default, requested=requested, fetch=fetch or GFetch(), cache_path=None,
                            now=now, env={"MODEL_ROUTER_OFFLINE": "1"} if env is None else env,
                            registry={"models": []} if registry is None else registry, **kw)

    def test_google_shut_down_in_the_record_is_refused(self):
        with self.assertRaises(mr.RouterError) as ctx:
            self.go("google", "gemini-2.0-flash")
        self.assertEqual(ctx.exception.exit_code, 2)
        text = str(ctx.exception)
        self.assertTrue(text.startswith("gemini-2.0-flash is retired"), text)
        self.assertIn("gemini-3.6-flash", text)
        self.assertIn("google deprecations record", text)

    def test_google_redirect_in_the_record_says_where_the_answer_comes_from(self):
        registry = {"models": [{"id": "gemini-3.5-flash", "status": "deprecated", "replacement_id": "gemini-3.6-flash"}]}
        r = self.go("google", "gemini-3.5-flash", registry=registry)
        joined = " ".join(r["warnings"])
        self.assertEqual((r["model"], r["basis"], r["replacement"]), ("gemini-3.5-flash", "offline", "gemini-3.6-flash"))
        self.assertIn("routes requests for it to gemini-3.6-flash", joined)
        self.assertIn("google deprecations record", joined)
        self.assertNotIn("shipped registry", joined)  # the stricter source wins; one warning, not two

    def test_google_future_shutdown_warns_with_its_date(self):
        r = self.go("google", "gemini-3.1-flash-lite")
        joined = " ".join(r["warnings"])
        self.assertIn("2027-05-07", joined)
        self.assertIn("gemini-3.5-flash-lite", joined)
        self.assertIn("google deprecations record", joined)
        self.assertNotIn("not in the shipped registry", joined)

    def test_a_list_timeout_takes_the_same_check(self):
        with self.assertRaises(mr.RouterError):
            self.go("google", "gemini-2.0-flash", env={}, fetch=GFetch(error=mr.FetchError("timeout", "timed out")))

    def test_the_stricter_source_wins_and_is_named(self):
        current = {"models": [{"id": "gemini-2.0-flash", "status": "current"}]}
        with self.assertRaises(mr.RouterError) as ctx:
            self.go("google", "gemini-2.0-flash", registry=current)
        self.assertIn("deprecations record", str(ctx.exception))
        retired = {"models": [{"id": "gemini-3.1-flash-lite", "status": "retired", "shutdown_date": "2026-06-01",
                               "replacement_id": "gemini-3.5-flash-lite"}]}
        with self.assertRaises(mr.RouterError) as ctx:
            self.go("google", "gemini-3.1-flash-lite", registry=retired)
        self.assertIn("shipped registry", str(ctx.exception))

    def test_a_model_neither_source_knows_is_named(self):
        r = self.go("google", "gemini-imaginary-9")
        self.assertTrue(any("not in the shipped registry or the hint book's google deprecations record" in w
                            for w in r["warnings"]), r["warnings"])

    def test_a_caller_can_say_the_record_does_not_apply(self):
        """SocialForge's Vertex runs: Vertex retires Gemini models on its own schedule."""
        r = self.go("google", "gemini-2.0-flash", record_applies=False)
        self.assertEqual((r["model"], r["basis"]), ("gemini-2.0-flash", "offline"))
        self.assertFalse(any("deprecations record" in w for w in r["warnings"]), r["warnings"])
        stale = copy.deepcopy(GHINTS)
        stale["deprecations"]["google"]["read_on"] = "2026-08-01"
        r = self.go("google", "gemini-3.6-flash", hints=stale, record_applies=False)
        self.assertEqual(r["warnings"], [f"gemini-3.6-flash is not in the shipped registry, so its lifecycle could "
                                         f"not be checked without the live list"])

    def test_cli_repro_from_the_installed_copy(self):
        """MODEL_ROUTER_OFFLINE=1 --requested gemini-2.0-flash exited 0 from an installed copy."""
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            hints, reg = Path(tmp, "hints.json"), Path(tmp, "registry.json")
            hints.write_text(json.dumps(GHINTS), encoding="utf-8")
            reg.write_text(json.dumps({"aliases": {"latest-vision-google": "gemini-3.6-flash"}, "models": []}),
                           encoding="utf-8")
            base = [sys.executable, str(SCRIPTS / "model_router.py"), "--hints", str(hints), "--registry", str(reg),
                    "--job", G_JOB, "--provider", "google", "--credential-name", G_CRED,
                    "--requested", "gemini-2.0-flash"]
            env = dict(os.environ, MODEL_ROUTER_OFFLINE="1")
            proc = subprocess.run(base, capture_output=True, text=True, timeout=60, env=env)
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            self.assertIn("gemini-3.6-flash", json.loads(proc.stdout)["error"])
            proc = subprocess.run(base + ["--ignore-deprecations-record"], capture_output=True, text=True,
                                  timeout=60, env=env)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["model"], "gemini-2.0-flash")

    def test_openai_past_shutdown_in_the_record_is_refused(self):
        with self.assertRaises(mr.RouterError) as ctx:
            self.go("openai", "o3", now=self.LATER, hints=HINTS)
        self.assertTrue(str(ctx.exception).startswith("o3 is retired"), str(ctx.exception))
        self.assertIn("gpt-5.6-sol", str(ctx.exception))

    def test_openai_future_shutdown_warns_and_a_fine_tune_follows_its_base(self):
        r = self.go("openai", "gpt-5.1", hints=HINTS)
        self.assertEqual(r["replacement"], "gpt-6-sol")
        self.assertIn("2027-04-01", " ".join(r["warnings"]))
        r = self.go("openai", "ft:gpt-4o-2024-08-06:acme-corp::def456", hints=HINTS)
        self.assertIn("2027-01-14", " ".join(r["warnings"]))

    def test_the_checker_refuses_a_retired_openai_model_offline(self):
        spec = importlib.util.spec_from_file_location("ai_visibility_checker", SCRIPTS / "ai-visibility-checker.py")
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        with tempfile.TemporaryDirectory() as home:
            old = {k: os.environ.get(k) for k in ("CLAUDE_MARKETING_HOME", "MODEL_ROUTER_OFFLINE")}
            os.environ.update({"CLAUDE_MARKETING_HOME": home, "MODEL_ROUTER_OFFLINE": "1"})
            try:
                with redirect_stderr(io.StringIO()), self.assertRaises(mr.RouterError) as ctx:
                    checker.route_openai("o3", OAI_KEY, fetch=OAIFetch(), now=self.LATER)
            finally:
                for k, v in old.items():
                    os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        self.assertIn("gpt-5.6-sol", str(ctx.exception))


class TestPageCap(unittest.TestCase):
    """A list with pages left at the cap is an error, never a short list (a short list makes a
    model look unlisted). 20 pages are read; a 21st means the list was cut."""

    @staticmethod
    def endless(pages: int, style: str):
        served = []

        def opener(req, timeout=None):
            served.append(req)
            n = len(served)
            more = n < pages
            if style == "anthropic":
                body = {"data": [{"id": f"claude-test-{n}", "lifecycle": "active"}], "has_more": more,
                        "last_id": f"claude-test-{n}"}
            else:
                body = {"models": [g_entry(f"gemini-test-{n}")]}
                if more:
                    body["nextPageToken"] = f"token-{n}"
            return Resp(json.dumps(body).encode())

        return opener, served

    def test_twenty_pages_are_read_and_a_twenty_first_is_refused(self):
        for style, fetch, key in (("anthropic", mr.fetch_anthropic, KEY), ("google", mr.fetch_google, G_KEY)):
            opener, served = self.endless(mr.MAX_PAGES, style)
            self.assertEqual(len(fetch(key, "2023-06-01", urlopen=opener)), mr.MAX_PAGES, style)
            opener, served = self.endless(mr.MAX_PAGES + 1, style)
            with self.assertRaises(mr.FetchError) as ctx:
                fetch(key, "2023-06-01", urlopen=opener)
            self.assertEqual(ctx.exception.kind, "schema", style)
            self.assertIn(f"more than {mr.MAX_PAGES} pages", ctx.exception.detail)

    def test_the_route_falls_back_offline_and_says_why(self):
        opener, _ = self.endless(mr.MAX_PAGES + 1, "google")
        with redirect_stderr(io.StringIO()):
            r = mr.route(G_JOB, GHINTS, provider="google", credential_name=G_CRED, api_key=G_KEY,
                         default_model="gemini-3.6-flash", fetch=lambda k, v: mr.fetch_google(k, v, urlopen=opener),
                         cache_path=None, now=NOW, env={})
        self.assertEqual((r["basis"], r["offline"]), ("offline", True))
        self.assertIn("pages", r["reason"])


class TestBackendReplacement(unittest.TestCase):
    """A registry entry can name a replacement per backend (replacement_by_backend). The router's
    google adapter calls the Gemini API, so offline it names the Gemini API's replacement unless the
    caller says the request goes elsewhere (backend="vertex"). Before 3.40.0 it named the single
    replacement_id, Vertex AI's veo-3.1-generate-001, which the Gemini API doesn't serve."""

    REGISTRY = {"models": [{"id": "veo-3.1-generate-preview", "status": "retired", "shutdown_date": "2026-10-22",
                            "replacement_id": "veo-3.1-generate-001",
                            "replacement_by_backend": {"gemini-api": "gemini-omni-1.1-flash",
                                                       "vertex": "veo-3.1-generate-001"}}]}

    def go(self, **kw):
        with redirect_stderr(io.StringIO()), self.assertRaises(mr.RouterError) as ctx:
            mr.route(G_JOB, GHINTS, provider="google", credential_name=G_CRED, api_key=G_KEY,
                     default_model="gemini-3.6-flash", requested="veo-3.1-generate-preview", fetch=GFetch(),
                     cache_path=None, now=NOW, env={"MODEL_ROUTER_OFFLINE": "1"}, registry=self.REGISTRY, **kw)
        return str(ctx.exception)

    def test_each_adapter_names_its_backend(self):
        self.assertEqual(mr.PROVIDER_BACKEND, {"anthropic": "anthropic", "openai": "openai", "google": "gemini-api"})

    def test_google_names_the_gemini_api_replacement(self):
        self.assertIn("Use gemini-omni-1.1-flash.", self.go())

    def test_a_vertex_run_names_the_vertex_replacement(self):
        self.assertIn("Use veo-3.1-generate-001.", self.go(record_applies=False, backend="vertex"))

    def test_the_helper(self):
        entry = self.REGISTRY["models"][0]
        self.assertEqual(mr.registry_replacement(entry, "vertex"), "veo-3.1-generate-001")
        self.assertEqual(mr.registry_replacement(entry, "gemini-api"), "gemini-omni-1.1-flash")
        self.assertEqual(mr.registry_replacement(entry, "openai"), "veo-3.1-generate-001")  # not listed: the default
        self.assertEqual(mr.registry_replacement({"replacement_id": "x"}, "vertex"), "x")

    def test_cli_backend(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            hints, reg = Path(tmp, "hints.json"), Path(tmp, "registry.json")
            hints.write_text(json.dumps(GHINTS), encoding="utf-8")
            reg.write_text(json.dumps({"aliases": {}, **self.REGISTRY}), encoding="utf-8")
            base = [sys.executable, str(SCRIPTS / "model_router.py"), "--hints", str(hints), "--registry", str(reg),
                    "--job", G_JOB, "--provider", "google", "--credential-name", G_CRED,
                    "--default-model", "gemini-3.6-flash", "--requested", "veo-3.1-generate-preview",
                    "--ignore-deprecations-record"]
            env = dict(os.environ, MODEL_ROUTER_OFFLINE="1")
            for extra, want in (([], "gemini-omni-1.1-flash"), (["--backend", "vertex"], "veo-3.1-generate-001")):
                proc = subprocess.run(base + extra, capture_output=True, text=True, timeout=60, env=env)
                self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
                self.assertIn(f"Use {want}.", json.loads(proc.stdout)["error"])


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
        self.assertIn(OAI_JOB, hints["jobs"])
        self.assertIn("openai", hints["deprecations"])

    def test_the_test_hint_book_is_valid(self):
        self.assertEqual(mr.validate_hints(HINTS), [])

    def test_a_rule_without_its_source_or_date_is_rejected(self):
        bad = copy.deepcopy(HINTS)
        del bad["jobs"][JOB]["read_on"]
        bad["jobs"]["test.fast"]["source"] = ""
        problems = "\n".join(mr.validate_hints(bad))
        self.assertIn(f"{JOB}: read_on", problems)
        self.assertIn("test.fast: source", problems)

    def test_family_rules_and_the_deprecations_record_are_checked(self):
        bad = copy.deepcopy(HINTS)
        bad["jobs"][OAI_JOB]["family"] = r"^gpt-\d+-sol$"
        bad["jobs"][OAI_JOB]["capabilities"] = ["pdf_input"]
        bad["jobs"]["test.fast"]["family"] = SOL
        bad["deprecations"]["openai"]["models"]["gpt-5.1"].pop("replacement")
        del bad["deprecations"]["openai"]["read_on"]
        problems = "\n".join(mr.validate_hints(bad))
        for expected in (f"{OAI_JOB}: family needs a (?P<version>", f"{OAI_JOB}: openai lists no capabilities",
                         "test.fast: give line or family, not both", "deprecations.openai: read_on missing",
                         "deprecations.openai.gpt-5.1: replacement missing"):
            self.assertIn(expected, problems)


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

    def test_route_openai_live(self):
        checker = self.load_checker()
        with tempfile.TemporaryDirectory() as home:
            old = {k: os.environ.get(k) for k in ("CLAUDE_MARKETING_HOME", "MODEL_ROUTER_OFFLINE")}
            os.environ["CLAUDE_MARKETING_HOME"] = home
            os.environ.pop("MODEL_ROUTER_OFFLINE", None)
            try:
                with redirect_stderr(io.StringIO()):
                    live = checker.route_openai(None, OAI_KEY, fetch=OAIFetch(), now=NOW)
                    kept = checker.route_openai("gpt-5.1", OAI_KEY, fetch=OAIFetch(), now=NOW)
            finally:
                for k, v in old.items():
                    os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        self.assertEqual((live["model"], live["provider"]), ("gpt-6.1-sol", "openai"))
        self.assertEqual((kept["model"], kept["basis"]), ("gpt-5.1", "requested"))

    def test_offline_the_checker_still_warns_about_a_deprecated_request(self):
        checker = self.load_checker()
        with tempfile.TemporaryDirectory() as home:
            old = {k: os.environ.get(k) for k in ("CLAUDE_MARKETING_HOME", "MODEL_ROUTER_OFFLINE")}
            os.environ["CLAUDE_MARKETING_HOME"] = home
            os.environ["MODEL_ROUTER_OFFLINE"] = "1"
            try:
                with redirect_stderr(io.StringIO()):
                    r = checker.route_anthropic("claude-sonnet-4-5-20250929", KEY, "2023-06-01", fetch=Fetch(), now=NOW)
            finally:
                for k, v in old.items():
                    os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        self.assertEqual(r["basis"], "offline")
        self.assertTrue(any("2026-11-30" in w for w in r["warnings"]), r["warnings"])

    def test_no_leg_resolves_a_model_name_outside_the_router(self):
        source = (SCRIPTS / "ai-visibility-checker.py").read_text(encoding="utf-8")
        self.assertNotIn("_negotiate_model(", source)
        self.assertIn("route_openai(", source)
        self.assertIn("route_anthropic(", source)


class TestPrivacyDocsTruth(unittest.TestCase):

    def test_privacy_names_the_list_call_and_its_limits(self):
        text = (REPO / "PRIVACY.md").read_text(encoding="utf-8")
        for needed in ("/v1/models", "MODEL_ROUTER_OFFLINE", f"once every {mr.TTL_DAYS} days",
                       "never the key", "model-router-cache.json", "generativelanguage.googleapis.com",
                       "x-goog-api-key"):
            self.assertIn(needed, text)

    def test_curator_examples_quote_the_routers_own_words(self):
        """docs/MODEL-CURATOR.md's warnings, regenerated from the real hint book and the fixtures.
        3.38.0's OpenAI example said "the router would choose gpt-6-luna": Luna is the page's
        recommendation, while the router's family pick is GPT-6.1 Sol."""
        doc = (REPO / "docs" / "MODEL-CURATOR.md").read_text(encoding="utf-8")
        hints = json.loads((SCRIPTS / "model_hints.json").read_text(encoding="utf-8"))
        cases = (("anthropic", JOB, CRED, KEY, Fetch(), "claude-sonnet-4-5-20250929"),
                 ("openai", OAI_JOB, OAI_CRED, OAI_KEY, OAIFetch(), "gpt-4o-2024-08-06"))
        for provider, job, cred, key, fetch, requested in cases:
            with redirect_stderr(io.StringIO()):
                r = mr.route(job, hints, provider=provider, credential_name=cred, api_key=key, default_model=None,
                             requested=requested, fetch=fetch, now=NOW, env={})
            self.assertEqual(len(r["warnings"]), 1, r["warnings"])
            self.assertIn(f"WARNING ({provider}): {r['warnings'][0]}", doc)


def committed_bytes(path: Path) -> bytes:
    """The file as git stores it: a checkout with core.autocrlf=true writes CRLF on disk while the
    committed blob stays LF, so two identical copies can differ only in that setting."""
    return path.read_bytes().replace(b"\r\n", b"\n")


class TestParity(unittest.TestCase):
    """One file, byte-identical wherever it is copied (the hero-sync pattern)."""

    def test_sibling_copies_are_identical(self):
        mine = committed_bytes(SCRIPTS / "model_router.py")
        copies = [p for p in (REPO.parent / name / "scripts" / "model_router.py"
                              for name in ("contentforge", "socialforge", "CutForge")) if p.exists()]
        for p in copies:
            self.assertEqual(committed_bytes(p), mine, f"{p} differs from DMP's model_router.py")
        if not copies:
            self.skipTest("no sibling copy checked out yet")

    def test_line_endings_from_a_checkout_are_not_a_difference(self):
        with tempfile.TemporaryDirectory() as tmp:
            lf, crlf, edited = Path(tmp, "lf.py"), Path(tmp, "crlf.py"), Path(tmp, "edited.py")
            lf.write_bytes(b"a = 1\nb = 2\n")
            crlf.write_bytes(b"a = 1\r\nb = 2\r\n")
            edited.write_bytes(b"a = 1\nb = 3\n")
            self.assertEqual(committed_bytes(crlf), committed_bytes(lf))
            self.assertNotEqual(committed_bytes(edited), committed_bytes(lf))


class TestNoKeyFollowsARedirect(unittest.TestCase):
    """urllib's redirect handler copies every ordinary header to the host a 3xx names. The router's
    key headers are unredirected, so a redirect from a model-list endpoint carries no key. The stub
    answers the first request, then builds the follow-up exactly as urllib would."""

    EVIL = "https://evil.example/v1/models"

    def follow_ups(self, fetch, page):
        sent, follows = [], []

        def opener(req, timeout=None):
            sent.append(req)
            follows.append(urllib.request.HTTPRedirectHandler().redirect_request(
                req, None, 302, "Found", {}, self.EVIL))
            return Resp(json.dumps(page).encode())
        fetch(opener)
        return sent, follows

    def test_each_provider_key_stays_off_the_redirect(self):
        cases = (
            ("x-api-key", KEY, lambda o: mr.fetch_anthropic(KEY, "2023-06-01", urlopen=o),
             {"data": [], "has_more": False}),
            ("Authorization", f"Bearer {OAI_KEY}", lambda o: mr.fetch_openai(OAI_KEY, urlopen=o),
             {"data": [], "has_more": False}),
            ("x-goog-api-key", G_KEY, lambda o: mr.fetch_google(G_KEY, urlopen=o), {"models": []}),
        )
        for header, value, fetch, page in cases:
            with self.subTest(header=header):
                sent, follows = self.follow_ups(fetch, page)
                self.assertEqual(sent[0].get_header(header.capitalize()), value)
                followed = {k.lower(): v for k, v in follows[0].header_items()}
                self.assertNotIn(header.lower(), followed)
                self.assertNotIn(value, json.dumps(followed))


if __name__ == "__main__":
    unittest.main()
