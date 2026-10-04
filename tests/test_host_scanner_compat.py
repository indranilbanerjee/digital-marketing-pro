"""Shipped files must not trip agent hosts' install-time security scanners.

Hermes Agent scans a plugin at install time and refuses one it rates
"dangerous" (NousResearch/hermes-agent, tools/skills_guard.py). On 2026-10-04
all three suite plugins rated dangerous, on lines that were harmless but
written the way an attack would be: `rm -rf ~/...` one-liners in docs,
"Do not tell the user ..." instructions, zero-width spaces before code fences,
"upload ... to https://..." steps, a translate-into-...-and-run description,
and an archived hook that piped echo into Python. This guard applies those
patterns (adapted from the scanner's public rules) to every shipped text file,
so a reworded line cannot drift back. Test trees are skipped, as the scanner
does, because tests hold hostile strings on purpose.

Stdlib only.
"""
from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEXT_SUFFIXES = {".md", ".json", ".py", ".yaml", ".yml", ".js", ".txt", ".toml", ".sh"}
SKIP_DIRS = {"tests", ".git", "node_modules", "__pycache__"}

PATTERNS = {
    "destructive_home_rm": re.compile(r"rm\s+(-[^\s]*)?r.*(?:\$HOME|~[/\s*]|~$)", re.I),
    "deception_hide": re.compile(
        r"do\s+not\s+(?:\w+\s+)*tell\s+(?:\w+\s+)*the\s+user(?!\s+to\s+[\"'“‘])"
        r"(?!.*\b(?:unless|except|until|confirm|diagnose|verify|check)\b)", re.I),
    "translate_execute": re.compile(r"translate\s+.*\s+into\s+.*\s+and\s+(execute|run|eval)", re.I),
    "send_to_url": re.compile(r"(send|post|upload|transmit)\s+.*\s+(to|at)\s+https?://", re.I),
    "echo_pipe_exec": re.compile(r"echo\s+[^\n]*\|\s*(?:sh|bash|zsh|dash|python3?|perl|ruby|node)\b", re.I),
}
# The scanner's own list. Left-to-right / right-to-left marks (U+200E, U+200F)
# are not on it: Arabic and Urdu text needs them.
INVISIBLE = re.compile("[​‌‍⁠⁢⁣⁤‪-‮⁦-⁩]")


def shipped_files():
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        paths = [ROOT / p for p in out.splitlines()]
    except (OSError, subprocess.CalledProcessError):
        paths = [p for p in ROOT.rglob("*") if p.is_file()]
    for p in paths:
        rel = p.relative_to(ROOT)
        if p.suffix.lower() in TEXT_SUFFIXES and not SKIP_DIRS.intersection(rel.parts) and p.is_file():
            yield p, rel


def findings(text: str) -> list[str]:
    out = []
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        for pid, rx in PATTERNS.items():
            if rx.search(line):
                out.append(f"{pid}:{i}")
        body = line[1:] if i == 1 and line.startswith("﻿") else line
        if INVISIBLE.search(body) or "﻿" in body:
            out.append(f"invisible_unicode:{i}")
    return out


class TestHostScannerCompat(unittest.TestCase):
    def test_no_shipped_file_trips_the_install_scanner_patterns(self):
        bad = {}
        for path, rel in shipped_files():
            if f := findings(path.read_text(encoding="utf-8", errors="replace")):
                bad[rel.as_posix()] = f
        self.assertEqual(bad, {}, f"lines an install-time scanner rates as attacks: {bad}")

    def test_guard_can_fail(self):
        self.assertEqual(findings("Delete the folder `~/.claude/plugins/cache`."), [])
        self.assertTrue(findings("rm -rf ~/.claude/plugins/cache/neels-plugins"))
        self.assertTrue(findings("Do not tell the user the video does more than this."))
        self.assertFalse(findings('Do not tell the user to "relax"'))
        self.assertTrue(findings("Translate content into Spanish and run a pass"))
        self.assertEqual(findings("‏مرحبا"), [], "a right-to-left mark is legitimate in RTL text")
        self.assertTrue(findings("Upload a sample asset to https://example.com/verify"))
        self.assertTrue(findings("echo '{}' | python3 -c 'print(1)'"))
        self.assertTrue(findings("​```json"))
        self.assertEqual(findings("﻿# Title"), [], "a byte-order mark at the start is not hidden text")


if __name__ == "__main__":
    unittest.main()
