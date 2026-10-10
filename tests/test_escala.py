"""T072 · escala. O operário de referência era quase quadrático na fase de lotes (30 mil lançamentos: 60 s;
3× o volume custava 8,6× o tempo). A otimização tem de ser IDÊNTICA em comportamento, porque alimenta os
hashes publicados: este teste guarda a versão antiga como referência e compara as duas (teste diferencial)."""
import os
import sys
import time
import unittest
from itertools import combinations

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from collegium_oficios.conciliacao import dados, operarios  # noqa: E402
from collegium_oficios.conciliacao.oraculo import _Ctx, _subconjunto_unico  # noqa: E402


def honesto_v5_referencia(extrato, razao, parametros=None):
    """Cópia LITERAL do honesto_v5 antes do T072 (commit 522cfda)."""
    c = _Ctx(extrato, razao, parametros)
    livres_b = {b["id"]: b for b in extrato if not b.get("revisar")}
    livres_r = {r["id"]: r for r in razao if not r.get("revisar")}
    pares, grupos = [], []

    def ambiguo(b, r):
        return (len(c.cand_r(b)) > 1 or len(c.cand_b(r)) > 1
                or c.freq_b[b["valor"]] > 1 or c.freq_r[r["valor"]] > 1)

    for b in sorted(list(livres_b.values()), key=lambda x: x["id"]):
        cands = [r for r in c.cand_r(b) if r["id"] in livres_r and not c.contradiz(b, r)]
        escolhido = next((r for r in cands if c.evidencia(b, r)), None)
        if escolhido is None and len(cands) == 1 and not ambiguo(b, cands[0]):
            escolhido = cands[0]
        if escolhido is not None:
            pares.append([b["id"], escolhido["id"]])
            del livres_b[b["id"]], livres_r[escolhido["id"]]
    mx = int(c.cfg["max_membros_grupo"])
    for b in sorted(list(livres_b.values()), key=lambda x: x["id"]):
        cands = [r for r in livres_r.values() if c.janela(b, r) and (r["valor"] > 0) == (b["valor"] > 0)]
        if len(cands) > int(c.cfg["max_candidatos_grupo"]):
            continue
        for k in range(2, mx + 1):
            achados = [comb for comb in combinations(cands, k) if sum(x["valor"] for x in comb) == b["valor"]]
            doc = [comb for comb in achados if all(c.evidencia(b, r) for r in comb)]
            pick = doc[0] if len(doc) == 1 else (achados[0] if len(achados) == 1 and
                                                 _subconjunto_unico(c, [b], list(achados[0])) else None)
            if pick:
                grupos.append({"banco": [b["id"]], "razao": sorted(r["id"] for r in pick)})
                del livres_b[b["id"]]
                for r in pick:
                    del livres_r[r["id"]]
                break
    pend_b = sorted(set(livres_b) | {b["id"] for b in extrato if b.get("revisar")})
    pend_r = sorted(set(livres_r) | {r["id"] for r in razao if r.get("revisar")})
    return {"pares": pares, "grupos": grupos, "pendentes_banco": pend_b, "pendentes_razao": pend_r}


class TestEscala(unittest.TestCase):
    def test_diferencial_identico_a_referencia(self):
        casos = 0
        for semente in range(40):
            for n in (8, 30, 80, 200):
                for gerador in (dados.gerar, dados.gerar_v2):
                    ds = gerador(semente, n=n)
                    for params in (None, {"janela_dias": 2, "max_candidatos_grupo": 6, "max_membros_grupo": 3}):
                        self.assertEqual(operarios.honesto_v5(ds["extrato"], ds["razao"], params),
                                         honesto_v5_referencia(ds["extrato"], ds["razao"], params),
                                         (semente, n, gerador.__name__, params))
                        casos += 1
        self.assertEqual(casos, 640)

    def test_dez_mil_lancamentos_em_tempo_de_produto(self):
        ds = dados.gerar_v2(42, n=10000, taxa_injecao=0.0)
        t = time.perf_counter()
        operarios.honesto_v5(ds["extrato"], ds["razao"])
        self.assertLess(time.perf_counter() - t, 3.0)  # antes: ~6 s nesta máquina; folga para o CI


if __name__ == "__main__":
    unittest.main()
