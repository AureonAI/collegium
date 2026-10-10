"""T061: pré-registro selado."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collegium import ed25519 as ed  # noqa: E402
from collegium.preregistro import conferir, hash_arquivo, preregistrar  # noqa: E402

SK = bytes([5]) * 32
PUB = ed.publica(SK).hex()


class TestPreregistro(unittest.TestCase):
    def test_selar_conferir_e_detectar_edicao(self):
        with tempfile.TemporaryDirectory() as d:
            exp, reg = os.path.join(d, "t10.py"), os.path.join(d, "pre", "REGISTRO.jsonl")
            with open(exp, "w", encoding="utf-8") as f:
                f.write('"""P1: aceite < 50%."""\n')
            preregistrar(exp, SK, reg, "2026-10-10T08:00:00-03:00")
            ok, info = conferir(exp, reg, PUB)
            self.assertTrue(ok)
            self.assertEqual(info["indice"], 0)
            with open(exp, "w", encoding="utf-8") as f:          # mudar o critério DEPOIS do resultado...
                f.write('"""P1: aceite < 90%."""\n')
            self.assertFalse(conferir(exp, reg, PUB)[0])         # ...não confere com o selado
            self.assertFalse(conferir(exp, reg, ed.publica(bytes(32)).hex())[0])

    def test_hash_igual_com_crlf(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = os.path.join(d, "a"), os.path.join(d, "b")
            with open(a, "wb") as f:
                f.write(b"linha 1\nlinha 2\n")
            with open(b, "wb") as f:
                f.write(b"linha 1\r\nlinha 2\r\n")
            self.assertEqual(hash_arquivo(a), hash_arquivo(b))


if __name__ == "__main__":
    unittest.main()
