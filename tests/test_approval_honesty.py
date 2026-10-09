"""The docs must not claim more than the approval code can prove.

Hermes review item 2 and the D1 red-team (2026-10-10): code cannot tell the
user from the model (the model runs every command, including `approve`), and
writes through MCP server tools never pass through connector_executor.py. So
the honest claim is "a write the plugin sends cannot fire without a matching
approval record", never "cannot fire without your yes" or "code verifies you
typed it". This guard keeps that wording from creeping back, keeps the two
limits stated where users read them, and keeps approval records from claiming
who approved.

Stdlib only.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

OVERCLAIMS = [
    r"cannot (?:fire|run|execute|send)[^.\n]{0,40}without your (?:typed )?yes",
    r"can't (?:fire|run|execute|send)[^.\n]{0,40}without your (?:typed )?yes",
    r"code (?:verifies|checks|confirms) (?:that )?(?:you|the user) typed",
    r"verif(?:y|ies) (?:that )?the user typed",
    r"every live write (?:is|gets) (?:checked|enforced|verified) (?:by|in) code",
]
USER_DOCS = ["PRIVACY.md", "README.md", "commands/execute-action.md"]


def shipped_docs():
    skip = {"CHANGELOG.md"}
    for p in ROOT.rglob("*.md"):
        rel = p.relative_to(ROOT).as_posix()
        if p.name in skip or rel.startswith(("evals/results/", "tests/", "research/")) or "/node_modules/" in rel:
            continue
        yield p


def overclaims_in(text: str) -> list[str]:
    return [pat for pat in OVERCLAIMS if re.search(pat, text, re.I)]


class TestApprovalHonesty(unittest.TestCase):
    def test_no_doc_overclaims_the_gate(self):
        bad = {}
        for p in shipped_docs():
            hits = overclaims_in(p.read_text(encoding="utf-8", errors="replace"))
            if hits:
                bad[p.relative_to(ROOT).as_posix()] = hits
        self.assertEqual(bad, {}, "docs claim more than the approval code proves (see docstring)")

    def test_user_docs_state_both_limits(self):
        for rel in USER_DOCS:
            t = (ROOT / rel).read_text(encoding="utf-8").lower()
            with self.subTest(doc=rel):
                self.assertIn("allowlist", t, "the host permission prompt / allowlist advice is missing")
                self.assertRegex(t, r"mcp[^.\n]{0,120}outside|outside[^.\n]{0,60}code check",
                                 "the MCP-writes-are-outside-the-code-check limit is missing")

    def test_records_do_not_claim_who_approved(self):
        src = (ROOT / "scripts" / "approval-manager.py").read_text(encoding="utf-8")
        self.assertNotRegex(src, r"""\[["']approved_by["']\]\s*=\s*["']user["']""")
        self.assertIn('"approval-step"', src)
        self.assertNotIn("typed-yes-in-chat", src)

    def test_no_auto_confirm_for_live_writes(self):
        t = (ROOT / "skills" / "context-engine" / "approval-framework.md").read_text(encoding="utf-8")
        self.assertNotRegex(t, r"\|\s*\*\*Low\*\*\s*\|\s*Auto-confirm")
        self.assertNotRegex(t, r"Slack notifications and internal messages \| Internal only")

    # ── plant checks ─────────────────────────────────────────────

    def test_plant_overclaims_are_caught(self):
        for s in ("A write cannot fire without your yes.", "The plugin can't send anything without your typed yes",
                  "Code verifies that you typed it.", "every live write is enforced by code"):
            with self.subTest(s=s):
                self.assertTrue(overclaims_in(s))

    def test_plant_honest_wording_passes(self):
        self.assertEqual(overclaims_in(
            "A write the plugin sends cannot fire without a matching approval record; MCP writes are outside "
            "that code check."), [])


if __name__ == "__main__":
    unittest.main()
