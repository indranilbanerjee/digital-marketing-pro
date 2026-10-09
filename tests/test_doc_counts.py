"""Live documentation must not advertise stale skill / agent / command / script counts.

The repo grows faster than the prose describing it: skills, agents and commands are added
release after release while guides keep quoting the counts they were written against.
Counts are derived from the filesystem here, so the only way to satisfy this test is to
fix the prose.

The 2026-08-16 documentation audit found the original guard was pattern-blind: the README
comparison table said "Skills count **158**", claude-interfaces.md said "86 Python
scripts" and "The 158 SKILL.md files", and AGENTS.md pinned v3.17.0 — all rotten, all
invisible to a regex that needed the number directly before one of three nouns. The guard
now also covers scripts, "N SKILL.md files", and comparison-table "Skills count" rows —
and AGENTS.md (auto-loaded by every non-Claude runtime) must carry the current release
version on its surfaces line.

Deliberately NOT flagged:
  - CHANGELOG.md, research/ (dated internal design docs), and any file banner-marked
    HISTORICAL DOCUMENT
  - lines carrying a bold dated version tag ("**v3.9 rebuilt ..."), which narrate a past
    release truthfully and must keep their ship-time numbers
  - sections whose heading names a release, for the same reason
  - ranges and thresholds ("3-5 skills", "<5 agents", "~86 scripts")
  - sentences about a sibling plugin, which has its own counts
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# "163 skills" / "93 Python scripts" but not "3-5 skills", "<5 agents", "v3.19.2 skills".
# 2026-10-04: "18 top-level commands", "18 top-level slash commands" and "24 specialist
# agents" escaped the single optional qualifier and stayed stale after 13 commands were
# folded into their skills; qualifiers now chain.
# 2026-10-10 (Hermes docs sweep): the pattern above could not see "158 Agent Skills", "86 Python
# helpers", "209 stdlib-unittest tests" or "169 reference knowledge files", and AGENTS.md carried
# all four, 6 to 40 releases stale. Nouns are now case-insensitive, "helpers" counts as scripts,
# "Agent" is accepted before "Skills", zero and ranges are not claims, and a '#' before the number
# is a markdown anchor (#14-commands). Connector counts are deliberately NOT guarded here: DMP
# documents several different connector sets (first-party HTTP, registry-backed, executable,
# catalog) and no single filesystem number is "the" count.
COUNT_RE = re.compile(
    r"(?<![-<>~#\d])\b([1-9]\d{0,2})\s+"
    r"(?:(?:Python|top-level|slash|specialist|Claude\s+Code|executable)\s+)*"
    r"(?:Agent\s+(?=skills))?"
    r"(skills|agents|commands|scripts|helpers)\b", re.I)
NOUNS = {"skills": "skills", "agents": "agents", "commands": "commands", "scripts": "scripts",
         "helpers": "scripts"}
# "209 stdlib-unittest tests" and the table cell "**585 stdlib unittest**": the qualifier is itself
# the suite marker.
TESTS_Q_RE = re.compile(r"(?<![-<>~\d])\b(\d{1,4})\s+(?:stdlib[-\s]unittest(?:\s+tests)?|(?:stdlib|unit)\s+tests)\b", re.I)
# "169 reference knowledge files", "Reference knowledge (169 files)", the table cell
# "| Reference knowledge files | ~5 | 169 |" and AGENTS.md's "`skills/<name>/*.md` (169 of them".
REF_RES = (
    re.compile(r"(?<![-<>~#\d])\b([1-9]\d{0,2})\s+reference(?:\s+knowledge)?\s+files\b", re.I),
    re.compile(r"reference knowledge \(([1-9]\d{0,2}) files\)", re.I),
    re.compile(r"reference knowledge files\s*\|[^|]*\|\s*([1-9]\d{0,2})\s*\|", re.I),
    re.compile(r"skills/<name>/\*\.md`\s*\(([1-9]\d{0,2}) of them"),
)
# "The 158 SKILL.md files" — the phrasing the original guard could not see.
# 2026-08-17: backticks ("158 `SKILL.md` files") made the same rot invisible again.
SKILL_MD_RE = re.compile(r"(?<![-<>~\d])\b(\d{1,3})\s+`?SKILL\.md`?\s+files?\b")
# "all 158 marketing skills" / "All 158 DMP skill names" — a qualifier word between
# the number and the noun escaped COUNT_RE (found rotten 2026-08-17, five releases old).
QUALIFIED_SKILLS_RE = re.compile(
    r"(?<![-<>~\d])\b(\d{1,3})\s+(?:marketing\s+skills|DMP\s+skills|DMP\s+skill\s+names)\b")
# "All 209 tests are stdlib-only" — tests was never a guarded noun; found 170 stale.
# In a marketing repo "tests" also means A/B tests ("running 8 tests per quarter"),
# so the number only counts as a suite claim when the same line carries a suite
# marker (stdlib / passing / test suite / unittest).
TESTS_RE = re.compile(
    r"(?<![-<>~\d])\b(\d{1,4})\s+tests\b"
    r"(?=[^.\n]*?\b(?:stdlib|passing|test suite|unittest)\b)")
# "| Skills count | **158** |" — comparison-table row form
TABLE_ROW_RE = re.compile(r"Skills count\s*\|\s*\*\*(\d{1,3})\*\*")
DATED_LINE = re.compile(r"\*\*v\d+\.\d+")
# A heading that narrates a release keeps its ship-time numbers.
RELEASE_HEADING = re.compile(r"^#{1,6}\s.*\bv\d+\.\d+.*", re.I)
RELEASE_HEADING_WORDS = ("release", "earlier", "previous", "what's new", "whats-new",
                         "shipped", "upgrad", "history", "changelog")
HISTORICAL_BANNER = "HISTORICAL DOCUMENT"
SIBLINGS = ("contentforge", "content forge", "socialforge", "social forge")


def ground_truth():
    return {
        "skills": len([d for d in (REPO / "skills").iterdir() if d.is_dir()]),
        "agents": len(list((REPO / "agents").glob("*.md"))),
        "commands": len(list((REPO / "commands").glob("*.md"))),
        "scripts": len(list((REPO / "scripts").glob("*.py"))),
        "tests": sum(
            len(re.findall(r"^\s*def test_", f.read_text(encoding="utf-8"), re.M))
            for f in (REPO / "tests").glob("test_*.py")),
        # reference knowledge files live inside each skill: skills/<name>/*.md except SKILL.md
        "references": len([f for f in (REPO / "skills").rglob("*.md") if f.name != "SKILL.md"]),
    }


def claims_in(line):
    """Every (number, noun, matched text) count claim on one line."""
    found = [(int(m.group(1)), NOUNS[m.group(2).lower()], m.group(0))
             for m in COUNT_RE.finditer(line)]
    found += [(int(m.group(1)), "skills", m.group(0))
              for pat in (SKILL_MD_RE, TABLE_ROW_RE, QUALIFIED_SKILLS_RE)
              for m in pat.finditer(line)]
    found += [(int(m.group(1)), "tests", m.group(0))
              for pat in (TESTS_RE, TESTS_Q_RE) for m in pat.finditer(line)]
    found += [(int(m.group(1)), "references", m.group(0))
              for pat in REF_RES for m in pat.finditer(line)]
    return found


def stale_claims(line, truth):
    """The claims on a line that disagree with the repo."""
    return [(n, noun, shown) for n, noun, shown in claims_in(line) if n != truth[noun]]


def live_docs():
    for f in sorted(REPO.rglob("*.md")):
        if any(p in f.parts for p in (".git", "node_modules", ".pytest_cache", "research")):
            continue
        if f.name == "CHANGELOG.md":
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        if HISTORICAL_BANNER in text[:800]:
            continue
        yield f, text


def _is_release_heading(line):
    if not RELEASE_HEADING.match(line):
        return False
    # A heading that IS a version number labels a release entry outright.
    if re.match(r'#{1,6}\s+v\d+\.\d+', line):
        return True
    low = line.lower()
    return any(w in low for w in RELEASE_HEADING_WORDS)


def live_lines():
    """(file, line number, line) for every live-doc line that states current facts."""
    for f, text in live_docs():
        in_history = False
        for i, line in enumerate(text.splitlines(), 1):
            # Headings reset the state: a release-narrative heading opens a
            # historical run, any other heading closes one.
            if line.lstrip().startswith("#"):
                in_history = _is_release_heading(line.lstrip())
            # A bold dated version tag opens one, and everything after it in this
            # section narrates past releases: the entry's body keeps its ship-time
            # numbers even though the tag sits on an earlier line.
            if DATED_LINE.search(line):
                in_history = True
                continue
            if in_history:
                continue
            low = line.lower()
            if any(s in low for s in SIBLINGS):
                continue
            yield f, i, line


class TestLiveDocCounts(unittest.TestCase):
    def test_no_stale_counts_in_live_docs(self):
        truth = ground_truth()
        stale = []
        for f, i, line in live_lines():
            for n, noun, shown in stale_claims(line, truth):
                stale.append(
                    "%s:%d says '%s' but the repo has %d %s"
                    % (f.relative_to(REPO).as_posix(), i, shown, truth[noun], noun))
        self.assertEqual(stale, [], "Stale counts in live docs:\n  " + "\n  ".join(stale))

    def test_ground_truth_is_sane(self):
        """A miscounted truth would make the guard above vacuous."""
        truth = ground_truth()
        self.assertGreater(truth["skills"], 0)
        self.assertGreater(truth["agents"], 0)
        self.assertGreater(truth["commands"], 0)
        self.assertGreater(truth["scripts"], 0)
        self.assertGreater(truth["tests"], 0)
        self.assertGreater(truth["references"], 0)

    def test_guard_can_fail(self):
        """Plant-check: each new pattern must actually match its rot form."""
        self.assertTrue(SKILL_MD_RE.search("The 158 SKILL.md files can be loaded"))
        self.assertTrue(SKILL_MD_RE.search("DMP's 158 `SKILL.md` files work out-of-the-box"))
        self.assertTrue(TABLE_ROW_RE.search("| Skills count | **158** |"))
        self.assertTrue(COUNT_RE.search("86 Python scripts"))
        self.assertFalse(COUNT_RE.search("~86 scripts"))  # approx stays exempt
        self.assertTrue(COUNT_RE.search("### 18 top-level commands"))
        self.assertTrue(COUNT_RE.search("**18 top-level slash commands**"))
        self.assertTrue(COUNT_RE.search("24 specialist agents"))
        self.assertTrue(QUALIFIED_SKILLS_RE.search("all 158 marketing skills are discoverable"))
        self.assertTrue(QUALIFIED_SKILLS_RE.search("All 158 DMP skill names pass this regex"))
        self.assertTrue(TESTS_RE.search("All 209 tests are stdlib-only"))
        # A/B-testing prose must stay exempt — "tests" is a marketing noun too.
        self.assertFalse(TESTS_RE.search("A team running 8 tests per quarter with a 30% win rate"))
        # 2026-10-10 phrasings (each was invisible to the old patterns)
        self.assertTrue(COUNT_RE.search("158 Agent Skills (the surface area)"))
        self.assertTrue(COUNT_RE.search("86 Python helpers"))
        self.assertTrue(COUNT_RE.search("## 14. All 25 Commands"))
        self.assertTrue(TESTS_Q_RE.search("209 stdlib-unittest tests covering resolve_model"))
        self.assertTrue(TESTS_Q_RE.search("| Tests | **585 stdlib unittest** | unknown |"))
        self.assertFalse(COUNT_RE.search("3-5 skills"))
        self.assertFalse(COUNT_RE.search("expect 0 skills loaded"))

    def test_guard_flags_planted_numbers(self):
        """Plant a wrong number in each phrasing and confirm the guard reports it; the right
        number must pass. A pattern that matches but never reports proves nothing."""
        truth = ground_truth()
        plants = [("%d Agent Skills (the surface area)", "skills"),
                  ("%d Python helpers", "scripts"),
                  ("## 14. All %d Commands", "commands"),
                  ("%d specialist agents", "agents"),
                  ("%d stdlib-unittest tests covering resolve_model", "tests"),
                  ("| Tests | **%d stdlib unittest** | unknown |", "tests"),
                  ("ships with %d reference knowledge files", "references"),
                  ("Reference knowledge (%d files)", "references"),
                  ("| Reference knowledge files | ~5 | %d |", "references"),
                  ("`skills/<name>/*.md` (%d of them", "references")]
        for template, noun in plants:
            wrong = template % (truth[noun] + 7)
            right = template % truth[noun]
            self.assertTrue(stale_claims(wrong, truth), "guard missed a planted '%s'" % wrong)
            self.assertEqual(stale_claims(right, truth), [], "guard rejected '%s'" % right)


class TestExecutorConnectorCounts(unittest.TestCase):
    """The executor's two connector sets, in the phrasings the docs use for them.

    Connector counts in general stay unguarded (see COUNT_RE's note), but the executor
    has exactly two sets with one source of truth, connector_executor.EXECUTE_PROFILES:
    connectors it sends HTTP requests to itself, and OAuth-only or MCP-only connectors it
    returns a manifest for. The README said "25 OAuth connectors" and "25 manifest-ready"
    for two releases after the three official ad-platform MCP servers made it 28.
    """
    PHRASES = (
        (re.compile(r"(?<![-<>~#\d])\b([1-9]\d?)\s+verified\s+(?:HTTP\s+)?connectors\b", re.I), "live"),
        (re.compile(r"(?<![-<>~#\d])\b([1-9]\d?)\s+connectors\s+live\b", re.I), "live"),
        (re.compile(r"(?<![-<>~#\d])\b([1-9]\d?)\s+OAuth(?:-only)?(?:\s+or\s+MCP-only)?\s+connectors\b", re.I), "mcp"),
        (re.compile(r"(?<![-<>~#\d])\b([1-9]\d?)\s+manifest-ready\b", re.I), "mcp"),
    )

    @staticmethod
    def truth():
        import importlib.util
        import sys
        scripts = REPO / "scripts"
        sys.path.insert(0, str(scripts))
        spec = importlib.util.spec_from_file_location("ce_counts", scripts / "connector_executor.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        profiles = mod.EXECUTE_PROFILES
        mcp = sum(1 for v in profiles.values() if v.get("oauth_only"))
        return {"live": len(profiles) - mcp, "mcp": mcp}

    def stale(self, line, truth):
        return [(m.group(0), key) for pat, key in self.PHRASES for m in pat.finditer(line)
                if int(m.group(1)) != truth[key]]

    def test_executor_connector_counts_match_the_executor(self):
        truth, seen, wrong = self.truth(), 0, []
        for f, i, line in live_lines():
            seen += sum(1 for pat, _ in self.PHRASES for _ in pat.finditer(line))
            for shown, key in self.stale(line, truth):
                wrong.append("%s:%d says '%s' but the executor has %d" % (f.relative_to(REPO).as_posix(), i,
                                                                          shown, truth[key]))
        self.assertGreater(seen, 0, "no executor connector count found; the guard is vacuous")
        self.assertEqual(wrong, [])

    def test_guard_flags_planted_numbers(self):
        truth = self.truth()
        self.assertGreater(truth["live"], 0)
        self.assertGreater(truth["mcp"], 0)
        for template, key in (("%d verified HTTP connectors executing end-to-end", "live"),
                              ("Yes — %d connectors live", "live"),
                              ("%d OAuth connectors via MCP manifest", "mcp"),
                              ("%d OAuth-only or MCP-only connectors", "mcp"),
                              ("%d manifest-ready", "mcp")):
            self.assertTrue(self.stale(template % (truth[key] - 3), truth), template)
            self.assertEqual(self.stale(template % truth[key], truth), [], template)


class TestBrandPathCanonical(unittest.TestCase):
    """Brand data lives under ~/.claude-marketing/brands/<slug>/ (_common.brand_dir).

    The README's "Find your output" tree, its FAQ, SECURITY.md and SUBMISSION.md all gave
    ~/.claude-marketing/<brand-slug>/ (a pre-v3.15 layout the code only reads as a legacy
    fallback), with folder names (01-client-inputs/, brand-profile.json,
    PROJECT_INSTRUCTIONS.md) that no script writes.
    """
    WRONG = re.compile(r"~/\.claude-marketing/[<{](?:brand|slug|client)[^/`\s]*[>}]")

    def test_live_docs_use_the_brands_folder(self):
        wrong = ["%s:%d: %s" % (f.relative_to(REPO).as_posix(), i, m.group(0))
                 for f, i, line in live_lines() for m in self.WRONG.finditer(line)]
        self.assertEqual(wrong, [])

    def test_guard_can_fail(self):
        for bad in ("`~/.claude-marketing/<brand-slug>/`", "`~/.claude-marketing/{brand}/executions/`"):
            self.assertTrue(self.WRONG.search(bad), bad)
        self.assertIsNone(self.WRONG.search("`~/.claude-marketing/brands/<brand-slug>/`"))


class TestPythonMinimum(unittest.TestCase):
    """One Python minimum, stated the same way everywhere.

    Before 2026-10-10 the docs disagreed (3.8+ in guides, 3.10+ in the submission bundle)
    while the pinned c2pa-python 0.38.0 needs 3.10. The floor is the highest requires_python
    among the pinned packages (scripts/embed-c2pa.py C2PA_PIN and scripts/requirements.txt); raise FLOOR_MINOR here and in every doc when a pin
    moves. This test cannot reach PyPI, so it keeps the prose consistent, not the pins.
    """
    FLOOR_MINOR = 10
    OPTIONAL_EXTRA_MINOR = None
    OPTIONAL_EXTRA_LINE = None
    STATEMENT = re.compile(r"Python\s+3\.(\d{1,2})\s*(?:\+|or newer)|\b3\.(\d{1,2})\+")

    def statements(self):
        for f, text in live_docs():
            for i, line in enumerate(text.splitlines(), 1):
                if "python" not in line.lower():
                    continue
                for m in self.STATEMENT.finditer(line):
                    yield f, i, int(m.group(1) or m.group(2)), line

    def allowed(self, minor, line):
        if minor == self.FLOOR_MINOR:
            return True
        return bool(self.OPTIONAL_EXTRA_MINOR and minor == self.OPTIONAL_EXTRA_MINOR
                    and self.OPTIONAL_EXTRA_LINE.search(line))

    def test_every_statement_names_the_same_minimum(self):
        seen, wrong = 0, []
        for f, i, minor, line in self.statements():
            seen += 1
            if not self.allowed(minor, line):
                wrong.append("%s:%d says Python 3.%d but the minimum is 3.%d"
                             % (f.relative_to(REPO).as_posix(), i, minor, self.FLOOR_MINOR))
        self.assertGreater(seen, 0, "no Python-minimum statement found; the guard is vacuous")
        self.assertEqual(wrong, [], "Python minimum disagrees:\n  " + "\n  ".join(wrong))

    def test_guard_can_fail(self):
        """Plant-check: the old wrong forms must be seen and rejected."""
        for planted in ("Requires Python 3.8+ with optional dependencies",
                        "- **Python 3.9 or newer** unlocks scoring",
                        "Python version: must be 3.8+"):
            hits = [int(m.group(1) or m.group(2)) for m in self.STATEMENT.finditer(planted)]
            self.assertTrue(hits and not all(self.allowed(h, planted) for h in hits), planted)
        self.assertTrue(all(self.allowed(int(m.group(1) or m.group(2)), "Python 3.%d+" % self.FLOOR_MINOR)
                            for m in self.STATEMENT.finditer("Python 3.%d+" % self.FLOOR_MINOR)))


class TestAgentsContextCurrent(unittest.TestCase):
    """AGENTS.md is auto-loaded by Codex / Cursor / Copilot / Antigravity. Before this
    guard it pinned 'Supported surfaces (v3.17.0)' — thirteen releases stale."""

    def setUp(self):
        self.text = (REPO / "AGENTS.md").read_text(encoding="utf-8")
        self.version = json.loads(
            (REPO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]

    def test_supported_surfaces_version_is_current(self):
        m = re.search(r"Supported surfaces \(v([\d.]+)\)", self.text)
        self.assertIsNotNone(m, "AGENTS.md lost its 'Supported surfaces (vX.Y.Z)' line")
        self.assertEqual(m.group(1), self.version,
                         "AGENTS.md surfaces line pins v%s but the plugin is v%s"
                         % (m.group(1), self.version))

    def test_supported_surfaces_lists_all_native_surfaces(self):
        m = re.search(r"^.*Supported surfaces.*$", self.text, re.M)
        line = m.group(0) if m else ""
        for name in ("Claude Code", "Cowork", "Codex", "Cursor", "Copilot",
                     "Antigravity", "Hermes", "OpenClaw", "Grok"):
            self.assertIn(name, line, "AGENTS.md surfaces line is missing %s" % name)


if __name__ == "__main__":
    unittest.main()
