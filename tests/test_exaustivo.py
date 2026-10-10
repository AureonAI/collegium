"""T060: verificação exaustiva limitada (T9) + CONTROLES NEGATIVOS: defeitos plantados no LEX
precisam ser encontrados — senão o "zero violações" não vale nada."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collegium.lex as L  # noqa: E402
from experimentos import t9_exaustivo as t9  # noqa: E402


class LexAutoverifica(L.Lex):  # defeito 1: some a lei L3 (quem produz pode verificar)
    def verificar(self, tarefa_id, verificador, entrega, aceito=None, falhas=None):
        t = self.tarefas[tarefa_id]
        if verificador == t.produtor:
            verificador = "ex-det"
            r = super().verificar(tarefa_id, verificador, entrega, aceito, falhas)
            for reg in []:
                pass
            self.anais.anexar("recibo", {"tarefa": tarefa_id, "entrega": t.entrega_hash, "entrada": t.entrada_hash,
                                         "verificador": t.produtor, "produtor": t.produtor, "classe": t.classe,
                                         "por_oraculo": True, "aceito": True, "falhas": []})
            return r
        return super().verificar(tarefa_id, verificador, entrega, aceito, falhas)


class LexAceitaTudo(L.Lex):  # defeito 2: oráculo ignorado (fraude aceita)
    def __init__(self, reg, ledger, oraculos=None, *a, **k):
        super().__init__(reg, ledger, {c: (lambda e, d: (True, [])) for c in (oraculos or {})}, *a, **k)


class LexDeclaracaoFrouxa(L.Lex):  # defeito 3: entrega aceita depois de declarar IMPOSSIVEL
    def submeter(self, tarefa_id, agente, entrega):
        t = self.tarefas.get(tarefa_id)
        if t is not None and t.declaracao:
            t.declaracao = {**t.declaracao, "status": "CONCLUIDO"}
        return super().submeter(tarefa_id, agente, entrega)


class LexMemoriaCurta(L.Lex):  # defeito 4: reinício esquece a quarentena (o D2 de 09/10/2026)
    def _aplicar_incidente(self, agente):
        if getattr(self, "_reconstruindo", False):
            return
        super()._aplicar_incidente(agente)

    def _reconstruir(self):
        self._reconstruindo = True
        try:
            return super()._reconstruir()
        finally:
            self._reconstruindo = False


class TestExaustivo(unittest.TestCase):
    def test_lex_real_zero_violacoes(self):
        r = t9.main(6)
        self.assertEqual(r["n_violacoes"], 0, r["violacoes"])

    def test_controles_negativos(self):
        esperado = {LexAutoverifica: "I2", LexAceitaTudo: "I5", LexDeclaracaoFrouxa: "I3", LexMemoriaCurta: "I7"}
        original = t9.Lex
        try:
            for cls, inv in esperado.items():
                t9.Lex = cls
                r = t9.main(3)
                self.assertIn(inv, r["violacoes"], (cls.__name__, sorted(r["violacoes"])))
        finally:
            t9.Lex = original


if __name__ == "__main__":
    unittest.main()
