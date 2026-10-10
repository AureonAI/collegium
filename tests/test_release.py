"""T062: pacote reprodutível e assinado + SBOM."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "ferramentas"))
sys.path.insert(0, RAIZ)

TEM_GIT = shutil.which("git") is not None and subprocess.run(["git", "rev-parse"], cwd=RAIZ,
                                                             capture_output=True).returncode == 0


@unittest.skipUnless(TEM_GIT, "precisa do repositório git")
class TestRelease(unittest.TestCase):
    def test_reprodutivel_assinado_e_sbom(self):
        import release
        from collegium import ed25519 as ed
        sk = bytes([4]) * 32
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            m1, m2 = release.construir(a, sk), release.construir(b, sk)
            self.assertEqual(m1["sha256"], m2["sha256"])                       # reprodutível
            pacote = os.path.join(a, m1["pacote"])
            self.assertTrue(release.verificar(pacote, os.path.join(a, "MANIFESTO.json"), ed.publica(sk).hex()))
            with open(pacote, "ab") as f:
                f.write(b"x")                                                   # pacote adulterado
            self.assertFalse(release.verificar(pacote, os.path.join(a, "MANIFESTO.json"), ed.publica(sk).hex()))
            import json
            with open(os.path.join(a, "sbom.cdx.json"), encoding="utf-8") as f:
                s = json.load(f)
            self.assertEqual(s["bomFormat"], "CycloneDX")
            self.assertTrue(any(c["name"] == "collegium/lex.py" for c in s["components"]))


if __name__ == "__main__":
    unittest.main()
