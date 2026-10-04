"""A slash command must not duplicate a skill of the same name.

Claude Code lists BOTH a `commands/<name>.md` and a `skills/<name>/` entry, so a
same-named pair costs always-on context twice for one slash command — the skill
already provides `/digital-marketing-pro:<name>`. Thirteen pairs were folded into
their skills in October 2026 (command-only guidance moved into a supplementary
file beside SKILL.md); this guard keeps the duplication from growing back, keeps
links to the deleted files from dangling, and keeps the folded-in supplementary
files reachable from their SKILL.md.

Each guard has a planted-failure test proving it fires on a synthetic tree.
"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from _helpers import PLUGIN_ROOT

COMMANDS = PLUGIN_ROOT / "commands"
SKILLS = PLUGIN_ROOT / "skills"

# skill -> supplementary file(s) that carry the folded command-only guidance;
# SKILL.md must name each one so the agent knows when to read it.
FOLDED_SUPPLEMENTS = {
    "campaign-plan": ["brief-structure.md"],
    "competitor-analysis": ["dimension-checklists.md"],
    "content-engine": ["draft-deliverables.md"],
    "email-sequence": ["sequence-blueprint.md"],
    "performance-report": ["deliverable-layout.md"],
    "seo-audit": ["dimension-checklists.md"],
}

LINK_RE = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")


def duplicated_names(commands_dir: Path, skills_dir: Path) -> list[str]:
    """Names that exist both as commands/<name>.md and skills/<name>/SKILL.md."""
    if not commands_dir.is_dir():
        return []
    return sorted(
        c.stem for c in commands_dir.glob("*.md")
        if (skills_dir / c.stem / "SKILL.md").exists())


def dangling_command_links(root: Path, scan_files) -> list[str]:
    """Relative markdown links that resolve into <root>/commands/ but whose
    target file does not exist."""
    cmd_dir = (root / "commands").resolve()
    bad = []
    for f in scan_files:
        text = f.read_text(encoding="utf-8", errors="replace")
        for m in LINK_RE.finditer(text):
            target = m.group(1)
            if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("/"):
                continue
            resolved = (f.parent / target).resolve()
            try:
                resolved.relative_to(cmd_dir)
            except ValueError:
                continue
            if resolved.suffix == ".md" and not resolved.exists():
                bad.append(f"{f.relative_to(root).as_posix()} -> {target}")
    return bad


def unreachable_supplements(skills_dir: Path, mapping: dict) -> list[str]:
    """Supplementary files that are missing, or that SKILL.md never names."""
    problems = []
    for skill, files in mapping.items():
        body = (skills_dir / skill / "SKILL.md").read_text(encoding="utf-8")
        for name in files:
            if not (skills_dir / skill / name).is_file():
                problems.append(f"{skill}/{name} is missing")
            elif name not in body:
                problems.append(f"{skill}/SKILL.md never names {name} "
                                "(the agent would not know to read it)")
    return problems


def surfaces_to_scan():
    files = []
    files += sorted((PLUGIN_ROOT / "commands").glob("*.md"))
    files += sorted((PLUGIN_ROOT / "docs").glob("*.md"))
    files += sorted(SKILLS.rglob("*.md"))
    files += [p for p in (PLUGIN_ROOT / "CONTRIBUTING.md",) if p.exists()]
    return files


class TestNoCommandDuplicatesASkill(unittest.TestCase):
    def test_no_command_shares_a_name_with_a_skill(self):
        dupes = duplicated_names(COMMANDS, SKILLS)
        self.assertEqual(
            dupes, [],
            "commands/ files duplicating a skill (always-on cost paid twice; the "
            "skill already provides the slash command — fold any command-only "
            "guidance into a supplementary file beside SKILL.md and delete the "
            "command): " + ", ".join(dupes))

    def test_planted_duplicate_is_caught(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "commands").mkdir()
            (root / "skills" / "alpha").mkdir(parents=True)
            (root / "skills" / "beta").mkdir(parents=True)
            (root / "skills" / "alpha" / "SKILL.md").write_text("x", encoding="utf-8")
            (root / "skills" / "beta" / "SKILL.md").write_text("x", encoding="utf-8")
            (root / "commands" / "alpha.md").write_text("dup", encoding="utf-8")
            (root / "commands" / "gamma.md").write_text("command-only", encoding="utf-8")
            self.assertEqual(
                duplicated_names(root / "commands", root / "skills"), ["alpha"])


class TestNoDanglingCommandLinks(unittest.TestCase):
    def test_no_link_points_at_a_missing_command_file(self):
        bad = dangling_command_links(PLUGIN_ROOT, surfaces_to_scan())
        self.assertEqual(
            bad, [],
            "Links to command files that no longer exist (point them at the "
            "skill's SKILL.md instead):\n  " + "\n  ".join(bad))

    def test_planted_dangling_link_is_caught(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "commands").mkdir()
            (root / "docs").mkdir()
            (root / "commands" / "keep.md").write_text("ok", encoding="utf-8")
            doc = root / "docs" / "guide.md"
            doc.write_text(
                "[ok](../commands/keep.md) [gone](../commands/removed.md#x) "
                "[web](https://example.org/commands/removed.md)",
                encoding="utf-8")
            self.assertEqual(
                dangling_command_links(root, [doc]),
                ["docs/guide.md -> ../commands/removed.md"])


class TestFoldedSupplementsAreReachable(unittest.TestCase):
    def test_supplement_exists_and_is_named_in_skill_md(self):
        problems = unreachable_supplements(SKILLS, FOLDED_SUPPLEMENTS)
        self.assertEqual(problems, [], "\n  ".join(problems))

    def test_planted_missing_and_unreferenced_supplements_are_caught(self):
        with tempfile.TemporaryDirectory() as td:
            skills = Path(td)
            (skills / "good").mkdir()
            (skills / "good" / "SKILL.md").write_text("read extra.md when drafting", encoding="utf-8")
            (skills / "good" / "extra.md").write_text("x", encoding="utf-8")
            (skills / "unnamed").mkdir()
            (skills / "unnamed" / "SKILL.md").write_text("no pointer here", encoding="utf-8")
            (skills / "unnamed" / "extra.md").write_text("x", encoding="utf-8")
            (skills / "absent").mkdir()
            (skills / "absent" / "SKILL.md").write_text("read extra.md", encoding="utf-8")
            mapping = {"good": ["extra.md"], "unnamed": ["extra.md"], "absent": ["extra.md"]}
            problems = unreachable_supplements(skills, mapping)
            self.assertEqual(len(problems), 2, problems)
            self.assertTrue(any("unnamed" in p and "never names" in p for p in problems))
            self.assertTrue(any("absent" in p and "missing" in p for p in problems))


if __name__ == "__main__":
    unittest.main()
