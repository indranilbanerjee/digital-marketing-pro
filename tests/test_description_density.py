"""Skill descriptions must carry enough signal to route on.

For a model-invoked skill, the frontmatter description is the entire routing
layer: it is the only thing the model reads when deciding whether a skill
applies — and with 163 skills, weak descriptions mean wrong routing, not just
bad docs. The house pattern (proven on the suite's smaller plugins first):
state what the skill does and produces, then "Triggers on" with the quoted
phrases a user would actually type (slash alias first), then what it reads or
pairs with. This guard makes the pattern mechanical.

Stdlib only.
"""
from __future__ import annotations

import re
import statistics
import unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parent.parent / "skills"

MIN_LENGTH = 300
MAX_LENGTH = 900
MIN_TRIGGER_PHRASES = 4
SLASH_PREFIX = "/digital-marketing-pro:"

DESC_RE = re.compile(r'^description:\s*"(.*)"\s*$', re.M)
PHRASE_RE = re.compile(r'\\"([^"]+?)\\"')


def description_line(skill_dir: Path) -> str | None:
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8", errors="replace")
    m = DESC_RE.search(text)
    return m.group(1) if m else None


def analyze(desc: str) -> dict:
    phrases = PHRASE_RE.findall(desc)
    return {
        "length": len(desc),
        "has_triggers": "Triggers on" in desc,
        "phrases": phrases,
        "has_slash": any(p.startswith(SLASH_PREFIX) for p in phrases),
    }


def all_skills():
    for d in sorted(SKILLS.iterdir()):
        if d.is_dir() and (d / "SKILL.md").exists():
            yield d


class TestNoDeadFrontmatter(unittest.TestCase):
    """`triggers:` is not a Claude Code skill field (the documented one is
    `when_to_use`, which is loaded into every session alongside the
    description). Sixteen skills carried trigger lists in it that no host ever
    read; their routing phrases live in the description's "Triggers on" clause,
    which the density guard below enforces. Found 2026-10-04."""

    def test_no_skill_declares_triggers(self):
        bad = []
        for d in all_skills():
            fm = (d / "SKILL.md").read_text(encoding="utf-8", errors="replace").split("---")[1]
            if re.search(r"^triggers:", fm, re.M):
                bad.append(d.name)
        self.assertEqual(bad, [], f"skills with an unread `triggers:` field: {bad}")


class TestDescriptionDensity(unittest.TestCase):
    def test_every_description_is_single_line_double_quoted(self):
        bad = [d.name for d in all_skills() if description_line(d) is None]
        self.assertEqual(bad, [],
                         "Skills whose description is not a single-line double-quoted "
                         "string:\n  " + "\n  ".join(bad))

    def test_every_description_meets_the_floor(self):
        failures = []
        for d in all_skills():
            desc = description_line(d)
            if desc is None:
                continue  # reported by the test above
            a = analyze(desc)
            problems = []
            if a["length"] < MIN_LENGTH:
                problems.append(f"{a['length']} chars < {MIN_LENGTH}")
            if a["length"] > MAX_LENGTH:
                problems.append(f"{a['length']} chars > {MAX_LENGTH}")
            if not a["has_triggers"]:
                problems.append("no 'Triggers on'")
            if len(a["phrases"]) < MIN_TRIGGER_PHRASES:
                problems.append(f"{len(a['phrases'])} quoted trigger phrases < {MIN_TRIGGER_PHRASES}")
            if not a["has_slash"]:
                problems.append(f"no quoted {SLASH_PREFIX}<name> alias")
            if problems:
                failures.append(f"{d.name}: " + "; ".join(problems))
        self.assertEqual(failures, [],
                         "Descriptions below the routing floor:\n  " + "\n  ".join(failures))

    def test_median_stays_dense(self):
        """A per-skill floor survives one lazy rewrite at a time; the median
        catches a slow slide back toward one-liners."""
        lengths = [len(description_line(d) or "") for d in all_skills()]
        self.assertGreaterEqual(statistics.median(lengths), 350,
                                f"median description length {statistics.median(lengths)} — "
                                "the routing layer is thinning out")

    # ── plant checks ────────────────────────────────────────────────

    def test_analyzer_accepts_the_house_pattern(self):
        good = ('Does a real thing and produces a real artifact for the brand. '
                'Triggers on \\"/digital-marketing-pro:example\\", \\"do the thing\\", '
                '\\"why is the thing broken\\", \\"make me a thing plan\\". '
                'Reads the brand profile; pairs with /digital-marketing-pro:check.')
        a = analyze(good)
        self.assertTrue(a["has_triggers"] and a["has_slash"])
        self.assertGreaterEqual(len(a["phrases"]), 4)

    def test_analyzer_rejects_a_one_liner(self):
        a = analyze("Show the getting started guide for the plugin")
        self.assertFalse(a["has_triggers"])
        self.assertEqual(a["phrases"], [])


if __name__ == "__main__":
    unittest.main()
