"""T049: dois ofícios sob o MESMO núcleo + suíte de conformidade com mutação."""
import copy
import json
import os
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from collegium import Ledger, Lex  # noqa: E402
from collegium.oficio import conformidade  # noqa: E402
from collegium_oficios import tres_vias as tv  # noqa: E402
from collegium_oficios.conciliacao.oficio import OFICIO as CONC  # noqa: E402

with open(os.path.join(RAIZ, "regimento.exemplo.json"), encoding="utf-8") as _f:
    BASE = json.load(_f)


class TestTresVias(unittest.TestCase):
    def _duplicidade(self):
        for s in range(1, 200):
            c = tv.gerar(s)
            if "DUPLICIDADE" in c["gabarito"]["anomalia"].values():
                return c
        self.fail("gerador não produziu duplicidade")

    def test_duplicidade_paga_a_mais_antiga_e_marca_a_outra(self):
        """Achado do teste de mutação: pagar a 2ª via no lugar da 1ª passava; o motivo era impreciso."""
        c = self._duplicidade()
        e = c["entrada"]
        p = tv.operario(copy.deepcopy(e))
        dup = next(i for i, t in c["gabarito"]["anomalia"].items() if t == "DUPLICIDADE")
        self.assertIn({"id": dup, "motivo": "DUPLICIDADE"}, p["retidas"])
        nfs = {n["id"]: n for n in e["notas"]}
        orig = next(i for i in p["aprovadas"] if nfs[i]["pedido"] == nfs[dup]["pedido"]
                    and nfs[i]["itens"] == nfs[dup]["itens"])
        invertido = {"aprovadas": [dup if x == orig else x for x in p["aprovadas"]],
                     "retidas": [{"id": orig, "motivo": "DUPLICIDADE"} if x["id"] == dup else x for x in p["retidas"]]}
        ok, falhas = tv.verificar(e, invertido)
        self.assertFalse(ok)
        self.assertTrue(any(f.startswith("RETENCAO_INDEVIDA") for f in falhas), falhas)

    def test_operario_bate_com_o_gabarito_construido(self):
        ok = tot = 0
        for s in range(1, 61):
            c = tv.gerar(s)
            ap = set(tv.operario(c["entrada"])["aprovadas"])
            for nid, tipo in c["gabarito"]["anomalia"].items():
                tot += 1
                ok += (nid in ap) == (tipo is None)
        self.assertEqual(ok, tot)


class TestConformidade(unittest.TestCase):
    def test_os_dois_oficios_sao_conformes(self):
        for of in (CONC, tv.OFICIO):
            r = conformidade(of, range(1, 41))
            self.assertTrue(r["conforme"], (of.nome, r["falhas"][:5], r["escore_mutacao"]))
            self.assertEqual(r["sobreviventes"], [], of.nome)

    def test_suite_pega_oraculo_fraco(self):
        """Controle negativo: um oráculo que aceita tudo PRECISA ser reprovado pela suíte."""
        fraco = copy.copy(tv.OFICIO)
        fraco.oraculo = lambda e, d: (True, [])
        r = conformidade(fraco, range(1, 6))
        self.assertFalse(r["conforme"])
        self.assertTrue(any(f.startswith("C3") for f in r["falhas"]))


class TestNucleoAgnostico(unittest.TestCase):
    def test_tres_vias_no_mesmo_lex_sem_mudar_o_nucleo(self):
        reg = copy.deepcopy(BASE)
        reg["classes_tarefa"].update(tv.OFICIO.classe_regimento())
        with tempfile.TemporaryDirectory() as d:
            lex = Lex(reg, Ledger(os.path.join(d, "a.jsonl"), chave=b"k"), {"tres_vias": tv.verificar})
            c = tv.gerar(7)
            boa = tv.operario(c["entrada"])
            lex.abrir_tarefa("ap1", "tres_vias", "op-1", entrada=c["entrada"])
            lex.submeter("ap1", "op-1", boa)
            self.assertEqual(lex.verificar("ap1", "ex-det", boa).codigo, "ACEITA")
            fraude = copy.deepcopy(boa)
            fraude["aprovadas"].append("NF999999")           # paga nota que não existe
            lex.abrir_tarefa("ap2", "tres_vias", "op-2", entrada=c["entrada"])
            lex.submeter("ap2", "op-2", fraude)
            self.assertEqual(lex.verificar("ap2", "ex-det", fraude).codigo, "REJEITADA")
            self.assertIn("op-2", lex.quarentena)                 # fabricação = fraude, também neste ofício


if __name__ == "__main__":
    unittest.main()
