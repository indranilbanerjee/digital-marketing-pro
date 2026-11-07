"""A CI job that holds a secret runs only pinned code.

The 2026-11-05 security review (finding 11): the Tessl review job installed `@tessl/cli` unpinned while
holding TESSL_API_KEY and a token with PR write access, so whatever the registry served next would
run with both. Since 3.42.0, in every workflow job that reads a repository secret other than the
built-in GITHUB_TOKEN:
  * every `uses:` action is pinned to a full 40-character commit SHA;
  * every `npm install -g` / `npx` package names an exact version.

Stdlib only (no YAML parser: jobs are split on their two-space-indented keys under `jobs:`).
"""
from __future__ import annotations

import re
import unittest

from _helpers import PLUGIN_ROOT

WORKFLOWS = sorted((PLUGIN_ROOT / ".github" / "workflows").glob("*.y*ml"))
SECRET = re.compile(r"secrets\.(?!GITHUB_TOKEN\b)[A-Z0-9_]+")
USES = re.compile(r"(?m)^\s*-?\s*uses:\s*([^\s#]+)")
NPM = re.compile(r"(?m)\b(?:npm\s+(?:install|i)\s+(?:-g\s+|--global\s+)?(?:--[\w-]+\s+)*|npx\s+(?:-y\s+|--yes\s+)?)"
                 r"(@?[\w./-]+(?:@[\w.^~<>=*-]+)?)")
EXACT = re.compile(r"^(?:@[\w.-]+/)?[\w.-]+@\d+\.\d+\.\d+$")


def jobs_of(text: str) -> dict[str, str]:
    text = text.replace("\r\n", "\n")
    m = re.search(r"(?m)^jobs:\s*$", text)
    if not m:
        return {}
    body = text[m.end():]
    parts = re.split(r"(?m)^  ([A-Za-z0-9_-]+):\s*$", body)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def problems(job_text: str) -> list[str]:
    if not SECRET.search(job_text):
        return []
    out = []
    for action in USES.findall(job_text):
        if action.startswith("./"):
            continue
        if not re.search(r"@[0-9a-f]{40}$", action):
            out.append(f"action {action} is not pinned to a commit SHA")
    for pkg in NPM.findall(job_text):
        if not EXACT.match(pkg):
            out.append(f"package {pkg} has no exact version")
    return out


class TestSecretJobsArePinned(unittest.TestCase):
    def test_workflows(self):
        bad = {}
        for wf in WORKFLOWS:
            for name, job in jobs_of(wf.read_text(encoding="utf-8")).items():
                if p := problems(job):
                    bad[f"{wf.name}:{name}"] = p
        self.assertEqual(bad, {})

    def test_the_tessl_job_is_covered(self):
        jobs = jobs_of((PLUGIN_ROOT / ".github" / "workflows" / "skill-review.yml").read_text(encoding="utf-8"))
        self.assertIn("review", jobs)
        self.assertTrue(SECRET.search(jobs["review"]))
        self.assertIn("@tessl/cli@", jobs["review"])

    def test_guard_can_fail(self):
        job = ("    steps:\n      - uses: actions/checkout@v4\n      - run: npm install -g @tessl/cli\n"
               "        env:\n          K: ${{ secrets.TESSL_API_KEY }}\n")
        self.assertEqual(len(problems(job)), 2)
        ok = job.replace("@v4", "@" + "a" * 40).replace("@tessl/cli", "@tessl/cli@0.119.0")
        self.assertEqual(problems(ok), [])
        self.assertEqual(problems(job.replace("secrets.TESSL_API_KEY", "secrets.GITHUB_TOKEN")), [])


if __name__ == "__main__":
    unittest.main()
