"""embed-c2pa.py never installs packages, cleans up its dev key, writes the
digital-source-type the current c2pa-python requires, and its --verify mode
reports what the pre-publish gate relies on.

Hermes review (NousResearch/hermes-agent#132571, item 1 and a smaller note):
the script ran `pip install c2pa-python>=0.32` on ImportError with no consent,
and wrote the dev signing key to a temp dir it never deleted. Verified end to
end against c2pa-python 0.38.0 when 3.35.0 shipped; these tests pin the
behaviour without needing the package (a fake `c2pa` module stands in).

Stdlib only.
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _helpers import SCRIPTS_DIR, import_script  # noqa: E402

SCRIPT = SCRIPTS_DIR / "embed-c2pa.py"
c2 = import_script("embed-c2pa.py", module_name="embed_c2pa_test")

BLOCK_C2PA = (
    "import importlib.abc, runpy, sys\n"
    "class _Block(importlib.abc.MetaPathFinder):\n"
    "    def find_spec(self, name, path=None, target=None):\n"
    "        if name.split('.')[0] in ('c2pa', 'cryptography'):\n"
    "            raise ImportError(name)\n"
    "        return None\n"
    "sys.meta_path.insert(0, _Block())\n"
    "sys.argv = sys.argv[1:]\n"
    "runpy.run_path(sys.argv[0], run_name='__main__')\n"
)


def _png(path: Path) -> Path:
    import struct
    import zlib

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) + chunk(b"IEND", b""))
    return path


class TestNeverInstalls(unittest.TestCase):
    def test_script_has_no_install_path(self):
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        imports = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        self.assertNotIn("subprocess", imports, "embed-c2pa.py must not be able to run pip")
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                args = [a.value for a in node.args if isinstance(a, ast.Constant)]
                self.assertFalse({"pip", "install"} <= set(map(str, args)), ast.unparse(node))

    def test_missing_package_prints_the_pinned_command_and_exits_2(self):
        with tempfile.TemporaryDirectory() as td:
            src = _png(Path(td) / "in.png")
            proc = subprocess.run([sys.executable, "-c", BLOCK_C2PA, str(SCRIPT), "--input", str(src),
                                   "--output", str(Path(td) / "out.png"), "--brand", "B", "--generator", "g"],
                                  capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn('python -m pip install "c2pa-python==0.38.0"', proc.stderr)
        self.assertIn("does not install packages", proc.stderr)

    def test_pins_are_exact(self):
        self.assertRegex(c2.C2PA_PIN, r"^c2pa-python==\d+\.\d+\.\d+$")
        self.assertRegex(c2.CRYPTOGRAPHY_PIN, r"^cryptography==\d+\.\d+\.\d+$")


class TestManifestAndKey(unittest.TestCase):
    def test_created_action_carries_the_iptc_digital_source_type(self):
        for claim, uri in c2.IPTC_SOURCE_TYPE.items():
            with self.subTest(claim=claim):
                m = c2.build_manifest_json("B", "g", claim, "2026-10-10T00:00:00Z", None, None, ".png")
                created = m["assertions"][0]["data"]["actions"][0]
                self.assertEqual(created["action"], "c2pa.created")
                self.assertEqual(created["digitalSourceType"], uri)
                self.assertTrue(uri.startswith("http://cv.iptc.org/newscodes/digitalsourcetype/"))

    def test_prompt_lives_on_the_one_created_action(self):
        """c2pa-python 0.38 rejects a second c2pa.created/c2pa.opened action, and
        c2pa.opened without an ingredient; --prompt used to add exactly that."""
        m = c2.build_manifest_json("B", "g", "ai-generated-content", "2026-10-10T00:00:00Z",
                                   "a red anvil", "Jane", ".png")
        actions = m["assertions"][0]["data"]["actions"]
        starts = [a for a in actions if a["action"] in ("c2pa.created", "c2pa.opened")]
        self.assertEqual(len(starts), 1, actions)
        self.assertEqual(starts[0]["description"], "Source prompt: a red anvil")

    def test_dev_key_directory_is_deleted_even_when_signing_fails(self):
        made = []

        def fake_cert(tmpdir):
            made.append(Path(tmpdir))
            (Path(tmpdir) / "key.pem").write_text("PRIVATE KEY")
            (Path(tmpdir) / "cert.pem").write_text("CERT")
            return str(Path(tmpdir) / "cert.pem"), str(Path(tmpdir) / "key.pem")

        fake = types.SimpleNamespace(
            C2paSignerInfo=lambda **kw: kw,
            Signer=types.SimpleNamespace(from_info=lambda info: object()),
            Builder=mock.Mock(side_effect=RuntimeError("signing blew up")),
        )
        with tempfile.TemporaryDirectory() as td:
            src = _png(Path(td) / "in.png")
            argv = ["embed-c2pa.py", "--input", str(src), "--output", str(Path(td) / "out.png"),
                    "--brand", "B", "--generator", "g"]
            with mock.patch.object(c2, "ensure_c2pa", return_value=fake), \
                    mock.patch.object(c2, "generate_self_signed_cert", side_effect=fake_cert), \
                    mock.patch.object(sys, "argv", argv), mock.patch("sys.stderr"):
                with self.assertRaises(SystemExit) as cm:
                    c2.main()
        self.assertEqual(cm.exception.code, 4)
        self.assertEqual(len(made), 1)
        self.assertFalse(made[0].exists(), "the dev signing key was left on disk")


class TestVerifyMode(unittest.TestCase):
    def _verify(self, reader):
        fake = types.SimpleNamespace(Reader=reader)
        with tempfile.TemporaryDirectory() as td:
            asset = _png(Path(td) / "a.png")
            with mock.patch.object(c2, "ensure_c2pa", return_value=fake), \
                    mock.patch("sys.stdout") as out:
                with self.assertRaises(SystemExit) as cm:
                    c2.verify_asset(str(asset))
                    raise SystemExit(0)
            printed = "".join(call.args[0] for call in out.write.call_args_list if call.args)
        return cm.exception.code, json.loads(printed)

    @staticmethod
    def _reader(data=None, exc=None):
        class R:
            def __init__(self, *a):
                if exc:
                    raise exc

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def json(self):
                return json.dumps(data)
        return R

    def test_unsigned_asset_exits_6(self):
        code, out = self._verify(self._reader(exc=RuntimeError("ManifestNotFound: no JUMBF data found")))
        self.assertEqual(code, 6)
        self.assertFalse(out["manifest_present"])

    def test_dev_signed_asset_is_valid_with_an_untrusted_signer(self):
        data = {"active_manifest": "urn:c2pa:x", "validation_state": "Valid",
                "validation_status": [{"code": "signingCredential.untrusted"}]}
        code, out = self._verify(self._reader(data=data))
        self.assertEqual(code, 0)
        self.assertTrue(out["untrusted_signer"])
        self.assertEqual(out["issues"], [])

    def test_invalid_manifest_exits_7(self):
        data = {"active_manifest": "urn:c2pa:x", "validation_state": "Invalid",
                "validation_status": [{"code": "assertion.hashedURI.mismatch"}]}
        code, out = self._verify(self._reader(data=data))
        self.assertEqual(code, 7)
        self.assertEqual(out["issues"], ["assertion.hashedURI.mismatch"])


class TestPrivacyDisclosures(unittest.TestCase):
    """Review item 4: every network call the scripts make is listed in PRIVACY.md."""

    def test_timestamp_and_nltk_endpoints_are_disclosed(self):
        privacy = (SCRIPTS_DIR.parent / "PRIVACY.md").read_text(encoding="utf-8")
        if "timestamp.digicert.com" in SCRIPT.read_text(encoding="utf-8"):
            self.assertIn("timestamp.digicert.com", privacy)
        uses_nltk_download = any("nltk.download(" in p.read_text(encoding="utf-8", errors="replace")
                                 for p in SCRIPTS_DIR.glob("*.py"))
        if uses_nltk_download:
            self.assertRegex(privacy, r"(?i)nltk")


if __name__ == "__main__":
    unittest.main()
