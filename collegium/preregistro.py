"""Pré-registro selado (T061). Antes de rodar um experimento, sela-se o ARQUIVO que contém as previsões:
hash SHA-256 + assinatura Ed25519 do autor + entrada numa cadeia própria (preregistros/REGISTRO.jsonl).
Testemunha externa: o workflow do GitHub publica a cabeça dessa cadeia como ANOTAÇÃO a cada envio, com
o carimbo de tempo do GitHub (terceiro). Assim "a previsão veio antes do resultado" deixa de depender só
da data do commit, que o autor controla.
Limite declarado: sem carimbo de tempo RFC 3161 (exige rede para uma autoridade de carimbo); a testemunha
é o GitHub. O que já foi rodado antes deste módulo NÃO é retroativamente pré-registrado.
"""
from __future__ import annotations

import hashlib
import os

from . import ed25519
from .ledger import Ledger, canonico


def hash_arquivo(caminho: str) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(65536), b""):
            h.update(bloco.replace(b"\r\n", b"\n"))  # mesmo hash no Windows (checkout com CRLF) e no Linux
    return h.hexdigest()


def preregistrar(caminho: str, privada: bytes, registro: str, instante: str) -> dict:
    corpo = {"arquivo": os.path.basename(caminho), "sha256": hash_arquivo(caminho), "instante_declarado": instante,
             "chave": ed25519.publica(privada).hex()}
    corpo["assinatura"] = ed25519.assinar(privada, canonico(corpo)).hex()
    os.makedirs(os.path.dirname(os.path.abspath(registro)), exist_ok=True)
    return Ledger(registro).anexar("preregistro", corpo)


def conferir(caminho: str, registro: str, chave_confiavel: str) -> tuple[bool, dict | None]:
    """O arquivo atual é EXATAMENTE um que foi selado? Devolve o registro (com índice na cadeia)."""
    L = Ledger(registro)
    if not L.verificar()[0]:
        return False, None
    h = hash_arquivo(caminho)
    for reg in L.registros():
        d = dict(reg["corpo"]["dados"])
        sig = d.pop("assinatura", "")
        if d.get("sha256") == h and d.get("chave") == chave_confiavel and ed25519.verificar(
                bytes.fromhex(chave_confiavel), canonico(d), bytes.fromhex(sig)):
            return True, {"indice": reg["i"], "selo": reg["selo"], **d}
    return False, None
