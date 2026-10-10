"""Fila do humano (T057): o que espera decisão, com evidência, prazo e a medida de "carimbo".

Carimbo = aprovar sem ler. Mede-se pelo tempo entre a tarefa ENTRAR na fila (registro AGUARDA_HUMANO)
e a decisão humana, ambos selados no ANAIS. Abaixo do mínimo do REGIMENTO
(autonomia.segundos_minimos_decisao, padrão 20 s), a decisão é marcada como suspeita (ASI09).
"""
from __future__ import annotations

from .lex import Lex


def fila(lex: Lex, agora: float) -> list[dict]:
    entrou: dict[str, float] = {}
    recibo: dict[str, dict] = {}
    for reg in lex.anais.registros():
        c = reg["corpo"]
        d = c["dados"]
        if c["tipo"] == "decisao" and d.get("codigo") == "AGUARDA_HUMANO":
            entrou[d["tarefa"]] = c["t"]
        elif c["tipo"] == "recibo":
            recibo[d["tarefa"]] = d
    prazo = float(lex.r["autonomia"].get("prazo_humano_horas", 24)) * 3600
    quatro = float(lex.r["autonomia"].get("alcada_quatro_olhos", 0) or 0)
    out = []
    for tid, t in sorted(lex.tarefas.items()):
        if t.estado != "AGUARDA_HUMANO":
            continue
        r = recibo.get(tid, {})
        idade = agora - entrou.get(tid, agora)
        out.append({"tarefa": tid, "classe": t.classe, "produtor": t.produtor, "valor": t.valor,
                    "irreversivel": t.irreversivel, "entrega": t.entrega_hash,
                    "evidencia": {"verificador": r.get("verificador"), "por_oraculo": r.get("por_oraculo"),
                                  "falhas": r.get("falhas", [])},
                    "aprovacoes": sorted(t.aprovacoes), "aprovacoes_necessarias": 2 if quatro and t.valor >= quatro else 1,
                    "idade_segundos": round(idade, 1), "atrasada": idade > prazo})
    return sorted(out, key=lambda x: (not x["irreversivel"], -x["valor"], -x["idade_segundos"]))


def carimbos(lex: Lex) -> dict:
    """Decisões humanas rápidas demais para terem sido lidas."""
    minimo = float(lex.r["autonomia"].get("segundos_minimos_decisao", 20))
    entrou: dict[str, float] = {}
    total, suspeitas = 0, []
    for reg in lex.anais.registros():
        c = reg["corpo"]
        d = c["dados"]
        if c["tipo"] != "decisao":
            continue
        if d.get("codigo") == "AGUARDA_HUMANO":
            entrou[d["tarefa"]] = c["t"]
        elif d.get("tipo") == "aprovacao" and d.get("permitido") is not None and d["tarefa"] in entrou \
                and d.get("codigo") in {"LIBERADA", "REJEITADA", "APROVACAO_PARCIAL"}:
            total += 1
            dt = c["t"] - entrou[d["tarefa"]]
            if dt < minimo:
                suspeitas.append({"tarefa": d["tarefa"], "humano": d["agente"], "segundos": round(dt, 1)})
    return {"decisoes": total, "carimbos": len(suspeitas), "suspeitas": suspeitas, "minimo_segundos": minimo}
