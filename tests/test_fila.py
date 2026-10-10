"""T057: quatro olhos, veto, fila com prazo e medida de carimbo."""
import copy
import json
import os
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from collegium import Ledger, Lex  # noqa: E402
from collegium.fila import carimbos, fila  # noqa: E402
from collegium.lex import assinar_humano  # noqa: E402
from pacotes.conciliacao import dados, operarios, oraculo  # noqa: E402

with open(os.path.join(RAIZ, "regimento.exemplo.json"), encoding="utf-8") as _f:
    BASE = json.load(_f)
CH = b"chave-do-patronus"


class Relogio:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class TestFila(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        r = copy.deepcopy(BASE)
        r["agentes"]["bia"] = {"papel": "patronus", "familia_modelo": "humano"}
        r["autonomia"]["alcada_quatro_olhos"] = 10_000
        self.reg, self.rel = r, Relogio()
        self.cam = os.path.join(self.tmp.name, "a.jsonl")
        self.lex = Lex(r, Ledger(self.cam, chave=b"k", relogio=self.rel), {"conciliacao_bancaria": oraculo.oraculo_lex}, CH)

    def tearDown(self):
        self.tmp.cleanup()

    def _aguardando(self, tid, valor):
        ds = dados.gerar(2)
        p = operarios.honesto_v4(ds["extrato"], ds["razao"])
        self.lex.abrir_tarefa(tid, "conciliacao_bancaria", "op-1", valor=valor,
                              entrada={"extrato": ds["extrato"], "razao": ds["razao"]})
        self.lex.submeter(tid, "op-1", p)
        self.lex.verificar(tid, "ex-det", p)
        self.assertEqual(self.lex.liberar(tid).codigo, "AGUARDA_HUMANO")
        return self.lex.tarefas[tid].entrega_hash

    def _sig(self, tid, h, ok, quem):
        return assinar_humano(CH, "aprovar", tid, h, ok, quem)

    def test_quatro_olhos(self):
        h = self._aguardando("grande", 50_000)
        self.rel.t += 60
        self.assertEqual(self.lex.aprovar_humano("grande", "renato", True, self._sig("grande", h, True, "renato")).codigo,
                         "APROVACAO_PARCIAL")
        self.assertEqual(self.lex.aprovar_humano("grande", "renato", True, self._sig("grande", h, True, "renato")).codigo,
                         "MESMO_HUMANO")
        self.assertEqual(self.lex.aprovar_humano("grande", "bia", True, self._sig("grande", h, True, "bia")).codigo,
                         "LIBERADA")

    def test_abaixo_da_alcada_um_humano_basta_e_veto_rejeita(self):
        h = self._aguardando("pequena", 500)
        self.assertEqual(self.lex.aprovar_humano("pequena", "renato", True, self._sig("pequena", h, True, "renato")).codigo,
                         "LIBERADA")
        h = self._aguardando("vetada", 50_000)
        self.lex.aprovar_humano("vetada", "renato", True, self._sig("vetada", h, True, "renato"))
        self.assertEqual(self.lex.aprovar_humano("vetada", "bia", False, self._sig("vetada", h, False, "bia")).codigo,
                         "REJEITADA")

    def test_aprovacao_parcial_sobrevive_ao_reinicio(self):
        h = self._aguardando("grande", 50_000)
        self.lex.aprovar_humano("grande", "renato", True, self._sig("grande", h, True, "renato"))
        novo = Lex(self.reg, Ledger(self.cam, chave=b"k"), {"conciliacao_bancaria": oraculo.oraculo_lex}, CH)
        self.assertEqual(novo.tarefas["grande"].aprovacoes, {"renato"})
        self.assertEqual(novo.aprovar_humano("grande", "renato", True, self._sig("grande", h, True, "renato")).codigo,
                         "MESMO_HUMANO")

    def test_fila_ordenada_com_prazo_e_carimbo(self):
        h1 = self._aguardando("a", 50_000)
        self._aguardando("b", 100)
        self.rel.t += 3 * 86400
        f = fila(self.lex, self.rel.t)
        self.assertEqual([x["tarefa"] for x in f], ["a", "b"])           # maior valor primeiro
        self.assertTrue(f[0]["atrasada"])
        self.assertEqual(f[0]["aprovacoes_necessarias"], 2)
        h3 = self._aguardando("c", 100)
        self.rel.t += 2                                                    # aprovou em 2 segundos: carimbo
        self.lex.aprovar_humano("c", "renato", True, self._sig("c", h3, True, "renato"))
        self.rel.t += 120
        self.lex.aprovar_humano("a", "renato", True, self._sig("a", h1, True, "renato"))
        c = carimbos(self.lex)
        self.assertEqual(c["carimbos"], 1)
        self.assertEqual(c["suspeitas"][0]["tarefa"], "c")


if __name__ == "__main__":
    unittest.main()
