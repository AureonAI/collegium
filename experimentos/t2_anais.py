"""T2 — Integridade do ANAIS sob adulteração.

Critério PRÉ-REGISTRADO:
  (a) com chave HMAC fora do alcance do agente: 100% das adulterações detectadas,
      INCLUSIVE recomputar a cadeia inteira (atacante sem a chave);
  (b) sem chave: adulteração ingênua detectada 100%; recomputação total NÃO é detectável
      — esperado e declarado (o ataque vence; mitigação = chave + âncora externa da cabeça).
Errata 0.1.1: o modo truncar_cauda (apagar os registros mais recentes) VENCEU a v0.1.0 com
chave (1/100 em sorteio; 100% quando mirado). Por isso a configuração "com_chave+ancora".
Uso: python experimentos/t2_anais.py [n_tentativas]
"""
from __future__ import annotations

import json
import os
import random
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collegium.ledger import GENESE, Ledger, _selo  # noqa: E402


def _escrever(caminho, regs):
    with open(caminho, "w", encoding="utf-8") as f:
        for r in regs:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")


def adulterar(regs: list[dict], modo: str, rnd: random.Random) -> list[dict]:
    regs = [json.loads(json.dumps(r)) for r in regs]
    k = rnd.randrange(1, len(regs) - 1)
    if modo == "alterar_valor":
        regs[k]["corpo"]["dados"]["valor"] = regs[k]["corpo"]["dados"]["valor"] + 1
    elif modo == "apagar":
        del regs[k]
    elif modo == "trocar_ordem":
        regs[k], regs[k + 1] = regs[k + 1], regs[k]
    elif modo == "truncar_meio":
        k = min(k, len(regs) - 3)
        regs = regs[:k] + regs[k + 2:]
    elif modo == "truncar_cauda":
        regs = regs[:-rnd.randrange(1, 5)]
    elif modo == "recomputar_cadeia":  # atacante reescreve e re-sela tudo SEM a chave
        regs[k]["corpo"]["dados"]["valor"] += 1
        prev = GENESE
        for i, r in enumerate(regs):
            r["i"], r["prev"] = i, prev
            r["selo"] = _selo(prev, r["corpo"], None)
            prev = r["selo"]
    return regs


def main(n: int = 1000) -> dict:
    rnd = random.Random(20261009)
    modos = ["alterar_valor", "apagar", "trocar_ordem", "truncar_meio", "truncar_cauda", "recomputar_cadeia"]
    res = {}
    with tempfile.TemporaryDirectory() as tmp:
        for rotulo, chave, usa_ancora in (("com_chave+ancora", b"segredo-do-patronus", True),
                                          ("com_chave", b"segredo-do-patronus", False),
                                          ("sem_chave", None, False)):
            base = os.path.join(tmp, f"base_{rotulo}.jsonl")
            L = Ledger(base, chave=chave)
            for i in range(200):
                L.anexar("pagamento", {"valor": i * 100, "ref": f"X{i}"})
            regs = list(L.registros())
            anc = L.ancora() if usa_ancora else None
            for modo in modos:
                det = 0
                for j in range(n // len(modos)):
                    alvo = os.path.join(tmp, f"t_{modo}_{j}.jsonl")
                    _escrever(alvo, adulterar(regs, modo, rnd))
                    ok, _ = _Leitor(alvo, chave).verificar(anc)
                    det += int(not ok)
                    os.remove(alvo)
                res[f"{rotulo}/{modo}"] = f"{det}/{n // len(modos)} detectadas"
    return res


class _Leitor(Ledger):
    def __init__(self, caminho, chave):  # leitura sem validação no construtor
        self.caminho, self.chave = caminho, chave


if __name__ == "__main__":
    print(json.dumps(main(int(sys.argv[1]) if len(sys.argv) > 1 else 1000), indent=2, ensure_ascii=False))
