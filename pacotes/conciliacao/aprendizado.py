"""Minerador de regras da conciliação (T052): janela de compensação aprendida das decisões humanas."""
from __future__ import annotations

from collections import Counter
from datetime import date

from collegium.aprendizado import Proposta

from . import operarios


def _gap(b: dict, r: dict) -> int:
    return abs((date.fromisoformat(b["data"]) - date.fromisoformat(r["data"])).days)


def minerar_janela(casos: list[dict], janela_atual: int, suporte_min: int = 5, fracao_min: float = 0.05,
                   teto: int = 15) -> Proposta | None:
    """Pares confirmados pelo humano FORA da janela atual, mesmo valor. Propõe a maior folga em que cada
    dia usado tem suporte >= max(suporte_min, fracao_min * total_fora). Dias sem suporte (ex.: poucas
    decisões falsas) não puxam a janela."""
    fora: Counter = Counter()
    total_humano = 0
    for c in casos:
        B = {x["id"]: x for x in c["entrada"]["extrato"]}
        R = {x["id"]: x for x in c["entrada"]["razao"]}
        for b, r in c["decisoes_humanas"].items():
            if r is None or b not in B or r not in R or B[b]["valor"] != R[r]["valor"]:
                continue
            total_humano += 1
            g = _gap(B[b], R[r])
            if janela_atual < g <= teto:
                fora[g] += 1
    if not fora:
        return None
    limiar = max(suporte_min, fracao_min * sum(fora.values()))
    dias = sorted(g for g, n in fora.items() if n >= limiar)
    if not dias:
        return None
    # só estende até onde não há BURACO sem suporte (contiguidade a partir da janela atual)
    nova = janela_atual
    for g in range(janela_atual + 1, max(dias) + 1):
        if fora[g] >= limiar or (g + 1 in fora and fora[g + 1] >= limiar):
            nova = g
        else:
            break
    if nova == janela_atual:
        return None
    return Proposta("conciliacao_bancaria", "janela_dias", janela_atual, nova,
                    {"pares_humanos": total_humano, "fora_da_janela_por_dia": dict(sorted(fora.items())),
                     "suporte_exigido": limiar})


def rodar(params: dict, entrada: dict) -> tuple[set, int]:
    p = operarios.honesto_v5(entrada["extrato"], entrada["razao"], params)
    return {tuple(x) for x in p["pares"]}, len(p["pendentes_banco"]) + len(p["pendentes_razao"])
