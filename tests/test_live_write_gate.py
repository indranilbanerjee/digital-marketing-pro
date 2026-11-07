"""No skill or command pre-approves shell access, and the host asks before every live-write step.

The 2026-11-05 security review (finding 2): a live write is three shell commands the model runs itself,
`connector_executor.py --execute` (prepare), `approval-manager.py --action approve`, then `--execute
--approval-id` (fire). 14 skills and commands listed bare `Bash` in `allowed-tools`, which grants every
shell command without a prompt while the skill is active, so inside `execute-action` or `launch-campaign`
nothing reached the host's permission prompt, the one check the model cannot fake.

Since 3.42.0:
  * `allowed-tools` may grant Bash (or PowerShell) only for named scripts in this plugin's scripts/ folder,
    never for approval-manager.py or connector_executor.py, and never unrestricted;
  * hooks/gate_live_writes.py answers "ask" for the prepare, approve, create-standing and fire commands, so
    Claude Code prompts even when an allow rule (a skill's, or one the user saved) would match;
  * both scripts refuse abbreviated options, so `--exec` cannot slip past the hook's spelling check.

Stdlib only.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

from _helpers import PLUGIN_ROOT, run_script

HOOK = PLUGIN_ROOT / "hooks" / "gate_live_writes.py"
GATED_SCRIPTS = ("approval-manager.py", "connector_executor.py")
SCRIPT_RULE = re.compile(r'^(?:Bash|PowerShell)\((?:python3?|py) "\$\{CLAUDE_PLUGIN_ROOT\}/scripts/'
                         r'(?P<script>[A-Za-z0-9_.-]+\.py)" \*\)$')


def frontmatter(text: str) -> str:
    text = text.replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return ""
    end = text.find("\n---\n", 4)
    return text[4:end] if end > 0 else ""


def allowed_tools(text: str) -> list[str]:
    """The `allowed-tools` entries, split on spaces or commas outside parentheses."""
    m = re.search(r"(?m)^allowed-tools:[ \t]*(.*)$", frontmatter(text))
    if not m:
        return []
    out, depth, cur = [], 0, ""
    for ch in m.group(1):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if depth == 0 and ch in " ,\t":
            if cur:
                out.append(cur)
            cur = ""
            continue
        cur += ch
    if cur:
        out.append(cur)
    return out


def grant_problems(entries: list[str]) -> list[str]:
    out = []
    for entry in entries:
        if not re.match(r"^(?:Bash|PowerShell)\b", entry):
            continue
        m = SCRIPT_RULE.match(entry)
        if not m:
            out.append(f"{entry!r} is not limited to one named plugin script")
        elif m.group("script") in GATED_SCRIPTS:
            out.append(f"{entry!r} pre-approves a live-write step")
        elif not (PLUGIN_ROOT / "scripts" / m.group("script")).exists():
            out.append(f"{entry!r} names a script that does not exist")
    return out


def run_hook(stdin: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(HOOK)], input=stdin, capture_output=True, text=True, timeout=30)


def hook_decision(command: str):
    proc = run_hook(json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}))
    if proc.returncode != 0:
        raise AssertionError(f"hook exited {proc.returncode}: {proc.stderr}")
    return json.loads(proc.stdout)["hookSpecificOutput"] if proc.stdout.strip() else None


class TestNoBroadShellGrants(unittest.TestCase):
    FILES = sorted(PLUGIN_ROOT.glob("skills/*/SKILL.md")) + sorted(PLUGIN_ROOT.glob("commands/*.md"))

    def test_no_skill_or_command_grants_unrestricted_or_gated_shell(self):
        bad = {}
        for f in self.FILES:
            problems = grant_problems(allowed_tools(f.read_text(encoding="utf-8")))
            if problems:
                bad[f.relative_to(PLUGIN_ROOT).as_posix()] = problems
        self.assertEqual(bad, {}, "allowed-tools pre-approves shell access the user never sees")

    def test_files_that_run_live_steps_grant_no_shell(self):
        """execute-action and the send/publish/launch skills must reach the prompt for every command."""
        bad = []
        for f in self.FILES:
            text = f.read_text(encoding="utf-8")
            if re.search(r"connector_executor\.py|--action (?:approve|create-standing)\b", text):
                if any(re.match(r"^(?:Bash|PowerShell)\b", e) for e in allowed_tools(text)):
                    bad.append(f.relative_to(PLUGIN_ROOT).as_posix())
        self.assertEqual(bad, [])

    def test_guard_can_fail(self):
        parse = allowed_tools("---\nname: x\nallowed-tools: Read Bash(git log *) Glob\n---\n")
        self.assertEqual(parse, ["Read", "Bash(git log *)", "Glob"])
        for entry in ("Bash", "Bash(*)", "Bash(python *)", "PowerShell",
                      'Bash(python "${CLAUDE_PLUGIN_ROOT}/scripts/approval-manager.py" *)',
                      'Bash(python "${CLAUDE_PLUGIN_ROOT}/scripts/connector_executor.py" *)',
                      'Bash(python "${CLAUDE_PLUGIN_ROOT}/scripts/no-such-script.py" *)'):
            with self.subTest(entry=entry):
                self.assertTrue(grant_problems([entry]), entry)
        self.assertEqual(grant_problems(['Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dm-status.py" *)', "Read"]), [])


class TestGateHook(unittest.TestCase):
    ASK = [
        'python "/p/scripts/approval-manager.py" --brand a --action approve --id x',
        'python3 /p/scripts/approval-manager.py --brand a --action=approve --id x',
        'python /p/scripts/approval-manager.py --brand a --action "create-standing" --data @/tmp/s.json',
        'python "/p/scripts/connector_executor.py" --action internal-kickoff --brand a --execute',
        'python /p/scripts/connector_executor.py --action x --brand a --execute --approval-id ap-1',
        'python /p/scripts/connector_executor.py --brand a --prepare-batch plan.json',
        'python /p/scripts/connector_executor.py --action x --brand a --exec',
        'cd /p/scripts && python connector_executor.py --action x --brand a --execute',
        'SLACK_BOT_TOKEN=x python C:\\p\\scripts\\connector_executor.py --action x --brand a --execute',
    ]
    NO_ASK = [
        'python /p/scripts/connector_resolver.py --action x --brand a',
        'python /p/scripts/connector_executor.py --action x --brand a',
        'python /p/scripts/connector_executor.py --list-executable',
        'python /p/scripts/approval-manager.py --brand a --action list-pending',
        'python /p/scripts/approval-manager.py --brand a --action get-approval --id x',
        'git status',
    ]

    def test_live_steps_force_a_prompt(self):
        for cmd in self.ASK:
            with self.subTest(cmd=cmd):
                out = hook_decision(cmd)
                self.assertIsNotNone(out, cmd)
                self.assertEqual(out["hookEventName"], "PreToolUse")
                self.assertEqual(out["permissionDecision"], "ask")
                self.assertIn("Digital Marketing Pro", out["permissionDecisionReason"])

    def test_other_commands_pass_silently(self):
        for cmd in self.NO_ASK:
            with self.subTest(cmd=cmd):
                self.assertIsNone(hook_decision(cmd), cmd)

    def test_unparseable_input_is_still_checked(self):
        proc = run_hook("not json: python approval-manager.py --action approve --id x")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"], "ask")
        self.assertEqual(run_hook("").stdout, "")

    def test_registered_for_both_shells_and_both_scripts(self):
        doc = json.loads((PLUGIN_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        self.assertEqual(set(doc), {"hooks"})
        groups = doc["hooks"]["PreToolUse"]
        handlers = [(g["matcher"], h) for g in groups for h in g["hooks"]]
        ifs = {h.get("if") for _, h in handlers}
        for tool in ("Bash", "PowerShell"):
            for script in ("approval-manager", "connector_executor"):
                self.assertIn(f"{tool}(*{script}*)", ifs)
        for matcher, h in handlers:
            self.assertIn("Bash", matcher.split("|"))
            self.assertIn("PowerShell", matcher.split("|"))
            self.assertEqual(h["type"], "command")
            self.assertIn("${CLAUDE_PLUGIN_ROOT}/hooks/gate_live_writes.py", h["command"])
        self.assertEqual(set(doc["hooks"]), {"PreToolUse"}, "the gate is the only hook this plugin ships")

    def test_the_registered_command_works_through_a_shell(self):
        """Run the hooks.json command string the way Claude Code does (sh -c, or Git Bash on Windows)."""
        import os
        import shutil
        sh = shutil.which("sh") or shutil.which("bash")
        if not sh:
            self.skipTest("no POSIX shell here")
        doc = json.loads((PLUGIN_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        cmd = doc["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        env = {**os.environ, "CLAUDE_PLUGIN_ROOT": PLUGIN_ROOT.as_posix()}
        live = json.dumps({"tool_input": {"command": "python x/approval-manager.py --brand a --action approve --id i"}})
        proc = subprocess.run([sh, "-c", cmd], input=live, capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"], "ask")
        quiet = subprocess.run([sh, "-c", cmd], input=json.dumps({"tool_input": {"command": "ls"}}),
                               capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual((quiet.returncode, quiet.stdout), (0, ""))


class TestNoAbbreviatedOptions(unittest.TestCase):
    def test_executor_refuses_exec(self):
        proc = run_script("connector_executor.py", "--action", "internal-kickoff", "--brand", "a", "--exec")
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("unrecognized arguments", proc.stderr)

    def test_approval_manager_refuses_act(self):
        proc = run_script("approval-manager.py", "--brand", "a", "--act", "approve", "--id", "x")
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
