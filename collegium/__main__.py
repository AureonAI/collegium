"""Linha de comando do Patronus (humano). Chaves SEMPRE pelo ambiente, nunca por argumento:
  COLLEGIUM_CHAVE           chave HMAC do ANAIS
  COLLEGIUM_CHAVE_PATRONUS  chave de assinatura humana

  python -m collegium verificar ANAIS.jsonl [--ancora N:SELO]   integridade (+ cauda, com âncora)
  python -m collegium ancora ANAIS.jsonl                         imprime N:SELO para publicar fora
  python -m collegium relatorio ANAIS.jsonl REGIMENTO.json PASTA gera MEMORIA.md + painel.html
  python -m collegium assinar aprovar TAREFA HASH_ENTREGA true|false HUMANO
  python -m collegium assinar reabilitar AGENTE HUMANO

Assinatura assimétrica (T042, recomendada; a chave privada fica SÓ no computador do humano):
  python -m collegium gerar-chave ARQUIVO_PRIVADO           cria a chave e imprime a PÚBLICA
  python -m collegium hash-regimento REGIMENTO.json          hash a assinar numa mudança de regras
  python -m collegium assinar-ed ARQUIVO_PRIVADO regimento HASH
  python -m collegium assinar-ed ARQUIVO_PRIVADO aprovar TAREFA HASH_ENTREGA true|false HUMANO
  python -m collegium assinar-ed ARQUIVO_PRIVADO reabilitar AGENTE HUMANO

Recibo verificável (T043; o cliente confere sem acesso ao sistema):
  python -m collegium cabeca ANAIS.jsonl ARQUIVO_PRIVADO "NOME DO ENTE"   > cabeca.json
  python -m collegium recibo ANAIS.jsonl TAREFA cabeca.json               > recibo.json
  python -m collegium conferir-recibo recibo.json CHAVE_PUBLICA [ENTRADA.json]
  python -m collegium consistencia ANAIS.jsonl TAMANHO_ANTIGO TAMANHO_NOVO > prova.json
  python -m collegium conferir-consistencia antiga.json nova.json prova.json CHAVE_PUBLICA
"""
from __future__ import annotations

import os
import sys

from .equipe import memoria_md, painel_html, relatorio
from .ledger import Ledger
import json
from datetime import datetime, timezone

from . import ed25519
from . import recibo as rc
from .lex import Lex, _h, assinar_humano, assinar_humano_ed25519, carregar_regimento


def _chave(var: str) -> bytes | None:
    return Ledger.chave_de_ambiente(var)


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    cmd = argv[0]
    if cmd == "verificar":
        L = Ledger.__new__(Ledger)
        L.caminho, L.chave = argv[1], _chave("COLLEGIUM_CHAVE")
        anc = None
        if "--ancora" in argv:
            n, selo = argv[argv.index("--ancora") + 1].split(":")
            anc = (int(n), selo)
        ok, ruim = L.verificar(anc)
        print("ÍNTEGRO" if ok else f"CORROMPIDO a partir do registro {ruim}")
        return 0 if ok else 1
    if cmd == "ancora":
        L = Ledger(argv[1], chave=_chave("COLLEGIUM_CHAVE"))
        n, selo = L.ancora()
        print(f"Publique fora (e-mail, repositório, cartório): {n}:{selo}")
        return 0
    if cmd == "relatorio":
        lex = Lex(argv[2], Ledger(argv[1], chave=_chave("COLLEGIUM_CHAVE")))
        rel = relatorio(lex)
        os.makedirs(argv[3], exist_ok=True)
        with open(os.path.join(argv[3], "MEMORIA.md"), "w", encoding="utf-8") as f:
            f.write(memoria_md(rel))
        with open(os.path.join(argv[3], "painel.html"), "w", encoding="utf-8") as f:
            f.write(painel_html(rel))
        print(f"gerados MEMORIA.md e painel.html em {argv[3]}")
        return 0
    if cmd == "assinar":
        chave = _chave("COLLEGIUM_CHAVE_PATRONUS")
        if not chave:
            print("defina COLLEGIUM_CHAVE_PATRONUS", file=sys.stderr)
            return 2
        campos: list = list(argv[1:])
        if campos[0] == "aprovar":
            campos[3] = campos[3].lower() == "true"
        print(assinar_humano(chave, *campos))
        return 0
    if cmd == "gerar-chave":
        if os.path.exists(argv[1]):
            print("arquivo já existe: não sobrescrevo chave", file=sys.stderr)
            return 2
        sk = ed25519.gerar_privada()
        fd = os.open(argv[1], os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(sk.hex())
        print(ed25519.publica(sk).hex())
        return 0
    if cmd == "hash-regimento":
        print(_h(carregar_regimento(argv[1])))
        return 0
    if cmd == "assinar-ed":
        with open(argv[1], encoding="utf-8") as f:
            sk = bytes.fromhex(f.read().strip())
        campos = list(argv[2:])
        if campos and campos[0] == "aprovar":
            campos[3] = campos[3].lower() == "true"
        print(assinar_humano_ed25519(sk, *campos))
        return 0
    if cmd == "cabeca":
        with open(argv[2], encoding="utf-8") as f:
            sk = bytes.fromhex(f.read().strip())
        agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
        print(json.dumps(rc.cabeca(argv[1], sk, argv[3], agora), ensure_ascii=False, indent=1))
        return 0
    if cmd == "recibo":
        with open(argv[3], encoding="utf-8") as f:
            cab = json.load(f)
        print(json.dumps(rc.emitir_recibo(argv[1], argv[2], cab), ensure_ascii=False, indent=1))
        return 0
    if cmd == "conferir-recibo":
        with open(argv[1], encoding="utf-8") as f:
            rec = json.load(f)
        entrada = None
        if len(argv) > 3:
            with open(argv[3], encoding="utf-8") as f:
                entrada = json.load(f)
        ok, motivos, resumo = rc.conferir_recibo(rec, argv[2], entrada=entrada)
        print(json.dumps({"valido": ok, "motivos": motivos, "resumo": resumo}, ensure_ascii=False, indent=1))
        return 0 if ok else 1
    if cmd == "consistencia":
        print(json.dumps(rc.prova_consistencia(argv[1], int(argv[2]), int(argv[3]))))
        return 0
    if cmd == "conferir-consistencia":
        objs = []
        for a in argv[1:4]:
            with open(a, encoding="utf-8") as f:
                objs.append(json.load(f))
        ok = rc.conferir_consistencia(objs[0], objs[1], objs[2], argv[4])
        print("CONSISTENTE: o histórico só cresceu" if ok else "INCONSISTENTE: histórico reescrito ou cabeça inválida")
        return 0 if ok else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
