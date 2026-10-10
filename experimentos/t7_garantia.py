"""T7 — A garantia estatística para classes SEM oráculo se cumpre? (T050)

Simulação com verdade CONHECIDA analiticamente: itens bons com probabilidade π; 3 jurados de
outras famílias com taxas de erro e_i. Cenário "correlacionado": com probabilidade ρ, um modo de
falha comum faz TODOS os jurados aprovarem um item ruim (é o que acontece com linhagens parecidas).

PREVISÕES (registradas em 10/10/2026, ANTES de rodar; falsificáveis):
  G1. Learn-then-Test (α=0.05, δ=0.10, calibração n=600): a fração de simulações em que a política
      escolhida tem risco VERDADEIRO > α é <= δ, nos dois cenários (independente e correlacionado).
  G2. O "voto da maioria sem calibração" tem risco verdadeiro > α no cenário correlacionado
      (é o erro que a garantia existe para evitar).
  G3. Vigia SPRT (p0=α, p1=2α): sem piora, falso alarme <= 5%; com o erro dobrando, revoga em >= 95%.

RESULTADO v1 (10/10/2026): G1 e G2 PASSARAM; G3 FALSIFICADA — detecção 0,94 (300 sim., semente 2026,
erros do teste a=b=0,05). Arquivo: resultados/historico/T7_v1_G3_FALSIFICADO.json. Causa: a previsão
foi posta EXATAMENTE no poder nominal (1-b = 0,95); com o ruído de 300 simulações, é cara ou coroa.
CORREÇÃO PÓS-HOC (declarada): b = 0,02 (poder nominal 98%).
G3-CONFIRMATÓRIA (registrada ANTES de rodar): semente NOVA 2027, 1000 simulações, mesmo critério
(falso alarme <= 5%, detecção >= 95%). Se falhar, fica falsificada também.
"""
from __future__ import annotations

import os
import random
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from collegium.garantia import Calibracao, Vigia, learn_then_test  # noqa: E402

PI, ERROS = 0.80, (0.10, 0.15, 0.20)
ALFA, DELTA, N_CAL = 0.05, 0.10, 600


def amostra(rnd, rho):
    bom = rnd.random() < PI
    if not bom and rnd.random() < rho:
        return [True, True, True], bom          # modo de falha comum: todos aprovam o ruim
    return [(rnd.random() >= e) == bom for e in ERROS], bom


def risco_verdadeiro(minimo, rho, n=200_000, seed=999):
    rnd = random.Random(seed)
    ac = er = 0
    for _ in range(n):
        v, b = amostra(rnd, rho)
        if sum(v) >= minimo:
            ac += 1
            er += not b
    return er / ac if ac else 0.0


B_VIGIA = 0.02  # pós-hoc, ver docstring


def main(sims: int = 300, seed: int = 2026, sims_vigia: int = 1000, seed_vigia: int = 2027) -> dict:
    rnd = random.Random(seed)
    res = {}
    for nome, rho in (("independente", 0.0), ("correlacionado", 0.25)):
        verd = {m: risco_verdadeiro(m, rho) for m in (1, 2, 3)}
        violacoes = escolhidas = 0
        dist = {}
        for _ in range(sims):
            votos, hum = zip(*(amostra(rnd, rho) for _ in range(N_CAL)))
            esc = learn_then_test(Calibracao(list(votos), list(hum)), ALFA, DELTA)
            dist[str(esc.minimo_votos)] = dist.get(str(esc.minimo_votos), 0) + 1
            if esc.minimo_votos is not None:
                escolhidas += 1
                violacoes += verd[esc.minimo_votos] > ALFA
        res[nome] = {"risco_verdadeiro_por_politica": {str(k): round(v, 4) for k, v in verd.items()},
                     "politica_escolhida": dict(sorted(dist.items())),
                     "violacoes": violacoes, "taxa_violacao": round(violacoes / sims, 4),
                     "maioria_sem_calibracao_risco": round(verd[2], 4)}
    # G3: vigia
    fa = det = 0
    amostras = []
    for i in range(sims_vigia):
        r = random.Random(seed_vigia * 100_000 + i)
        v = Vigia(ALFA, 2 * ALFA, a=0.05, b=B_VIGIA)
        while v.estado == "continuar":
            v.registrar(r.random() < ALFA)
        fa += v.estado == "revogar"
        v = Vigia(ALFA, 2 * ALFA, a=0.05, b=B_VIGIA)
        while v.estado == "continuar":
            v.registrar(r.random() < 2 * ALFA)
        det += v.estado == "revogar"
        amostras.append(v.n)
    amostras.sort()
    res["vigia"] = {"falso_alarme": round(fa / sims_vigia, 4), "deteccao": round(det / sims_vigia, 4),
                    "auditorias_ate_decidir_mediana": amostras[len(amostras) // 2], "b": B_VIGIA,
                    "semente": seed_vigia, "simulacoes": sims_vigia}
    res["veredito"] = {
        "G1": "PASSOU" if all(res[k]["taxa_violacao"] <= DELTA for k in ("independente", "correlacionado")) else "FALHOU",
        "G2": "PASSOU" if res["correlacionado"]["maioria_sem_calibracao_risco"] > ALFA else "FALHOU",
        "G3": "PASSOU" if res["vigia"]["falso_alarme"] <= 0.05 and res["vigia"]["deteccao"] >= 0.95 else "FALHOU"}
    res["veredito"]["geral"] = "PASSOU" if all(v == "PASSOU" for v in res["veredito"].values()) else "FALHOU"
    return res


if __name__ == "__main__":
    import json
    print(json.dumps(main(), indent=2, ensure_ascii=False))
