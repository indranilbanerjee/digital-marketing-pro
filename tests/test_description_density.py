"""Skill and command descriptions must be SHORT, front-loaded and unambiguous.

Why short (read this before making descriptions "denser" again)
--------------------------------------------------------------
Claude Code lists every model-invocable skill and command in one listing whose
budget is measured in CHARACTERS, not tokens: context tokens x 4 x 0.01
(`skillListingBudgetFraction`), so 8,000 chars on a 200k window and 40,000 on
1M, shared by every installed plugin; `SLASH_COMMAND_TOOL_CHAR_BUDGET`
overrides it. Each entry costs `- <plugin>:<name>: <description>` plus a
separator. Names always stay; when the total overflows, descriptions are
truncated to a common length (names only below ~20 chars), so a long
description does not route better, it pushes everyone's text off the end.
Verified against Claude Code 2.1.289 on 2026-10-04: with the old 300-900 char
rule DMP alone needed ~126,600 chars and on a 1M window every DMP description
was cut to ~195 chars, so the "Triggers on" clause never reached the model.
The same mistake happened once already in this suite: ContentForge trimmed its
descriptions in March 2026 and an August 2026 density guard (this file's
predecessor, MIN 300 / median 350 / 4+ phrases) pushed them back up because
nobody wrote the reason down. This docstring is that reason.

The rule (Stage 2, 2026-10-09)
------------------------------
- 60-150 chars, median <= 110, and the whole listing (skills + commands, by
  the formula above) <= LISTING_CEILING chars.
- Verb + object + scope first: a token of the skill's own name inside the
  first 100 chars, and the reason to load the skill rather than answer
  freehand (it runs a script, has an approval gate, reads the brand profile).
  The Stage-2 baseline showed every routing miss was under-triggering: the
  model answered in chat instead of loading the skill.
- One quoted user phrase (two at most), owned by exactly one description in
  the plugin.
- No slash alias (the name is already listed), no "Triggers on" label, no
  `when_to_use` field (it is appended to the description and counts).
- Each registered near-miss pair names the other on ONE side only: the broader
  skill points at the narrower one with a bare name, or, where the evals showed
  one side pulling the other's requests, that side carries the pointer.
- Workflows (`workflows/*.js`, `meta.description`) are listed alongside skills
  and commands, so they count toward the ceiling and follow the same rule. The
  Stage-2 after-eval found the competitor-sweep workflow, with a 183-char
  description this guard did not see, taking competitor-analysis requests.

Stdlib only.
"""
from __future__ import annotations

import json
import re
import statistics
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
COMMANDS = ROOT / "commands"
WORKFLOWS = ROOT / "workflows"
NAMESPACE = "digital-marketing-pro"

MIN_LENGTH = 60
MAX_LENGTH = 150
MAX_MEDIAN = 110
LISTING_CEILING = 26_000
MIN_PHRASES, MAX_PHRASES = 1, 2
FRONT_WINDOW = 100
NAME_TOKEN_STOPLIST = frozenset({"check", "plan", "run", "audit", "cf", "sf"})

# First element carries the "→ other" pointer (the broader skill, or the side the evals
# showed pulling the other's requests); the second must not name it back. Pairs come from
# the Stage-2 trigger evals and the phrase collisions.
NEAR_MISS_PAIRS = (
    ("seo-audit", "page-seo-analysis"),
    ("tech-seo-audit", "page-seo-analysis"),
    ("keyword-research", "keyword-cluster"),
    ("rank-monitor", "seo-drift"),
    ("content-engine", "content-brief"),
    ("video-script", "video-packaging"),
    ("creative-testing-framework", "creative-health"),
    ("budget-optimizer", "budget-tracker"),
    ("cohort-analysis", "churn-risk"),
    ("reputation-management", "review-response"),
    ("reputation-management", "crisis-response"),
    ("competitor-analysis", "competitor-monitor"),
    ("performance-report", "anomaly-scan"),
    ("attribution-model", "attribution-report"),
    ("eval-content", "eval-suite"),
    ("localize-campaign", "translate-content"),
    ("client-report", "agency-dashboard"),
    ("language-audit", "hreflang-check"),
    ("digital-pr", "pr-pitch"),
    ("cro", "landing-page-audit"),
    ("audience-intelligence", "audience-profile"),
    ("funnel-architect", "funnel-audit"),
    ("simulate", "what-if"),
    ("competitor-sweep", "competitor-analysis"),
)

DESC_RE = re.compile(r'^description:\s*"((?:[^"\\]|\\.)*)"\s*$', re.M)
WORKFLOW_META_RE = re.compile(r"export const meta = \{(.*?)\n\}", re.S)
WORKFLOW_DESC_RE = re.compile(r"^\s*description:\s*'((?:[^'\\]|\\.)*)'", re.M)
PHRASE_RE = re.compile(r'"([^"]+)"')


# ── pure helpers (the plant checks below exercise these directly) ──────────

def frontmatter(text: str) -> str:
    text = text.replace("\r\n", "\n")
    return text.split("---", 2)[1] if text.startswith("---") else ""


def parse_description(text: str) -> str | None:
    """The single-line double-quoted description, unescaped; None if absent."""
    m = DESC_RE.search(frontmatter(text))
    return json.loads('"' + m.group(1) + '"') if m else None


def parse_workflow_description(js: str) -> str | None:
    """The literal `description` inside a workflow's `export const meta = {...}` block."""
    meta = WORKFLOW_META_RE.search(js)
    m = WORKFLOW_DESC_RE.search(meta.group(1)) if meta else None
    return re.sub(r"\\(.)", r"\1", m.group(1)) if m else None


def phrases(desc: str) -> list[str]:
    return PHRASE_RE.findall(desc)


def normalize_phrase(p: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", p.lower()).strip()


def has_name_token(name: str, desc: str) -> bool:
    tokens = [t for t in name.split("-") if t not in NAME_TOKEN_STOPLIST]
    if not tokens:
        return True
    head = desc[:FRONT_WINDOW].lower()
    return any(re.search(r"\b" + re.escape(t) + (r"\b" if len(t) <= 3 else ""), head) for t in tokens)


def names_skill(desc: str, other: str) -> bool:
    return re.search(r"(?<![\w-])" + re.escape(other) + r"(?![\w-])", desc) is not None


def description_problems(name: str, desc: str) -> list[str]:
    out = []
    if not MIN_LENGTH <= len(desc) <= MAX_LENGTH:
        out.append(f"{len(desc)} chars, outside {MIN_LENGTH}-{MAX_LENGTH}")
    n = len(phrases(desc))
    if not MIN_PHRASES <= n <= MAX_PHRASES:
        out.append(f"{n} quoted phrases, want {MIN_PHRASES}-{MAX_PHRASES}")
    if f"/{NAMESPACE}:" in desc:
        out.append("contains a slash alias (the name is already listed)")
    if "Triggers on" in desc:
        out.append('contains the "Triggers on" label')
    if not has_name_token(name, desc):
        out.append(f"no token of '{name}' in the first {FRONT_WINDOW} chars")
    return out


def frontmatter_problems(text: str) -> list[str]:
    fm = frontmatter(text)
    out = []
    if re.search(r"^when_to_use:", fm, re.M):
        out.append("declares when_to_use (appended to the listing; it counts)")
    if parse_description(text) is None:
        out.append("description is not a single-line double-quoted string")
    return out


def listing_chars(entries: dict[str, str]) -> int:
    """Claude Code's listing cost: '- <ns>:<name>: <description>' plus a newline each."""
    return sum(len(f"- {NAMESPACE}:{name}: {desc}") + 1 for name, desc in entries.items())


def shared_phrases(entries: dict[str, str]) -> dict[str, list[str]]:
    owners: dict[str, list[str]] = {}
    for name, desc in entries.items():
        for p in phrases(desc):
            owners.setdefault(normalize_phrase(p), []).append(name)
    return {p: who for p, who in owners.items() if len(who) > 1}


def pair_problems(entries: dict[str, str], pairs) -> list[str]:
    out = []
    for broad, narrow in pairs:
        if broad not in entries or narrow not in entries:
            out.append(f"{broad}/{narrow}: not both present")
            continue
        if not names_skill(entries[broad], narrow):
            out.append(f"{broad} does not point at {narrow}")
        if names_skill(entries[narrow], broad):
            out.append(f"{narrow} names {broad} back (pointer must be one-sided)")
    return out


# ── the real files ──────────────────────────────────────────────────────────

def skill_files() -> dict[str, Path]:
    return {d.name: d / "SKILL.md" for d in sorted(SKILLS.iterdir())
            if d.is_dir() and (d / "SKILL.md").exists()}


def command_files() -> dict[str, Path]:
    return {p.stem: p for p in sorted(COMMANDS.glob("*.md"))}


def workflow_files() -> dict[str, Path]:
    return {p.stem: p for p in sorted(WORKFLOWS.glob("*.js"))} if WORKFLOWS.is_dir() else {}


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def all_entries() -> dict[str, str]:
    """Every listed entry: skills, commands and workflows."""
    out = {}
    for name, p in {**skill_files(), **command_files()}.items():
        desc = parse_description(read(p))
        if desc is not None:
            out[name] = desc
    for name, p in workflow_files().items():
        desc = parse_workflow_description(read(p))
        if desc is not None:
            out[name] = desc
    return out


class TestNoDeadFrontmatter(unittest.TestCase):
    """`triggers:` is not a Claude Code skill field. Sixteen skills carried
    trigger lists in it that no host ever read. Found 2026-10-04."""

    def test_no_skill_declares_triggers(self):
        bad = [n for n, p in skill_files().items()
               if re.search(r"^triggers:", frontmatter(read(p)), re.M)]
        self.assertEqual(bad, [], f"skills with an unread `triggers:` field: {bad}")


class TestDescriptionRule(unittest.TestCase):
    def test_frontmatter_shape(self):
        bad = {n: pr for n, p in {**skill_files(), **command_files()}.items()
               if (pr := frontmatter_problems(read(p)))}
        self.assertEqual(bad, {}, "frontmatter problems:\n  " +
                         "\n  ".join(f"{n}: {'; '.join(v)}" for n, v in bad.items()))

    def test_every_workflow_description_is_readable(self):
        bad = [n for n, p in workflow_files().items() if parse_workflow_description(read(p)) is None]
        self.assertEqual(bad, [], "workflows whose meta.description this guard cannot read "
                                  "(they would escape the listing ceiling)")

    def test_every_description_follows_the_rule(self):
        bad = {n: pr for n, d in all_entries().items() if (pr := description_problems(n, d))}
        self.assertEqual(bad, {}, "descriptions breaking the Stage-2 rule:\n  " +
                         "\n  ".join(f"{n}: {'; '.join(v)}" for n, v in bad.items()))

    def test_median_stays_short(self):
        med = statistics.median(len(d) for d in all_entries().values())
        self.assertLessEqual(med, MAX_MEDIAN, f"median description length {med} > {MAX_MEDIAN}")

    def test_listing_fits_the_ceiling(self):
        chars = listing_chars(all_entries())
        self.assertLessEqual(chars, LISTING_CEILING,
                             f"listing costs {chars} chars > {LISTING_CEILING} (see module docstring)")

    def test_every_quoted_phrase_has_one_owner(self):
        self.assertEqual(shared_phrases(all_entries()), {},
                         "a quoted user phrase appears in more than one description")

    def test_near_miss_pointers_are_one_sided(self):
        self.assertEqual(pair_problems(all_entries(), NEAR_MISS_PAIRS), [])


class TestPlantedFailures(unittest.TestCase):
    """Each check above, fed a known-bad input, must fail."""

    GOOD = 'Cluster keywords into pillar pages by SERP overlap via script. "cluster these keywords"'

    def test_good_example_passes(self):
        self.assertEqual(description_problems("keyword-cluster", self.GOOD), [])

    def test_length_bounds(self):
        self.assertTrue(description_problems("keyword-cluster", 'Cluster it. "cluster these"'))
        self.assertTrue(description_problems("keyword-cluster", self.GOOD[:-24] + "x" * 80 + ' "cluster these keywords"'))

    def test_phrase_count(self):
        no_phrase = self.GOOD.split(' "')[0] + " for the brand team today."
        three = self.GOOD + ' "a" "b"'
        self.assertTrue(any("phrases" in p for p in description_problems("keyword-cluster", no_phrase)))
        self.assertTrue(any("phrases" in p for p in description_problems("keyword-cluster", three)))

    def test_slash_alias_and_triggers_label(self):
        self.assertTrue(description_problems("keyword-cluster", self.GOOD + f" /{NAMESPACE}:x"))
        self.assertTrue(description_problems("keyword-cluster", "Triggers on " + self.GOOD))

    def test_front_loaded_name_token(self):
        late = ("Group a list of search terms into pillar pages and spokes, with an internal "
                "link map and anchor suggestions; keyword clustering by script.")
        self.assertGreater(late.lower().index("keyword"), FRONT_WINDOW)
        self.assertFalse(has_name_token("keyword-cluster", late))
        self.assertFalse(has_name_token("seo-audit", "Run an audit of the whole site"))  # 'audit' is stoplisted
        self.assertTrue(has_name_token("check", "Anything at all"))  # every token stoplisted

    def test_median_ceiling(self):
        self.assertGreater(statistics.median([100, 111, 140]), MAX_MEDIAN)

    def test_listing_formula(self):
        entries = {"x": "a" * 10}
        self.assertEqual(listing_chars(entries), len(f"- {NAMESPACE}:x: ") + 10 + 1)
        big = {f"s{i}": "d" * MAX_LENGTH for i in range(200)}
        self.assertGreater(listing_chars(big), LISTING_CEILING)

    def test_when_to_use_and_unquoted_description(self):
        self.assertTrue(frontmatter_problems('---\nname: x\ndescription: "ok"\nwhen_to_use: y\n---\n'))
        self.assertTrue(frontmatter_problems("---\nname: x\ndescription: not quoted\n---\n"))
        self.assertEqual(frontmatter_problems('---\nname: x\ndescription: "say \\"hi\\""\n---\n'), [])

    def test_phrase_uniqueness(self):
        dup = {"a": 'One thing. "Check our hreflang tags"', "b": 'Other. "check our hreflang tags!"'}
        self.assertIn("check our hreflang tags", shared_phrases(dup))

    def test_pair_pointer_one_sided(self):
        both = {"wide": "goes → narrow", "narrow": "goes → wide"}
        neither = {"wide": "nothing", "narrow": "nothing"}
        self.assertTrue(pair_problems(both, [("wide", "narrow")]))
        self.assertTrue(pair_problems(neither, [("wide", "narrow")]))
        self.assertEqual(pair_problems({"wide": "→ narrow", "narrow": "x"}, [("wide", "narrow")]), [])
        self.assertFalse(names_skill("see page-seo-analysis-v2", "page-seo-analysis"))

    def test_workflow_description_is_counted(self):
        js = ("export const meta = {\n  name: 'w',\n  description: '" + "x" * 183 + "',\n}\n"
              "const schema = { description: 'not this one' }\n")
        desc = parse_workflow_description(js)
        self.assertEqual(desc, "x" * 183)
        self.assertTrue(description_problems("w", desc))  # over 150 chars
        self.assertIsNone(parse_workflow_description("export const meta = {\n  name: 'w',\n}\n"))

    def test_pointer_detection_ignores_arrow_style(self):
        """The pair check keys on the bare skill name, not on the arrow, so an ASCII
        '->' (the style CF and SF use) or no arrow at all cannot hide a pointer."""
        wrong_side = {"seo-audit": "Full audit. A single page → page-seo-analysis.",
                      "page-seo-analysis": "One URL. Site-wide -> seo-audit."}
        self.assertTrue(pair_problems(wrong_side, [("seo-audit", "page-seo-analysis")]))
        self.assertTrue(names_skill("Site-wide ->seo-audit.", "seo-audit"))
        self.assertTrue(names_skill("see seo-audit for the site", "seo-audit"))
        self.assertFalse(names_skill("Audit via tech-seo-audit only", "seo-audit"))

    def test_registered_pairs_exist(self):
        names = set(skill_files()) | set(workflow_files())
        missing = [p for p in NEAR_MISS_PAIRS if not set(p) <= names]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
