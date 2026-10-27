"""Every connector count in the docs is computed from the file that defines it.

On 2026-10-27 the docs gave four numbers for "connectors" (14 HTTP MCP, 13 HTTP, a catalog of 33,
8 live) while plugin-metadata.py reported 35 HTTP + 3 npx and connector-status 36. They were three
different things, each stated with a stale number:
  * the connector catalog, scripts/_connector_registry.py: what connector-status reports;
  * the ready-to-copy HTTP entries in .mcp.json.connectors-reference (plus the vendor npx entries
    in .mcp.json.example): what plugin-metadata.py reports;
  * the connectors connector_executor.py runs end to end (profiles without oauth_only), and the
    rest of the catalog, which is manifest-ready.
Each phrasing below is tied to one of them.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import _connector_registry as registry  # noqa: E402
import connector_executor as executor  # noqa: E402


def counts() -> dict:
    ref = json.loads((REPO / ".mcp.json.connectors-reference").read_text(encoding="utf-8-sig"))
    servers = ref.get("mcpServers_reference") or ref.get("mcpServers") or {}
    example = json.loads((REPO / ".mcp.json.example").read_text(encoding="utf-8-sig")).get("mcpServers", {})
    live = [k for k, v in executor.EXECUTE_PROFILES.items() if not v.get("oauth_only")]
    return {
        "http": sum(1 for v in servers.values() if isinstance(v, dict) and v.get("type") == "http"),
        "npx": sum(1 for v in example.values() if isinstance(v, dict) and v.get("command") == "npx"),
        "catalog": len(registry.list_all_connector_names()),
        "categories": len(registry.CONNECTOR_REGISTRY),
        "live": len(live),
        "manifest": len(executor.EXECUTE_PROFILES) - len(live),
    }


PHRASES = [  # (pattern with one or two number groups, keys they must equal)
    (r"(\d+) HTTP (?:MCP )?connectors", ("http",)),
    (r"(\d+) ready-to-copy HTTP", ("http",)),
    (r"(\d+) vendor npx entries", ("npx",)),
    (r"catalog of (\d+) connectors, (\d+) categories", ("catalog", "categories")),
    (r"(\d+) connectors in the catalog", ("catalog",)),
    (r"(\d+) connectors live, (\d+) manifest-ready", ("live", "manifest")),
    (r"from Python \((\d+) connectors", ("live",)),
    (r"send-and-receive for the (\d+) connectors", ("live",)),
]
LIVE_DOCS = ["README.md", "AGENTS.md", "CONNECTORS.md", "docs/*.md", "skills/*/SKILL.md", "commands/*.md",
             "skills/context-engine/*.md"]


def stale(root: Path, numbers: dict) -> list[str]:
    out = []
    files = sorted({p for pattern in LIVE_DOCS for p in root.glob(pattern)})
    for path in files:
        for n, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            for pattern, keys in PHRASES:
                for m in re.finditer(pattern, line):
                    got = tuple(int(g) for g in m.groups())
                    want = tuple(numbers[k] for k in keys)
                    if got != want:
                        out.append(f"{path.relative_to(root)}:{n}: '{m.group(0)}' should say {want}")
    return out


class TestConnectorCounts(unittest.TestCase):

    def test_docs_state_the_computed_counts(self):
        problems = stale(REPO, counts())
        self.assertEqual(problems, [], "\n  " + "\n  ".join(problems))

    def test_the_three_things_add_up(self):
        c = counts()
        self.assertEqual(c["live"] + c["manifest"], c["catalog"])  # every catalog entry has a profile

    def test_plant(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "README.md").write_text("### 14 HTTP MCP connectors\n(catalog of 33 connectors, 11 categories)\n",
                                              encoding="utf-8")
            got = stale(Path(tmp), {"http": 35, "npx": 3, "catalog": 36, "categories": 11, "live": 8, "manifest": 28})
        self.assertEqual(len(got), 2, got)


if __name__ == "__main__":
    unittest.main()
