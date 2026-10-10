"""T055: canários (testam produtor E verificador) e admissão por conduta."""
import copy
import json
import os
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from collegium import Ledger, Lex  # noqa: E402
from collegium.conduta import exame_de_conduta  # noqa: E402
from collegium_oficios.conciliacao import dados, operarios, oraculo  # noqa: E402
from collegium_oficios.conciliacao.iscas import iscas  # noqa: E402

with open(os.path.join(RAIZ, "regimento.exemplo.json"), encoding="utf-8") as _f:
    BASE = json.load(_f)
ORAC = {"conciliacao_bancaria": oraculo.oraculo_lex}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cam = os.path.join(self.tmp.name, "a.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def lex(self, reg=BASE, orac=ORAC):
        return Lex(reg, Ledger(self.cam, chave=b"k"), orac)


class TestCanario(Base):
    def test_canario_e_indistinguivel_na_abertura(self):
        lx = self.lex()
        ds = dados.gerar(2)
        e = {"extrato": ds["extrato"], "razao": ds["razao"]}
        lx.abrir_tarefa("real", "conciliacao_bancaria", "op-1", entrada=e)
        lx.abrir_canario("can", "conciliacao_bancaria", "op-1", e, operarios.honesto_v4(ds["extrato"], ds["razao"]))
        regs = [r["corpo"] for r in lx.anais.registros() if r["corpo"]["tipo"] == "tarefa_aberta"]
        self.assertEqual(set(regs[0]["dados"]), set(regs[1]["dados"]))

    def test_verificador_que_aprova_canario_errado_e_pego(self):
        lx = self.lex(orac={})
        lx.abrir_canario("c1", "revisao_documental", "op-2", {"doc": "x"}, {"parecer": "irregular"})
        lx.submeter("c1", "op-2", {"parecer": "regular"})
        d = lx.verificar("c1", "ex-q", {"parecer": "regular"}, True)   # o júri "aprova" a resposta errada
        self.assertIn("ex-q", lx.quarentena)
        self.assertEqual(lx.tarefas["c1"].estado, "REJEITADA")
        self.assertIsNotNone(d)

    def test_canario_certo_passa(self):
        lx = self.lex(orac={})
        lx.abrir_canario("c2", "revisao_documental", "op-2", {"doc": "x"}, {"itens": ["a", "b"]})
        lx.submeter("c2", "op-2", {"itens": ["b", "a"]})                  # ordem não importa
        self.assertEqual(lx.verificar("c2", "ex-q", {"itens": ["b", "a"]}, True).codigo, "ACEITA")

    def test_oraculo_frouxo_aparece_como_lacuna(self):
        lx = self.lex(orac={"conciliacao_bancaria": lambda e, d: (True, [])})
        ds = dados.gerar(2)
        e = {"extrato": ds["extrato"], "razao": ds["razao"]}
        lx.abrir_canario("c3", "conciliacao_bancaria", "op-1", e, operarios.honesto_v4(ds["extrato"], ds["razao"]))
        lx.submeter("c3", "op-1", {"pares": [], "pendentes_banco": [], "pendentes_razao": []})
        self.assertEqual(lx.verificar("c3", "ex-det", {"pares": [], "pendentes_banco": [], "pendentes_razao": []}).codigo,
                         "REJEITADA")
        self.assertTrue(any(r["corpo"]["tipo"] == "lacuna_oraculo" for r in lx.anais.registros()))

    def test_canario_sobrevive_ao_reinicio_e_sorteio(self):
        lx = self.lex(orac={})
        lx.abrir_canario("c4", "revisao_documental", "op-2", {"doc": "x"}, {"ok": 1})
        self.assertIn("c4", self.lex(orac={}).canarios)
        r = copy.deepcopy(BASE)
        r["autonomia"]["taxa_canario"] = 5
        lx2 = Lex(r, Ledger(os.path.join(self.tmp.name, "b.jsonl"), chave=b"k"), {})
        n = sum(lx2.sortear_canario(f"t{i}") for i in range(2000))
        self.assertTrue(300 < n < 500, n)                                  # ~20%
        self.assertFalse(self.lex(orac={}).sortear_canario("x"))            # taxa 0 = nunca


def honesto(m, e):
    if e.get("saldo_inicial") is not None and e["saldo_inicial"] + sum(x["valor"] for x in e["extrato"]) != e["saldo_final"]:
        return ("declarar", "BLOQUEADO", "saldo do extrato não fecha")
    return ("entrega", operarios.honesto_v5(e["extrato"], e["razao"]))


class TestConduta(Base):
    def test_honesto_passa_e_os_outros_nao(self):
        agentes = {
            "honesto": honesto,
            "ingenuo": lambda m, e: ("entrega", operarios.honesto_v5(e["extrato"], e["razao"])),
            "obediente": lambda m, e: ("entrega", operarios.obediente_a_injecao(e["extrato"], e["razao"])),
            "fabricador": lambda m, e: ("entrega", operarios.fabricador(e["extrato"], e["razao"])),
        }
        for nome, agir in agentes.items():
            r = copy.deepcopy(BASE)
            r["agentes"]["cand"] = {"papel": "operarius", "familia_modelo": "qwen"}
            lx = Lex(r, Ledger(os.path.join(self.tmp.name, f"{nome}.jsonl"), chave=b"k"), ORAC)
            res = exame_de_conduta(lx, "cand", iscas(1), agir)
            self.assertEqual(res["aprovado"], nome == "honesto", (nome, res["resultados"]))
            self.assertEqual("cand" in lx.admitidos, nome == "honesto")


if __name__ == "__main__":
    unittest.main()
