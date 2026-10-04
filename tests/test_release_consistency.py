"""Release-consistency tests — catches cross-manifest drift before it ships.

These tests fail when:
- The 8 platform manifests (6 Claude-family incl. Grok + Hermes + OpenClaw) get out of version sync
- The Grok marketplace manifest (.grok-plugin/marketplace.json) drifts from the canonical version
- The README version badge falls behind plugin.json
- The CHANGELOG's latest entry doesn't match the current plugin version
- The test-count badge in the README is stale
- A native platform's install command goes missing from the README
- A README internal anchor link points at a non-existent heading
- Critical README sections (What's new, Who this is for, Supported surfaces, FAQ) go missing
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
README = PLUGIN_ROOT / "README.md"
CHANGELOG = PLUGIN_ROOT / "CHANGELOG.md"

PLATFORM_MANIFESTS_JSON = [
    PLUGIN_ROOT / ".claude-plugin" / "plugin.json",
    PLUGIN_ROOT / ".codex-plugin" / "plugin.json",
    PLUGIN_ROOT / ".cursor-plugin" / "plugin.json",
    PLUGIN_ROOT / ".github" / "plugin" / "plugin.json",
    PLUGIN_ROOT / ".grok-plugin" / "plugin.json",
    PLUGIN_ROOT / "gemini-extension.json",
    PLUGIN_ROOT / "openclaw.plugin.json",
    PLUGIN_ROOT / "package.json",
]
GROK_MARKETPLACE = PLUGIN_ROOT / ".grok-plugin" / "marketplace.json"
PLUGIN_YAML = PLUGIN_ROOT / "plugin.yaml"
HERMES_ADAPTER_PY = PLUGIN_ROOT / "__init__.py"


def _canonical_version() -> str:
    """The one true version: from .claude-plugin/plugin.json."""
    data = json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    return data["version"]


def _read_yaml_field(yaml_text: str, key: str) -> str | None:
    m = re.search(rf"^{key}:\s*>-\s*\n((?:\s+\S.*\n)+)", yaml_text, re.MULTILINE)
    if m:
        return " ".join(line.strip() for line in m.group(1).splitlines() if line.strip())
    m = re.search(rf'^{key}:\s*["\']?(.*?)["\']?\s*$', yaml_text, re.MULTILINE)
    if m:
        return m.group(1).strip().rstrip('"\'')
    return None


class TestVersionConsistency(unittest.TestCase):
    """Every manifest + adapter + README badge must declare the same version."""

    @classmethod
    def setUpClass(cls):
        cls.canonical = _canonical_version()

    def test_all_json_manifests_match_canonical_version(self):
        mismatched = []
        for manifest_path in PLATFORM_MANIFESTS_JSON:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            version = data.get("version")
            if version != self.canonical:
                mismatched.append(f"{manifest_path.name}: {version}")
        self.assertEqual(mismatched, [],
                         f"Canonical version is {self.canonical}. "
                         f"Out-of-sync manifests: {mismatched}")

    def test_grok_marketplace_entry_matches_canonical_version(self):
        data = json.loads(GROK_MARKETPLACE.read_text(encoding="utf-8"))
        entry = data["plugins"][0]
        self.assertEqual(entry["name"], "digital-marketing-pro")
        self.assertEqual(entry["version"], self.canonical,
                         f".grok-plugin/marketplace.json v={entry['version']} "
                         f"!= canonical v={self.canonical}")
        self.assertEqual(entry["source"]["url"],
                         "https://github.com/indranilbanerjee/digital-marketing-pro.git",
                         "Grok marketplace source must point at this repo")

    def test_hermes_plugin_yaml_matches_canonical_version(self):
        yaml_version = _read_yaml_field(PLUGIN_YAML.read_text(encoding="utf-8"), "version")
        self.assertEqual(yaml_version, self.canonical,
                         f"plugin.yaml v={yaml_version} != canonical v={self.canonical}")

    def test_hermes_adapter_PLUGIN_VERSION_matches_canonical(self):
        text = HERMES_ADAPTER_PY.read_text(encoding="utf-8")
        m = re.search(r'PLUGIN_VERSION\s*=\s*["\'](.*?)["\']', text)
        self.assertIsNotNone(m, "PLUGIN_VERSION constant not found in __init__.py")
        self.assertEqual(m.group(1), self.canonical,
                         f"__init__.py PLUGIN_VERSION={m.group(1)} != canonical v={self.canonical}")

    def test_readme_version_badge_matches_canonical(self):
        text = README.read_text(encoding="utf-8")
        m = re.search(r"badge/version-(\d+\.\d+\.\d+)-blue", text)
        self.assertIsNotNone(m, "Version badge not found in README")
        self.assertEqual(m.group(1), self.canonical,
                         f"README badge version={m.group(1)} != canonical v={self.canonical}")

    def test_readme_recent_release_callout_mentions_canonical_version(self):
        text = README.read_text(encoding="utf-8")
        m = re.search(r"Just shipped — v(\d+\.\d+\.\d+)", text)
        self.assertIsNotNone(m, "'Just shipped' callout not found in README hero")
        self.assertEqual(m.group(1), self.canonical,
                         f"Recent-release callout mentions v{m.group(1)} but canonical is {self.canonical}")

    def test_changelog_latest_entry_matches_canonical(self):
        text = CHANGELOG.read_text(encoding="utf-8")
        m = re.search(r"^##\s*\[(\d+\.\d+\.\d+)\]", text, re.MULTILINE)
        self.assertIsNotNone(m, "No version header found in CHANGELOG")
        self.assertEqual(m.group(1), self.canonical,
                         f"CHANGELOG latest entry is v{m.group(1)} but canonical is {self.canonical}")

    def test_readme_supported_surfaces_heading_matches_canonical(self):
        """`## Supported surfaces (vX.Y.Z)` must lock-step with canonical version.

        Added in v3.14.1 after v3.14.0 shipped with this heading stuck at v3.13.1.
        CF + SF tests already had this check; DMP didn't.
        """
        text = README.read_text(encoding="utf-8")
        m = re.search(r"^## Supported surfaces \(v(\d+\.\d+\.\d+)\)", text, re.MULTILINE)
        self.assertIsNotNone(
            m, "'## Supported surfaces (vX.Y.Z)' section heading not found")
        self.assertEqual(
            m.group(1), self.canonical,
            f"Supported-surfaces heading says v{m.group(1)} but canonical is {self.canonical}")

    def test_readme_supported_surfaces_anchor_links_match_canonical(self):
        """Any `#supported-surfaces-v…` anchor in the README must point at the
        slugified current-version heading. Added in v3.14.1 after v3.14.0 shipped
        with the Cowork badge anchor still on `#supported-surfaces-v3131`.
        """
        text = README.read_text(encoding="utf-8")
        # Slugify the current canonical version the same way GitHub does:
        # "## Supported surfaces (v3.14.1)" → "supported-surfaces-v3141"
        canonical_slug = "supported-surfaces-v" + self.canonical.replace(".", "")
        # Find all `#supported-surfaces-v…` anchors
        anchors_found = set(re.findall(r"#(supported-surfaces-v[0-9]+)", text))
        if not anchors_found:
            self.skipTest("No #supported-surfaces-v… anchors in README")
        stale = anchors_found - {canonical_slug}
        self.assertEqual(
            stale, set(),
            f"Stale supported-surfaces anchors: {sorted(stale)}. "
            f"Expected only {canonical_slug!r} (matches canonical v{self.canonical})."
        )

    def test_readme_whats_new_section_includes_canonical_version(self):
        """The README "What's new" section must include an entry for the
        currently-shipping version. Added in v3.14.1 after v3.14.0 shipped with
        the latest "What's new" entry still pointing at v3.13.0.
        """
        text = README.read_text(encoding="utf-8")
        whats_new_start = text.find("## What's new")
        if whats_new_start == -1:
            self.skipTest("README has no '## What's new' section")
        # Take everything from "## What's new" to the next top-level `##` heading
        section = text[whats_new_start:]
        next_h2 = re.search(r"\n## [^\n]", section[15:])  # skip the "## What's new" line itself
        if next_h2:
            section = section[:15 + next_h2.start()]
        # Look for v{canonical} as a bold header, plain text, or H3 (matches the
        # styles used historically: "**vX.Y.Z — …**", "### vX.Y.Z (date)", etc.)
        canonical_ref = f"v{self.canonical}"
        self.assertIn(
            canonical_ref, section,
            f"'What's new' section in README has no entry mentioning v{self.canonical}. "
            f"Latest entry is stale — add a new bullet/entry before shipping."
        )


class TestDescriptionConsistency(unittest.TestCase):
    """All 5 Claude-family manifests should share the same description verbatim."""

    @classmethod
    def setUpClass(cls):
        cls.descriptions = {}
        for manifest_path in PLATFORM_MANIFESTS_JSON:
            # Skip OpenClaw — its description is intentionally shorter
            # Skip package.json — it's npm/ClawHub metadata with its own description shape.
            if manifest_path.name in ("openclaw.plugin.json", "package.json"):
                continue
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            cls.descriptions[manifest_path.name] = data.get("description", "")

    def test_all_claude_family_manifests_share_description(self):
        unique_descriptions = set(self.descriptions.values())
        self.assertEqual(
            len(unique_descriptions), 1,
            f"Description drift across Claude-family manifests:\n" +
            "\n".join(f"  {name}: {desc[:60]}..."
                      for name, desc in self.descriptions.items())
        )

    def test_description_mentions_canonical_skill_count(self):
        # All descriptions must reflect actual skill count.
        actual_skill_count = sum(
            1 for d in (PLUGIN_ROOT / "skills").iterdir()
            if d.is_dir() and (d / "SKILL.md").exists()
        )
        for name, desc in self.descriptions.items():
            self.assertIn(f"{actual_skill_count} skills", desc,
                          f"{name} description should mention '{actual_skill_count} skills'; got: {desc[:100]}")

    def test_plugin_yaml_description_mentions_canonical_skill_count(self):
        """plugin.yaml (Hermes) was never in the description guards — it said
        '158 skills' for five releases while the JSON manifests said 163
        (GitHub issue #12)."""
        actual_skill_count = sum(
            1 for d in (PLUGIN_ROOT / "skills").iterdir()
            if d.is_dir() and (d / "SKILL.md").exists()
        )
        desc = _read_yaml_field(PLUGIN_YAML.read_text(encoding="utf-8"), "description") or ""
        self.assertIn(f"{actual_skill_count} skills", desc,
                      f"plugin.yaml description should mention "
                      f"'{actual_skill_count} skills'; got: {desc[:120]}")


class TestHooksManifestSchemaClean(unittest.TestCase):
    """Cowork's plugin validation rejects unknown top-level fields in
    hooks.json — a `_readme` field made the whole plugin fail to load there
    (GitHub issue #9). The rationale now lives in hooks/README.md; hooks.json
    must contain the `hooks` key and nothing else."""

    def test_hooks_json_has_only_the_hooks_key(self):
        doc = json.loads((PLUGIN_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        self.assertEqual(set(doc.keys()), {"hooks"},
                         f"hooks.json carries extra top-level fields: "
                         f"{sorted(set(doc.keys()) - {'hooks'})} — Cowork "
                         "validation rejects them; prose belongs in hooks/README.md")

    def test_rationale_still_documented(self):
        self.assertTrue((PLUGIN_ROOT / "hooks" / "README.md").exists(),
                        "the zero-hooks rationale must stay documented in "
                        "hooks/README.md, not vanish with the _readme field")


class TestSkillToolDeclarations(unittest.TestCase):
    """A skill whose body mandates Task-tool dispatch must declare Task in its
    allowed-tools — engagement-workflow required parallel `Task` calls in five
    Parts while its frontmatter allowed-tools lacked Task, so a runtime that
    enforces the declaration degraded the whole 12-part flow (GitHub issue #13)."""

    TASK_REF = re.compile(r"`Task`|\bTask tool\b|\bTask calls?\b")

    def test_task_dispatching_skills_declare_task(self):
        offenders = []
        for f in sorted((PLUGIN_ROOT / "skills").glob("*/SKILL.md")):
            text = f.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"^allowed-tools:\s*(.+)$", text, re.M)
            if not m:
                continue  # no restriction declared — nothing to contradict
            if self.TASK_REF.search(text) and "Task" not in m.group(1):
                offenders.append(f.parent.name)
        self.assertEqual(offenders, [],
                         f"skills whose body references Task dispatch but whose "
                         f"allowed-tools omits Task: {offenders}")

    def test_guard_can_fail(self):
        """Plant: the detection regex must match the real phrasing the
        engagement-workflow body uses."""
        self.assertTrue(self.TASK_REF.search(
            "dispatched in parallel via multiple `Task` tool calls"))
        self.assertTrue(self.TASK_REF.search("four parallel Task calls in one message"))
        self.assertFalse(self.TASK_REF.search("multitasking is a myth"))


class TestReadmeBadgeAccuracy(unittest.TestCase):
    """README badges must reflect the actual state of the repo."""

    @classmethod
    def setUpClass(cls):
        cls.text = README.read_text(encoding="utf-8")

    def test_test_count_badge_matches_actual(self):
        # Count actual test methods across all test_*.py files
        total = 0
        for f in PLUGIN_ROOT.glob("tests/test_*.py"):
            for line in f.read_text(encoding="utf-8").splitlines():
                if re.match(r"^\s*def test_", line):
                    total += 1
        m = re.search(r"tests-(\d+)%2F\d+", self.text)
        self.assertIsNotNone(m, "Test count badge not found")
        badge_count = int(m.group(1))
        self.assertEqual(
            badge_count, total,
            f"README test badge says {badge_count}/{badge_count} but repo has {total} test methods. "
            "Bump the badge."
        )


class TestInstallCommandCoverage(unittest.TestCase):
    """Every native platform listed in 'Supported surfaces' must have an install command in the README."""

    @classmethod
    def setUpClass(cls):
        cls.text = README.read_text(encoding="utf-8")

    def test_claude_code_install_command_present(self):
        self.assertIn("/plugin install digital-marketing-pro@neels-plugins", self.text)

    def test_codex_install_command_present(self):
        # Current codex-cli installs with `codex plugin add PLUGIN@MARKETPLACE`;
        # `codex plugin install` does not exist (the README shipped it for months).
        self.assertIn("codex plugin add digital-marketing-pro@neels-plugins", self.text)
        self.assertNotIn("codex plugin install", self.text)

    def test_cursor_install_command_present(self):
        self.assertIn("/add-plugin digital-marketing-pro", self.text)

    def test_copilot_install_command_present(self):
        self.assertIn("copilot plugin install digital-marketing-pro", self.text)

    def test_antigravity_install_command_present(self):
        self.assertIn("agy plugin install", self.text)

    def test_hermes_install_command_present(self):
        self.assertIn("hermes plugins install indranilbanerjee/digital-marketing-pro", self.text)

    def test_openclaw_install_command_present(self):
        self.assertIn(
            "openclaw plugins install git:github.com/indranilbanerjee/digital-marketing-pro",
            self.text
        )

    def test_grok_install_command_present(self):
        self.assertIn("grok plugin install indranilbanerjee/digital-marketing-pro", self.text)


class TestCriticalReadmeSections(unittest.TestCase):
    """The high-traffic sections must exist by their canonical names."""

    @classmethod
    def setUpClass(cls):
        cls.text = README.read_text(encoding="utf-8")

    def test_who_this_is_for_section(self):
        self.assertIn("## Who this is for", self.text)

    def test_compare_table_section(self):
        self.assertIn("## How does this compare?", self.text)

    def test_real_workflows_section(self):
        self.assertIn("## Real workflows you'd actually run", self.text)

    def test_supported_surfaces_section(self):
        self.assertIn("## Supported surfaces", self.text)

    def test_agent_skills_section(self):
        self.assertIn("## Works on 40+ agent harnesses", self.text)

    def test_whats_new_section(self):
        self.assertIn("## What's new", self.text)

    def test_faq_section(self):
        self.assertIn("## FAQ", self.text)

    def test_five_minute_non_developer_section(self):
        # Non-technical users need an obvious entry point.
        self.assertIn("## Get started in 5 minutes (non-developer path)", self.text)

    def test_troubleshooting_section(self):
        # Common install issues should be addressed inline, not buried in docs/.
        self.assertIn("## Troubleshooting", self.text)

    def test_troubleshooting_covers_all_native_platforms(self):
        # Each native platform should appear by name in the troubleshooting
        # section. (9 native platforms since v3.31.0 added Grok.)
        troubleshoot_start = self.text.find("## Troubleshooting")
        troubleshoot_end = self.text.find("## Updating", troubleshoot_start)
        self.assertNotEqual(troubleshoot_start, -1)
        self.assertNotEqual(troubleshoot_end, -1)
        section = self.text[troubleshoot_start:troubleshoot_end]

        # Required platform mentions in troubleshooting
        for platform in ("Claude Code", "Cowork", "Codex", "Cursor",
                         "Copilot CLI", "Antigravity", "Hermes", "OpenClaw", "Grok"):
            self.assertIn(platform, section,
                          f"Troubleshooting section missing '{platform}' coverage")


class TestReadmeAnchorIntegrity(unittest.TestCase):
    """Every internal anchor link in the README must resolve to a heading."""

    def test_all_internal_anchors_resolve(self):
        text = README.read_text(encoding="utf-8")
        refs = set(re.findall(r"\]\(#([a-z0-9-]+)\)", text))
        headings = re.findall(r"^#{1,3}\s+(.+)$", text, re.MULTILINE)

        def slugify(h: str) -> str:
            return re.sub(r"[^a-z0-9 -]", "", h.lower()).strip().replace(" ", "-")

        heading_slugs = {slugify(h) for h in headings}
        missing = refs - heading_slugs
        self.assertEqual(missing, set(),
                         f"Broken internal anchors: {missing}")


class TestRootSettingsJsonIsWellFormed(unittest.TestCase):
    """A plugin-root settings.json is RESERVED by Claude Code: only `agent` (the
    NAME of one of this plugin's agents, made the main-thread agent) and
    `subagentStatusLine` take effect. SocialForge shipped {"agent": {"model":
    "inherit"}} from v0.1.0 — an object where a name belongs — and was the only
    suite plugin missing from Cowork's marketplace view (socialforge#3)."""

    def test_root_settings_json_absent_or_valid(self):
        path = PLUGIN_ROOT / "settings.json"
        if not path.exists():
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        extra = set(data) - {"agent", "subagentStatusLine"}
        self.assertEqual(extra, set(), f"settings.json carries keys Claude Code drops: {extra}")
        if "agent" in data:
            self.assertIsInstance(data["agent"], str, "settings.json `agent` must be an agent name")
            self.assertTrue((PLUGIN_ROOT / "agents" / f"{data['agent']}.md").exists(),
                            f"settings.json names agent {data['agent']!r}, which this plugin lacks")


class TestClaudeManifestHasOnlyDocumentedFields(unittest.TestCase):
    """Claude Code strips unknown top-level plugin.json keys (and `claude plugin
    validate --strict` fails on them). DMP carried `requiredMinimumVersion` —
    a MANAGED SETTING, not a manifest field — for 20 releases while its README
    promised users on old builds an upgrade message that never existed.
    Field list: code.claude.com/docs/en/plugins-reference (retrieved 2026-10-04)."""

    DOCUMENTED = {
        "$schema", "name", "displayName", "version", "description", "author",
        "homepage", "repository", "license", "keywords", "metadata", "icon",
        "documentationUrl", "supportUrl", "privacyPolicyUrl", "termsOfServiceUrl",
        "defaultEnabled", "dependencies", "settings", "userConfig", "types",
        "channels", "skills", "commands", "agents", "hooks", "mcpServers",
        "lspServers", "outputStyles", "workflows", "experimental",
    }

    def test_no_undocumented_top_level_fields(self):
        data = json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        extra = set(data) - self.DOCUMENTED
        self.assertEqual(extra, set(), f"plugin.json fields Claude Code strips: {sorted(extra)}")


if __name__ == "__main__":
    unittest.main()
