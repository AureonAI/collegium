"""Linha de comando do Patronus (humano). Chaves SEMPRE pelo ambiente, nunca por argumento:
  COLLEGIUM_CHAVE           chave HMAC do ANAIS
  COLLEGIUM_CHAVE_PATRONUS  chave de assinatura humana

  python -m collegium verificar ANAIS.jsonl [--ancora N:SELO]   integridade (+ cauda, com âncora)
  python -m collegium ancora ANAIS.jsonl                         imprime N:SELO para publicar fora
  python -m collegium relatorio ANAIS.jsonl REGIMENTO.json PASTA gera MEMORIA.md + painel.html
  python -m collegium assinar aprovar TAREFA HASH_ENTREGA true|false HUMANO
  python -m collegium assinar reabilitar AGENTE HUMANO
"""
from __future__ import annotations

import os
import sys

from .equipe import memoria_md, painel_html, relatorio
from .ledger import Ledger
from .lex import Lex, assinar_humano


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
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
