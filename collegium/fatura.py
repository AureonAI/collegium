"""Métricas de valor e FATURA conferível pelo cliente (T064) — cobrança por resultado verificável.

Cada item cobrado é um recibo do ANAIS: aceito, por oráculo, da classe com preço, dentro do período, com
PROVA DE INCLUSÃO na cabeça assinada. O cliente confere sozinho: assinatura, inclusão, aceite, período,
duplicidade e soma. Canários (tarefas internas de teste) não são cobrados.
Formato 2 (T067): cada item leva a HISTÓRIA COMPLETA da tarefa, provada pelo mapa assinado na cabeça.
O cliente passa a provar sozinho que o item não era canário (F-L, antes um limite), que o recibo cobrado é
o ÚLTIMO da tarefa e que ninguém (oráculo ou humano) rejeitou a entrega depois.
"""
from __future__ import annotations

import json
from collections import Counter

from . import ed25519
from . import mapa as mp
from . import merkle as mk
from .ledger import canonico
from .recibo import FORMATO_CABECA, arvore, conferir_cabeca

FORMATO = "collegium-fatura/2"


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
    """Cobra cada tarefa UMA vez, pelo seu recibo FINAL, se o estado final não for rejeição nem canário.
    R6-8 (10/10/2026): a v2 inicial cobrava o PRIMEIRO recibo aceito e ignorava a recusa posterior do
    humano; o emissor e o conferidor usavam regras diferentes. Agora ambos usam `mapa.estado_da_tarefa`."""
    a, linhas = arvore(fonte)
    n = int(cab["tamanho"])
    por: dict[str, list[dict]] = {}
    for ln in linhas[:n]:
        reg = json.loads(ln)
        t = reg["corpo"]["dados"].get("tarefa") if isinstance(reg["corpo"]["dados"], dict) else None
        if isinstance(t, str) and t:
            por.setdefault(t, []).append(reg)
    itens = []
    for t in sorted(por, key=lambda k: min(r["i"] for r in por[k])):
        est = mp.estado_da_tarefa(por[t])
        rf = est["recibo_final"]
        if est["canario"] or rf is None or est["estado"] == "REJEITADA":
            continue
        i = rf["_indice"]
        c = json.loads(linhas[i])["corpo"]
        d = c["dados"]
        if not (d.get("aceito") and d.get("por_oraculo") and d.get("classe") in precos and inicio <= c["t"] < fim):
            continue
        j = next(r["i"] for r in por[t] if r["corpo"]["tipo"] == "tarefa_aberta")
        item = {"indice": i, "linha": linhas[i], "prova": [h.hex() for h in a.prova_inclusao(i, n)],
                "abertura": {"indice": j, "linha": linhas[j], "prova": [h.hex() for h in a.prova_inclusao(j, n)]},
                "preco_centavos": int(precos[d["classe"]])}
        if "mapa" in cab:  # T067: história completa da tarefa, provada pelo mapa assinado
            pm = mp.provar(linhas, n, t)
            item["historia"] = {"mapa": pm, "linhas": [
                {"indice": k, "linha": linhas[k], "prova": [h.hex() for h in a.prova_inclusao(k, n)]}
                for k in pm["alvo"]["folha"]["indices"]]}
        itens.append(item)
    f = {"formato": FORMATO, "ente": cab.get("ente"), "periodo": [inicio, fim], "precos": dict(precos),
         "cabeca": cab, "itens": itens, "total_centavos": sum(x["preco_centavos"] for x in itens)}
    f["assinatura"] = ed25519.assinar(privada, _corpo(f)).hex()
    return f


def conferir_fatura(f, chave_confiavel: str, entradas_do_cliente: set[str] | None = None) -> tuple[bool, list[str], dict]:
    """entradas_do_cliente: hashes das entradas que ESTE cliente enviou (ele tem os arquivos); com eles,
    cobrança de tarefa de outro cliente no mesmo ANAIS é detectada."""
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
            ab = it.get("abertura") or {}
            try:
                ok_ab = mk.verificar_inclusao(mk.folha(ab["linha"].encode("utf-8")), int(ab["indice"]), n,
                                              [bytes.fromhex(x) for x in ab["prova"]], raiz)
                da = json.loads(ab["linha"])
            except (KeyError, TypeError, ValueError):
                ok_ab, da = False, {}
            if not ok_ab or da.get("i") != ab.get("indice") or da.get("corpo", {}).get("tipo") != "tarefa_aberta" \
                    or da["corpo"]["dados"].get("tarefa") != d.get("tarefa") or da["corpo"]["dados"].get("entrada") != d.get("entrada"):
                motivos.append(f"ABERTURA_NAO_CONFERE:{d.get('tarefa')}")
            elif entradas_do_cliente is not None and d.get("entrada") not in entradas_do_cliente:
                motivos.append(f"ENTRADA_DE_OUTRO_CLIENTE:{d.get('tarefa')}")
            if f["cabeca"].get("formato") == FORMATO_CABECA:
                motivos += _conferir_historia(it, d, f["cabeca"], n, raiz)
            else:
                motivos.append(f"SEM_PROVA_DE_COMPLETUDE:{d.get('tarefa')}")
            if int(it["preco_centavos"]) != int(f["precos"].get(d.get("classe"), -1)):
                motivos.append(f"PRECO_DIVERGENTE:{d.get('tarefa')}")
            soma += int(it["preco_centavos"])
        if soma != int(f["total_centavos"]):
            motivos.append(f"TOTAL_NAO_FECHA:{f['total_centavos']}!={soma}")
        return (not motivos), motivos, {"itens": len(f["itens"]), "total_centavos": soma, "ente": f.get("ente")}
    except (AttributeError, KeyError, TypeError, ValueError, json.JSONDecodeError) as e:
        return False, [f"FATURA_MALFORMADA:{type(e).__name__}"], {}


def _conferir_historia(it: dict, d: dict, cab: dict, n: int, raiz: bytes) -> list[str]:
    """T067: a história inteira da tarefa, provada pelo mapa: não era canário, o recibo cobrado é o último,
    e ninguém rejeitou depois."""
    t = d.get("tarefa")
    h = it.get("historia")
    if not isinstance(h, dict):
        return [f"SEM_HISTORIA:{t}"]
    ok, mot, folha = mp.conferir(h.get("mapa"), t, cab["mapa"])
    if not ok:
        return [f"{m}:{t}" for m in mot]
    regs = []
    for x in h.get("linhas", []):
        try:
            if not mk.verificar_inclusao(mk.folha(x["linha"].encode("utf-8")), int(x["indice"]), n,
                                         [bytes.fromhex(p) for p in x["prova"]], raiz):
                return [f"HISTORIA_INCLUSAO_FALHOU:{t}"]
            reg = json.loads(x["linha"])
        except (KeyError, TypeError, ValueError):
            return [f"HISTORIA_MALFORMADA:{t}"]
        if reg.get("i") != x["indice"] or reg["corpo"]["dados"].get("tarefa") != t:
            return [f"HISTORIA_OUTRA_LINHA:{t}"]
        regs.append(reg)
    if sorted(r["i"] for r in regs) != folha["indices"]:
        return [f"HISTORIA_INCOMPLETA:{t}"]
    if int(it["indice"]) not in folha["indices"]:
        return [f"RECIBO_FORA_DA_HISTORIA:{t}"]
    est = mp.estado_da_tarefa(regs)
    out = []
    if est["canario"]:
        out.append(f"COBRANCA_DE_CANARIO:{t}")
    if est["recibo_final"] is None or est["recibo_final"]["_indice"] != int(it["indice"]):
        out.append(f"COBRANCA_DE_RECIBO_SUPERADO:{t}")
    if est["estado"] == "REJEITADA":
        out.append(f"COBRANCA_DE_ENTREGA_REJEITADA:{t}")
    return out
