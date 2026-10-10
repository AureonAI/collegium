"""T3 — Autonomia conquistada sob monitoramento contínuo (nível recalculado após CADA tarefa).

v0.1.2 (registro histórico): sem estabilidade, p=0,97 chegava a L2 em 9,8% das trajetórias (A7)
e a reputação antiga protegia o agente que piorava (R4).

Histórico: a v0.1.3 (z=1,96) FALSIFICOU o critério (a): 4,55% (resultados/historico/).
O z=2,326 foi escolhido DEPOIS, num exploratório com a semente 11 (1,85%).
Esta é a execução CONFIRMATÓRIA v0.1.4: mesmos critérios, z=2,326 vindo do REGIMENTO e
semente NOVA (2027), nunca usada antes. Critérios (inalterados):
  (a) p=0,97 chega a L2 em <= 2% das trajetórias de 1000 tarefas;
  (b) p=0,95 <= 1% e p=0,90 <= 0,5%;
  (c) p=0,995 chega a L2 em >= 95%, com mediana de tarefas reportada (custo da cautela);
  (d) DEGRADAÇÃO: agente em L2 (600 tarefas a p=0,999) que passa a p=0,90 perde o L2 em
      <= 100 tarefas em >= 95% das trajetórias.
Uso: python experimentos/t3_autonomia.py [n_trajetorias]
"""
from __future__ import annotations

import json
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collegium.autonomia import Historico, nivel  # noqa: E402

with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "regimento.exemplo.json"), encoding="utf-8") as _f:
    CFG = dict(json.load(_f)["autonomia"], janela_incidente=0)


def trajetoria(p: float, alvo: int, horizonte: int, rnd: random.Random, cfg: dict = CFG) -> int | None:
    h = Historico()
    for t in range(1, horizonte + 1):
        h.registrar(rnd.random() < p)
        if nivel(h, cfg) >= alvo:
            return t
    return None


def degradacao(rnd: random.Random) -> int | None:
    h = Historico()
    for _ in range(600):
        h.registrar(rnd.random() < 0.999)
    if nivel(h, CFG) < 2:
        return -1  # nem chegou a L2: trajetória não conta como "perdeu a tempo"
    for t in range(1, 301):
        h.registrar(rnd.random() < 0.90)
        if nivel(h, CFG) < 2:
            return t
    return None


def main(n: int = 2000) -> dict:
    rnd = random.Random(2027)
    res = {}
    for p in (0.90, 0.95, 0.97, 0.98, 0.99, 0.995, 1.0):
        tempos = [trajetoria(p, 2, 1000, rnd) for _ in range(n)]
        ok = [t for t in tempos if t is not None]
        res[f"p={p}"] = {"chegou_L2": f"{len(ok)}/{n} ({100 * len(ok) / n:.2f}%)",
                         "mediana_tarefas": statistics.median(ok) if ok else None}
    dg = [degradacao(rnd) for _ in range(n // 4)]
    validas = [x for x in dg if x != -1]
    rapidas = [x for x in validas if x is not None and x <= 100]
    res["degradacao_0.999_para_0.90"] = {"trajetorias_validas": len(validas),
                                          "perdeu_L2_em_ate_100": f"{len(rapidas)}/{len(validas)}",
                                          "mediana": statistics.median([x for x in validas if x]) if validas else None}

    def frac(p):
        return int(res[f"p={p}"]["chegou_L2"].split("/")[0]) / n
    v = {"a": frac(0.97) <= 0.02, "b": frac(0.95) <= 0.01 and frac(0.9) <= 0.005, "c": frac(0.995) >= 0.95,
         "d": bool(validas) and len(rapidas) / len(validas) >= 0.95}
    v["geral"] = "PASSOU" if all(v.values()) else "FALSIFICADO"
    res["veredito"] = v
    return res


if __name__ == "__main__":
    print(json.dumps(main(int(sys.argv[1]) if len(sys.argv) > 1 else 2000), indent=2, ensure_ascii=False))
