"""Plugin workflow scripts must satisfy the Claude Code workflow runtime.

The runtime (code.claude.com/docs/en/workflows, read 2026-10-04) drops a
workflow from autocomplete unless `export const meta` is the first statement
and a plain literal with a name and description; it makes Date.now(),
Math.random() and a no-argument new Date() throw (so relaunched runs replay
identically); and it rejects scripts containing import(). A workflow also
cannot ask the user anything mid-run, so none may generate paid creative or
publish anything.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parent.parent / "workflows"

FORBIDDEN = {
    "Date.now()": re.compile(r"\bDate\.now\s*\("),
    "Math.random()": re.compile(r"\bMath\.random\s*\("),
    "new Date()": re.compile(r"new\s+Date\s*\(\s*\)"),
    "import()": re.compile(r"\bimport\s*\("),
}
META = re.compile(r"\Aexport const meta = \{(?P<body>.*?)\n\}", re.S)


def problems(text: str, stem: str) -> list[str]:
    out = []
    m = META.match(text)
    if not m:
        return ["`export const meta = {` is not the first statement"]
    body = m.group("body")
    name = re.search(r"\bname:\s*'([^']+)'", body)
    if not name:
        out.append("meta has no literal name")
    elif name.group(1) != stem:
        out.append(f"meta.name {name.group(1)!r} != file name {stem!r}")
    if not re.search(r"\bdescription:\s*'", body):
        out.append("meta has no literal description")
    if re.search(r"\.\.\.|\$\{|\b[A-Za-z_]\w*\(", body):
        out.append("meta contains a non-literal (spread, template or call)")
    for label, rx in FORBIDDEN.items():
        if rx.search(text):
            out.append(f"uses {label}, which the runtime makes throw or reject")
    return out


class TestWorkflowScripts(unittest.TestCase):
    def test_every_workflow_satisfies_the_runtime(self):
        files = sorted(WORKFLOWS.glob("*.js"))
        self.assertTrue(files, "workflows/ has no scripts")
        bad = {}
        for f in files:
            p = problems(f.read_text(encoding="utf-8"), f.stem)
            if p:
                bad[f.name] = p
        self.assertEqual(bad, {}, f"workflow scripts the runtime would reject: {bad}")

    def test_guard_can_fail(self):
        good = "export const meta = {\n  name: 'x',\n  description: 'd',\n}\nreturn 1\n"
        self.assertEqual(problems(good, "x"), [])
        self.assertTrue(problems("const a = 1\n" + good, "x"))
        self.assertTrue(problems(good.replace("return 1", "const t = Date.now()"), "x"))
        self.assertTrue(problems(good, "y"))
        self.assertTrue(problems(good.replace("description: 'd'", "description: makeDesc()"), "x"))


if __name__ == "__main__":
    unittest.main()
