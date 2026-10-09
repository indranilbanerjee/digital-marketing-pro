"""Every CLI argument that can become part of a file path is validated as a
single path component before any script uses it.

Hermes review item 3 named seven managers; a re-review of the delta looks for
the pattern everywhere. So every `--brand`, `--slug`, `--run-id` and `--client`
argument in scripts/ declares `type=_common.path_component`, which rejects
`/`, `\\`, `..`, absolute paths and drive prefixes at the command line. The
allow-list holds only values that are never used in a path, each with its
reason. (Library entry points that take the same names call safe_child; see
tests/test_path_containment.py.)

Stdlib only.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
FLAGS = {"--brand", "--slug", "--run-id", "--client"}
TYPE = "_common.path_component"
ALLOW = {
    ("embed-c2pa.py", "--brand"): "the brand NAME written into the C2PA manifest's CreativeWork.author; "
                                  "never part of a path, and real names may contain '/'",
}


def unvalidated(source: str, filename: str) -> list[str]:
    """Return 'flag@line' for each path-forming argument that lacks the type."""
    out = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "add_argument":
            flag = next((a.value for a in node.args if isinstance(a, ast.Constant) and a.value in FLAGS), None)
            if not flag or (filename, flag) in ALLOW:
                continue
            typ = next((k.value for k in node.keywords if k.arg == "type"), None)
            if typ is None or ast.unparse(typ) != TYPE:
                out.append(f"{flag}@{node.lineno}")
    return out


class TestCliPathArguments(unittest.TestCase):
    def test_every_path_forming_argument_is_validated(self):
        bad = {}
        for p in sorted(SCRIPTS.glob("*.py")):
            hits = unvalidated(p.read_text(encoding="utf-8"), p.name)
            if hits:
                bad[p.name] = hits
        self.assertEqual(bad, {}, f"arguments without type={TYPE} (see this module's docstring)")

    def test_allow_list_entries_still_exist_and_have_reasons(self):
        for (fname, flag), reason in ALLOW.items():
            with self.subTest(entry=(fname, flag)):
                self.assertTrue((SCRIPTS / fname).exists())
                self.assertIn(f'"{flag}"', (SCRIPTS / fname).read_text(encoding="utf-8"))
                self.assertGreater(len(reason), 30)

    def test_the_type_rejects_paths(self):
        import argparse
        import sys
        sys.path.insert(0, str(SCRIPTS))
        import _common
        for bad in ("../x", "..\\x", "/etc", "C:\\x", "a/b", ""):
            with self.subTest(bad=bad):
                with self.assertRaises(argparse.ArgumentTypeError):
                    _common.path_component(bad)
        self.assertEqual(_common.path_component("Acme Corp"), "Acme Corp")

    # ── plant checks ─────────────────────────────────────────────

    def test_plant_missing_type_is_caught(self):
        src = 'import argparse\np = argparse.ArgumentParser()\np.add_argument("--brand", required=True)\n'
        self.assertEqual(unvalidated(src, "planted.py"), ["--brand@3"])

    def test_plant_wrong_type_is_caught(self):
        src = 'p.add_argument("--run-id", type=str)\n'
        self.assertEqual(unvalidated(src, "planted.py"), ["--run-id@1"])

    def test_plant_validated_passes(self):
        src = 'p.add_argument("--slug", type=_common.path_component, help="x")\n'
        self.assertEqual(unvalidated(src, "planted.py"), [])


if __name__ == "__main__":
    unittest.main()
