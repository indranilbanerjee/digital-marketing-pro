"""Agent descriptions are short, front-loaded, and still route to the right agent.

Why short: Claude Code lists every agent with its FULL description in every
session, unlike skill descriptions, which are truncated to share a budget. In
`claude plugin details` (CLI 2.1.311, 2026-10-27) DMP's 24 agents cost about
3,210 always-on tokens, and the ten most expensive rows were all agents
(140-180 tokens each), because each description ran 200-470 characters of
"Invoke when the user needs help with ... Triggers on requests involving ...".
The same 60-150 character rule as skills (test_description_density.py)
applies, with the reason to pick the agent first.

What keeps routing intact (the delegation checks):
  * ROUTING: the request words that should send work to each agent must stay
    in its description. Trimming that drops "attribution" from
    analytics-analyst or "journalist" from pr-outreach fails here.
  * POINTERS: near-miss pairs name the other agent on one side only.
  * Every agent a skill lists under "## Agents Used" exists, and every agent
    is named by at least one skill, command or other agent.
Stdlib only.
"""
from __future__ import annotations

import json
import re
import statistics
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENTS = ROOT / "agents"

MIN_LENGTH, MAX_LENGTH, MAX_MEDIAN = 60, 150, 135
FRONT_WINDOW = 100
NAME_STOPLIST = frozenset({"agent", "specialist", "manager"})
BOILERPLATE = ("Invoke when", "Use when", "Triggers on")

ROUTING = {
    "agency-operations": ["client", "portfolio", "credential"],
    "analytics-analyst": ["kpi", "attribution", "dashboard"],
    "brand-guardian": ["brand", "compliance", "accessibility"],
    "competitive-intel": ["competitor", "share of voice"],
    "content-creator": ["blog", "ad copy", "email"],
    "crm-manager": ["crm", "lead", "pipeline"],
    "cro-specialist": ["conversion", "landing page", "a/b test"],
    "email-specialist": ["email", "deliverability", "automation"],
    "execution-coordinator": ["publish", "launch", "approval"],
    "growth-engineer": ["product-led", "referral", "retention"],
    "influencer-manager": ["influencer", "creator", "ftc"],
    "intelligence-curator": ["learnings", "playbook"],
    "journey-orchestrator": ["journey", "nurture"],
    "localization-specialist": ["translation", "transcreation", "hreflang"],
    "market-intelligence": ["economic", "regulatory", "algorithm"],
    "marketing-scientist": ["mix model", "incrementality", "causal"],
    "marketing-strategist": ["strategy", "budget", "go-to-market"],
    "media-buyer": ["paid", "bidding", "budget pacing"],
    "memory-manager": ["store", "index", "memory"],
    "performance-monitor-agent": ["anomaly", "pacing", "real-time"],
    "pr-outreach": ["press release", "journalist", "pr"],
    "quality-assurance": ["eval", "hallucination"],
    "seo-specialist": ["seo", "keyword", "ai answers"],
    "social-media-manager": ["social", "community", "calendar"],
}

# (side that carries the pointer, side that must not name it back)
POINTERS = (
    ("market-intelligence", "competitive-intel"),
    ("growth-engineer", "cro-specialist"),
    ("memory-manager", "intelligence-curator"),
)

DESC_RE = re.compile(r'^description:\s*"((?:[^"\\]|\\.)*)"\s*$', re.M)


def frontmatter(text: str) -> str:
    text = text.replace("\r\n", "\n")
    return text.split("---", 2)[1] if text.startswith("---") else ""


def parse_description(text: str) -> str | None:
    m = DESC_RE.search(frontmatter(text))
    return json.loads('"' + m.group(1) + '"') if m else None


def has_name_token(name: str, desc: str) -> bool:
    head = desc[:FRONT_WINDOW].lower()
    tokens = [t for t in name.split("-") if t not in NAME_STOPLIST]
    return any(re.search(r"\b" + re.escape(t) + (r"\b" if len(t) <= 3 else ""), head) for t in tokens)


def names(desc: str, other: str) -> bool:
    return re.search(r"(?<![\w-])" + re.escape(other) + r"(?![\w-])", desc) is not None


def description_problems(name: str, desc: str | None) -> list[str]:
    if desc is None:
        return ["description is not a single-line double-quoted string"]
    out = []
    if not MIN_LENGTH <= len(desc) <= MAX_LENGTH:
        out.append(f"{len(desc)} chars, outside {MIN_LENGTH}-{MAX_LENGTH}")
    for phrase in BOILERPLATE:
        if phrase in desc:
            out.append(f'contains "{phrase}" boilerplate')
    if not has_name_token(name, desc):
        out.append(f"no token of '{name}' in the first {FRONT_WINDOW} chars")
    for word in ROUTING.get(name, []):
        if word not in desc.lower():
            out.append(f"lost routing word '{word}'")
    return out


def pointer_problems(descs: dict[str, str]) -> list[str]:
    out = []
    for carrier, target in POINTERS:
        if not names(descs[carrier], target):
            out.append(f"{carrier} does not point at {target}")
        if names(descs[target], carrier):
            out.append(f"{target} names {carrier} back (pointer must be one-sided)")
    return out


def agent_descriptions() -> dict[str, str | None]:
    return {p.stem: parse_description(p.read_text(encoding="utf-8")) for p in sorted(AGENTS.glob("*.md"))}


class TestAgentDescriptions(unittest.TestCase):

    def test_every_agent_has_a_routing_entry(self):
        self.assertEqual(sorted(agent_descriptions()), sorted(ROUTING))

    def test_descriptions_follow_the_rule(self):
        problems = [f"{n}: {p}" for n, d in agent_descriptions().items() for p in description_problems(n, d)]
        self.assertEqual(problems, [], "\n  " + "\n  ".join(problems))

    def test_median_length(self):
        lengths = [len(d) for d in agent_descriptions().values() if d]
        self.assertLessEqual(statistics.median(lengths), MAX_MEDIAN)

    def test_near_miss_pointers_are_one_sided(self):
        problems = pointer_problems(agent_descriptions())
        self.assertEqual(problems, [], "\n  " + "\n  ".join(problems))

    def test_plants(self):
        old = ("Invoke when the user needs help with marketing measurement, KPI definition, dashboard design, "
               "attribution reporting, performance analysis, competitive benchmarking, or translating data into "
               "marketing decisions. Triggers on requests involving metrics, reporting, analytics setup, or data "
               "interpretation.")
        self.assertGreaterEqual(len(description_problems("analytics-analyst", old)), 3)
        dropped = "Marketing analytics: KPI definition, dashboards, performance analysis, and turning data into decisions."
        self.assertIn("lost routing word 'attribution'", description_problems("analytics-analyst", dropped))
        descs = dict(agent_descriptions())
        descs["competitive-intel"] += " Macro trends → market-intelligence."
        self.assertTrue(pointer_problems(descs))


class TestDelegationTargetsExist(unittest.TestCase):

    def test_agents_used_sections_name_real_agents(self):
        real = set(agent_descriptions())
        unknown = []
        for skill in sorted((ROOT / "skills").glob("*/SKILL.md")):
            m = re.search(r"^## Agents Used\s*\n(.*?)(?=^## |\Z)", skill.read_text(encoding="utf-8"), re.S | re.M)
            if m:
                unknown += [f"{skill.parent.name}: {n}" for n in re.findall(r"^- \*\*([a-z0-9-]+)\*\*", m.group(1), re.M)
                            if n not in real]
        self.assertEqual(unknown, [], "\n  " + "\n  ".join(unknown))

    def test_every_agent_is_reachable(self):
        corpus = ""
        for folder in ("skills", "commands", "agents"):
            for p in (ROOT / folder).rglob("*.md"):
                text = p.read_text(encoding="utf-8")
                corpus += text.split("---", 2)[-1] if folder == "agents" else text  # an agent's own frontmatter doesn't count
        unreachable = [n for n in agent_descriptions() if not names(corpus, n)]
        self.assertEqual(unreachable, [], "agents no skill, command or agent names: " + ", ".join(unreachable))


if __name__ == "__main__":
    unittest.main()
