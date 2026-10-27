"""The example commands in skills/*/SKILL.md run.

The examples at budget-optimizer/SKILL.md and exec-summary/SKILL.md exited 2 on their first run
(each channel needed conversions and revenue), so an agent that followed the skill failed before
it recovered from the error. This runs every concrete example offline, in a sandbox HOME with a
brand called acme: no traceback, and no exit 2 (a usage or input error).

Common placeholders are filled ({slug} -> acme, {amount} -> 100000, {YYYY-MM} -> 2026-10). An
example is skipped when a placeholder is left, when it installs packages or fetches from the
network, or when it reads an input file this sandbox doesn't have. The test also checks that a
minimum number of examples ran, so it can't pass by skipping everything.
"""
from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"

CMD = re.compile(r'python3?\s+"\$\{CLAUDE_PLUGIN_ROOT\}/scripts/([\w.-]+\.py)"(.*)')
FILL = {"{slug}": "acme", "{brand}": "acme", "{brand_slug}": "acme", "{brand-slug}": "acme", "{amount}": "100000",
        "{YYYY-MM}": "2026-10", "{budget}": "100000", "{period}": "2026-10"}
SKIP_WORDS = ("--install", "--fetch", "--execute", "--api", "pip ", "|", ">", "&&")
# Options whose value is an input file or folder.
FILE_OPTIONS = {"--file", "--robots", "--html", "--feed", "--acp-feed", "--baseline", "--current", "--keywords",
                "--serps", "--draft", "--source", "--content-file", "--validation-file", "--input", "--evidence",
                "--gsc-export", "--ours", "--competitors-file", "--links", "--csv", "--export"}
MIN_RUN = 45  # 54 ran on 2026-10-28; a drop means the extractor broke


def examples() -> list:
    """(skill, script, args) for every example command, continuation lines joined."""
    out = []
    for path in sorted((REPO / "skills").glob("*/SKILL.md")):
        lines = path.read_text(encoding="utf-8").splitlines()
        joined, buf = [], ""
        for line in lines:
            if line.rstrip().endswith("\\"):
                buf += line.rstrip()[:-1] + " "
                continue
            joined.append(buf + line)
            buf = ""
        for line in joined:
            for chunk in re.findall(r"`([^`]*python[^`]*)`", line) or [line]:
                m = CMD.search(chunk)
                if m:
                    out.append((path.parent.name, m.group(1), m.group(2).strip()))
    return out


def runnable(args: str):
    """The argument list to run, or None with the reason to skip."""
    for k, v in FILL.items():
        args = args.replace(k, v)
    if re.search(r"[{<]\s*[A-Za-z_]|\.\.\.|\[--", args) or "{N}" in args:
        return None, "placeholder"
    if any(w in args for w in SKIP_WORDS):
        return None, "installs, fetches, writes elsewhere or pipes"
    try:
        argv = shlex.split(args)
    except ValueError:
        return None, "not one shell command"
    for i, a in enumerate(argv):
        if a.split("=", 1)[0] in FILE_OPTIONS:
            return None, "reads an input file"
    return argv, None


class TestSkillExamplesRun(unittest.TestCase):

    def test_every_concrete_example_runs(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        home = tmp / "home"
        home.mkdir()
        env = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY") and k not in ("CLAUDE_PLUGIN_DATA", "PLUGIN_DATA")}
        env.update(HOME=str(home), USERPROFILE=str(home), CLAUDE_MARKETING_HOME=str(home / ".claude-marketing"),
                   CLAUDE_PLUGIN_ROOT=str(REPO), MODEL_ROUTER_OFFLINE="1",
                   HTTP_PROXY="http://127.0.0.1:9", HTTPS_PROXY="http://127.0.0.1:9", NO_PROXY="")
        subprocess.run([sys.executable, str(SCRIPTS / "setup.py"), "--create-brand", "Acme"], capture_output=True,
                       env=env, cwd=str(tmp), timeout=120)
        ran, failed, seen = 0, [], set()
        for skill, script, args in examples():
            argv, why = runnable(args)
            if argv is None or (script, tuple(argv)) in seen:
                continue
            seen.add((script, tuple(argv)))
            proc = subprocess.run([sys.executable, str(SCRIPTS / script), *argv], capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", env=env, cwd=str(tmp), timeout=120)
            ran += 1
            out = proc.stdout + proc.stderr
            if proc.returncode == 2 or "Traceback" in out:
                failed.append(f"{skill}: {script} {args[:120]} -> rc {proc.returncode}: {out.strip()[-300:]}")
        self.assertEqual(failed, [], "\n" + "\n".join(failed))
        self.assertGreaterEqual(ran, MIN_RUN, f"only {ran} examples ran")

    def test_the_two_reported_examples_are_in_the_run(self):
        names = {(s, a.split()[0] if a else "") for s, _, a in examples()}
        found = {s for s, script, a in examples() if runnable(a)[0] is not None
                 and script in ("budget-optimizer.py", "roi-calculator.py") and s in ("budget-optimizer", "exec-summary")}
        self.assertEqual(found, {"budget-optimizer", "exec-summary"}, names)


if __name__ == "__main__":
    unittest.main()
