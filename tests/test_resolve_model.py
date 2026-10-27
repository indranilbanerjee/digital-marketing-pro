"""Model curator (scripts/resolve_model.py) — alias resolution, deprecation check, registry age."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import resolve_model  # noqa: E402  # pyright: ignore[reportMissingImports]  # type: ignore[import-not-found]


class TestAliasResolution(unittest.TestCase):
    def test_resolves_balanced_anthropic(self):
        result = resolve_model.resolve("latest-balanced-anthropic")
        self.assertTrue(result.startswith("claude-sonnet"),
                        f"expected a claude-sonnet variant, got {result}")

    def test_resolves_text_anthropic(self):
        result = resolve_model.resolve("latest-text-anthropic")
        self.assertTrue(result.startswith("claude-opus"),
                        f"expected a claude-opus variant, got {result}")

    def test_resolves_fast_anthropic(self):
        result = resolve_model.resolve("latest-fast-anthropic")
        self.assertTrue(result.startswith("claude-haiku"),
                        f"expected a claude-haiku variant, got {result}")

    def test_resolves_text_openai(self):
        result = resolve_model.resolve("latest-text-openai")
        self.assertTrue(result.startswith("gpt-"),
                        f"expected a gpt-* variant, got {result}")

    def test_resolves_text_google(self):
        result = resolve_model.resolve("latest-text-google")
        self.assertTrue(result.startswith("gemini-"),
                        f"expected a gemini-* variant, got {result}")

    def test_exact_id_passes_through(self):
        result = resolve_model.resolve("claude-opus-4-7")
        self.assertEqual(result, "claude-opus-4-7")

    def test_unknown_alias_raises(self):
        with self.assertRaises(KeyError):
            resolve_model.resolve("latest-imaginary-vendor")


class TestDeprecationCheck(unittest.TestCase):
    # Fixtures come from the live registry, so a refresh never strands them (the old
    # hard-coded gemini-2.5-flash stopped being deprecated on 2026-10-27).
    @classmethod
    def setUpClass(cls):
        models = resolve_model.get_registry()["models"]
        cls.DEPRECATED_FIXTURE = next(m["id"] for m in models
                                      if m.get("status") == "deprecated" and m.get("replacement_id"))
        cls.RETIRED_FIXTURE = next(m["id"] for m in models
                                   if m.get("status") == "retired" and m.get("replacement_id"))
        cls.CURRENT_FIXTURE = resolve_model.get_registry()["aliases"]["latest-text-anthropic"]

    def test_deprecated_returns_replacement(self):
        result = resolve_model.resolve(self.DEPRECATED_FIXTURE)
        self.assertNotEqual(result, self.DEPRECATED_FIXTURE,
                            "deprecated id should fall forward to replacement")

    def test_deprecated_with_allow_flag(self):
        result = resolve_model.resolve(self.DEPRECATED_FIXTURE, allow_deprecated=True)
        self.assertEqual(result, self.DEPRECATED_FIXTURE,
                         "allow_deprecated=True should return the deprecated id as-is")

    def test_check_returns_status(self):
        status, replacement = resolve_model.check(self.DEPRECATED_FIXTURE)
        self.assertEqual(status, "deprecated")
        self.assertIsNotNone(replacement)

    def test_check_current(self):
        status, _ = resolve_model.check(self.CURRENT_FIXTURE)
        self.assertEqual(status, "current")

    def test_check_unknown(self):
        status, replacement = resolve_model.check("claude-fake-9000")
        self.assertEqual(status, "unknown")
        self.assertIsNone(replacement)

    def test_retired_falls_forward_unconditionally(self):
        # Retired models no longer respond at the API — resolver MUST rewrite
        # them regardless of allow_deprecated flag.
        result_default = resolve_model.resolve(self.RETIRED_FIXTURE)
        result_allow = resolve_model.resolve(self.RETIRED_FIXTURE, allow_deprecated=True)
        self.assertNotEqual(result_default, self.RETIRED_FIXTURE)
        self.assertNotEqual(result_allow, self.RETIRED_FIXTURE,
                            "retired models must fall forward even with allow_deprecated=True")


class TestRegistryAge(unittest.TestCase):
    def test_registry_age_is_int(self):
        age = resolve_model.registry_age_days()
        self.assertIsInstance(age, int, "registry_age_days must return an int")
        self.assertGreaterEqual(age, 0, "registry age cannot be negative")

    def test_get_registry_returns_dict_with_models(self):
        reg = resolve_model.get_registry()
        self.assertIn("models", reg)
        self.assertIsInstance(reg["models"], list)
        self.assertGreater(len(reg["models"]), 0)

    def test_aliases_block_present(self):
        reg = resolve_model.get_registry()
        self.assertIn("aliases", reg)
        self.assertGreater(len(reg["aliases"]), 0)


class TestEvolinkAliasResolution(unittest.TestCase):
    def test_resolves_text_evolink(self):
        result = resolve_model.resolve("latest-text-evolink")
        self.assertTrue(result.startswith("gpt-"),
                        f"expected a gpt-* variant, got {result}")

    def test_resolves_balanced_evolink(self):
        result = resolve_model.resolve("latest-balanced-evolink")
        self.assertEqual(result, "deepseek-chat")
        balanced_ids = {
            m["id"] for m in resolve_model.list_models(vendor="evolink", tier="balanced")
        }
        self.assertIn(result, balanced_ids)

    def test_resolves_fast_evolink(self):
        result = resolve_model.resolve("latest-fast-evolink")
        self.assertTrue(result.startswith("deepseek"),
                        f"expected a deepseek variant, got {result}")

    def test_evolink_check_current(self):
        status, _ = resolve_model.check("gpt-5.2")
        self.assertEqual(status, "current")

    def test_evolink_vendor_filter(self):
        models = resolve_model.list_models(vendor="evolink")
        self.assertGreater(len(models), 0,
                           "expected at least one evolink model in registry")
        for m in models:
            self.assertEqual(m["vendor"], "evolink")


class TestListFilter(unittest.TestCase):
    def test_filter_by_vendor(self):
        models = resolve_model.list_models(vendor="anthropic")
        for m in models:
            self.assertEqual(m["vendor"], "anthropic")
        self.assertGreater(len(models), 0)

    def test_filter_by_status(self):
        current = resolve_model.list_models(status="current")
        deprecated = resolve_model.list_models(status="deprecated")
        self.assertGreater(len(current), 0)
        self.assertGreater(len(deprecated), 0)
        for m in current:
            self.assertEqual(m["status"], "current")
        for m in deprecated:
            self.assertEqual(m["status"], "deprecated")


class TestExecutionLadder(unittest.TestCase):
    """resolve_for_execution never returns a bare id — provenance travels with
    every resolution, and unknown input refuses instead of guessing."""

    def test_known_alias_carries_provenance(self):
        payload, code = resolve_model.resolve_for_execution("latest-balanced-anthropic")
        self.assertEqual(code, 0)
        self.assertEqual(payload["basis"], "shipped-registry")
        self.assertIn("registry_age_days", payload)
        self.assertIn("registry_last_updated", payload)
        self.assertTrue(payload["model_id"].startswith("claude-"))

    def test_unknown_input_refuses_with_ladder(self):
        payload, code = resolve_model.resolve_for_execution("latest-imaginary-vendor")
        self.assertEqual(code, 3)
        self.assertEqual(payload["status"], "unresolved")
        self.assertIn("Do NOT guess", payload["action_required"])
        self.assertNotIn("model_id", payload)

    def test_aged_registry_attaches_warning(self):
        from unittest import mock
        with mock.patch.object(resolve_model, "registry_age_days", return_value=45):
            payload, code = resolve_model.resolve_for_execution("latest-balanced-anthropic")
        self.assertEqual(code, 0)
        self.assertIn("45 days old", payload["warning"])
        self.assertIn("Live-verify", payload["warning"])

    def test_fresh_registry_has_no_warning(self):
        from unittest import mock
        with mock.patch.object(resolve_model, "registry_age_days", return_value=2):
            payload, _ = resolve_model.resolve_for_execution("latest-balanced-anthropic")
        self.assertNotIn("warning", payload)

    def test_undated_registry_warns(self):
        from unittest import mock
        with mock.patch.object(resolve_model, "registry_age_days", return_value=None):
            payload, _ = resolve_model.resolve_for_execution("latest-balanced-anthropic")
        self.assertIn("undated", payload["warning"])


if __name__ == "__main__":
    unittest.main()
