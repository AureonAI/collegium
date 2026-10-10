"""Recibo verificável offline — T043.

O operador assina uma CABEÇA (tamanho + raiz Merkle do ANAIS) com a chave Ed25519 do ente.
O cliente recebe um RECIBO: as linhas do ANAIS daquela tarefa + provas de inclusão + a cabeça.
Ele confere SOZINHO, sem acesso ao sistema e sem a chave HMAC:
  1. a cabeça foi assinada pela chave pública que ele já conhece;
  2. cada linha está na árvore daquela cabeça (prova de inclusão);
  3. a tarefa foi aberta sobre a ENTRADA DELE (hash do extrato + razão que ele mesmo tem);
  4. o recibo diz aceito, por oráculo, verificado por quem não produziu.
Guardando cabeças antigas, ele exige prova de consistência e detecta reescrita do histórico.

Limite declarado: o recibo prova que estas linhas EXISTEM; não prova que NÃO existe outra
linha posterior sobre a mesma tarefa (prova de ausência exige outro índice — registrado).
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from . import ed25519
from . import merkle as mk
from .ledger import canonico

FORMATO_CABECA = "collegium-cabeca/1"
FORMATO_RECIBO = "collegium-recibo/1"


def _linhas(fonte) -> list[str]:
    """fonte = caminho de um ANAIS JSONL ou um objeto ledger com .linhas() (JSONL ou SQLite, T058)."""
    if hasattr(fonte, "linhas"):
        return fonte.linhas()
    if not os.path.exists(fonte):
        return []
    with open(fonte, encoding="utf-8") as f:
        return [ln.rstrip("\n") for ln in f if ln.strip()]


def arvore(caminho: str) -> tuple[mk.Arvore, list[str]]:
    linhas = _linhas(caminho)
    return mk.Arvore([mk.folha(ln.encode("utf-8")) for ln in linhas]), linhas


def _corpo_cabeca(c: dict) -> bytes:
    return canonico({k: v for k, v in c.items() if k != "assinatura"})


def cabeca(caminho: str, privada: bytes, ente: str, instante: str, tamanho: int | None = None) -> dict:
    a, _ = arvore(caminho)
    n = len(a) if tamanho is None else tamanho
    c = {"formato": FORMATO_CABECA, "ente": ente, "tamanho": n, "raiz": a.raiz(0, n).hex(),
         "instante": instante, "chave": ed25519.publica(privada).hex()}
    c["assinatura"] = ed25519.assinar(privada, _corpo_cabeca(c)).hex()
    return c


def conferir_cabeca(c: Any, chave_confiavel: str) -> bool:
    try:
        return (c.get("formato") == FORMATO_CABECA and c.get("chave") == chave_confiavel
                and ed25519.verificar(bytes.fromhex(chave_confiavel), _corpo_cabeca(c),
                                      bytes.fromhex(c["assinatura"])))
    except (AttributeError, KeyError, TypeError, ValueError):
        return False


def emitir_recibo(caminho: str, tarefa: str, cab: dict) -> dict:
    a, linhas = arvore(caminho)
    n = cab["tamanho"]
    itens = []
    for i, ln in enumerate(linhas[:n]):
        d = json.loads(ln)["corpo"]
        if d.get("dados", {}).get("tarefa") == tarefa and d["tipo"] in {"tarefa_aberta", "recibo", "decisao"}:
            if d["tipo"] == "decisao" and d["dados"].get("codigo") not in {"LIBERADA", "AGUARDA_HUMANO",
                                                                             "SUBMETIDA", "DECLARADO"}:
                continue
            itens.append({"indice": i, "linha": ln, "prova": [h.hex() for h in a.prova_inclusao(i, n)]})
    return {"formato": FORMATO_RECIBO, "tarefa": tarefa, "cabeca": cab, "itens": itens}


def _hash_obj(obj: Any) -> str:
    return hashlib.sha256(canonico(obj)).hexdigest()


def conferir_recibo(rec: Any, chave_confiavel: str, entrada: Any = None,
                    entrega: Any = None) -> tuple[bool, list[str], dict]:
    """Retorna (ok, motivos_de_recusa, resumo). Falha fechada: qualquer exceção é recusa."""
    motivos: list[str] = []
    resumo: dict = {}
    try:
        if rec.get("formato") != FORMATO_RECIBO:
            return False, ["FORMATO"], resumo
        cab, tarefa = rec["cabeca"], rec["tarefa"]
        if not conferir_cabeca(cab, chave_confiavel):
            return False, ["CABECA_NAO_ASSINADA_PELA_CHAVE_CONFIAVEL"], resumo
        raiz, n = bytes.fromhex(cab["raiz"]), int(cab["tamanho"])
        abertura, recibos, eventos = None, [], []
        for it in rec["itens"]:
            prova = [bytes.fromhex(x) for x in it["prova"]]
            if not mk.verificar_inclusao(mk.folha(it["linha"].encode("utf-8")), int(it["indice"]), n, prova, raiz):
                motivos.append(f"INCLUSAO_FALHOU:{it['indice']}")
                continue
            reg = json.loads(it["linha"])
            if reg.get("i") != it["indice"]:
                motivos.append(f"INDICE_DIVERGENTE:{it['indice']}")
                continue
            corpo = reg["corpo"]
            if corpo["dados"].get("tarefa") != tarefa:
                motivos.append(f"OUTRA_TAREFA:{it['indice']}")
                continue
            if corpo["tipo"] == "tarefa_aberta":
                abertura = corpo["dados"]
            elif corpo["tipo"] == "recibo":
                recibos.append((reg["i"], corpo["dados"]))
            else:
                eventos.append(corpo["dados"].get("codigo"))
        if abertura is None:
            motivos.append("SEM_ABERTURA")
        if not recibos:
            motivos.append("SEM_RECIBO")
        if motivos:
            return False, motivos, resumo
        _, r = max(recibos)  # o recibo mais recente entre os apresentados
        resumo = {"tarefa": tarefa, "classe": r.get("classe"), "aceito": bool(r.get("aceito")),
                  "por_oraculo": bool(r.get("por_oraculo")), "produtor": r.get("produtor"),
                  "verificador": r.get("verificador"), "falhas": r.get("falhas", []),
                  "eventos": eventos, "ente": cab.get("ente"), "instante_cabeca": cab.get("instante")}
        if r.get("entrada") != abertura.get("entrada"):
            motivos.append("ENTRADA_DO_RECIBO_DIFERE_DA_ABERTURA")
        if entrada is not None and _hash_obj(entrada) != abertura.get("entrada"):
            motivos.append("NAO_E_A_SUA_ENTRADA")
        if entrega is not None and _hash_obj(entrega) != r.get("entrega"):
            motivos.append("NAO_E_A_ENTREGA_RECEBIDA")
        if r.get("produtor") == r.get("verificador"):
            motivos.append("AUTOVERIFICACAO")
        if not resumo["aceito"]:
            motivos.append("RECIBO_DE_REJEICAO")
        return (not motivos), motivos, resumo
    except (AttributeError, KeyError, TypeError, ValueError, json.JSONDecodeError) as e:
        return False, [f"RECIBO_MALFORMADO:{type(e).__name__}"], resumo


def prova_consistencia(caminho: str, m: int, n: int) -> list[str]:
    a, _ = arvore(caminho)
    return [h.hex() for h in a.prova_consistencia(m, n)]


def conferir_consistencia(antiga: dict, nova: dict, prova: list[str], chave_confiavel: str) -> bool:
    """O cliente guardou a cabeça antiga; a nova só vale se ESTENDER a antiga."""
    if not (conferir_cabeca(antiga, chave_confiavel) and conferir_cabeca(nova, chave_confiavel)):
        return False
    try:
        return mk.verificar_consistencia(int(antiga["tamanho"]), bytes.fromhex(antiga["raiz"]),
                                         int(nova["tamanho"]), bytes.fromhex(nova["raiz"]),
                                         [bytes.fromhex(x) for x in prova])
    except (KeyError, TypeError, ValueError):
        return False
