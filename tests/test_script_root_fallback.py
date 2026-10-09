"""Every skill or command that runs `${CLAUDE_PLUGIN_ROOT}/scripts/...` says where
the scripts are when the host does not set that variable.

Hermes review (NousResearch/hermes-agent#132571): Hermes does not define
`${CLAUDE_PLUGIN_ROOT}`, so `python ${CLAUDE_PLUGIN_ROOT}/scripts/x.py`
expands to `/scripts/x.py` and fails. The fix is one prose line, identical in
ContentForge and SocialForge, that stays correct on every host (Claude Code,
Codex, Cursor and the others set the variable; the line is then just a note).
It lives in skill bodies, not descriptions, so the listing budget is untouched.

Stdlib only.
"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VAR = "${CLAUDE_PLUGIN_ROOT}"
FALLBACK = ("> **Script location.** If your host does not set `${CLAUDE_PLUGIN_ROOT}`, the scripts are in "
            "this plugin's `scripts/` folder, next to `skills/`.")


def missing_fallback(text: str) -> bool:
    """True if the text uses the variable (outside the fallback line) but lacks the line."""
    return VAR in text.replace(FALLBACK, "") and FALLBACK not in text


def checked_files():
    return sorted(list((ROOT / "skills").glob("*/*.md")) + list((ROOT / "commands").glob("*.md")))


class TestScriptRootFallback(unittest.TestCase):
    def test_every_file_using_the_variable_has_the_fallback(self):
        bad = [str(p.relative_to(ROOT)) for p in checked_files()
               if missing_fallback(p.read_text(encoding="utf-8", errors="replace"))]
        self.assertEqual(bad, [], "files that run ${CLAUDE_PLUGIN_ROOT}/scripts/... without the "
                                  "script-location line (see this module's docstring):\n  " + "\n  ".join(bad))

    def test_the_line_is_present_where_expected(self):
        users = [p for p in checked_files() if VAR in p.read_text(encoding="utf-8", errors="replace")]
        self.assertGreaterEqual(len(users), 100, "expected the ~100 script-running skills to be found")

    # ── plant checks ─────────────────────────────────────────────

    def test_plant_missing_line_is_caught(self):
        self.assertTrue(missing_fallback('# X\n\nRun `python "${CLAUDE_PLUGIN_ROOT}/scripts/a.py"`.\n'))

    def test_plant_line_present_passes(self):
        self.assertFalse(missing_fallback('# X\n\n' + FALLBACK + '\n\nRun `python "${CLAUDE_PLUGIN_ROOT}/scripts/a.py"`.\n'))

    def test_plant_file_without_the_variable_is_ignored(self):
        self.assertFalse(missing_fallback("# X\n\nNo scripts here.\n"))


if __name__ == "__main__":
    unittest.main()
