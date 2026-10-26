"""DMP offers a runnable `npx` command only for vendor-published, version-pinned packages.

The failure this prevents: `.mcp.json.example` and the connector registry named
npm packages that did not exist (51 of 73 returned 404 on 2026-10-27), three
that had been unpublished, and several published by third parties, and
connector_resolver handed the agent a paste-ready `npx -y <name>` with the API
keys in its env block. Whoever registers a missing name receives those keys.

So:
  * scripts/_connector_registry.py VERIFIED_NPX_PACKAGES lists the only
    packages DMP ever offers to run: the vendor's own npm account and
    repository, an exact version, a verified_on date.
  * Every runnable entry in .mcp.json.example is on that list and pinned.
  * Every registry connector's package is None or on that list.
  * connector_resolver and connector-status print no npx line and no env block
    for anything else.
  * No shipped doc shows `npx -y <name>` for an unlisted name.
  * The weekly dated-checks job runs scripts/npm_allowlist_check.py against
    registry.npmjs.org; its logic is tested here offline with a fake registry.
Each check has a plant that the old code or data fails.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _connector_registry as reg  # noqa: E402
import connector_resolver as cr  # noqa: E402
import npm_allowlist_check as npmcheck  # noqa: E402

VERIFY_MAX_DAYS = 120
EXACT_VERSION = re.compile(r"^\d+\.\d+\.\d+$")
SKIP_DIRS = {".git", "tests", "research", "evals", "node_modules", "__pycache__"}
SKIP_FILES = {"CHANGELOG.md"}
# `npx -y name` in prose, and `"-y", "name"` in JSON-ish snippets
NPX_PROSE = re.compile(r"npx\s+-y\s+(@?[A-Za-z0-9._/<>-]+(?:@[A-Za-z0-9.<>-]+)?)")
NPX_ARGS = re.compile(r'"-y",\s*"([^"]+)"')


def _status_module():
    spec = importlib.util.spec_from_file_location("connector_status", SCRIPTS / "connector-status.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def split_spec(spec: str) -> tuple[str, str | None]:
    """'@scope/pkg@1.2.3' -> ('@scope/pkg', '1.2.3'); a bare name has version None."""
    at = spec.rfind("@")
    if at > 0:
        return spec[:at], spec[at + 1:]
    return spec, None


def allowlist_problems(table: dict, on: date) -> list[str]:
    out = []
    for pkg, e in table.items():
        if not EXACT_VERSION.match(e.get("version", "")):
            out.append(f"{pkg}: version {e.get('version')!r} is not an exact x.y.z pin")
        for field in ("npm_maintainer", "repository", "vendor", "verified_on"):
            if not e.get(field):
                out.append(f"{pkg}: missing {field}")
        if not str(e.get("repository", "")).startswith("https://"):
            out.append(f"{pkg}: repository must be an https URL")
        if e.get("verified_on"):
            age = (on - date.fromisoformat(e["verified_on"])).days
            if age > VERIFY_MAX_DAYS:
                out.append(f"{pkg}: last verified {e['verified_on']} ({age} days); re-check "
                           f"registry.npmjs.org and the vendor's docs")
    return out


def example_problems(example: dict, table: dict) -> list[str]:
    out = []
    for name, cfg in example.get("mcpServers", {}).items():
        if cfg.get("command") != "npx":
            continue
        specs = [a for a in cfg.get("args", []) if not a.startswith("-")]
        if not specs:
            out.append(f"{name}: npx entry without a package")
            continue
        pkg, version = split_spec(specs[0])
        if pkg not in table:
            out.append(f"{name}: {pkg} is not a vendor-verified package (VERIFIED_NPX_PACKAGES)")
        elif version != table[pkg]["version"]:
            out.append(f"{name}: {pkg} must be pinned as {pkg}@{table[pkg]['version']}, got {specs[0]}")
    return out


def registry_problems(registry: dict, table: dict) -> list[str]:
    out = []
    for cat in registry.values():
        for name, info in cat.get("connectors", {}).items():
            pkg = info.get("package")
            if pkg and pkg not in table:
                out.append(f"{name}: package {pkg} is not vendor-verified; set it to None")
    return out


def prose_problems(root: Path, table: dict) -> list[str]:
    out = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in {".md", ".json", ".example",
                                                       ".connectors-reference", ".yaml", ".yml"}:
            continue
        rel = path.relative_to(root)
        if path.name in SKIP_FILES or set(rel.parts) & SKIP_DIRS:
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for n, line in enumerate(text.splitlines(), 1):
            for rx in (NPX_PROSE, NPX_ARGS):
                for m in rx.finditer(line):
                    spec = m.group(1).rstrip(".,;:)`'\"")
                    if "<" in spec or spec.startswith("-"):
                        continue  # a <placeholder> or a flag
                    pkg, version = split_spec(spec)
                    if pkg not in table or version != table[pkg]["version"]:
                        out.append(f"{rel}:{n}: npx {spec} is not a pinned vendor-verified package")
    return out


class TestAllowlist(unittest.TestCase):

    def test_entries_are_pinned_and_recent(self):
        on = date.fromisoformat(os.environ["DMP_TODAY"]) if os.environ.get("DMP_TODAY") else date.today()
        problems = allowlist_problems(reg.VERIFIED_NPX_PACKAGES, on)
        self.assertEqual(problems, [], "\n  " + "\n  ".join(problems))

    def test_allowlist_check_catches_bad_entries(self):
        bad = {"x": {"version": "^1.0.0", "npm_maintainer": "", "repository": "github.com/x",
                     "vendor": "X", "verified_on": "2026-01-01"}}
        self.assertEqual(len(allowlist_problems(bad, date(2026, 10, 27))), 4)

    def test_verified_npx_args_pins_and_refuses(self):
        self.assertEqual(reg.verified_npx_args("deepl-mcp-server"),
                         ["-y", "deepl-mcp-server@" + reg.VERIFIED_NPX_PACKAGES["deepl-mcp-server"]["version"]])
        for name in ("mcp-pipedrive", "mcp-shopify", "@anthropic/mcp-slack", "", None):
            self.assertIsNone(reg.verified_npx_args(name))


class TestShippedConfig(unittest.TestCase):

    def test_example_runs_only_pinned_vendor_packages(self):
        example = json.loads((REPO / ".mcp.json.example").read_text(encoding="utf-8-sig"))
        problems = example_problems(example, reg.VERIFIED_NPX_PACKAGES)
        self.assertEqual(problems, [], "\n  " + "\n  ".join(problems))
        self.assertTrue(example["mcpServers"], "the example should still show the verified entries")

    def test_example_check_catches_unlisted_and_unpinned(self):
        planted = {"mcpServers": {
            "pipedrive": {"command": "npx", "args": ["-y", "mcp-pipedrive"]},
            "deepl": {"command": "npx", "args": ["-y", "deepl-mcp-server"]},
            "ok": {"command": "npx", "args": ["-y", reg.verified_npx_args("deepl-mcp-server")[1]]},
        }}
        problems = example_problems(planted, reg.VERIFIED_NPX_PACKAGES)
        self.assertEqual(len(problems), 2, problems)

    def test_registry_names_no_unverified_package(self):
        problems = registry_problems(reg.CONNECTOR_REGISTRY, reg.VERIFIED_NPX_PACKAGES)
        self.assertEqual(problems, [], "\n  " + "\n  ".join(problems))

    def test_registry_check_catches_an_unverified_package(self):
        planted = {"crm": {"connectors": {"pipedrive": {"transport": "npx", "package": "mcp-pipedrive"}}}}
        self.assertEqual(len(registry_problems(planted, reg.VERIFIED_NPX_PACKAGES)), 1)

    def test_no_doc_shows_npx_for_an_unlisted_package(self):
        problems = prose_problems(REPO, reg.VERIFIED_NPX_PACKAGES)
        self.assertEqual(problems, [], "\n  " + "\n  ".join(problems))

    def test_prose_check_catches_the_old_wording(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "guide.md").write_text(
                'npx -y mcp-moz --help\n"args": ["-y", "mcp-server-mailchimp"]\n'
                'npx -y deepl-mcp-server\nnpx -y <vendor-package>@<exact-version>\n', encoding="utf-8")
            problems = prose_problems(root, reg.VERIFIED_NPX_PACKAGES)
        self.assertEqual(len(problems), 3, problems)


class TestNoNpxForUnlistedPackages(unittest.TestCase):
    """The two places that print setup snippets: the resolver and connector-status."""

    def _fake(self, package):
        return {"transport": "npx", "package": package, "env_vars": ["EVIL_API_KEY"]}

    def test_resolver_refuses_an_unlisted_package(self):
        with mock.patch.object(cr, "find_connector", return_value=self._fake("mcp-evil")):
            hint = cr._build_setup_hint(["evil"])["setup_options"][0]
        self.assertEqual(hint["transport"], "unavailable")
        dumped = json.dumps(hint)
        self.assertNotIn("npx", dumped)
        self.assertNotIn("EVIL_API_KEY", dumped)

    def test_resolver_pins_an_allowlisted_package(self):
        with mock.patch.object(cr, "find_connector", return_value=self._fake("deepl-mcp-server")):
            hint = cr._build_setup_hint(["deepl"])["setup_options"][0]
        self.assertEqual(hint["transport"], "npx")
        self.assertEqual(hint["step_2_mcp_json_snippet"]["deepl"]["args"],
                         reg.verified_npx_args("deepl-mcp-server"))

    def test_every_registry_connector_hint_is_safe(self):
        for name in reg.list_all_connector_names():
            for hint in cr._build_setup_hint([name])["setup_options"]:
                if hint["transport"] == "npx":
                    pkg, version = split_spec(hint["step_2_mcp_json_snippet"][name]["args"][1])
                    self.assertEqual(version, reg.VERIFIED_NPX_PACKAGES[pkg]["version"], name)

    def test_connector_status_refuses_an_unlisted_package(self):
        status = _status_module()
        fake_registry = {"crm": {"description": "x", "connectors": {"evil": {
            "transport": "npx", "package": "mcp-evil", "description": "Evil",
            "env_vars": ["EVIL_API_KEY"], "skills_unlocked": []}}}}
        with mock.patch.object(status, "CONNECTOR_REGISTRY", fake_registry), \
                mock.patch.object(status, "_load_mcp_json", return_value={}):
            guide = status.setup_guide("evil")
            check = status.check_connector("evil")
            listing = status.list_available()
        for out in (guide, check, listing):
            dumped = json.dumps(out)
            self.assertNotIn("mcp-evil", dumped)
            self.assertNotIn("EVIL_API_KEY", dumped)
            self.assertNotIn('"command": "npx"', dumped)
            self.assertNotIn('"transport": "npx"', dumped)


class TestRegistryCheck(unittest.TestCase):
    """scripts/npm_allowlist_check.py, offline, against a fake registry."""

    ENTRY = {"version": "1.2.3", "npm_maintainer": "vendor-co",
             "repository": "https://github.com/vendor/vendor-mcp", "vendor": "V", "verified_on": "2026-10-27"}

    def _doc(self, maintainers=("vendor-co",), versions=("1.2.3",), repo="git+https://github.com/vendor/vendor-mcp.git"):
        return {"maintainers": [{"name": m} for m in maintainers],
                "versions": {v: {"repository": {"url": repo}} for v in versions}, "time": {}}

    def test_good_entry_passes(self):
        self.assertEqual(npmcheck.check_entry("vendor-mcp", self.ENTRY, lambda p: (200, self._doc())), [])

    def test_plants_fail(self):
        cases = {
            "404": lambda p: (404, None),
            "maintainer": lambda p: (200, self._doc(maintainers=("someone-else",))),
            "version gone": lambda p: (200, self._doc(versions=("1.2.4",))),
            "repo moved": lambda p: (200, self._doc(repo="https://github.com/other/fork")),
        }
        for label, fetcher in cases.items():
            with self.subTest(label):
                self.assertTrue(npmcheck.check_entry("vendor-mcp", self.ENTRY, fetcher))

    def test_unreachable_registry_fails(self):
        def boom(p):
            raise OSError("network down")
        self.assertTrue(npmcheck.check_entry("vendor-mcp", self.ENTRY, boom))

    def test_weekly_workflow_runs_the_check(self):
        wf = (REPO / ".github" / "workflows" / "dated-checks.yml").read_text(encoding="utf-8")
        self.assertRegex(wf, r"schedule:\s*\n\s*- cron: \"[^\"]+\"")
        self.assertIn("python scripts/npm_allowlist_check.py", wf)
        self.assertIn("python tests/run_all.py --dated", wf)
        self.assertIn("gh issue create", wf)
        self.assertIn("issues: write", wf)


if __name__ == "__main__":
    unittest.main()
