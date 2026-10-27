"""Brand names, user-supplied paths, profile encodings and UTF-8 output.

Found by an outside read of the 3.39.1 scripts (all planted before the fix):
  * `setup.py --create-brand` replaced an existing profile.json with a blank one (exit 0), and the
    slugifier dropped every non-ASCII letter, so two Devanagari or CJK names both became "brand"
    and the second wiped the first. A brand called "Nul" ended in a traceback.
  * A brand name outside Windows-1252 crashed dm-status and setup with UnicodeEncodeError where
    stdout is a pipe (Claude Code's Bash tool, Cowork); PYTHONUTF8=1 on the owner's machine hid it.
  * campaign-tracker built file names from names inside --data and from --id, so
    "../../../../x" wrote a file outside the brand folder. The same hole was in nine more scripts,
    one of them a delete (crm-sync log-synced).
  * A profile.json saved as UTF-16 (PowerShell 5.1's default) or Windows-1252 crashed six scripts;
    a JSON-valid profile with "industry": "saas" ended in AttributeError.
  * SECURITY.md named 3.17.x as the supported line.
Subprocess runs use a temporary HOME and CLAUDE_MARKETING_HOME, PYTHONUTF8 removed and
PYTHONIOENCODING=cp1252, which is what a Windows pipe gives a script on any OS.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _common  # noqa: E402

DEVANAGARI = "भारत चाय"
HAS_NLTK = importlib.util.find_spec("nltk") is not None  # brand-voice-scorer imports it at load
CJK = "北京茶庭"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Sandbox(unittest.TestCase):
    """A temporary HOME and workspace for every subprocess, so nothing touches the real one."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "home"
        self.ws = self.home / ".claude-marketing"
        self.brands = self.ws / "brands"
        self.home.mkdir()
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("PYTHONUTF8", "PYTHONIOENCODING", "CLAUDE_PLUGIN_DATA", "PLUGIN_DATA",
                                 "DIGITAL_MARKETING_PRO_PUBLISH_DIR")}
        self.env.update(HOME=str(self.home), USERPROFILE=str(self.home), CLAUDE_MARKETING_HOME=str(self.ws),
                        PYTHONIOENCODING="cp1252")
        patcher = mock.patch.dict(os.environ, {"CLAUDE_MARKETING_HOME": str(self.ws)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_script(self, script: str, *args: str) -> tuple[int, str]:
        proc = subprocess.run([sys.executable, str(SCRIPTS / script), *args], capture_output=True,
                              timeout=120, env=self.env, cwd=str(self.tmp))
        return proc.returncode, (proc.stdout + proc.stderr).decode("utf-8", errors="replace")

    def create(self, name: str, *extra: str) -> tuple[int, str]:
        return self.run_script("setup.py", "--create-brand", name, *extra)

    def profile(self, slug: str) -> dict:
        return json.loads((self.brands / slug / "profile.json").read_text(encoding="utf-8"))

    def files_outside(self, inside: Path) -> list[str]:
        return sorted(str(p.relative_to(self.tmp)) for p in self.tmp.rglob("*")
                      if p.is_file() and inside not in p.parents)


class TestSlug(unittest.TestCase):

    def test_ascii_names_keep_their_old_slug(self):
        for name in ("Acme", "Acme Corp!", "  spaced  out ", "", "a--b__c", "x" * 80, "Q4 / 2026"):
            self.assertEqual(_common.slugify_brand(name), _common.legacy_slug(name), name)

    def test_accents_fold_and_other_scripts_get_a_stable_tag(self):
        self.assertEqual(_common.slugify_brand("Café"), "cafe")
        self.assertEqual(_common.slugify_brand("ñandú"), "nandu")
        self.assertRegex(_common.slugify_brand(DEVANAGARI), r"^brand-[0-9a-f]{6}$")
        self.assertRegex(_common.slugify_brand("भारत Foods"), r"^foods-[0-9a-f]{6}$")
        self.assertNotEqual(_common.slugify_brand(DEVANAGARI), _common.slugify_brand(CJK))
        self.assertEqual(_common.slugify_brand(DEVANAGARI), _common.slugify_brand(DEVANAGARI))
        # NFC and NFD spellings of the same name are the same brand
        self.assertEqual(_common.slugify_brand("Café भारत"), _common.slugify_brand("Café भारत"))
        self.assertEqual(_common.slugify_brand("Acme — Pro"), "acme-pro")  # punctuation adds no tag

    def test_windows_device_names(self):
        for name in ("Nul", "CON", "com1", "LPT9", "aux"):
            self.assertEqual(_common.slugify_brand(name), name.lower() + "-brand")

    def test_a_brand_saved_under_its_old_slug_is_still_found(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"CLAUDE_MARKETING_HOME": tmp}):
            old = Path(tmp, "brands", "caf")
            old.mkdir(parents=True)
            (old / "profile.json").write_text(json.dumps({"brand_name": "Café"}), encoding="utf-8")
            self.assertEqual(_common.brand_dir("Café"), old)
            (old / "profile.json").write_text(json.dumps({"brand_name": "Caf"}), encoding="utf-8")
            self.assertEqual(_common.brand_dir("Café"), Path(tmp, "brands", "cafe"))  # someone else's folder


class TestCreateBrand(Sandbox):

    def test_an_existing_brand_is_not_overwritten(self):
        self.assertEqual(self.create("Acme")[0], 0)
        p = self.profile("acme")
        p["identity"]["tagline"] = "HAND-EDITED TAGLINE"
        (self.brands / "acme" / "profile.json").write_text(json.dumps(p), encoding="utf-8")
        code, out = self.create("Acme")
        self.assertEqual(code, 2, out)
        self.assertIn("BRAND_EXISTS", out)
        self.assertEqual(self.profile("acme")["identity"]["tagline"], "HAND-EDITED TAGLINE")
        code, out = self.create("Acme", "--force")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.profile("acme")["identity"]["tagline"], "")

    def test_two_non_latin_names_get_two_folders(self):
        for name in (DEVANAGARI, CJK):
            code, out = self.create(name)
            self.assertEqual(code, 0, out)
            self.assertNotIn("Traceback", out)
        folders = sorted(p.name for p in self.brands.iterdir() if p.is_dir() and not p.name.startswith("_"))
        self.assertEqual(len(folders), 2, folders)
        self.assertEqual(sorted(self.profile(f)["brand_name"] for f in folders), sorted([DEVANAGARI, CJK]))
        self.assertTrue(all(f.isascii() for f in folders), folders)

    def test_a_slug_owned_by_another_brand_is_refused_even_with_force(self):
        self.create("Acme")
        code, out = self.create("Other Co", "--slug", "acme", "--force")
        self.assertEqual(code, 2, out)
        self.assertEqual(self.profile("acme")["brand_name"], "Acme")

    def test_device_names(self):
        code, out = self.create("Nul")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.profile("nul-brand")["brand_name"], "Nul")
        code, out = self.create("Anything", "--slug", "con")
        self.assertEqual(code, 2, out)
        self.assertNotIn("Traceback", out)


class TestUtf8Output(Sandbox):

    def test_non_latin_brand_names_print(self):
        code, out = self.create("भारत Foods")
        self.assertEqual(code, 0, out)
        self.assertIn("भारत Foods", out)
        slug = _common.slugify_brand("भारत Foods")
        for script, args in (("dm-status.py", ["--brand", slug]), ("setup.py", ["--list-brands"]),
                             ("setup.py", ["--check-brand"]), ("setup.py", ["--summary"])):
            code, out = self.run_script(script, *args)
            self.assertEqual(code, 0, f"{script} {args}: {out}")
            self.assertNotIn("UnicodeEncodeError", out)
            self.assertIn("भारत Foods", out, f"{script} {args}")
        code, out = self.run_script("language-router.py", "--action", "detect", "--text", "नमस्ते दुनिया, यह एक परीक्षण है")
        self.assertEqual(code, 0, out)
        self.assertNotIn("UnicodeEncodeError", out)
        # The same crash in three more scripts, from text echoed out of an argument
        code, out = self.run_script("checkpoint-manager.py", "init", "--brand", slug, "--workflow", "campaign-plan",
                                    "--topic", "भारत 🚀 लॉन्च")
        self.assertEqual(code, 0, out)
        self.assertNotIn("UnicodeEncodeError", out)
        parent = self.tmp / "फ़ोल्डर"
        parent.mkdir()
        code, out = self.run_script("registry_mirror.py", "--check", "--parent", str(parent))
        self.assertNotIn("UnicodeEncodeError", out)
        self.assertIn("फ़ोल्डर", out)

    def test_every_script_writes_utf8(self):
        # _common reconfigures stdout and stderr when imported; a script that doesn't import it
        # does the same itself. model_router.py prints ASCII-only JSON and is byte-pinned in a
        # sibling plugin, so it is the one exemption.
        missing = []
        for path in sorted(SCRIPTS.glob("*.py")):
            text = path.read_text(encoding="utf-8-sig")
            if path.name in ("_common.py", "model_router.py"):
                continue
            imports_common = re.search(r"^\s*(import _common|from _common import)", text, re.M)
            if not imports_common and 'reconfigure(encoding="utf-8"' not in text:
                missing.append(path.name)
        self.assertEqual(missing, [])
        self.assertIn("\nensure_utf8_stdout()\n", (SCRIPTS / "_common.py").read_text(encoding="utf-8"))
        router = (SCRIPTS / "model_router.py").read_text(encoding="utf-8")
        self.assertNotIn("ensure_ascii=False", router)


class TestPathContainment(Sandbox):

    def setUp(self):
        super().setUp()
        self.assertEqual(self.create("Acme")[0], 0)
        self.acme = self.brands / "acme"
        self.victim = self.tmp / "victim.json"
        self.victim.write_text("{}", encoding="utf-8")

    def assert_contained(self, code: int, out: str):
        """No traceback, the planted file outside the brand folder survives, and nothing named
        "escaped" exists outside it. `code` is kept for the call sites' readability."""
        self.assertNotIn("Traceback", out, f"rc={code}")
        self.assertTrue(self.victim.exists(), "a file outside the brand folder was deleted")
        self.assertEqual([f for f in self.files_outside(self.acme) if "escaped" in f], [], out)

    def test_campaign_tracker(self):
        bad = "../../../../escaped"
        code, out = self.run_script("campaign-tracker.py", "--brand", "acme", "--action", "save-campaign",
                                    "--data", json.dumps({"name": bad, "status": "planned"}))
        self.assertEqual(code, 0, out)
        self.assert_contained(code, out)
        saved = json.loads(out[out.index("{"):])
        self.assertTrue(Path(saved["path"]).resolve().parent == (self.acme / "campaigns").resolve(), saved)
        code, out = self.run_script("campaign-tracker.py", "--brand", "acme", "--action", "save-performance",
                                    "--data", json.dumps({"campaign_id": "../../../escaped", "clicks": 1}))
        self.assertNotEqual(code, 0, out)
        self.assert_contained(code, out)
        code, out = self.run_script("campaign-tracker.py", "--brand", "acme", "--action", "get-campaign",
                                    "--id", "../../victim")
        self.assertEqual(code, 2, out)

    def test_crm_sync_log_synced_never_deletes_outside(self):
        rel = os.path.relpath(self.victim.with_suffix(""), self.acme / "crm" / "pending")
        code, out = self.run_script("crm-sync.py", "--brand", "acme", "--action", "log-synced", "--data",
                                    json.dumps({"record_type": "contact", "crm_platform": "hubspot",
                                                "crm_record_id": "1", "local_id": "x/" + rel}))
        self.assertNotEqual(code, 0, out)
        self.assert_contained(code, out)

    def test_execution_tracker(self):
        code, out = self.run_script("execution-tracker.py", "--brand", "acme", "--action", "log-execution", "--data",
                                    json.dumps({"platform": "../../../../escaped", "action_type": "post",
                                                "result": "success"}))
        self.assertNotEqual(code, 0, out)
        self.assert_contained(code, out)

    def test_ids_from_the_command_line(self):
        for script, args in (
                ("intelligence-graph.py", ["--action", "update-confidence", "--learning-id", "../../../victim",
                                           "--direction", "up", "--evidence", "x"]),
                ("macro-signal-tracker.py", ["--action", "acknowledge", "--signal-id", "../../../victim",
                                             "--action-taken", "x"]),
                ("pdf-generator.py", ["--action", "get-report", "--report-id", "../../../../victim"]),
                ("pdf-generator.py", ["--action", "export-markdown", "--report-id", "../../../../victim"]),
                ("report-generator.py", ["--action", "format-slack", "--id", "../../../victim"])):
            code, out = self.run_script(script, "--brand", "acme", *args)
            self.assertNotEqual(code, 0, f"{script}: {out}")
            self.assertIn("unsafe name", out, script)
            self.assert_contained(code, out)

    def test_checkpoint_extension_and_panel_id(self):
        code, out = self.run_script("checkpoint-manager.py", "init", "--brand", "acme", "--workflow", "campaign-plan")
        self.assertEqual(code, 0, out)
        run_id = json.loads(out[out.index("{"):])["run_id"]
        # ".md" has its dots stripped, so "./../../../escaped" used to become a path out of the run folder
        code, out = self.run_script("checkpoint-manager.py", "save", "--brand", "acme", "--run-id", run_id,
                                    "--step", "1", "--content", "x", "--extension", "./../../../../escaped")
        self.assertNotEqual(code, 0, out)
        self.assert_contained(code, out)
        code, out = self.run_script("audience-simulator.py", "--brand", "acme", "--action", "focus-group",
                                    "--panel-id", "../../../victim", "--stimulus", "x", "--questions", '["q"]')
        self.assertNotEqual(code, 0, out)
        self.assertIn("unsafe name", out)
        self.assert_contained(code, out)

    def test_names_inside_data(self):
        # The report period is slugged: a path, a slash ("10/2026" crashed) and a colon ("Q3: Jul–Sep"
        # left an empty file, the text after the colon going to an NTFS alternate data stream).
        for period, want in (("../../../../escaped", "weekly-pulse-escaped"), ("10/2026", "weekly-pulse-10-2026"),
                             ("Q3: Jul–Sep", "weekly-pulse-q3-jul-sep")):
            code, out = self.run_script("report-generator.py", "--brand", "acme", "--action", "generate-report",
                                        "--data", json.dumps({"report_type": "weekly-pulse", "period": period,
                                                              "metrics": {"clicks": 1}}))
            self.assertEqual(code, 0, f"{period}: {out}")
            self.assert_contained(code, out)
            saved = self.acme / "reports" / f"{want}.json"
            self.assertTrue(saved.is_file() and saved.stat().st_size > 0, f"{period}: {out}")
            self.assertEqual(json.loads(saved.read_text(encoding="utf-8"))["period"], period)
        code, out = self.run_script("churn-predictor.py", "--brand", "acme", "--action", "trend",
                                    "--segment-name", "..\\..\\..\\..\\escaped", "--score", "50")
        self.assert_contained(code, out)


PATH_JOIN = re.compile(r"/\s*f[\"'][^\"']*\{")


def unguarded_joins(lines) -> list[int]:
    """Line numbers that join an interpolated name onto a path without safe_child/child_or_error
    and without a `# path-safe: <reason>` note saying why the name can't hold a path."""
    return [n for n, line in enumerate(lines, 1) if PATH_JOIN.search(line)
            and not any(mark in line for mark in ("safe_child(", "child_or_error(", "# path-safe:"))]


class TestPathJoinGuard(unittest.TestCase):
    """Every `dir / f"...{name}..."` in scripts/ is contained or says why it doesn't need to be.
    A script can't tell where a value came from, so the note is for the reviewer: a timestamp, a
    hash, an argparse choice, or a value already checked a few lines above."""

    def test_every_interpolated_join_is_contained_or_explained(self):
        found = [f"{path.name}:{n}" for path in sorted(SCRIPTS.glob("*.py"))
                 for n in unguarded_joins(path.read_text(encoding="utf-8-sig").splitlines())]
        self.assertEqual(found, [], "use _common.safe_child, or add '# path-safe: <why>' to the line")

    def test_plant(self):
        lines = ['path = base / f"{name}.json"', 'path = base / f"{name}.json"  # path-safe: a timestamp',
                 'path = _common.safe_child(base, name, ".json")', 'x = a / b']
        self.assertEqual(unguarded_joins(lines), [1])


class TestProfileFiles(Sandbox):

    def setUp(self):
        super().setUp()
        self.assertEqual(self.create("Café Olé")[0], 0)
        self.slug = _common.slugify_brand("Café Olé")
        self.path = self.brands / self.slug / "profile.json"
        self.good = self.path.read_text(encoding="utf-8")

    def commands(self):
        return (("dm-status.py", ["--brand", self.slug]), ("setup.py", ["--check-brand"]),
                ("setup.py", ["--summary"]), ("setup.py", ["--list-brands"]))

    def test_utf16_profiles_are_read(self):
        self.path.write_bytes(self.good.encode("utf-16"))  # what PowerShell 5.1's Out-File writes
        for script, args in self.commands():
            code, out = self.run_script(script, *args)
            self.assertEqual(code, 0, f"{script} {args}: {out}")
            self.assertIn("Café Olé", out, f"{script} {args}")
        if HAS_NLTK:
            self.assertNotIn("error", _load("brand-voice-scorer").load_brand_profile(self.slug))
        ctx, err = _load("adaptive-scorer").load_brand_context(self.slug)
        self.assertIsNone(err)

    def test_a_windows_1252_profile_gets_a_message_not_a_traceback(self):
        self.path.write_bytes(self.good.encode("cp1252"))
        for script, args in self.commands():
            code, out = self.run_script(script, *args)
            self.assertNotIn("Traceback", out, f"{script} {args}")
            self.assertIn("not UTF-8", out, f"{script} {args}")
        if HAS_NLTK:
            self.assertIn("not UTF-8", _load("brand-voice-scorer").load_brand_profile(self.slug)["error"])
        self.assertIn("not UTF-8", _load("adaptive-scorer").load_brand_context(self.slug)[1])

    def test_one_bad_profile_does_not_hide_the_others(self):
        self.assertEqual(self.create("Acme")[0], 0)
        self.path.write_bytes(b"\xff\xfe\x00garbage")
        code, out = self.run_script("setup.py", "--list-brands")
        self.assertEqual(code, 0, out)
        self.assertIn("Acme [acme]", out)
        self.assertIn(self.slug, out)

    def test_a_wrongly_shaped_profile_names_the_field(self):
        p = json.loads(self.good)
        p["industry"], p["brand_voice"] = "saas", "plain and friendly"
        self.path.write_text(json.dumps(p), encoding="utf-8")
        for script, args in self.commands()[:3]:
            code, out = self.run_script(script, *args)
            self.assertNotIn("Traceback", out, f"{script} {args}")
            self.assertIn("industry", out, f"{script} {args}")
        if HAS_NLTK:
            self.assertIn("industry", _load("brand-voice-scorer").load_brand_profile(self.slug)["error"])
        self.assertIn("industry", _load("adaptive-scorer").load_brand_context(self.slug)[1])
        self.path.write_text("[1, 2]", encoding="utf-8")
        code, out = self.run_script("dm-status.py", "--brand", self.slug)
        self.assertNotIn("Traceback", out)


class TestSecurityPolicy(unittest.TestCase):

    def test_the_supported_line_is_the_current_minor(self):
        version = json.loads((REPO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
        minor = ".".join(version.split(".")[:2])
        text = (REPO / "SECURITY.md").read_text(encoding="utf-8")
        self.assertIn(f"{minor}.x", text)
        stale = sorted(set(re.findall(r"\b(\d+\.\d+)\.x\b", text)) - {minor})
        self.assertEqual(stale, [], "SECURITY.md names other release lines")


if __name__ == "__main__":
    unittest.main()
