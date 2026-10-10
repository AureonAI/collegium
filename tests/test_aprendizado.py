"""T052: aprendizado governado — proposta, backtest, assinatura do quórum e envenenamento."""
import copy
import json
import os
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from collegium import Ledger, Lex, RegimentoInvalido  # noqa: E402
from collegium import ed25519 as ed  # noqa: E402
from collegium.aprendizado import Proposta, aplicar, backtest  # noqa: E402
from collegium.lex import assinar_humano_ed25519  # noqa: E402
from experimentos import t8_aprendizado as t8  # noqa: E402
from pacotes.conciliacao.aprendizado import minerar_janela, rodar  # noqa: E402

with open(os.path.join(RAIZ, "regimento.exemplo.json"), encoding="utf-8") as _f:
    BASE = json.load(_f)


class TestAprendizado(unittest.TestCase):
    def test_experimento_t8_passa(self):
        self.assertEqual(t8.main()["veredito"]["geral"], "PASSOU")

    def test_proposta_nao_aprovavel_nao_vira_regimento(self):
        p = Proposta("conciliacao_bancaria", "janela_dias", 5, 30, {})
        p.backtest = {"residuo_antes": 10, "residuo_depois": 2, "contradicoes": 4, "alfa": None}
        with self.assertRaises(PermissionError):
            aplicar(BASE, p, "0.1.5")

    def test_tolerancia_estatistica(self):
        p = Proposta("x", "y", 1, 2, {})
        p.backtest = {"residuo_antes": 10, "residuo_depois": 2, "contradicoes": 1, "alfa": 0.05,
                      "limite_superior_contradicao": 0.012}
        self.assertTrue(p.aprovavel)
        p.backtest["limite_superior_contradicao"] = 0.08
        self.assertFalse(p.aprovavel)

    def test_regra_aprendida_so_entra_com_quorum(self):
        sk = {n: bytes([i + 9]) * 32 for i, n in enumerate(["ana", "bia"])}
        reg = copy.deepcopy(BASE)
        reg["patronus"] = {"quorum": 2, "chaves": {n: ed.publica(k).hex() for n, k in sk.items()}}
        hist = [t8.caso(s, t8.BASE) for s in range(1, 11)]
        prop = minerar_janela(hist, 5)
        backtest(prop, hist, rodar, t8.BASE)
        novo, h = aplicar(reg, prop, "0.1.5-aprendido")
        self.assertEqual(novo["parametros_oficio"]["conciliacao_bancaria"]["janela_dias"], prop.proposto)
        with tempfile.TemporaryDirectory() as d:
            cam = os.path.join(d, "a.jsonl")
            Lex(reg, Ledger(cam, chave=b"k"), {})
            with self.assertRaises(RegimentoInvalido):          # aprendeu, mas ninguém assinou: não entra
                Lex(novo, Ledger(cam, chave=b"k"), {})
            sig = {n: assinar_humano_ed25519(k, "regimento", h) for n, k in sk.items()}
            self.assertEqual(Lex(novo, Ledger(cam, chave=b"k"), {}, assinatura_regimento=sig).r["versao"],
                             "0.1.5-aprendido")


if __name__ == "__main__":
    unittest.main()
