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
  3. Each sibling IS the mirror (canonical minus DMP_ONLY, its own $comment kept),
     and `sync_model_registry.sh --check` reports drift in both directions: entries
     a sibling lacks and entries upstream dropped. The surgical by-id sync it
     replaced (3.37.2) reported neither, so Worker B finished the 3.36.2 sync by hand.

If the ContentForge sibling repo is not checked out next to this repo, the
cross-repo assertions are skipped (the deviation allowlist is still checked).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import registry_mirror  # noqa: E402
from registry_mirror import DMP_ONLY_ALIASES, DMP_ONLY_MODELS  # noqa: E402

DMP_REGISTRY = Path(__file__).resolve().parent.parent / "scripts" / "model_registry.json"
CF_REGISTRY = (Path(__file__).resolve().parent.parent.parent
               / "contentforge" / "scripts" / "model_registry.json")

# The documented DMP-only families (DMP_ONLY_MODELS / DMP_ONLY_ALIASES) live in
# scripts/registry_mirror.py, the one place the mirror and these tests read them.


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
    name: Path(__file__).resolve().parent.parent.parent / folder / rel
    for name, folder, rel in (("contentforge", "contentforge", "scripts/model_registry.json"),
                              ("socialforge", "socialforge", "scripts/model_registry.json"),
                              ("cutforge", "CutForge", "engine/template/tools/model_registry.json"))
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


class TestSiblingsAreTheMirror(unittest.TestCase):
    """Checked-out siblings must equal the mirror exactly (skipped when none is checked out)."""

    def test_each_checked_out_sibling(self):
        canon, checked = _load(DMP_REGISTRY), 0
        for name, path in SIBLING_REGISTRIES.items():
            if not path.exists():
                continue
            checked += 1
            sibling = _load(path)
            with self.subTest(sibling=name):
                found = registry_mirror.differences(registry_mirror.mirror(canon, sibling), sibling)
                self.assertEqual(found, [], f"{name}: run sh scripts/sync_model_registry.sh")
        if not checked:
            self.skipTest("sibling repos not checked out")


class TestRegistryMirror(unittest.TestCase):
    """The mirror against throwaway sibling folders."""

    def setUp(self):
        self.canon = _load(DMP_REGISTRY)
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        for name in registry_mirror.SIBLINGS:
            self.write(name, registry_mirror.mirror(self.canon, {"$comment": f"{name} copy"}))

    def path(self, name: str) -> Path:
        p = self.tmp / name / registry_mirror.SIBLINGS[name]
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def write(self, name: str, doc: dict) -> None:
        self.path(name).write_text(registry_mirror.render(doc), encoding="utf-8", newline="")

    def run_mirror(self, *args: str) -> tuple[int, str]:
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = registry_mirror.main([*args, "--parent", str(self.tmp)])
        return code, out.getvalue() + err.getvalue()

    def test_mirror_drops_dmp_only_and_keeps_the_sibling_comment(self):
        m = registry_mirror.mirror(self.canon, {"$comment": "ContentForge copy"})
        self.assertEqual(m["$comment"], "ContentForge copy")
        self.assertEqual([x["id"] for x in m["models"]],
                         [x["id"] for x in self.canon["models"] if x["id"] not in DMP_ONLY_MODELS])
        self.assertFalse(set(m["aliases"]) & DMP_ONLY_ALIASES)
        self.assertEqual(m["tiers"], self.canon["tiers"])

    def test_check_reports_both_directions_and_writes_nothing(self):
        # What the by-id sync could not see: an unreferenced canonical entry and alias key
        # the sibling lacks, and an entry and alias key upstream has dropped.
        doc = registry_mirror.mirror(self.canon, {"$comment": "x"})
        doc["models"] = [m for m in doc["models"] if m["id"] != "scribe_v1"]
        doc["models"].append({"id": "dropped-upstream", "vendor": "x", "family": "x",
                              "display_name": "x", "status": "current"})
        del doc["aliases"]["latest-stt-sarvam"]
        doc["aliases"]["latest-dropped-upstream"] = "dropped-upstream"
        self.write("contentforge", doc)
        before = self.path("contentforge").read_text(encoding="utf-8")
        code, out = self.run_mirror("--check")
        self.assertEqual(code, 1, out)
        for expected in ("DRIFT contentforge", "missing models: scribe_v1",
                         "extra models (dropped or DMP-only upstream): dropped-upstream",
                         "missing aliases: latest-stt-sarvam",
                         "extra aliases (dropped or DMP-only upstream): latest-dropped-upstream",
                         "OK    socialforge"):
            self.assertIn(expected, out)
        self.assertEqual(self.path("contentforge").read_text(encoding="utf-8"), before)

    def test_sync_writes_the_mirror_and_is_idempotent(self):
        doc = registry_mirror.mirror(self.canon, {"$comment": "keep me"})
        doc["models"] = doc["models"][:5]
        doc["tiers"] = {}
        self.write("socialforge", doc)
        code, out = self.run_mirror()
        self.assertEqual(code, 0, out)
        self.assertIn("SYNC  socialforge", out)
        want = registry_mirror.render(registry_mirror.mirror(self.canon, {"$comment": "keep me"}))
        self.assertEqual(self.path("socialforge").read_text(encoding="utf-8"), want)
        code, out = self.run_mirror("--check")
        self.assertEqual(code, 0, out)
        self.assertIn("OK    socialforge", out)

    def test_an_alias_to_a_dmp_only_model_cannot_be_mirrored(self):
        canon = dict(self.canon, aliases=dict(self.canon["aliases"], **{"latest-x": "gpt-5.2"}))
        with self.assertRaisesRegex(ValueError, "alias latest-x -> gpt-5.2"):
            registry_mirror.mirror(canon)

    def test_cutforge_copy_is_created_by_its_first_sync(self):
        shutil.rmtree(self.tmp / "cutforge")
        tools = self.tmp / "CutForge" / "engine" / "template" / "tools"
        tools.mkdir(parents=True)
        code, out = self.run_mirror("--check")
        self.assertEqual(code, 1, out)
        self.assertIn("DRIFT cutforge: no registry copy yet", out)
        self.assertFalse((tools / "model_registry.json").exists())
        code, out = self.run_mirror()
        self.assertEqual(code, 0, out)
        self.assertIn("SYNC  cutforge created", out)
        self.assertEqual((tools / "model_registry.json").read_text(encoding="utf-8"),
                         registry_mirror.render(registry_mirror.mirror(self.canon)))
        code, out = self.run_mirror("--check")
        self.assertEqual(code, 0, out)
        self.assertIn("OK    cutforge", out)

    def test_a_cutforge_checkout_without_the_template_folder_is_skipped(self):
        shutil.rmtree(self.tmp / "cutforge")
        (self.tmp / "CutForge").mkdir()
        code, out = self.run_mirror("--check")
        self.assertEqual(code, 0, out)
        self.assertIn("SKIP  cutforge (no registry at", out)

    def test_missing_sibling_is_skipped(self):
        shutil.rmtree(self.tmp / "socialforge")
        code, out = self.run_mirror("--check")
        self.assertEqual(code, 0, out)
        self.assertIn("SKIP  socialforge", out)

    @unittest.skipUnless(shutil.which("sh"), "no POSIX sh on PATH")
    def test_shell_wrapper_passes_its_arguments(self):
        script = (SCRIPTS / "sync_model_registry.sh").as_posix()
        ok = subprocess.run(["sh", script, "--check", "--parent", str(self.tmp)],
                            capture_output=True, text=True, timeout=60)
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertIn("OK    contentforge", ok.stdout)
        bad = subprocess.run(["sh", script, "--bogus"], capture_output=True, text=True, timeout=60)
        self.assertEqual(bad.returncode, 2, bad.stdout + bad.stderr)


if __name__ == "__main__":
    unittest.main()
