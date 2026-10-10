"""T064: fatura conferível pelo cliente. Cada teste é um golpe de COBRANÇA."""
import copy
import json
import os
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from collegium import Ledger, Lex  # noqa: E402
from collegium import ed25519 as ed  # noqa: E402
from collegium import recibo as rc  # noqa: E402
from collegium.fatura import conferir_fatura, emitir_fatura, metricas  # noqa: E402
from collegium_oficios.conciliacao import dados, operarios, oraculo  # noqa: E402

with open(os.path.join(RAIZ, "regimento.exemplo.json"), encoding="utf-8") as _f:
    REG = json.load(_f)
SK = bytes([6]) * 32
PUB = ed.publica(SK).hex()
PRECOS = {"conciliacao_bancaria": 1500}


class Relogio:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        self.t += 1
        return self.t


class TestFatura(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cam = os.path.join(self.tmp.name, "a.jsonl")
        lex = Lex(REG, Ledger(self.cam, chave=b"k", relogio=Relogio()), {"conciliacao_bancaria": oraculo.oraculo_lex})
        for tid, seed, op in (("a", 2, operarios.honesto_v4), ("b", 4, operarios.honesto_v4),
                              ("ruim", 3, operarios.fabricador)):
            ds = dados.gerar(seed)
            e = {"extrato": ds["extrato"], "razao": ds["razao"]}
            p = op(ds["extrato"], ds["razao"])
            prod = "op-1" if tid != "ruim" else "op-2"
            lex.abrir_tarefa(tid, "conciliacao_bancaria", prod, entrada=e)
            lex.submeter(tid, prod, p)
            lex.verificar(tid, "ex-det", p)
        ds = dados.gerar(5)
        e = {"extrato": ds["extrato"], "razao": ds["razao"]}
        g = operarios.honesto_v4(ds["extrato"], ds["razao"])
        lex.abrir_canario("can", "conciliacao_bancaria", "op-1", e, g)       # canário: não se cobra
        lex.submeter("can", "op-1", g)
        lex.verificar("can", "ex-det", g)
        self.cab = rc.cabeca(self.cam, SK, "Escritório", "agora")
        self.f = emitir_fatura(self.cam, self.cab, 0, 10_000, PRECOS, SK)

    def tearDown(self):
        self.tmp.cleanup()

    def test_fatura_honesta_confere(self):
        ok, motivos, r = conferir_fatura(json.loads(json.dumps(self.f)), PUB)
        self.assertTrue(ok, motivos)
        self.assertEqual(r, {"itens": 2, "total_centavos": 3000, "ente": "Escritório"})   # a, b; sem ruim e sem canário

    def test_golpes_de_cobranca(self):
        f = copy.deepcopy(self.f)
        f["total_centavos"] = 4500                                                # total inflado (re-assinado ou não)
        self.assertFalse(conferir_fatura(f, PUB)[0])
        f = emitir_fatura(self.cam, self.cab, 0, 10_000, PRECOS, SK)
        f["itens"].append(copy.deepcopy(f["itens"][0]))                           # item duplicado
        f["total_centavos"] += 1500
        from collegium.fatura import _corpo
        f["assinatura"] = ed.assinar(SK, _corpo(f)).hex()                          # mesmo assinado pelo operador...
        ok, motivos, _ = conferir_fatura(f, PUB)
        self.assertFalse(ok)
        self.assertTrue(any(m.startswith("COBRANCA_DUPLICADA") for m in motivos))  # ...o cliente pega
        f = emitir_fatura(self.cam, self.cab, 0, 10_000, PRECOS, SK)
        f["itens"][0]["linha"] = f["itens"][0]["linha"].replace('"aceito": true', '"aceito": false')
        self.assertFalse(conferir_fatura(f, PUB)[0])                               # linha adulterada
        f = emitir_fatura(self.cam, self.cab, 0, 10_000, PRECOS, bytes([1]) * 32)
        self.assertFalse(conferir_fatura(f, PUB)[0])                               # outra chave

    def test_cobrar_tarefa_de_outro_cliente(self):
        """Red Team rodada 5: no mesmo ANAIS, o cliente A recebia cobrança da tarefa do cliente B sem como saber."""
        from collegium.lex import _h
        ds = dados.gerar(2)
        meu = {_h({"extrato": ds["extrato"], "razao": ds["razao"]})}          # o cliente só conhece a entrada da tarefa "a"
        ok, motivos, _ = conferir_fatura(self.f, PUB, entradas_do_cliente=meu)
        self.assertFalse(ok)
        self.assertTrue(any(m.startswith("ENTRADA_DE_OUTRO_CLIENTE") for m in motivos), motivos)

    def test_periodo_e_metricas(self):
        self.assertEqual(emitir_fatura(self.cam, self.cab, 0, 1, PRECOS, SK)["itens"], [])
        m = metricas(self.cam)
        self.assertEqual(m["por_classe"]["conciliacao_bancaria"]["aceitos"], 3)   # a, b e o canário
        self.assertEqual(m["canario"], 1)
        self.assertGreaterEqual(m["incidente"], 1)


if __name__ == "__main__":
    unittest.main()
