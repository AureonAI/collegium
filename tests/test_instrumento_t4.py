"""M4 (10/10/2026): validade do instrumento do T4.
Um operário que segue SOMENTE as regras escritas no enunciado (SISTEMA) tem de ser aceito em
20/20 tarefas. Se não for, o oráculo cobra regra escondida e a reprovação do LLM mede o
enunciado, não o modelo (com o enunciado v1, o operário literal passava só 9/20)."""
import os
import re
import sys
import unittest
from collections import Counter
from datetime import date

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from experimentos import t4_llm_ollama  # noqa: E402
from collegium_oficios.conciliacao import dados, oraculo  # noqa: E402


def literal(ex, rz):
    """Implementa, ao pé da letra, as regras do enunciado v2 — e nada mais."""
    d = date.fromisoformat
    fb, fr = Counter(b["valor"] for b in ex), Counter(r["valor"] for r in rz)
    usados, pares = set(), []
    for b in ex:
        m = re.search(r"NF\d+", b["desc"])
        for r in rz:
            if r["id"] in usados or r["valor"] != b["valor"] or abs((d(b["data"]) - d(r["data"])).days) > 5:
                continue
            if m and r.get("doc") != m.group(0):          # regra: doc citado tem de bater
                continue
            repetido = fb[b["valor"]] > 1 or fr[r["valor"]] > 1
            if repetido and not (r.get("doc") and r["doc"] in b["desc"]):  # regra: valor repetido exige doc
                continue
            pares.append([b["id"], r["id"]])
            usados.add(r["id"])
            break
    casados = {p[0] for p in pares}
    return {"pares": pares, "pendentes_banco": [b["id"] for b in ex if b["id"] not in casados],
            "pendentes_razao": [r["id"] for r in rz if r["id"] not in usados]}


class TestInstrumentoT4(unittest.TestCase):
    def test_enunciado_declara_a_regra_de_valor_repetido(self):
        self.assertIn("MAIS DE UMA VEZ", t4_llm_ollama.SISTEMA)

    def test_operario_literal_do_enunciado_passa_20_de_20(self):
        aceitas = 0
        for s in range(1, 21):
            ds = dados.gerar(1000 + s, n=12, taxa_sem_par=0.15, taxa_duplicata=0.15)
            aceitas += oraculo.verificar(ds["extrato"], ds["razao"], literal(ds["extrato"], ds["razao"]))[0]
        self.assertEqual(aceitas, 20)


if __name__ == "__main__":
    unittest.main()
