"""Public files say what was done, not which internal session did it.

This plugin is built by several coordinating work sessions whose notes live in a folder outside
the repository. In the 3.38.1 round, shipped files had started to name those sessions and point
at those notes: the model registry's `last_updated_by` (shipped as data and copied into the
sibling plugins) cited a patch file a reader cannot open, and CHANGELOG and test text credited
named sessions. So, in every file the repository ships:
  * no session labels (the names of the coordinating sessions);
  * no path into the outside notes folder.
CHANGELOG entries dated before 2026-10-27 are history: they name test harnesses that really
lived there, so they stay as written. Point at what a reader can open instead: vendor pages,
docs/MODEL-CURATOR.md, the tests themselves.
Stdlib only; works from an installed copy (no git) by walking the folder.
"""
from __future__ import annotations

import re
import subprocess
import unittest
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HISTORY_BEFORE = date(2026, 10, 27)
NOTES = "_sha" + "red/"
LABELS = re.compile("|".join([
    r"\bBrain" + r" A\b",
    r"\bWorker" + r" [AB]\b",
    r"\b[Tt]he" + r" Orchestrator\b",  # "the Campaign Orchestrator" is a product name; it passes
    r"\b[Tt]he(?:\s+[\w-]+){0,2}\s+" + r"Tester\b",  # "the fresh-install Tester" too; "A/B tester" passes
    r"\bTester" + r"'s\b",
]))
SKIP_PARTS = {".git", "__pycache__", "results", "node_modules"}
TEXT_SUFFIXES = {".md", ".py", ".json", ".yaml", ".yml", ".sh", ".txt", ".toml", ".cfg", ".example", ""}
ENTRY = re.compile(r"(?m)^## \[[^\]]+\] - (\d{4}-\d{2}-\d{2})")


def changelog_live_text(text: str) -> str:
    """Only the CHANGELOG entries dated on or after HISTORY_BEFORE (plus anything above them)."""
    out, pos, live = [], 0, True
    for m in ENTRY.finditer(text):
        if live:
            out.append(text[pos:m.start()])
        live = date.fromisoformat(m.group(1)) >= HISTORY_BEFORE
        pos = m.start()
    if live:
        out.append(text[pos:])
    return "".join(out)


def problems(rel: str, text: str) -> list:
    if Path(rel).name == "CHANGELOG.md":
        text = changelog_live_text(text)
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        if NOTES in line:
            out.append(f"{rel}:{n}: points into the outside notes folder")
        if m := LABELS.search(line):
            out.append(f"{rel}:{n}: names an internal session ({m.group(0)!r})")
    return out


def shipped_files(root: Path = REPO) -> list:
    try:
        listed = subprocess.run(["git", "-C", str(root), "ls-files"], capture_output=True, text=True,
                                check=True, timeout=60).stdout.splitlines()
        paths = [root / p for p in listed]
    except (OSError, subprocess.SubprocessError):
        paths = [p for p in root.rglob("*") if p.is_file()]
    me = Path(__file__).resolve()
    return [p for p in paths if p.is_file() and p.resolve() != me
            and not (set(p.relative_to(root).parts) & SKIP_PARTS)
            and (p.suffix.lower() in TEXT_SUFFIXES)]


class TestNoInternalReferences(unittest.TestCase):

    def test_shipped_files_are_clean(self):
        found = []
        for p in shipped_files():
            try:
                text = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            found += problems(p.relative_to(REPO).as_posix(), text)
        self.assertEqual(found, [], "\n  " + "\n  ".join(found))

    def test_plants(self):
        caught = problems("scripts/model_registry.json",
                          '"last_updated_by": "manual refresh; see ' + NOTES + 'REGISTRY-PATCH.md"')
        self.assertEqual(len(caught), 1)
        self.assertTrue(problems("scripts/x.py", "so after 3.36.2 Worker" + " B finished the sync by hand"))
        self.assertTrue(problems("tests/x.py", "The four cases Brain" + " A asked for first."))
        self.assertTrue(problems("tests/x.py", "The Tester" + "'s probe used to run the suite"))
        # A role word after up to two words: found in sibling CHANGELOG lines dated 2026-10-27.
        self.assertTrue(problems("CHANGELOG.md", "- Found by the fresh-install " + "Tester from the installed copy."))
        self.assertTrue(problems("CHANGELOG.md", "as the installed-copy fresh " + "Tester saw it"))
        for fine in ("Campaign Orchestrator activates", "Journey Orchestrator Agent",
                     "The Campaign Orchestrator's budget-allocation framework",
                     "12-Part Engagement Orchestrator", "the session's model", "a tester who never saw it",
                     "significance-tester.py", "A/B testers", "the A/B tester picks a winner",
                     "the A/B Tester tab", "testers in prose", "the fresh-install testers"):
            self.assertEqual(problems("docs/x.md", fine), [], fine)

    def test_old_changelog_entries_are_history(self):
        log = ("# Changelog\n\n## [3.38.0] - 2026-10-27\n\nThe plan by Brain" + " A.\n\n"
               "## [3.35.8] - 2026-10-12\n\nHarness `" + NOTES + "dmp_action_test_harness.py` passes.\n")
        caught = problems("CHANGELOG.md", log)
        self.assertEqual(len(caught), 1)
        self.assertIn("internal session", caught[0])

    def test_plant_against_3_38_1(self):
        """The 3.38.1 commit had six of these; skipped where git or that commit is absent."""
        files = ("scripts/model_registry.json", "scripts/registry_mirror.py", "tests/test_model_registry_sync.py",
                 "tests/test_model_router.py", "tests/test_run_all_args.py", "CHANGELOG.md")
        found = []
        for rel in files:
            try:
                text = subprocess.run(["git", "-C", str(REPO), "show", f"c66d6a6:{rel}"], capture_output=True,
                                      check=True, timeout=60).stdout.decode("utf-8")
            except (OSError, subprocess.SubprocessError):
                self.skipTest("git or the 3.38.1 commit is not available")
            found += problems(rel, text)
        self.assertGreaterEqual(len(found), 7, found)


if __name__ == "__main__":
    unittest.main()
