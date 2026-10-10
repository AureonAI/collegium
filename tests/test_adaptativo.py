"""T051: regressão dos ataques ACHADOS pelo atacante adaptativo (A6) e pela revisão manual.
Cada caso derrubava o LEX com exceção (falha aberta) ou burlava o dever de declarar."""
import json
import os
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from collegium import Acao, Ledger, Lex  # noqa: E402

with open(os.path.join(RAIZ, "regimento.exemplo.json"), encoding="utf-8") as _f:
    REG = json.load(_f)

ACHADOS_A6 = [  # (agente, tipo, alvo, tarefa, payload) — exemplos reais do A6 v1
    ("op-1", "ferramenta", b"tarefa.distribuir", "t", {"dados": 7}),
    ("op-1", ["mensagem"], "email", "t", {"contaDestino": 7}),
    ("op-1", "ferramenta", "tarefa.distribuir", ["t"], {"dados": 7}),
    ({"alvo": "ex-q"}, "ferramenta", "extrato.ler", "t", {"dados": {"url": 7}}),
    ("op-1", "declaracao", ["CONCLUIDO"], "t", {"chave_pix": [1]}),
    ("op-1", "declaracao", "CONCLUIDO", "t", "texto"),
]


class TestAdaptativo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.lex = Lex(REG, Ledger(os.path.join(self.tmp.name, "a.jsonl"), chave=b"k"), {})
        self.lex.abrir_tarefa("t", "revisao_documental", "op-1")

    def tearDown(self):
        self.tmp.cleanup()

    def test_acao_malformada_e_recusada_sem_derrubar_o_lex(self):
        for caso in ACHADOS_A6:
            d = self.lex.autorizar(Acao(*caso))       # antes: TypeError (falha aberta)
            self.assertFalse(d.permitido, caso)
            self.assertEqual(d.codigo, "ACAO_MALFORMADA", caso)
        self.assertTrue(self.lex.anais.verificar()[0])

    def test_submeter_em_tarefa_inexistente_ou_malformada(self):
        """Achado na mesma revisão: submeter levantava KeyError/TypeError (o agente controla o id)."""
        self.assertEqual(self.lex.submeter("nao-existe", "op-1", {}).codigo, "TAREFA_INEXISTENTE")
        self.assertEqual(self.lex.submeter(["t"], "op-1", {}).codigo, "ACAO_MALFORMADA")
        self.assertEqual(self.lex.mandato("op-1").submeter({"t": 1}, {}).codigo, "ACAO_MALFORMADA")

    def test_payload_nao_sobrescreve_o_status_declarado(self):
        """Revisão manual (o A6 só reencontrou depois de ajuste de aptidão): declarar IMPOSSIVEL com
        payload {'status': 'CONCLUIDO'} deixava entregar depois — burla do Art. 3."""
        d = self.lex.autorizar(Acao("op-1", "declaracao", "IMPOSSIVEL", "t",
                                    {"evidencia": "não consigo", "status": "CONCLUIDO"}))
        self.assertTrue(d.permitido)
        self.assertEqual(self.lex.tarefas["t"].declaracao["status"], "IMPOSSIVEL")
        self.assertEqual(self.lex.submeter("t", "op-1", {"inventado": 1}).codigo, "DECLARADA_IMPOSSIVEL")


if __name__ == "__main__":
    unittest.main()
