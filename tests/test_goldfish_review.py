"""scripts/goldfish-review.py: a zero-context review of a client deliverable (3.41.0).

Borrow 1 of the 2026-10-27 ecosystem review, built the way Brain A asked: a reviewer is
zero-context only if it is handed nothing but the deliverable, the brief and the brand profile,
so the input is a file that holds exactly those three, and a test reads it. The two failures the
Orchestrator named are planted: an unstated budget assumption and a made-up benchmark. A host
without subagents gets a labelled, weaker same-session form, never a silent substitute. The QA
agent gets a goldfish mode instead of a new agent (agent descriptions are an always-on cost).
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _helpers import PLUGIN_ROOT, import_script, run_script  # noqa: E402

gf = import_script("goldfish-review.py", "goldfish_review")

BRIEF = """Client: Acme Anvils. Goal: more B2B demo requests in Q1 2027.
Channels the client named: LinkedIn and Google Search. Start date 2027-01-06.
"""
PLAN = """# Q1 plan for Acme Anvils

We recommend a monthly budget of ₹8 lakh across LinkedIn and Google Search.
The industry average CTR for B2B SaaS on LinkedIn is 0.65%, so we expect strong results.
LinkedIn's own benchmark puts sponsored content CTR near 0.44% (source: LinkedIn Marketing Solutions, 2026).
Target CTR: 1.2%. Assumes a $20k test budget for Google, to confirm with the client.
"""
PROFILE = {"brand_name": "Acme Anvils", "identity": {"tagline": "Forged to last"}}


class _Workspace(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / "cmh"
        brand = self.home / "brands" / "acme-anvils"
        brand.mkdir(parents=True)
        (brand / "profile.json").write_text(json.dumps(PROFILE), encoding="utf-8")
        self.plan = self.root / "q1-plan.md"
        self.plan.write_bytes(PLAN.encode("utf-8"))  # LF, as a deliverable is saved
        self.brief = self.root / "brief.md"
        self.brief.write_bytes(BRIEF.encode("utf-8"))
        self.env = {"HOME": str(self.root / "home"), "USERPROFILE": str(self.root / "home")}

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, *args):
        return run_script("goldfish-review.py", *args, marketing_home=self.home, env=self.env)

    def pack(self, plan=None, brief=None, brand="acme-anvils"):
        args = ["--action", "pack", "--deliverable", plan or self.plan, "--brief", brief or self.brief]
        if brand:
            args += ["--brand", brand]
        proc = self.cli(*args)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return Path(json.loads(proc.stdout)["packet"])

    def check(self, packet):
        proc = self.cli("--action", "check", "--packet", packet)
        return proc.returncode, json.loads(proc.stdout)


class TestPacket(_Workspace):

    def test_the_packet_holds_exactly_the_three_things(self):
        packet_path = self.pack()
        self.assertTrue(str(packet_path).startswith(str(self.home)), "the packet goes in the brand's own folder")
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        self.assertEqual(set(packet), {"deliverable", "brief", "brand_profile"})
        self.assertEqual(packet["deliverable"], {"name": "q1-plan.md", "text": PLAN})
        self.assertEqual(packet["brief"], {"name": "brief.md", "text": BRIEF})
        self.assertEqual(packet["brand_profile"], {"slug": "acme-anvils", "profile": PROFILE})

    def test_without_a_brand_the_profile_is_null(self):
        packet = json.loads(self.pack(brand=None).read_text(encoding="utf-8"))
        self.assertIsNone(packet["brand_profile"])

    def test_a_packet_with_anything_more_is_refused(self):
        packet_path = self.pack()
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        for extra in ({"conversation_summary": "for context"}, ):
            bad = self.root / "bad.json"
            bad.write_text(json.dumps({**packet, **extra}), encoding="utf-8")
            for action in ("check", "prompt"):
                proc = self.cli("--action", action, "--packet", bad)
                self.assertEqual(proc.returncode, 2, proc.stdout)
                self.assertIn("exactly deliverable, brief, brand_profile", json.loads(proc.stdout)["error"])
        nested = dict(packet, brief={"name": "brief.md", "text": BRIEF, "notes": "from the call"})
        bad.write_text(json.dumps(nested), encoding="utf-8")
        self.assertEqual(self.cli("--action", "check", "--packet", bad).returncode, 2)

    def test_bad_input(self):
        self.assertEqual(self.cli("--action", "pack", "--deliverable", self.plan).returncode, 2)  # no brief
        self.assertEqual(self.cli("--action", "check").returncode, 2)
        self.assertEqual(self.cli("--action", "pack", "--deliverable", self.plan, "--brief", self.brief,
                                  "--brand", "no-such-brand").returncode, 2)
        missing = self.cli("--action", "pack", "--deliverable", self.root / "nope.md", "--brief", self.brief)
        self.assertEqual(missing.returncode, 1)
        self.assertEqual(self.cli("--action", "check", "--packet", self.root / "nope.json").returncode, 1)


class TestCheck(_Workspace):

    def test_the_two_planted_failures_are_found(self):
        code, out = self.check(self.pack())
        self.assertEqual(code, 3)
        self.assertEqual(out["verdict"], "blocked")
        kinds = {(f["kind"], f["quote"]) for f in out["findings"]}
        self.assertIn(("unstated_figure", "₹8 lakh"), kinds)       # the unstated budget assumption
        self.assertIn(("uncited_benchmark", "0.65%"), kinds)       # the made-up benchmark
        self.assertEqual(len(out["findings"]), 2, out["findings"])  # the cited rate, the target and the
        #                                                            assumption the plan states all pass
        self.assertEqual({f["line"] for f in out["findings"]}, {3, 4})

    def test_a_figure_the_brief_states_passes_in_any_notation(self):
        brief = self.root / "brief2.md"
        brief.write_text(BRIEF + "Budget: ₹8,00,000 a month. LinkedIn CTR last quarter was 0.65%.\n", encoding="utf-8")
        code, out = self.check(self.pack(brief=brief))
        self.assertEqual((code, out["findings"]), (0, []))
        self.assertEqual(out["verdict"], "clear")

    def test_a_figure_from_the_profile_passes(self):
        profile = dict(PROFILE, business_model={"monthly_marketing_budget": "INR 800000"})
        (self.home / "brands" / "acme-anvils" / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
        code, out = self.check(self.pack())
        self.assertEqual([f["kind"] for f in out["findings"]], ["uncited_benchmark"])

    def test_answering_in_the_document_clears_it(self):
        fixed = PLAN.replace("We recommend a monthly budget of ₹8 lakh",
                             "We assume a monthly budget of ₹8 lakh (for the client to confirm)")
        fixed = fixed.replace("The industry average CTR for B2B SaaS on LinkedIn is 0.65%, so we expect strong results.",
                              "We expect strong results.")
        plan = self.root / "q1-plan-v2.md"
        plan.write_text(fixed, encoding="utf-8")
        self.assertEqual(self.check(self.pack(plan=plan))[0], 0)

    def test_other_currencies_and_units(self):
        out = gf.check({"deliverable": {"name": "d", "text": "Spend $12k on search.\nA 2 crore rupee fund.\n€1.5M for TV.\n"},
                        "brief": {"name": "b", "text": "Search spend: 12,000 USD."}, "brand_profile": None})
        self.assertEqual([f["quote"] for f in out["findings"]], ["2 crore rupee", "€1.5M"])


class TestPrompt(_Workspace):

    def test_the_prompt_names_only_the_packet(self):
        packet = self.pack()
        proc = self.cli("--action", "prompt", "--packet", packet)
        out = json.loads(proc.stdout)
        self.assertEqual(out["mode"], "subagent")
        self.assertEqual(out["agent"], "quality-assurance")
        self.assertTrue(out["prompt"].startswith("GOLDFISH REVIEW"))
        self.assertIn(str(packet), out["prompt"])
        self.assertNotIn("₹8 lakh", out["prompt"])           # the reviewer reads the file, not a paste
        self.assertNotIn(str(self.plan), out["prompt"])       # nor the working copy
        self.assertIn("Add nothing", out["instructions"])

    def test_without_subagents_the_form_is_labelled_weaker(self):
        out = json.loads(self.cli("--action", "prompt", "--packet", self.pack(), "--no-subagents").stdout)
        self.assertEqual(out["mode"], "same-session (weaker)")
        self.assertTrue(out["prompt"].startswith("Ignore everything earlier in this conversation"))
        self.assertIn("never as zero-context", out["instructions"])


class TestDocs(unittest.TestCase):

    def test_the_client_skills_send_the_deliverable_through_it(self):
        for skill in ("client-proposal", "client-report", "exec-summary", "campaign-plan", "media-plan", "qbr-plan"):
            text = (PLUGIN_ROOT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("## Before it goes to the client", text, skill)
            self.assertIn("--goldfish", text, skill)

    def test_check_and_the_qa_agent_carry_the_mode(self):
        check = (PLUGIN_ROOT / "skills" / "check" / "SKILL.md").read_text(encoding="utf-8")
        for phrase in ("goldfish-review.py\" --action pack", "--no-subagents", "same-session review (weaker)",
                       "Add nothing"):
            self.assertIn(phrase, check)
        qa = (PLUGIN_ROOT / "agents" / "quality-assurance.md").read_text(encoding="utf-8")
        self.assertIn("GOLDFISH REVIEW", qa)
        self.assertIn("Read only the packet file", qa)
        self.assertEqual(gf.PROMPT.split("\n", 1)[0].split(".")[0], "GOLDFISH REVIEW")


if __name__ == "__main__":
    unittest.main()
