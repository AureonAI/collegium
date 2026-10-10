"""Rodada 6, ataques do ambiente Windows (o do piloto). Cada um venceu contra a v0.3.0-pré:
R6-9  PowerShell 5.1 grava `>` em UTF-16: `collegium recibo ... cabeca.json` caía com UnicodeDecodeError.
R6-10 Pipe no Windows sai em CP-1252: JSON com acento (nome do ente) era corrompido por quem converte o
      texto e a ASSINATURA deixava de conferir. JSON de máquina agora sai em ASCII puro.
R6-11 Excel "Texto Unicode" grava UTF-16 com TAB: a importação dizia "cabeçalho não encontrado" (falso).
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from collegium import ed25519  # noqa: E402
from collegium.__main__ import _ler_json  # noqa: E402
from collegium_oficios.conciliacao import importadores as imp  # noqa: E402

SK = bytes([3]) * 32
PUB = ed25519.publica(SK).hex()
CSV = ("Data\tHistórico\tDocumento\tValor\n01/03/2026\tRecebimento NF 123 São Paulo\tNF123\t1.234,56\n"
       "02/03/2026\tTarifa\t\t-10,00\n")


def cli(*args, cwd, env_extra=None):
    env = dict(os.environ, PYTHONPATH=RAIZ, **(env_extra or {}))
    return subprocess.run([sys.executable, "-m", "collegium", *args], cwd=cwd, capture_output=True, env=env)


class TestWindows(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        with open(os.path.join(self.d, "k"), "w") as f:
            f.write(SK.hex())
        from collegium import Ledger
        led = Ledger(os.path.join(self.d, "a.jsonl"), chave=b"k")
        led.anexar("tarefa_aberta", {"tarefa": "t1", "entrada": "x"})

    def tearDown(self):
        self.tmp.cleanup()

    def test_r6_10_json_de_maquina_sai_em_ascii_e_a_assinatura_sobrevive(self):
        r = cli("cabeca", "a.jsonl", "k", "Escritório Ação Ltda", cwd=self.d, env_extra={"PYTHONIOENCODING": "cp1252"})
        self.assertEqual(r.returncode, 0, r.stderr)
        r.stdout.decode("ascii")  # ASCII puro: nenhuma página de código consegue corromper
        cab = json.loads(r.stdout)
        self.assertEqual(cab["ente"], "Escritório Ação Ltda")
        from collegium import recibo as rc
        self.assertTrue(rc.conferir_cabeca(cab, PUB))

    def test_r6_9_arquivo_gravado_pelo_powershell_51(self):
        r = cli("cabeca", "a.jsonl", "k", "Escritório", cwd=self.d)
        texto = r.stdout.decode("ascii")
        for enc in ("utf-16", "utf-8-sig", "utf-8"):
            cam = os.path.join(self.d, f"cab_{enc}.json")
            with open(cam, "w", encoding=enc) as f:
                f.write(texto)
            self.assertEqual(_ler_json(cam)["ente"], "Escritório", enc)
            r2 = cli("recibo", "a.jsonl", "t1", cam, cwd=self.d)
            self.assertEqual(r2.returncode, 0, (enc, r2.stderr[-300:]))

    def test_saida_para_humano_nunca_derruba_o_comando(self):
        r = cli("--versao", cwd=self.d, env_extra={"PYTHONIOENCODING": "ascii"})
        self.assertEqual(r.returncode, 0, r.stderr)
        r = cli("exemplo", "demo", cwd=self.d, env_extra={"PYTHONIOENCODING": "ascii"})
        self.assertEqual(r.returncode, 0, r.stderr[-300:])

    def test_r6_11_excel_texto_unicode(self):
        for enc in ("utf-16", "utf-16-le", "utf-16-be"):
            r = imp.ler_planilha(CSV.encode(enc), "r")
            self.assertEqual(len(r["itens"]), 2, enc)
            self.assertEqual(r["separador"], "\t")
            self.assertIn("São Paulo", r["itens"][0]["desc"])
            self.assertEqual(r["itens"][0]["valor"], 123456)


if __name__ == "__main__":
    unittest.main()
