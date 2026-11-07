"""Execution skills route through their gate, and only a person can start them.

The skills that write to live platforms (send, publish, launch, import, export, sync) each carry an
`## Execution gate` block: an Execution Summary, a typed `yes`, and an approval recorded with
approval-manager.py before the call.

3.15.0 to 3.41.0 kept them model-invocable (`disable-model-invocation: false`) on the reasoning that a
plain "send the campaign" should still load the gate. The 2026-11-05 security review showed the cost:
a page the model fetched can start the workflow, and the model then runs prepare, `approve` and fire
itself. Since 3.42.0 they are `disable-model-invocation: true`: the user starts them with
/digital-marketing-pro:<skill>, the model tells the user which command to run, and the host's prompt
(forced by hooks/gate_live_writes.py) covers each live step. Writes through MCP tools still depend on
the host's own prompt for that tool. Codex ignores the flag, so the gate in the skill body stays the
safety layer on every host.

launch-plan has a gate for its hand-off but performs no external action, so it stays invocable.

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
# Gated, but writes nothing itself: it hands off to the execution skills above.
PLANNING_ONLY = frozenset({"launch-plan"})
# Starts live actions without an `## Execution gate` block of its own (it shows one Execution Summary
# for the whole launch); it must not be model-invocable either.
LAUNCHERS = frozenset({"launch-campaign"})
COMMANDS = SKILLS.parent / "commands"

GATE = re.compile(r"^## Execution gate\b", re.M)
INVOCABLE = re.compile(r"\A---\n(?:(?!---\n).*\n)*?disable-model-invocation:\s*false\s*\n")
USER_ONLY = re.compile(r"\A---\n(?:(?!---\n).*\n)*?disable-model-invocation:\s*true\s*\n")
RECORDS_APPROVAL = re.compile(r"--action create-approval\b")
# A body that runs a live-write step: the executor, or an approval being recorded, approved or made standing.
LIVE_STEP = re.compile(r"connector_executor\.py|--action (?:create-approval|approve|create-standing)\b")


def _read(name: str) -> str:
    return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8").replace("\r\n", "\n")


def gate_problems(text: str, planning_only: bool = False) -> list[str]:
    out = []
    if not GATE.search(text):
        out.append("no `## Execution gate` block")
    if planning_only:
        if not INVOCABLE.match(text):
            out.append("frontmatter does not say `disable-model-invocation: false`")
    elif not USER_ONLY.match(text):
        out.append("frontmatter does not say `disable-model-invocation: true`")
    return out


class TestExecutionGates(unittest.TestCase):
    def test_every_execution_skill_exists(self):
        missing = sorted(n for n in EXECUTION_SKILLS if not (SKILLS / n / "SKILL.md").exists())
        self.assertEqual(missing, [], "execution skills listed here but not on disk")

    def test_every_execution_skill_has_its_gate_and_only_a_person_starts_it(self):
        bad = {n: p for n in sorted(EXECUTION_SKILLS)
               if (p := gate_problems(_read(n), planning_only=n in PLANNING_ONLY))}
        self.assertEqual(bad, {}, "an execution skill lost its gate or became model-invocable "
                                  f"(see this module's docstring): {bad}")

    def test_launchers_are_user_only(self):
        for n in sorted(LAUNCHERS):
            with self.subTest(skill=n):
                self.assertTrue(USER_ONLY.match(_read(n)), f"{n} must say disable-model-invocation: true")

    def test_any_file_that_runs_a_live_step_is_user_only(self):
        """Every skill or command whose body runs the executor or records/approves an approval."""
        files = [d / "SKILL.md" for d in sorted(SKILLS.iterdir()) if (d / "SKILL.md").exists()]
        files += sorted(COMMANDS.glob("*.md"))
        bad = []
        for f in files:
            text = f.read_text(encoding="utf-8").replace("\r\n", "\n")
            body = text.split("\n---\n", 1)[-1]
            if LIVE_STEP.search(body) and f.parent.name not in PLANNING_ONLY and not USER_ONLY.match(text):
                bad.append(f.relative_to(SKILLS.parent).as_posix())
        self.assertEqual(bad, [], "these run a live-write step but the model can start them on its own")

    def test_any_skill_that_records_an_approval_is_an_execution_skill(self):
        found = {d.name for d in SKILLS.iterdir()
                 if (d / "SKILL.md").exists() and RECORDS_APPROVAL.search(_read(d.name))}
        self.assertEqual(sorted(found - EXECUTION_SKILLS), [],
                         "these skills create approvals but are not in EXECUTION_SKILLS, "
                         "so nothing checks their gate")

    def test_guard_can_fail(self):
        ok = "---\nname: x\ndisable-model-invocation: true\n---\n\n## Execution gate\n"
        self.assertEqual(gate_problems(ok), [])
        self.assertTrue(gate_problems(ok.replace("true", "false")))
        self.assertTrue(gate_problems(ok.replace("disable-model-invocation: true\n", "")))
        self.assertTrue(gate_problems(ok.replace("## Execution gate", "## Gate")))
        body_only = "---\nname: x\n---\n\ndisable-model-invocation: true\n\n## Execution gate\n"
        self.assertTrue(gate_problems(body_only), "the flag outside the frontmatter must not count")
        self.assertEqual(gate_problems(ok.replace("true", "false"), planning_only=True), [])
        self.assertTrue(LIVE_STEP.search("run `connector_executor.py --execute`"))
        self.assertTrue(LIVE_STEP.search("approval-manager.py --brand a --action approve --id x"))
        self.assertFalse(LIVE_STEP.search("approval-manager.py --brand a --action list-pending"))


if __name__ == "__main__":
    unittest.main()
