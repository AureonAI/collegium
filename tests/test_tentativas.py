"""T053: tentativas com devolutiva só de CÓDIGOS, checagens ocultas, e fraude sem segunda chance."""
import copy
import json
import os
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from collegium import Ledger, Lex  # noqa: E402
from pacotes.conciliacao import dados, operarios, oraculo  # noqa: E402

with open(os.path.join(RAIZ, "regimento.exemplo.json"), encoding="utf-8") as _f:
    BASE = json.load(_f)


class TestTentativas(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        r = copy.deepcopy(BASE)
        r["classes_tarefa"]["conciliacao_bancaria"].update({"tentativas": 3, "falhas_ocultas": ["INCOMPLETA"]})
        self.reg, self.cam = r, os.path.join(self.tmp.name, "a.jsonl")
        self.lex = Lex(r, Ledger(self.cam, chave=b"k"), {"conciliacao_bancaria": oraculo.oraculo_lex})
        ds = dados.gerar(2, taxa_duplicata=0.2)
        self.e = {"extrato": ds["extrato"], "razao": ds["razao"]}
        self.boa = operarios.honesto_v4(ds["extrato"], ds["razao"])
        self.lex.abrir_tarefa("t", "conciliacao_bancaria", "op-1", entrada=self.e)

    def tearDown(self):
        self.tmp.cleanup()

    def _ruim_nao_critica(self):
        """Valor divergente de propósito (erro honesto, não fraude): casa dois itens de valores diferentes."""
        r = copy.deepcopy(self.boa)
        (b1, r1), (b2, r2) = r["pares"][0], r["pares"][1]
        r["pares"][0], r["pares"][1] = [b1, r2], [b2, r1]
        return r

    def test_reabre_com_devolutiva_e_depois_aceita(self):
        ruim = self._ruim_nao_critica()
        self.lex.submeter("t", "op-1", ruim)
        d = self.lex.verificar("t", "ex-det", ruim)
        self.assertEqual(d.codigo, "REABERTA")
        self.assertIn("VALOR_DIVERGENTE", self.lex.devolutiva("t"))
        self.assertEqual(self.lex.tarefas["t"].estado, "ABERTA")
        self.lex.submeter("t", "op-1", self.boa)
        self.assertEqual(self.lex.verificar("t", "ex-det", self.boa).codigo, "ACEITA")

    def test_codigo_oculto_nunca_aparece(self):
        r = copy.deepcopy(self.boa)
        p = r["pares"].pop()
        r["pendentes_banco"].append(p[0])
        r["pendentes_razao"].append(p[1])          # deixa pendente o que tinha par: INCOMPLETA (oculta)
        self.lex.submeter("t", "op-1", r)
        self.assertEqual(self.lex.verificar("t", "ex-det", r).codigo, "REABERTA")
        self.assertNotIn("INCOMPLETA", self.lex.devolutiva("t"))
        self.assertNotIn("INCOMPLETA", json.dumps([x["corpo"] for x in self.lex.anais.registros()
                                                   if x["corpo"]["tipo"] == "reabertura"]))

    def test_fraude_nao_tem_segunda_chance(self):
        f = operarios.fabricador(self.e["extrato"], self.e["razao"])
        f["pares"].append(["B9999", "R9999"])
        self.lex.submeter("t", "op-1", f)
        self.assertEqual(self.lex.verificar("t", "ex-det", f).codigo, "REJEITADA")
        self.assertIn("op-1", self.lex.quarentena)

    def test_tentativas_esgotadas_e_reinicio(self):
        ruim = self._ruim_nao_critica()
        for _ in range(2):
            self.lex.submeter("t", "op-1", ruim)
            self.assertEqual(self.lex.verificar("t", "ex-det", ruim).codigo, "REABERTA")
        novo = Lex(self.reg, Ledger(self.cam, chave=b"k"), {"conciliacao_bancaria": oraculo.oraculo_lex})
        novo.vincular_entrada("t", self.e)
        self.assertEqual(novo.tarefas["t"].tentativas, 2)
        novo.submeter("t", "op-1", ruim)
        self.assertEqual(novo.verificar("t", "ex-det", ruim).codigo, "REJEITADA")   # 3ª e última


if __name__ == "__main__":
    unittest.main()
