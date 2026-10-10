"""Resíduo da conciliação (T039/T040, decisão A de 10/10/2026).

Arquitetura híbrida: o CÓDIGO concilia (operário determinístico sob o LEX) e o que sobra
pendente vira um PACOTE para o humano, com motivo e candidatos calculados por código.
O LLM só escreve NOTAS sobre esse pacote: nunca cria par, nunca entra na conciliação aceita.

Por quê: com LLMs reais <= 4B, 0/79 conciliações aceitas; o operário determinístico, 20/20.
"""
from __future__ import annotations

from collections import Counter

from .oraculo import _Ctx

MOTIVOS = ("ITEM_REVISAR", "DOC_CONTRADIZ", "SEM_CANDIDATO_1A1", "VALOR_REPETIDO_SEM_DOC",
           "CANDIDATO_UNICO_NAO_CASADO")
MAX_TEXTO = 300


def _dist(a: dict, b: dict) -> tuple:
    from datetime import date
    return (abs((date.fromisoformat(a["data"]) - date.fromisoformat(b["data"])).days), b["id"])


def pacote_humano(extrato: list, razao: list, proposta: dict, parametros: dict | None = None) -> list[dict]:
    """Cada item pendente (dos dois lados) com motivo e candidatos 1:1 ainda pendentes do outro lado,
    ordenados pela data mais próxima. Determinístico: o mesmo dado gera o mesmo pacote."""
    c = _Ctx(extrato, razao, parametros)
    pb = {x for x in proposta["pendentes_banco"] if x in c.B}
    pr = {x for x in proposta["pendentes_razao"] if x in c.R}
    itens = []
    for lado, ids, proprio, outro_pend, cands_de in (
            ("banco", pb, c.B, pr, lambda x: c.cand_r(x)),
            ("razao", pr, c.R, pb, lambda x: c.cand_b(x))):
        for i in sorted(ids):
            x = proprio[i]
            todos = [y for y in cands_de(x) if y["id"] in outro_pend]
            par = (lambda y: (x, y)) if lado == "banco" else (lambda y: (y, x))
            validos = [y for y in todos if not c.contradiz(*par(y))]
            if x.get("revisar"):
                motivo = "ITEM_REVISAR"
            elif not validos:
                motivo = "DOC_CONTRADIZ" if todos else "SEM_CANDIDATO_1A1"
            elif len(validos) > 1 or c.freq_b[x["valor"]] > 1 or c.freq_r[x["valor"]] > 1:
                motivo = "VALOR_REPETIDO_SEM_DOC"
            else:
                motivo = "CANDIDATO_UNICO_NAO_CASADO"  # não deveria ocorrer com o operário v5
            itens.append({"id": i, "lado": lado, "motivo": motivo,
                          "candidatos": [y["id"] for y in sorted(validos, key=lambda y: _dist(x, y))]})
    return itens


def sugestao_base(item: dict) -> str | None:
    """Linha de base trivial: o candidato de data mais próxima, ou nenhum."""
    return item["candidatos"][0] if item["candidatos"] else None


def verificar_nota(pacote: list[dict], nota) -> tuple[bool, list[str]]:
    """Oráculo da nota do LLM. Puro, sem I/O. Códigos estáveis (REGRAS II.3)."""
    if not isinstance(nota, dict) or not isinstance(nota.get("itens"), list):
        return False, ["FORMATO_INVALIDO"]
    itens = {x["id"]: x for x in pacote}
    vistos, falhas = Counter(), []
    for n in nota["itens"]:
        if not isinstance(n, dict) or not isinstance(n.get("id"), str):
            falhas.append("FORMATO_INVALIDO:item")
            continue
        i = n["id"]
        if i not in itens:
            falhas.append(f"REFERENCIA_INEXISTENTE:{i}")
            continue
        vistos[i] += 1
        s = n.get("sugestao")
        if s not in (None, "") and s not in itens[i]["candidatos"]:
            falhas.append(f"SUGESTAO_FORA_DOS_CANDIDATOS:{i}:{s}")
        t = n.get("texto", "")
        if not isinstance(t, str) or len(t) > MAX_TEXTO:
            falhas.append(f"TEXTO_INVALIDO:{i}")
    for i in itens:
        if vistos[i] == 0:
            falhas.append(f"CONSERVACAO:{i}")  # Art. 7: omitir item do humano é crítico
        elif vistos[i] > 1:
            falhas.append(f"REUSO:{i}")
    return (not falhas), falhas


def oraculo_nota_lex(entrada: dict, entrega) -> tuple[bool, list[str]]:
    """Forma que o LEX registra: o pacote vem vinculado à tarefa, não do LLM."""
    return verificar_nota(entrada["pacote"], entrega)


def verdade_do_item(item: dict, gabarito: list) -> set[str]:
    """Pares verdadeiros do item segundo o gabarito (só para medir; o operário nunca vê)."""
    if item["lado"] == "banco":
        return {r for b, r in gabarito if b == item["id"]}
    return {b for b, r in gabarito if r == item["id"]}


def acertou(sugestao: str | None, verdade: set[str]) -> bool | None:
    """True/False quando dá para julgar; None quando o item é de grupo (mais de um par verdadeiro)."""
    if len(verdade) > 1:
        return None
    return (sugestao or None) == (next(iter(verdade)) if verdade else None)
