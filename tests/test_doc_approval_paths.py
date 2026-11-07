"""No shipped document describes a send or publish that skips approval.

The 2026-11-05 security review (finding 10): reference docs contradicted the enforced flows. The agency
operations guide listed the Weekly Pulse client email with "Approver: None (auto-send)" while
send-report requires a typed yes, and the custom-MCP guide said read tools were "auto-approved by
hooks.json", which has held no such hook since 3.1.0. A model reads docs as instructions, and the brand
profile is a file the model itself writes, so stale prose is attack surface.

Since 3.42.0 this test fails on `auto_publish`, `auto-send` or `auto-approved by hooks` in any shipped
file outside CHANGELOG.md (history stays as written).

Stdlib only.
"""
from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

from _helpers import PLUGIN_ROOT

PHRASES = re.compile(r"auto_publish|auto-send|auto-approved by hooks", re.I)
TEXT_SUFFIXES = {".md", ".py", ".json", ".yaml", ".yml", ".txt", ".toml", ".example", ".reference", ""}
ME = Path(__file__).resolve()


def shipped_files(root: Path = PLUGIN_ROOT) -> list[Path]:
    try:
        listed = subprocess.run(["git", "-C", str(root), "ls-files"], capture_output=True, text=True,
                                check=True, timeout=60).stdout.splitlines()
        paths = [root / p for p in listed]
    except (OSError, subprocess.SubprocessError):
        paths = [p for p in root.rglob("*") if p.is_file() and ".git" not in p.parts]
    return [p for p in paths if p.is_file() and p.name != "CHANGELOG.md" and p.resolve() != ME
            and (p.suffix.lower() in TEXT_SUFFIXES or p.name.startswith(".mcp.json"))]


def approval_free_lines(text: str) -> list[int]:
    return [n for n, line in enumerate(text.splitlines(), 1) if PHRASES.search(line)]


class TestNoApprovalFreePaths(unittest.TestCase):
    def test_shipped_files_describe_no_approval_free_send(self):
        bad = []
        for p in shipped_files():
            try:
                text = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            bad += [f"{p.relative_to(PLUGIN_ROOT).as_posix()}:{n}" for n in approval_free_lines(text)]
        self.assertEqual(bad, [])

    def test_guard_can_fail(self):
        self.assertEqual(approval_free_lines("| Weekly | None (auto-send) |\nok\nauto_publish: true\n"), [1, 3])
        self.assertEqual(approval_free_lines("// Read Tool (auto-approved by hooks.json)"), [1])
        self.assertEqual(approval_free_lines("typed yes per send"), [])


if __name__ == "__main__":
    unittest.main()
