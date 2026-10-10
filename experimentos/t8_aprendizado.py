"""T8 — Aprendizado governado: a regra aprendida das decisões humanas reduz o resíduo SEM errar? (T052)

Mundo: neste "escritório", BOLETO compensa 5 a 7 dias depois do razão (fora da janela padrão de 5).
Os humanos resolvem o resíduo (simulado pelo gabarito). O minerador propõe a nova janela; o backtest
decide se a proposta é aprovável; a validação usa tarefas FUTURAS (sementes nunca vistas).

PREVISÕES (registradas em 10/10/2026, ANTES de rodar; falsificáveis):
  L1. Com 30 tarefas de histórico, o minerador propõe janela entre 6 e 8.
  L2. Backtest: 0 contradições com decisões humanas e resíduo cai >= 30%.
  L3. Em 30 tarefas futuras, com a janela nova: 0 pares automáticos errados (contra o gabarito) e
      resíduo >= 30% menor que com a janela antiga.
  L4. Envenenamento: 3 decisões humanas FALSAS com folga de 12 dias, misturadas ao histórico, não
      empurram a janela proposta para além de 8.

ACHADO PÓS-EXECUÇÃO (registrado, não muda os critérios): com 10 a 30 decisões falsas coordenadas a
proposta continua 7 (o minerador não pula dias sem suporte), mas o backtest passa a mostrar
contradições e a melhoria LEGÍTIMA fica bloqueada: o envenenamento ataca a DISPONIBILIDADE do
aprendizado, não a integridade da regra. Também por isso existe a tolerância estatística opcional.
LIMITE: o mundo foi construído com atraso de 5–7 dias; achar 7 é esperado. Prova o MECANISMO.
"""
from __future__ import annotations

import copy
import os
import sys
from datetime import date, timedelta

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from collegium.aprendizado import backtest  # noqa: E402
from pacotes.conciliacao import dados  # noqa: E402
from pacotes.conciliacao.aprendizado import minerar_janela, rodar  # noqa: E402

BASE = {"janela_dias": 5, "padroes_documento": [r"NF\d+", r"BOL\d+", r"PED\d+"]}


def mundo(seed: int) -> dict:
    ds = copy.deepcopy(dados.gerar_v2(seed, n=50, taxa_lote=0.0))
    R = {x["id"]: x for x in ds["razao"]}
    par = {b: r for b, r in ds["gabarito"]}
    for x in ds["extrato"]:
        if x["desc"].startswith("BOLETO") and x["id"] in par:
            atraso = 5 + (sum(map(ord, x["id"])) + seed) % 3  # 5, 6 ou 7 dias depois do razão
            x["data"] = (date.fromisoformat(R[par[x["id"]]]["data"]) + timedelta(days=atraso)).isoformat()
    return ds


def caso(seed: int, params: dict) -> dict:
    ds = mundo(seed)
    ent = {"extrato": ds["extrato"], "razao": ds["razao"]}
    pares, _ = rodar(params, ent)
    auto = {b for b, _ in pares}
    par = dict(ds["gabarito"])
    hum = {x["id"]: par.get(x["id"]) for x in ds["extrato"] if x["id"] not in auto}  # o humano resolve o resíduo
    return {"entrada": ent, "decisoes_humanas": hum, "gabarito": par}


def main() -> dict:
    hist = [caso(s, BASE) for s in range(1, 31)]
    prop = minerar_janela(hist, BASE["janela_dias"])
    res = {"L1_proposta": prop.proposto if prop else None, "evidencia": prop.evidencia if prop else None}
    bt = backtest(prop, hist, rodar, BASE) if prop else {}
    res["backtest"] = {k: v for k, v in bt.items() if k != "exemplos"}
    novos = {**BASE, "janela_dias": prop.proposto} if prop else BASE
    errados = res_velho = res_novo = 0
    for s in range(1001, 1031):
        c = caso(s, BASE)
        pv, rv = rodar(BASE, c["entrada"])
        pn, rn = rodar(novos, c["entrada"])
        res_velho, res_novo = res_velho + rv, res_novo + rn
        errados += sum(1 for b, r in pn if c["gabarito"].get(b) != r)
    res["L3_futuro"] = {"pares_errados": errados, "residuo_antigo": res_velho, "residuo_novo": res_novo}
    envenenado = copy.deepcopy(hist)
    for i in range(3):  # 3 decisões falsas: casa um item com um par a 12 dias (o atacante "ensina" janela 12)
        c = envenenado[i]
        b = c["entrada"]["extrato"][0]
        r = dict(c["entrada"]["razao"][0])
        r.update({"id": f"RVEN{i}", "valor": b["valor"],
                  "data": (date.fromisoformat(b["data"]) - timedelta(days=12)).isoformat()})
        c["entrada"]["razao"].append(r)
        c["decisoes_humanas"][b["id"]] = r["id"]
    pv = minerar_janela(envenenado, BASE["janela_dias"])
    res["L4_envenenado"] = pv.proposto if pv else None
    queda_bt = 1 - bt["residuo_depois"] / bt["residuo_antes"] if bt.get("residuo_antes") else 0
    queda_fut = 1 - res_novo / res_velho if res_velho else 0
    res["veredito"] = {
        "L1": "PASSOU" if prop and 6 <= prop.proposto <= 8 else "FALHOU",
        "L2": "PASSOU" if bt.get("contradicoes") == 0 and queda_bt >= 0.30 else "FALHOU",
        "L3": "PASSOU" if errados == 0 and queda_fut >= 0.30 else "FALHOU",
        "L4": "PASSOU" if res["L4_envenenado"] is None or res["L4_envenenado"] <= 8 else "FALHOU"}
    res["quedas"] = {"backtest": round(queda_bt, 3), "futuro": round(queda_fut, 3)}
    res["veredito"]["geral"] = "PASSOU" if all(v == "PASSOU" for v in res["veredito"].values()) else "FALHOU"
    return res


if __name__ == "__main__":
    import json
    print(json.dumps(main(), indent=2, ensure_ascii=False))
