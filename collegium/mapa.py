"""Mapa verificável de tarefas (T067) — fecha R-1 e F-L e corrige R6-7.

R6-7 (10/10/2026): o recibo escolhia quais linhas mostrar. Até o recibo HONESTO omitia a rejeição
do humano (só alguns códigos entravam) e o cliente recebia "válido, aceito" para um trabalho RECUSADO.
O operador desonesto podia, além disso, esconder qualquer linha posterior. Raiz do problema: o
recibo provava que linhas EXISTEM, nunca que eram TODAS.

Solução: a cabeça assinada passa a comprometer também um MAPA — árvore de Merkle (mesma RFC 9162)
sobre folhas ORDENADAS por tarefa, cada folha = {"tarefa": t, "indices": [todas as linhas do ANAIS,
até o tamanho da cabeça, cujo dado "tarefa" é t]}. O cliente confere sozinho:
  1. a folha da tarefa dele está no mapa assinado (prova de inclusão);
  2. não há outra folha para a mesma tarefa: os VIZINHOS na ordem (com prova) têm chaves estritamente
     menor e maior; nas pontas, a posição bate com 0 ou com o tamanho do mapa, também assinado;
  3. o recibo apresenta EXATAMENTE os índices da folha — nem um a menos (nada escondido).
Limite declarado: quem assina pode mentir NO MAPA (ex.: omitir um índice). Isso não fica invisível:
vira uma afirmação ASSINADA e falsa, que qualquer auditor com o ANAIS detecta recalculando o mapa
(`auditar`). É o modelo de confiança dos logs de transparência: fraude passa a ser provável e atribuível.
"""
from __future__ import annotations

import json
from typing import Any

from . import merkle as mk
from .ledger import canonico

FORMATO_MAPA = "collegium-mapa/1"


def _tarefa_da_linha(ln: str) -> str | None:
    try:
        d = json.loads(ln)["corpo"]["dados"]
    except (ValueError, KeyError, TypeError):
        return None
    t = d.get("tarefa") if isinstance(d, dict) else None
    return t if isinstance(t, str) and t else None


def folhas(linhas: list[str], n: int) -> list[dict]:
    por: dict[str, list[int]] = {}
    for i, ln in enumerate(linhas[:n]):
        t = _tarefa_da_linha(ln)
        if t is not None:
            por.setdefault(t, []).append(i)
    return [{"tarefa": t, "indices": por[t]} for t in sorted(por)]


def _bytes(f: dict) -> bytes:
    return canonico({"formato": FORMATO_MAPA, "tarefa": f["tarefa"], "indices": f["indices"]})


def arvore(linhas: list[str], n: int) -> tuple[mk.Arvore, list[dict]]:
    fs = folhas(linhas, n)
    return mk.Arvore([mk.folha(_bytes(f)) for f in fs]), fs


def raiz(linhas: list[str], n: int) -> dict:
    a, fs = arvore(linhas, n)
    return {"raiz": a.raiz(0, len(fs)).hex() if fs else "", "tarefas": len(fs)}


def _no(a: mk.Arvore, fs: list[dict], p: int) -> dict:
    return {"posicao": p, "folha": fs[p], "prova": [h.hex() for h in a.prova_inclusao(p, len(fs))]}


def provar(linhas: list[str], n: int, tarefa: str) -> dict:
    a, fs = arvore(linhas, n)
    chaves = [f["tarefa"] for f in fs]
    if tarefa not in chaves:
        raise KeyError(f"tarefa {tarefa} não está no mapa desta cabeça")
    p = chaves.index(tarefa)
    return {"formato": FORMATO_MAPA, "alvo": _no(a, fs, p),
            "esquerda": _no(a, fs, p - 1) if p > 0 else None,
            "direita": _no(a, fs, p + 1) if p + 1 < len(fs) else None}


def _incluido(no: Any, raiz_b: bytes, tam: int) -> bool:
    try:
        return mk.verificar_inclusao(mk.folha(_bytes(no["folha"])), int(no["posicao"]), tam,
                                     [bytes.fromhex(x) for x in no["prova"]], raiz_b)
    except (KeyError, TypeError, ValueError):
        return False


def conferir(prova: Any, tarefa: str, mapa_cabeca: Any) -> tuple[bool, list[str], dict | None]:
    """Devolve (ok, motivos, folha). Falha fechada."""
    try:
        raiz_b, tam = bytes.fromhex(mapa_cabeca["raiz"]), int(mapa_cabeca["tarefas"])
        alvo = prova["alvo"]
        if alvo["folha"].get("tarefa") != tarefa:
            return False, ["MAPA_OUTRA_TAREFA"], None
        if not _incluido(alvo, raiz_b, tam):
            return False, ["MAPA_INCLUSAO_FALHOU"], None
        p = int(alvo["posicao"])
        esq, dir_ = prova.get("esquerda"), prova.get("direita")
        if p == 0:
            if esq is not None:
                return False, ["MAPA_VIZINHO_INDEVIDO"], None
        elif not (esq and int(esq["posicao"]) == p - 1 and _incluido(esq, raiz_b, tam)
                  and esq["folha"]["tarefa"] < tarefa):
            return False, ["MAPA_UNICIDADE_NAO_PROVADA"], None
        if p == tam - 1:
            if dir_ is not None:
                return False, ["MAPA_VIZINHO_INDEVIDO"], None
        elif not (dir_ and int(dir_["posicao"]) == p + 1 and _incluido(dir_, raiz_b, tam)
                  and dir_["folha"]["tarefa"] > tarefa):
            return False, ["MAPA_UNICIDADE_NAO_PROVADA"], None
        idx = alvo["folha"]["indices"]
        if not (isinstance(idx, list) and idx == sorted(set(idx)) and all(isinstance(i, int) for i in idx)):
            return False, ["MAPA_FOLHA_MALFORMADA"], None
        return True, [], alvo["folha"]
    except (AttributeError, KeyError, TypeError, ValueError):
        return False, ["MAPA_MALFORMADO"], None


def auditar(linhas: list[str], cab: dict) -> tuple[bool, list[str]]:
    """Para AUDITOR com o ANAIS completo: o mapa assinado é exatamente o que o registro diz?"""
    n = int(cab["tamanho"])
    if len(linhas) < n:
        return False, ["ANAIS_MENOR_QUE_A_CABECA"]
    esperado = raiz(linhas, n)
    m = cab.get("mapa")
    if m is None:
        return False, ["CABECA_SEM_MAPA"]
    if (m.get("raiz"), int(m.get("tarefas", -1))) != (esperado["raiz"], esperado["tarefas"]):
        return False, ["MAPA_ASSINADO_DIFERE_DO_ANAIS"]
    return True, []


def estado_da_tarefa(registros: list[dict]) -> dict:
    """Estado FINAL de uma tarefa a partir de TODAS as suas linhas, em ordem — mesmas regras da
    reconstrução do LEX (lex._reconstruir). Quem confere o recibo calcula o estado sozinho."""
    est, entrega, recibo_final, canario, eventos = None, None, None, False, []
    for reg in sorted(registros, key=lambda r: r["i"]):
        tipo, d = reg["corpo"]["tipo"], reg["corpo"]["dados"]
        if tipo == "tarefa_aberta":
            est = "ABERTA"
        elif tipo == "canario":
            canario = True
        elif tipo == "recibo":
            est, recibo_final = ("ACEITA" if d.get("aceito") else "REJEITADA"), dict(d, _indice=reg["i"])
            eventos.append(est)
        elif tipo == "reabertura":
            est, entrega = "ABERTA", None
            eventos.append("REABERTA")
        elif tipo == "decisao":
            c = d.get("codigo")
            if c == "DECLARADO":
                est = "DECLARADA"
            elif c == "SUBMETIDA":
                est, entrega = "SUBMETIDA", d.get("motivo")
            elif c in {"LIBERADA", "AGUARDA_HUMANO"} or (c == "REJEITADA" and d.get("tipo") == "aprovacao"):
                est = c
            if c and c != "OK":
                eventos.append(c)
    return {"estado": est, "entrega": entrega, "recibo_final": recibo_final, "canario": canario,
            "eventos": eventos}
