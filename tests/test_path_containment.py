"""Model-supplied IDs must never reach a delete or write outside the plugin's data.

Hermes review (NousResearch/hermes-agent#132571, item 3): `discard_run` did
`shutil.rmtree(runs/<run_id>)` with only an exists() check, so a `../..` or
absolute run_id deleted any directory; the team, memory, guidelines, journey,
PDF-schedule and approval managers built `<dir>/<id>.json` the same way, and
`_common.brand_dir` returned `brands/<raw>` for any existing directory a raw
`--brand` named. Every such ID now goes through `_common.safe_child`, which
rejects separators, `..`, absolute paths and drive colons and asserts the
result is a direct child of its directory.

Each manager is driven through its real CLI against a temp workspace with a
"victim" file outside brands/, using the three planted inputs the review
named: a relative `../` climb, an absolute path and a backslash climb.

Stdlib only.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _helpers import SCRIPTS_DIR, run_json, run_script  # noqa: E402

sys.path.insert(0, str(SCRIPTS_DIR))
import _common  # noqa: E402

BRAND = "acme"


class TestSafeChild(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_rejects_traversal_absolute_backslash_and_junk(self):
        bad = ["../x", "../../etc/passwd", "..\\x", "a/b", "a\\b", "/etc/passwd", "C:\\Windows", "C:",
               str(self.base.parent / "x"), "..", ".", "", "   ", "x\x00y", "file:stream"]
        for name in bad:
            with self.subTest(name=name):
                with self.assertRaises(_common.UnsafePathError):
                    _common.safe_child(self.base, name, ".json")
                path, err = _common.child_or_error(self.base, name, ".json")
                self.assertIsNone(path)
                self.assertTrue(err)
        with self.assertRaises(_common.UnsafePathError):
            _common.safe_child(self.base, None)

    def test_accepts_plain_names_as_direct_children(self):
        for name in ("run-2026-10-10_ab12", "member.one", "sched-weekly-20261010", "3f9a1c0d2b7e4a61"):
            with self.subTest(name=name):
                p = _common.safe_child(self.base, name, ".json")
                self.assertEqual(p.parent, self.base)
                self.assertEqual(p.name, f"{name}.json")

    def test_raw_brand_cannot_escape_the_workspace(self):
        # brand_dir may legitimately return a legacy slug dir directly under the
        # workspace (pre-v3.15 layout), but never anything outside the workspace.
        tmp = Path(tempfile.mkdtemp())
        home = tmp / "workspace"
        try:
            (home / "brands").mkdir(parents=True)
            (tmp / "outside").mkdir()
            old = os.environ.get("CLAUDE_MARKETING_HOME")
            os.environ["CLAUDE_MARKETING_HOME"] = str(home)
            try:
                for raw in ("../../outside", str(tmp / "outside"), "..\\..\\outside"):
                    with self.subTest(raw=raw):
                        d = _common.brand_dir(raw).resolve()
                        self.assertTrue(d.is_relative_to(home.resolve()), f"brand_dir({raw!r}) escaped to {d}")
                        self.assertNotEqual(d, (tmp / "outside").resolve())
            finally:
                if old is None:
                    os.environ.pop("CLAUDE_MARKETING_HOME", None)
                else:
                    os.environ["CLAUDE_MARKETING_HOME"] = old
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestManagersRefuseEscapes(unittest.TestCase):
    """Real CLI calls; the victim file outside brands/ must survive every one."""

    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.brand_dir = self.home / "brands" / BRAND
        for sub in ("runs", "team", "approvals", "journeys", "reports/schedules", "memory/pending",
                    "memory/stored", "guidelines/custom", "templates"):
            (self.brand_dir / sub).mkdir(parents=True, exist_ok=True)
        (self.brand_dir / "profile.json").write_text(json.dumps({"name": "Acme"}), encoding="utf-8")
        self.victim_dir = self.home / "victim"
        self.victim_dir.mkdir()
        # keep.json looks like a real pending record, so old code that parses before
        # writing (approve, cancel-schedule) would actually rewrite it.
        self.victim_content = {
            "keep.json": json.dumps({"id": "keep", "status": "pending", "active": True, "note": "do not touch"}),
            "keep.md": "do not touch",
            "keep": "do not touch",
        }
        for name, body in self.victim_content.items():
            (self.victim_dir / name).write_text(body, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def planted(self, depth: int):
        """The three planted inputs, each reaching victim/keep from a base dir `depth` levels below
        the workspace, so the OLD code would really hit the victim (a wrong depth would pass vacuously)."""
        up = "../" * depth
        return [up + "victim/keep", str(self.victim_dir / "keep"), up.replace("/", "\\") + "victim\\keep"]

    def assert_victim_intact(self):
        self.assertTrue(self.victim_dir.is_dir(), "victim directory was deleted")
        for name, body in self.victim_content.items():
            p = self.victim_dir / name
            self.assertTrue(p.exists(), f"victim/{name} was deleted")
            self.assertEqual(p.read_text(encoding="utf-8"), body, f"victim/{name} was rewritten")

    def assert_refused(self, script, *args):
        data, rc = run_json(script, *args, marketing_home=self.home)
        self.assertNotEqual(rc, 0, f"{script} {args} exited 0: {data}")
        blob = json.dumps(data).lower()
        self.assertIn("error", blob, f"{script} {args} gave no error: {data}")
        self.assertNotIn("traceback", blob)
        self.assert_victim_intact()

    def test_checkpoint_discard(self):
        for bad in self.planted(3) + ["../../../victim"]:
            with self.subTest(run_id=bad):
                self.assert_refused("checkpoint-manager.py", "discard", "--brand", BRAND, "--run-id", bad)

    def test_team_remove_member(self):
        for bad in self.planted(3):
            with self.subTest(member_id=bad):
                self.assert_refused("team-manager.py", "--brand", BRAND, "--action", "remove-member", "--id", bad)

    def test_journey_delete(self):
        for bad in self.planted(3):
            with self.subTest(journey_id=bad):
                self.assert_refused("journey-engine.py", "--brand", BRAND, "--action", "delete-journey",
                                    "--journey-id", bad)

    def test_pdf_cancel_schedule(self):
        for bad in self.planted(4):
            with self.subTest(schedule_id=bad):
                self.assert_refused("pdf-generator.py", "--brand", BRAND, "--action", "cancel-schedule",
                                    "--schedule-id", bad)

    def test_approval_approve(self):
        for bad in self.planted(3):
            with self.subTest(approval_id=bad):
                self.assert_refused("approval-manager.py", "--brand", BRAND, "--action", "approve", "--id", bad)

    def test_guidelines_delete_and_template_delete(self):
        for bad in self.planted(4):
            with self.subTest(category=bad):
                self.assert_refused("guidelines-manager.py", "--brand", BRAND, "--action", "delete",
                                    "--category", bad + ".md")
        for bad in self.planted(3):
            with self.subTest(template=bad):
                self.assert_refused("guidelines-manager.py", "--brand", BRAND, "--action", "delete-template",
                                    "--name", bad)

    def test_guideline_template_and_sop_saves_and_sop_delete(self):
        for bad in self.planted(4):  # brands/acme/guidelines/custom
            with self.subTest(save_category=bad):
                self.assert_refused("guidelines-manager.py", "--brand", BRAND, "--action", "save",
                                    "--category", bad, "--content", "x")
        for bad in self.planted(3):  # brands/acme/templates
            with self.subTest(save_template=bad):
                self.assert_refused("guidelines-manager.py", "--brand", BRAND, "--action", "save-template",
                                    "--name", bad, "--content", "x")
        for bad in self.planted(1):  # <workspace>/sops
            with self.subTest(sop=bad):
                self.assert_refused("guidelines-manager.py", "--action", "save-sop", "--name", bad,
                                    "--content", "x")
                self.assert_refused("guidelines-manager.py", "--action", "delete-sop", "--name", bad)

    def test_sops_live_in_the_configured_workspace(self):
        data, rc = run_json("guidelines-manager.py", "--action", "save-sop", "--name", "launch",
                            "--content", "1. check", marketing_home=self.home)
        self.assertEqual(rc, 0, data)
        self.assertTrue((self.home / "sops" / "launch.md").exists(),
                        "SOPs must honour CLAUDE_MARKETING_HOME like every other script")

    def test_memory_log_stored(self):
        for bad in self.planted(4):
            with self.subTest(content_hash=bad):
                payload = json.dumps({"content_hash": bad, "vector_db": "local", "storage_id": "x"})
                self.assert_refused("memory-manager.py", "--brand", BRAND, "--action", "log-stored",
                                    "--data", payload)

    def test_auto_save_insight_raw_brand(self):
        for bad in ("../victim", str(self.victim_dir), "..\\victim"):
            with self.subTest(brand=bad):
                proc = run_script("auto-save-insight.py", "--brand", bad, "--type", "session_learning",
                                  "--insight", "x", "--force", marketing_home=self.home)
                # Refused at the argparse type (exit 2) or, for library callers, by the
                # script's own check (exit 1): either way nothing is written.
                self.assertIn(proc.returncode, (1, 2), proc.stdout + proc.stderr)
                self.assertRegex(proc.stdout + proc.stderr, r"unsafe --brand|must be a plain name")
                self.assertFalse((self.victim_dir / "insights.json").exists())
                self.assert_victim_intact()

    # ── positive controls: plain IDs still work ────────────────────

    def test_checkpoint_lifecycle_still_works(self):
        init, rc = run_json("checkpoint-manager.py", "init", "--brand", BRAND, "--workflow", "seo-audit",
                            "--topic", "containment", marketing_home=self.home)
        self.assertEqual(rc, 0, init)
        run_id = init["run_id"]
        gone, rc = run_json("checkpoint-manager.py", "discard", "--brand", BRAND, "--run-id", run_id,
                            marketing_home=self.home)
        self.assertEqual(rc, 0, gone)
        self.assertEqual(gone["status"], "discarded")
        self.assertTrue((self.brand_dir / "runs").is_dir(), "discard removed more than the run")
        self.assert_victim_intact()

    def test_approval_create_then_approve_still_works(self):
        payload = json.dumps({"type": "publish-blog", "platform": "wordpress",
                              "content_summary": "containment test", "risk_level": "medium"})
        made, rc = run_json("approval-manager.py", "--brand", BRAND, "--action", "create-approval",
                            "--data", payload, marketing_home=self.home)
        self.assertEqual(rc, 0, made)
        approval_id = made.get("approval_id") or made.get("id")
        self.assertTrue(approval_id, made)
        ok, rc = run_json("approval-manager.py", "--brand", BRAND, "--action", "approve", "--id", approval_id,
                          marketing_home=self.home)
        self.assertEqual(rc, 0, ok)


if __name__ == "__main__":
    unittest.main()
