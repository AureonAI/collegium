"""Red Team rodada 5 (10/10/2026): validações de entrada que eram ponto cego."""
import copy
import json
import os
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from collegium import Ledger, Lex  # noqa: E402
from collegium.garantia import Calibracao  # noqa: E402

with open(os.path.join(RAIZ, "regimento.exemplo.json"), encoding="utf-8") as _f:
    BASE = json.load(_f)


class TestRodada5(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        r = copy.deepcopy(BASE)
        r["classes_tarefa"]["revisao_documental"]["orcamento"] = {"tokens": 100}
        r["autonomia"]["alcada_quatro_olhos"] = 1000
        self.lex = Lex(r, Ledger(os.path.join(self.tmp.name, "a.jsonl"), chave=b"k"), {})

    def tearDown(self):
        self.tmp.cleanup()

    def test_calibracao_com_tamanhos_diferentes(self):
        with self.assertRaises(ValueError):
            Calibracao([[True, True]] * 5, [True] * 4)          # zip cortaria em silêncio
        with self.assertRaises(ValueError):
            Calibracao([[True, True], [True]], [True, False])   # jurados faltando numa linha

    def test_consumo_negativo_nao_devolve_orcamento(self):
        self.lex.abrir_tarefa("t", "revisao_documental", "op-1")
        self.lex.registrar_consumo("t", tokens=150)
        with self.assertRaises(ValueError):
            self.lex.registrar_consumo("t", tokens=-100)
        self.assertTrue(self.lex.tarefas["t"].esgotada)

    def test_valor_negativo_nao_escapa_da_alcada(self):
        with self.assertRaises(ValueError):
            self.lex.abrir_tarefa("t", "revisao_documental", "op-1", valor=-5000)
        with self.assertRaises(ValueError):
            self.lex.abrir_tarefa("u", "revisao_documental", "op-1", valor=float("nan"))


if __name__ == "__main__":
    unittest.main()
