"""Rodada 6 · os MESMOS dados em todos os formatos prometidos (OFX, CNAB 240, Open Finance), de ponta a ponta.
R6-24 venceu contra a v0.3.0: com CNAB real (histórico de 25 posições, documento cortado no meio), o operário
propunha um lote que o oráculo recusava, e a conciliação inteira terminava em ERRO_INTERNO.
R6-26: Open Finance com transação agendada derrubava o produto (TypeError).
R6-25: CNAB com brancos finais cortados ou com o caractere de fim de arquivo (0x1A), e Open Finance salvo
com outra extensão, eram lidos como planilha e davam a mensagem FALSA "cabeçalho não encontrado"."""
import json
import os
import random
import shutil
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "tests"))
from collegium_oficios.conciliacao import dados, operarios, oraculo, piloto  # noqa: E402
from collegium_oficios.conciliacao import exemplo as kit  # noqa: E402
from collegium_oficios.conciliacao import importadores as imp  # noqa: E402
from test_importadores_br import cnab  # noqa: E402  (montado campo a campo pelo manual, independente do leitor)

O, C = kit.gerar()
EXT = imp.ler_ofx(O)["extrato"]


def _cnab_do_kit() -> str:
    lancs = [(x["data"][8:10] + x["data"][5:7] + x["data"][:4], abs(x["valor"]), "C" if x["valor"] > 0 else "D",
              x["desc"].encode("ascii", "replace").decode()) for x in EXT]
    return cnab(lancs, saldo_ini=1_234_567)


def _open_finance_do_kit() -> dict:
    return {"data": [{"transactionId": x["id"][2:], "completedAuthorisedPaymentType": "TRANSACAO_EFETIVADA",
                      "creditDebitType": "CREDITO" if x["valor"] > 0 else "DEBITO", "transactionName": x["desc"],
                      "type": "PIX", "transactionAmount": {"amount": f"{abs(x['valor']) / 100:.4f}", "currency": "BRL"},
                      "transactionDateTime": x["data"] + "T15:00:00Z"} for x in EXT]}


class TestFormatos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.raz = os.path.join(self.tmp, "r.csv")
        with open(self.raz, "wb") as f:
            f.write(C)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def conciliar(self, nome: str, conteudo: bytes) -> dict:
        p = os.path.join(self.tmp, nome)
        with open(p, "wb") as f:
            f.write(conteudo)
        return piloto.conciliar_arquivos(p, self.raz, os.path.join(self.tmp, "s_" + nome), "E")

    def test_r6_24_cnab_real_nunca_termina_em_erro_interno(self):
        r = self.conciliar("e.ret", _cnab_do_kit().encode("ascii"))
        self.assertEqual(r["status"], "CONCILIADO", r.get("falhas"))
        self.assertEqual(r["formato_extrato"], "CNAB 240")
        self.assertTrue(any("25" in a and "cortad" in a for a in r["avisos"]), r["avisos"])

    def test_r6_25_deteccao_pelo_conteudo(self):
        cn = _cnab_do_kit()
        sem_brancos = "\r\n".join(ln.rstrip() for ln in cn.split("\r\n")).encode("ascii")
        for nome, conteudo in (("cnab_sem_brancos.ret", sem_brancos),
                               ("cnab_eof.ret", cn.encode("ascii") + b"\r\n\x1a"),
                               ("cnab.txt", cn.encode("ascii"))):
            r = self.conciliar(nome, conteudo)
            self.assertEqual((r["status"], r["formato_extrato"]), ("CONCILIADO", "CNAB 240"), nome)
        for nome in ("of.json", "of.txt", "of"):
            r = self.conciliar(nome, json.dumps(_open_finance_do_kit()).encode())
            self.assertEqual(r["formato_extrato"], "Open Finance", nome)

    def test_r6_26_open_finance_com_lancamento_futuro(self):
        """R6-26: transação agendada (LANCAMENTO_FUTURO, comum em qualquer exportação real) derrubava o
        produto com TypeError: o piloto fazia len() de um número."""
        of = _open_finance_do_kit()
        of["data"].append({"transactionId": "FUT1", "completedAuthorisedPaymentType": "LANCAMENTO_FUTURO",
                           "creditDebitType": "DEBITO", "transactionName": "AGENDADO", "type": "TED",
                           "transactionAmount": {"amount": "10.00", "currency": "BRL"},
                           "transactionDateTime": "2026-10-20T15:00:00Z"})
        r = self.conciliar("of_futuro.json", json.dumps(of).encode())
        self.assertEqual(r["status"], "CONCILIADO")
        with open(os.path.join(self.tmp, "s_of_futuro.json", "relatorio.html"), encoding="utf-8") as f:
            self.assertIn("1 transações não efetivadas", f.read())

    def test_mesmos_dados_sem_corte_dao_o_mesmo_resultado(self):
        base = self.conciliar("e.ofx", O)
        of = self.conciliar("e.json", json.dumps(_open_finance_do_kit()).encode())
        chave = lambda r: (r["status"], r["pares"], r["grupos"], r["pendencias_extrato"], r["pendencias_razao"])  # noqa
        self.assertEqual(chave(base), ("CONCILIADO", 41, 6, 15, 12))
        self.assertEqual(chave(of), chave(base))


class TestOperarioNuncaRecusadoPeloOraculo(unittest.TestCase):
    """O invariante que o produto precisa: o operário determinístico é SEMPRE aceito pelo oráculo; senão o
    cliente recebe erro interno. Testado com históricos cortados em todos os comprimentos (CNAB tem 25)."""

    @staticmethod
    def _cortar(ds, n, rnd):
        ext = [dict(x, desc=x["desc"][:n] if rnd.random() < 0.7 else x["desc"]) for x in ds["extrato"]]
        return ext, ds["razao"]

    def _falhas(self, operario, sementes):
        ruins = []
        for s in sementes:
            rnd = random.Random(s)
            ds = dados.gerar_v2(s, n=40)
            for n in (6, 9, 12, 16, 20, 25, 32):
                ext, raz = self._cortar(ds, n, rnd)
                ok, falhas = oraculo.verificar(ext, raz, operario(ext, raz))
                if not ok:
                    ruins.append((s, n, falhas[:2]))
        return ruins

    def test_v6_nunca_e_recusado(self):
        self.assertEqual(self._falhas(operarios.honesto_v6, range(60)), [])

    def test_o_teste_morde_v5_e_recusado(self):
        self.assertTrue(self._falhas(operarios.honesto_v5, range(60)))


if __name__ == "__main__":
    unittest.main()
