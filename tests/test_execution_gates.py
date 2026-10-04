"""Execution skills route through their gate, so they must stay reachable.

The 18 skills that write to live platforms (send, publish, launch, import,
export, sync) each carry an `## Execution gate` block: an Execution Summary,
a typed `yes`, and an approval recorded with approval-manager.py before the
call. v3.15.0 set `disable-model-invocation: false` on all of them and closed
issue #6 promising a test that keeps it that way; the test was never written.

Why false, not true: with model invocation disabled, a plain request such as
"send the campaign" cannot load the skill, and the model can still reach the
same MCP write tools freehand. That bypasses the gate rather than enforcing it.
Keeping the skills invocable routes those requests through the gate, the
approval record and the execution log. Codex ignores the flag either way, so
the gate in the skill body is the safety layer on every host.

Stdlib only.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parent.parent / "skills"

EXECUTION_SKILLS = frozenset({
    "credential-switch", "crm-sync", "data-export", "data-import",
    "launch-ad-campaign", "launch-plan", "lead-import", "live-dashboard",
    "pipeline-update", "publish-blog", "redirect-manager", "schedule-social",
    "segment-audience", "send-email-campaign", "send-notification",
    "send-report", "send-sms", "seo-implement",
})

GATE = re.compile(r"^## Execution gate\b", re.M)
INVOCABLE = re.compile(r"\A---\n(?:(?!---\n).*\n)*?disable-model-invocation:\s*false\s*\n")
RECORDS_APPROVAL = re.compile(r"--action create-approval\b")


def _read(name: str) -> str:
    return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8").replace("\r\n", "\n")


def gate_problems(text: str) -> list[str]:
    out = []
    if not GATE.search(text):
        out.append("no `## Execution gate` block")
    if not INVOCABLE.match(text):
        out.append("frontmatter does not say `disable-model-invocation: false`")
    return out


class TestExecutionGates(unittest.TestCase):
    def test_every_execution_skill_exists(self):
        missing = sorted(n for n in EXECUTION_SKILLS if not (SKILLS / n / "SKILL.md").exists())
        self.assertEqual(missing, [], "execution skills listed here but not on disk")

    def test_every_execution_skill_has_its_gate_and_stays_invocable(self):
        bad = {n: p for n in sorted(EXECUTION_SKILLS) if (p := gate_problems(_read(n)))}
        self.assertEqual(bad, {}, "an execution skill lost its gate or was made "
                                  "uninvocable (see this module's docstring for why "
                                  f"`true` bypasses the gate): {bad}")

    def test_any_skill_that_records_an_approval_is_an_execution_skill(self):
        found = {d.name for d in SKILLS.iterdir()
                 if (d / "SKILL.md").exists() and RECORDS_APPROVAL.search(_read(d.name))}
        self.assertEqual(sorted(found - EXECUTION_SKILLS), [],
                         "these skills create approvals but are not in EXECUTION_SKILLS, "
                         "so nothing checks their gate")

    def test_guard_can_fail(self):
        ok = "---\nname: x\ndisable-model-invocation: false\n---\n\n## Execution gate\n"
        self.assertEqual(gate_problems(ok), [])
        self.assertTrue(gate_problems(ok.replace("false", "true")))
        self.assertTrue(gate_problems(ok.replace("disable-model-invocation: false\n", "")))
        self.assertTrue(gate_problems(ok.replace("## Execution gate", "## Gate")))
        body_only = "---\nname: x\n---\n\ndisable-model-invocation: false\n\n## Execution gate\n"
        self.assertTrue(gate_problems(body_only), "the flag outside the frontmatter must not count")


if __name__ == "__main__":
    unittest.main()
