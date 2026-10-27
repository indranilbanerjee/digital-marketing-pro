"""Self-containment guard: no part of the plugin may delegate a capability to a
sibling plugin.

Rule (2026-07-12): each plugin in the suite is fully standalone. Cross-promotion
(links to the author's other repos, marketplace install lines, suite branding in
the shared-registry infra) is fine; capability delegation is not.

Shipped in v3.15.1 for skills/agents/commands; extended 2026-07-29 to cover
docs/, scripts/, and root docs after the full-repo audit found leaks the
original scope missed (docs/c2pa-production-cert-guide.md, AGENTS.md,
scripts/output-publisher.py, docs/engagement-methodology.md).
"""
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SIBLING_PATTERN = re.compile(
    r"socialforge|social-forge|contentforge|content-forge", re.IGNORECASE
)

# The functional surface: capability delegation here is always a violation.
SURFACE_DIRS = ("skills", "agents", "commands")

# Extended scope: docs, scripts, and root-level docs. Same rule, with a
# cross-promotion allowlist below.
EXTENDED_DIRS = ("docs", "scripts")
ROOT_FILES = (
    "README.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "SUBMISSION.md",
    "TESTING-GUIDE.md",
    "CONNECTORS.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
)
EXTENDED_SUFFIXES = {".md", ".py", ".sh", ".yaml", ".yml"}

# Files that legitimately reference the sibling repos (shared model-registry
# distribution infrastructure — build tooling, not capability delegation).
FILE_ALLOWLIST = {
    "scripts/sync_model_registry.sh",
    "scripts/registry_mirror.py",
    "scripts/model_registry.json",
}

# Line-level allowlist: cross-promotion is fine anywhere. A line mentioning a
# sibling is allowed only if it is clearly promo/infra, i.e. contains one of:
LINE_ALLOW_MARKERS = (
    "github.com/indranilbanerjee/",  # links to the author's other repos
    "/plugin install",               # marketplace install commands
)

# Deliberate one-off exceptions, as "relative/path.md:token" (none today).
ALLOWLIST: set = set()


def _scan(files):
    violations = []
    for f in files:
        rel = f.relative_to(REPO).as_posix()
        if rel in FILE_ALLOWLIST:
            continue
        for i, line in enumerate(
            f.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            m = SIBLING_PATTERN.search(line)
            if not m:
                continue
            if any(marker in line for marker in LINE_ALLOW_MARKERS):
                continue
            if f"{rel}:{m.group(0).lower()}" in ALLOWLIST:
                continue
            violations.append(f"{rel}:{i}: {line.strip()[:100]}")
    return violations


class TestSelfContainment(unittest.TestCase):
    def test_no_sibling_plugin_references_in_functional_surface(self):
        files = []
        for d in SURFACE_DIRS:
            root = REPO / d
            if root.is_dir():
                files.extend(sorted(root.rglob("*.md")))
        violations = _scan(files)
        self.assertEqual(
            violations,
            [],
            "Sibling-plugin references found in the functional surface "
            "(skills must be self-contained — see CHANGELOG v3.15.1):\n"
            + "\n".join(violations),
        )

    def test_no_sibling_plugin_references_in_docs_scripts_and_root(self):
        files = []
        for d in EXTENDED_DIRS:
            root = REPO / d
            if root.is_dir():
                files.extend(
                    f
                    for f in sorted(root.rglob("*"))
                    if f.is_file() and f.suffix.lower() in EXTENDED_SUFFIXES
                )
        for name in ROOT_FILES:
            f = REPO / name
            if f.is_file():
                files.append(f)
        violations = _scan(files)
        self.assertEqual(
            violations,
            [],
            "Sibling-plugin references found outside the functional surface "
            "(docs/scripts/root must also be self-contained; cross-promo lines "
            "must carry a repo link or install command):\n" + "\n".join(violations),
        )


if __name__ == "__main__":
    unittest.main()
