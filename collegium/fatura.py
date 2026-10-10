"""Métricas de valor e FATURA conferível pelo cliente (T064) — cobrança por resultado verificável.

Cada item cobrado é um recibo do ANAIS: aceito, por oráculo, da classe com preço, dentro do período, com
PROVA DE INCLUSÃO na cabeça assinada. O cliente confere sozinho: assinatura, inclusão, aceite, período,
duplicidade e soma. Canários (tarefas internas de teste) não são cobrados.
Limite declarado: o cliente não consegue PROVAR que um item cobrado não era canário (exigiria prova de
ausência); mitigação: o cliente cruza com os próprios recibos, que só existem para tarefas dele.
"""
from __future__ import annotations

import json
from collections import Counter

from . import ed25519
from . import merkle as mk
from .ledger import canonico
from .recibo import arvore, conferir_cabeca

FORMATO = "collegium-fatura/1"


def metricas(fonte) -> dict:
    """Métricas de valor tiradas SÓ do ANAIS (nada declarado à mão)."""
    c: Counter = Counter()
    por_classe: dict[str, Counter] = {}
    for ln in arvore(fonte)[1]:
        corpo = json.loads(ln)["corpo"]
        d = corpo["dados"]
        if corpo["tipo"] == "recibo":
            k = por_classe.setdefault(d.get("classe", "?"), Counter())
            k["recibos"] += 1
            k["aceitos"] += bool(d.get("aceito"))
            k["por_oraculo"] += bool(d.get("por_oraculo"))
        elif corpo["tipo"] in ("incidente", "declaracao", "canario", "lacuna_oraculo", "atestacao_modelo"):
            c[corpo["tipo"]] += 1
        elif corpo["tipo"] == "decisao" and d.get("tipo") == "aprovacao":
            c["decisoes_humanas"] += 1
        elif corpo["tipo"] == "decisao" and d.get("codigo") == "AGUARDA_HUMANO":
            c["foram_ao_humano"] += 1
    out = {"por_classe": {k: dict(v) for k, v in sorted(por_classe.items())}, **dict(sorted(c.items()))}
    for k, v in out["por_classe"].items():
        v["taxa_aceite"] = round(v["aceitos"] / v["recibos"], 4) if v["recibos"] else None
    return out


def _corpo(f: dict) -> bytes:
    return canonico({k: v for k, v in f.items() if k != "assinatura"})


def emitir_fatura(fonte, cab: dict, inicio: float, fim: float, precos: dict[str, int], privada: bytes) -> dict:
    a, linhas = arvore(fonte)
    n = int(cab["tamanho"])
    canarios = set()
    for ln in linhas[:n]:
        c = json.loads(ln)["corpo"]
        if c["tipo"] == "canario":
            canarios.add(c["dados"]["tarefa"])
    itens, cobradas = [], set()
    for i, ln in enumerate(linhas[:n]):
        c = json.loads(ln)["corpo"]
        d = c["dados"]
        if (c["tipo"] == "recibo" and d.get("aceito") and d.get("por_oraculo") and d.get("classe") in precos
                and inicio <= c["t"] < fim and d["tarefa"] not in canarios and d["tarefa"] not in cobradas):
            cobradas.add(d["tarefa"])
            itens.append({"indice": i, "linha": ln, "prova": [h.hex() for h in a.prova_inclusao(i, n)],
                          "preco_centavos": int(precos[d["classe"]])})
    f = {"formato": FORMATO, "ente": cab.get("ente"), "periodo": [inicio, fim], "precos": dict(precos),
         "cabeca": cab, "itens": itens, "total_centavos": sum(x["preco_centavos"] for x in itens)}
    f["assinatura"] = ed25519.assinar(privada, _corpo(f)).hex()
    return f


def conferir_fatura(f, chave_confiavel: str) -> tuple[bool, list[str], dict]:
    try:
        if f.get("formato") != FORMATO:
            return False, ["FORMATO"], {}
        if not conferir_cabeca(f["cabeca"], chave_confiavel):
            return False, ["CABECA_NAO_CONFIAVEL"], {}
        if not ed25519.verificar(bytes.fromhex(chave_confiavel), _corpo(f), bytes.fromhex(f["assinatura"])):
            return False, ["FATURA_NAO_ASSINADA_PELA_CHAVE_CONFIAVEL"], {}
        raiz, n = bytes.fromhex(f["cabeca"]["raiz"]), int(f["cabeca"]["tamanho"])
        ini, fim = f["periodo"]
        motivos, vistas, soma = [], set(), 0
        for it in f["itens"]:
            prova = [bytes.fromhex(x) for x in it["prova"]]
            if not mk.verificar_inclusao(mk.folha(it["linha"].encode("utf-8")), int(it["indice"]), n, prova, raiz):
                motivos.append(f"INCLUSAO_FALHOU:{it['indice']}")
                continue
            reg = json.loads(it["linha"])
            c, d = reg["corpo"], reg["corpo"]["dados"]
            if reg["i"] != it["indice"] or c["tipo"] != "recibo":
                motivos.append(f"NAO_E_RECIBO:{it['indice']}")
                continue
            if not (d.get("aceito") and d.get("por_oraculo")):
                motivos.append(f"COBRANCA_DE_NAO_ACEITO:{d.get('tarefa')}")
            if d.get("verificador") == d.get("produtor"):
                motivos.append(f"AUTOVERIFICACAO:{d.get('tarefa')}")
            if not ini <= c["t"] < fim:
                motivos.append(f"FORA_DO_PERIODO:{d.get('tarefa')}")
            if d.get("tarefa") in vistas:
                motivos.append(f"COBRANCA_DUPLICADA:{d.get('tarefa')}")
            vistas.add(d.get("tarefa"))
            if int(it["preco_centavos"]) != int(f["precos"].get(d.get("classe"), -1)):
                motivos.append(f"PRECO_DIVERGENTE:{d.get('tarefa')}")
            soma += int(it["preco_centavos"])
        if soma != int(f["total_centavos"]):
            motivos.append(f"TOTAL_NAO_FECHA:{f['total_centavos']}!={soma}")
        return (not motivos), motivos, {"itens": len(f["itens"]), "total_centavos": soma, "ente": f.get("ente")}
    except (AttributeError, KeyError, TypeError, ValueError, json.JSONDecodeError) as e:
        return False, [f"FATURA_MALFORMADA:{type(e).__name__}"], {}
