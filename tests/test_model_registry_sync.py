"""Model-registry reconciliation test.

DMP's scripts/model_registry.json is the canonical superset of the Neelverse
Marketing Suite registry: it carries every entry ContentForge uses PLUS a small,
documented set of marketing-suite-specific model families. This test enforces:

  1. No DRIFT in shared entries — every model/alias id present in BOTH registries
     must have byte-identical content, and the shared top-level metadata
     (schema_version, tiers, param_compatibility_notes, stewardship_policy)
     must match. This is what sync_model_registry.sh keeps true.
  2. DMP's extra entries are exactly the DOCUMENTED deviation allowlist below,
     so a new, undocumented DMP-only id (silent drift) fails the build.

If the ContentForge sibling repo is not checked out next to this repo, the
cross-repo assertions are skipped (the deviation allowlist is still checked).
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

DMP_REGISTRY = Path(__file__).resolve().parent.parent / "scripts" / "model_registry.json"
CF_REGISTRY = (Path(__file__).resolve().parent.parent.parent
               / "contentforge" / "scripts" / "model_registry.json")

# Documented DMP-only additions (marketing-suite-specific model families). Two
# of these (deepseek-chat, gpt-5.2) plus the evolink aliases are referenced by
# tests/test_resolve_model.py, so per the reconciliation rule they are kept and
# reported as intentional deviations rather than deleted to match CF.
DMP_ONLY_MODELS = {
    "deepseek-chat", "deepseek-reasoner", "deepseek-v4-flash", "deepseek-v4-pro",
    "doubao-seed-2.0-lite", "doubao-seed-2.0-pro", "evolink-auto",
    "gpt-5.1", "gpt-5.2", "minimax-m2.5", "minimax-m3",
}
DMP_ONLY_ALIASES = {
    "latest-balanced-evolink", "latest-fast-evolink", "latest-text-evolink",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class TestDmpRegistryShape(unittest.TestCase):
    def setUp(self):
        self.dmp = _load(DMP_REGISTRY)
        self.dmp_models = {m["id"]: m for m in self.dmp["models"]}

    def test_registry_parses_and_has_required_keys(self):
        for key in ("models", "aliases", "schema_version", "last_updated", "tiers"):
            self.assertIn(key, self.dmp)

    def test_no_duplicate_model_ids(self):
        ids = [m["id"] for m in self.dmp["models"]]
        self.assertEqual(len(ids), len(set(ids)), "duplicate model ids in DMP registry")

    def test_every_alias_target_exists(self):
        for alias, target in self.dmp["aliases"].items():
            self.assertIn(target, self.dmp_models,
                          f"alias {alias!r} points at missing model {target!r}")

    def test_no_alias_targets_a_retired_model(self):
        """A 'latest-*' alias resolving to a shut-down model sends live calls to
        a dead endpoint — e.g. gemini-2.5-flash-image was still 'supported' two
        days after Google shut it down (found 2026-10-04)."""
        bad = {a: t for a, t in self.dmp["aliases"].items()
               if self.dmp_models.get(t, {}).get("status") == "retired"}
        self.assertEqual(bad, {}, f"aliases resolve to retired models: {bad}")

    def test_every_replacement_id_exists(self):
        bad = [m["id"] for m in self.dmp["models"]
               if m.get("replacement_id") and m["replacement_id"] not in self.dmp_models]
        self.assertEqual(bad, [], f"fall-forward targets missing from registry: {bad}")


SIBLING_REGISTRIES = {
    name: Path(__file__).resolve().parent.parent.parent / name / "scripts" / "model_registry.json"
    for name in ("contentforge", "socialforge")
}


class TestSiblingAliasClosure(unittest.TestCase):
    """sync_model_registry.sh once copied refreshed alias VALUES into the subset
    sibling registries without the entries they name — every new latest-* alias
    dangled in ContentForge and SocialForge (found 2026-10-04). The sync now
    pulls the closure in; this pins that every sibling alias and fall-forward
    resolves locally."""

    def test_sibling_aliases_and_replacements_resolve(self):
        checked = 0
        for name, path in SIBLING_REGISTRIES.items():
            if not path.exists():
                continue
            checked += 1
            reg = _load(path)
            ids = {m["id"]: m for m in reg["models"]}
            dangling = {a: t for a, t in reg["aliases"].items() if t not in ids}
            retired = {a: t for a, t in reg["aliases"].items()
                       if t in ids and ids[t].get("status") == "retired"}
            bad_rep = [m["id"] for m in reg["models"]
                       if m.get("replacement_id") and m["replacement_id"] not in ids]
            with self.subTest(sibling=name):
                self.assertEqual(dangling, {}, f"{name}: dangling aliases {dangling}")
                self.assertEqual(retired, {}, f"{name}: aliases to retired models {retired}")
                self.assertEqual(bad_rep, [], f"{name}: missing fall-forward targets {bad_rep}")
        if not checked:
            self.skipTest("sibling repos not checked out")


@unittest.skipUnless(CF_REGISTRY.exists(),
                     "ContentForge sibling repo not checked out; cross-repo drift check skipped")
class TestSharedEntriesNoDrift(unittest.TestCase):
    def setUp(self):
        self.dmp = _load(DMP_REGISTRY)
        self.cf = _load(CF_REGISTRY)
        self.dmp_models = {m["id"]: m for m in self.dmp["models"]}
        self.cf_models = {m["id"]: m for m in self.cf["models"]}

    def test_shared_models_are_identical(self):
        shared = set(self.dmp_models) & set(self.cf_models)
        drifted = [i for i in shared if self.dmp_models[i] != self.cf_models[i]]
        self.assertEqual(drifted, [],
                         f"shared model entries drifted between DMP and CF: {drifted}. "
                         "Run sync_model_registry.sh.")

    def test_shared_aliases_are_identical(self):
        shared = set(self.dmp["aliases"]) & set(self.cf["aliases"])
        drifted = [k for k in shared if self.dmp["aliases"][k] != self.cf["aliases"][k]]
        self.assertEqual(drifted, [], f"shared aliases drifted: {drifted}")

    def test_shared_metadata_matches(self):
        for key in ("schema_version", "tiers", "param_compatibility_notes",
                    "stewardship_policy"):
            self.assertEqual(self.dmp.get(key), self.cf.get(key),
                             f"top-level {key!r} drifted between DMP and CF registries")

    def test_dmp_only_models_are_the_documented_allowlist(self):
        extra = set(self.dmp_models) - set(self.cf_models)
        self.assertEqual(
            extra, DMP_ONLY_MODELS,
            f"Undocumented DMP-only model ids (update the allowlist or remove): "
            f"{sorted(extra - DMP_ONLY_MODELS)}; "
            f"missing expected deviations: {sorted(DMP_ONLY_MODELS - extra)}")

    def test_dmp_only_aliases_are_the_documented_allowlist(self):
        extra = set(self.dmp["aliases"]) - set(self.cf["aliases"])
        self.assertEqual(extra, DMP_ONLY_ALIASES,
                         f"Undocumented DMP-only aliases: {sorted(extra - DMP_ONLY_ALIASES)}")

    def test_cf_has_no_entries_missing_from_dmp(self):
        # DMP must be a strict superset — CF should never carry a model DMP lacks.
        missing = set(self.cf_models) - set(self.dmp_models)
        self.assertEqual(missing, set(),
                         f"CF has models DMP is missing (DMP must be the superset): {sorted(missing)}")


if __name__ == "__main__":
    unittest.main()
