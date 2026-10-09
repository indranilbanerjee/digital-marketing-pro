"""No plugin manifest may point at a file that does not ship.

The Cursor and Copilot CLI manifests carried `"mcpServers": "./.mcp.json"` (and
`"../../.mcp.json"`) although `.mcp.json` is gitignored and never ships. Cursor discovers
`mcp.json` by default and treats the manifest field as an override of that discovery;
Copilot CLI discovers `.mcp.json` on its own. Neither documents what a missing path does,
so the key was pointless at best and an override of a working default at worst. The
suite's other two plugins carried it until their 2026-10-10 releases; this plugin never did.
The same test runs in all three and keeps any manifest from naming an unshipped file.

A path starting with `./` is relative to the plugin root (Claude Code, Codex, Cursor, Grok,
OpenClaw read it that way); one starting with `../` is relative to the manifest's own folder
(Copilot CLI's `../../skills/`). In a git checkout "ships" means tracked; in an installed
copy (no .git) it means present.
"""
from __future__ import annotations

import json
import posixpath
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

MANIFESTS = (
    ".claude-plugin/plugin.json", ".claude-plugin/marketplace.json",
    ".codex-plugin/plugin.json", ".cursor-plugin/plugin.json", ".github/plugin/plugin.json",
    ".grok-plugin/plugin.json", ".grok-plugin/marketplace.json",
    "plugin.json", "gemini-extension.json", "openclaw.plugin.json", "package.json",
)


def shipped_files() -> set[str]:
    """Every file that ships: tracked files in a checkout, present files in an installed copy."""
    if (REPO / ".git").exists():
        out = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True,
                             encoding="utf-8", check=True).stdout
        return {line for line in out.split("\n") if line}
    return {p.relative_to(REPO).as_posix() for p in REPO.rglob("*") if p.is_file()}


def relative_paths(node):
    """Every string in a parsed manifest that is a ./ or ../ path."""
    if isinstance(node, dict):
        for value in node.values():
            yield from relative_paths(value)
    elif isinstance(node, list):
        for value in node:
            yield from relative_paths(value)
    elif isinstance(node, str) and (node.startswith("./") or node.startswith("../")):
        yield node


def resolve(manifest: str, path: str) -> str:
    """The repo-relative path a manifest value points at."""
    base = "" if path.startswith("./") else posixpath.dirname(manifest)
    return posixpath.normpath(posixpath.join(base, path))


def missing_references(manifest: str, data, shipped: set[str]) -> list[str]:
    out = []
    for path in relative_paths(data):
        target = resolve(manifest, path)
        if target in shipped or any(f.startswith(target.rstrip("/") + "/") for f in shipped):
            continue
        out.append("%s points at %s, which does not ship" % (manifest, path))
    return out


class TestManifestsPointOnlyAtShippedFiles(unittest.TestCase):
    def test_every_relative_path_in_every_manifest_ships(self):
        shipped, seen, problems = shipped_files(), 0, []
        for manifest in MANIFESTS:
            path = REPO / manifest
            if not path.exists():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            seen += len(list(relative_paths(data)))
            problems += missing_references(manifest, data, shipped)
        self.assertGreater(seen, 0, "no relative path found in any manifest; the guard is vacuous")
        self.assertEqual(problems, [], "\n  " + "\n  ".join(problems))

    def test_the_gitignored_mcp_json_is_not_named_by_any_manifest(self):
        for manifest in MANIFESTS:
            path = REPO / manifest
            if path.exists():
                with self.subTest(manifest=manifest):
                    self.assertNotIn(".mcp.json", path.read_text(encoding="utf-8").replace(
                        ".mcp.json.", ""), "a manifest names .mcp.json, which never ships")

    def test_plant_the_old_manifest_references_are_flagged(self):
        shipped = {"skills/a/SKILL.md", "assets/icon.png", ".cursor-plugin/plugin.json"}
        cursor = {"skills": "./skills/", "mcpServers": "./.mcp.json"}
        copilot = {"skills": "../../skills/", "mcpServers": "../../.mcp.json"}
        self.assertEqual(missing_references(".cursor-plugin/plugin.json", cursor, shipped),
                         [".cursor-plugin/plugin.json points at ./.mcp.json, which does not ship"])
        self.assertEqual(missing_references(".github/plugin/plugin.json", copilot, shipped),
                         [".github/plugin/plugin.json points at ../../.mcp.json, which does not ship"])
        good = {"skills": "./skills/", "icon": "./assets/icon.png"}
        self.assertEqual(missing_references(".claude-plugin/plugin.json", good, shipped), [])
        self.assertEqual(resolve(".github/plugin/plugin.json", "../../skills/"), "skills")
        self.assertEqual(resolve(".cursor-plugin/plugin.json", "./skills/"), "skills")


if __name__ == "__main__":
    unittest.main()
