"""T070 · rodada 6, arquivos hostis e usuário descuidado contra `collegium conciliar`.
Cada teste venceu contra a v0.3.0 antes da correção (sonda registrada no ADVERSARIAL_LOG, R6-14..R6-18)."""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from collegium_oficios.conciliacao import exemplo as kit  # noqa: E402
from collegium_oficios.conciliacao import importadores as imp  # noqa: E402
from collegium_oficios.conciliacao import piloto  # noqa: E402

O, C = kit.gerar(42)
OFX, CSV = O.decode("cp1252"), C.decode("cp1252")
BLOCOS = re.findall(r"<STMTTRN>.*?</STMTTRN>", OFX, re.S)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def arquivos(self, ofx=OFX, csv=CSV, ext_nome="e.ofx"):
        e, r = os.path.join(self.tmp, ext_nome), os.path.join(self.tmp, "r.csv")
        with open(e, "wb") as f:
            f.write(ofx.encode("cp1252") if isinstance(ofx, str) else ofx)
        with open(r, "wb") as f:
            f.write(csv.encode("cp1252"))
        return e, r

    def conciliar(self, **kw):
        e, r = self.arquivos(**kw)
        return piloto.conciliar_arquivos(e, r, os.path.join(self.tmp, "s"), "E")


class TestValores(unittest.TestCase):
    def test_r6_14_valor_ambiguo_ou_estrangeiro_nunca_vira_numero_errado(self):
        """R6-14: '1,234.56' virava R$ 1,23 e '1.234' virava R$ 1,23 (×1000), em silêncio."""
        certos = {"1.234,56": 123456, "1234,56": 123456, "1234.56": 123456, "1,234.56": 123456,
                  "-1,234.56": -123456, "1.234.567,89": 123456789, "1,234,567.89": 123456789,
                  "(1.234,56)": -123456, "R$ 1.234,56": 123456, "1.234,56D": -123456, "10,5": 1050,
                  "0,05": 5, "1234": 123400, "-26323.16": -2632316, "1.234.567": 123456700}
        for t, v in certos.items():
            self.assertEqual(imp.centavos(t), v, t)
        for t in ("1.234", "1,234", "12,345", "1,23,4", "1.2.3,45", "12.3456", "1,2345", "1.234,567", ",50", ""):
            with self.assertRaises(ValueError, msg=t):
                imp.centavos(t)


class TestHostil(Base):
    def test_r6_15_mesmo_arquivo_como_extrato_e_razao(self):
        """R6-15: o razão passado também como extrato dava CONCILIADO com 48 pares (conciliação falsa)."""
        r = self.conciliar(ofx=CSV, ext_nome="e.csv")
        self.assertEqual(r["status"], "BLOQUEADO")
        self.assertTrue(r["motivo"].startswith("S0"), r["motivo"])

    def test_r6_16_ofx_com_duas_contas(self):
        """R6-16: duas contas no mesmo OFX eram MISTURADAS numa só conciliação."""
        s0 = re.search(r"<STMTTRNRS>.*</STMTTRNRS>", OFX, re.S).group(0)
        s1 = re.sub(r"<FITID>([^\n<]+)", r"<FITID>X\1", s0).replace("<ACCTID>", "<ACCTID>9")
        with self.assertRaises(imp.ImportacaoInvalida) as cm:
            self.conciliar(ofx=OFX.replace(s0, s0 + "\n" + s1, 1))
        self.assertIn("2 contas", str(cm.exception))

    def test_r6_17_extrato_sem_lancamentos_e_arquivo_vazio(self):
        """R6-17: extrato sem lançamentos derrubava com IndexError; arquivo vazio dizia 'cabeçalho não encontrado'."""
        with self.assertRaises(imp.ImportacaoInvalida) as cm:
            self.conciliar(ofx=re.sub(r"<STMTTRN>.*?</STMTTRN>", "", OFX, flags=re.S))
        self.assertIn("sem lançamentos", str(cm.exception))
        with self.assertRaises(imp.ImportacaoInvalida) as cm:
            self.conciliar(ofx=b"")
        self.assertIn("vazio", str(cm.exception))

    def test_r6_18_tipo_ofx_contradiz_o_sinal_vira_aviso(self):
        """R6-18: CREDIT marcado como DEBIT passava sem nota. O sinal do TRNAMT manda (especificação OFX),
        mas a contradição indica exportação defeituosa e precisa aparecer."""
        cred = next(b for b in BLOCOS if "<TRNTYPE>CREDIT" in b)
        r = self.conciliar(ofx=OFX.replace(cred, cred.replace("<TRNTYPE>CREDIT", "<TRNTYPE>DEBIT"), 1))
        self.assertEqual(r["status"], "CONCILIADO")
        self.assertTrue(any("TRNTYPE" in a and "1 lançamento" in a for a in r["avisos"]), r["avisos"])

    def test_s3_aponta_causas_comuns(self):
        ls = CSV.split("\n")
        so12 = [ln for ln in ls if not re.match(r"\d\d/", ln) or int(ln[:2]) <= 12]
        us = "\n".join(re.sub(r"^(\d\d)/(\d\d)/", r"\2/\1/", ln) for ln in so12)
        r = self.conciliar(csv=us)
        self.assertEqual(r["status"], "BLOQUEADO")
        self.assertIn("mês/dia", r["motivo"])

    def test_cli_nunca_mostra_traceback(self):
        e, r = self.arquivos(ofx=re.sub(r"<STMTTRN>.*?</STMTTRN>", "", OFX, flags=re.S))
        p = subprocess.run([sys.executable, "-m", "collegium", "conciliar", "--extrato", e, "--razao", r,
                            "--saida", os.path.join(self.tmp, "s")], cwd=RAIZ, capture_output=True, text=True)
        self.assertEqual(p.returncode, 1)
        self.assertNotIn("Traceback", p.stderr)
        self.assertIn("sem lançamentos", p.stderr + p.stdout)


if __name__ == "__main__":
    unittest.main()
