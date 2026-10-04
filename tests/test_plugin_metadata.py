"""Plugin metadata probe (scripts/plugin-metadata.py)."""
from __future__ import annotations

import unittest

from _helpers import import_script  # type: ignore[import-not-found]


class TestPluginMetadata(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pm = import_script("plugin-metadata.py", module_name="plugin_metadata")

    def test_probe_version_has_name_and_version(self):
        v = self.pm.probe_version()
        self.assertEqual(v.get("name"), "digital-marketing-pro")
        self.assertTrue(v.get("version", "").startswith("3."))

    def test_probe_version_includes_required_min(self):
        v = self.pm.probe_version()
        self.assertIn("required_min_version", v)

    def test_probe_assets_counts(self):
        a = self.pm.probe_assets()
        self.assertGreater(a["skills_total"], 100,
                           "DMP should have 100+ skills")
        self.assertGreater(a["agents"], 20)
        self.assertGreater(a["scripts"], 10)
        # Commands whose names duplicated a skill were folded into the skill
        # (the skill already provides /digital-marketing-pro:<name>); only
        # commands with no same-named skill remain, so assert presence, not size.
        self.assertGreater(a["commands"], 0)

    def test_probe_connectors_has_keys(self):
        c = self.pm.probe_connectors()
        for k in ("available_http", "available_npx", "available_total",
                  "active_count", "active_names", "cowork_compatible_count"):
            self.assertIn(k, c)

    def test_probe_environment_returns_known_value(self):
        env = self.pm.probe_environment()
        self.assertIn(env["environment"], (
            "cowork-sandbox", "claude-code-windows", "claude-code-mac",
            "claude-code-linux", "unknown",
        ))

    def test_probe_skills_list_has_cowork_setup(self):
        skills = self.pm.probe_skills_list()
        slash = [s["slash_command"] for s in skills]
        self.assertIn("/digital-marketing-pro:cowork-setup", slash,
                      "v3.12.0 must ship the cowork-setup skill")

    def test_probe_commands_list_includes_doctor(self):
        cmds = self.pm.probe_commands_list()
        slash = [c["slash_command"] for c in cmds]
        self.assertIn("/digital-marketing-pro:doctor", slash)
        self.assertIn("/digital-marketing-pro:resume", slash)

    def test_all_sections_returns_all_keys(self):
        data = self.pm.all_sections()
        for k in ("version", "assets", "connectors", "skills", "commands"):
            self.assertIn(k, data)

    def test_all_with_environment_includes_env(self):
        data = self.pm.all_with_environment()
        self.assertIn("environment", data)

    def test_format_text_renders(self):
        data = self.pm.all_with_environment()
        text = self.pm.format_text(data)
        self.assertIn("DIGITAL MARKETING PRO", text)
        self.assertIn("Version:", text)


if __name__ == "__main__":
    unittest.main()
