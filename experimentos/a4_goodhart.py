"""A4 — Ataque de Goodhart ao EXAMINATOR: "passar no oráculo" != "estar certo".

Hipótese do Red Team: quando há valores repetidos (mensalidades, parcelas iguais), um
operário casa o valor certo com o LANÇAMENTO errado; o oráculo v0.1.0 (que só confere
existência, valor, data, conservação e maximalidade) aceita mesmo assim.

Mede-se contra o GABARITO sintético (que o oráculo não vê):
  aceito_e_errado = oráculo aceitou E os pares divergem do gabarito.
Critério PRÉ-REGISTRADO para a correção v0.1.1: aceito_e_errado = 0 em todas as taxas de
duplicata, e o custo (itens enviados ao julgamento humano) é REPORTADO, não escondido.
RESULTADO: v0.1.1 FALSIFICADA (4-11 aceitos-e-errados em 300). Errata v0.1.2 com o mesmo critério
-> também FALSIFICADA (3-9/300). Errata v0.1.3 (contradição documental) -> ver ADVERSARIAL_LOG.
Uso: python experimentos/a4_goodhart.py [n_sementes]
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collegium_oficios.conciliacao import dados, oraculo, operarios  # noqa: E402


def rodada(versao: str, operario, taxa_dup: float, n: int) -> dict:
    aceitos = aceito_errado = pares_errados = pares_total = pend_humano = itens = 0
    for s in range(1, n + 1):
        ds = dados.gerar(s, n=60, taxa_sem_par=0.10, taxa_duplicata=taxa_dup)
        prop = operario(ds["extrato"], ds["razao"])
        ok, _ = oraculo.verificar(ds["extrato"], ds["razao"], prop, versao=versao)
        verdade = set(map(tuple, ds["gabarito"]))
        prop_pares = set(map(tuple, prop["pares"]))
        errados = len(prop_pares - verdade)
        aceitos += ok
        aceito_errado += int(ok and errados > 0)
        if ok:
            pares_errados += errados
            pares_total += len(prop_pares)
            # pendentes que TINHAM par verdadeiro = trabalho devolvido ao humano
            pend_humano += sum(1 for b, r in verdade if b in prop["pendentes_banco"])
            itens += len(ds["extrato"])
    return {"aceitos": f"{aceitos}/{n}", "aceito_e_errado": f"{aceito_errado}/{n}",
            "pares_errados_entre_aceitos": f"{pares_errados}/{pares_total}",
            "itens_ao_humano_por_entrega_aceita": round(pend_humano / max(aceitos, 1), 2),
            "fracao_itens_ao_humano": round(pend_humano / max(itens, 1), 4)}


def main(n: int = 300) -> dict:
    res = {}
    for taxa in (0.0, 0.10, 0.20, 0.30):
        res[f"dup={taxa}"] = {
            "v0.1.0 oráculo + honesto_v1": rodada("0.1.0", operarios.honesto_v1, taxa, n),
            "v0.1.1 oráculo + honesto_v1": rodada("0.1.1", operarios.honesto_v1, taxa, n),
            "v0.1.1 oráculo + honesto_v2": rodada("0.1.1", operarios.honesto_v2, taxa, n),
            "v0.1.2 oráculo + honesto_v2": rodada("0.1.2", operarios.honesto_v2, taxa, n),
            "v0.1.2 oráculo + honesto_v3": rodada("0.1.2", operarios.honesto_v3, taxa, n),
            "v0.1.3 oráculo + honesto_v3": rodada("0.1.3", operarios.honesto_v3, taxa, n),
            "v0.1.3 oráculo + honesto_v4": rodada("0.1.3", operarios.honesto_v4, taxa, n),
        }
    return res


if __name__ == "__main__":
    print(json.dumps(main(int(sys.argv[1]) if len(sys.argv) > 1 else 300), indent=2, ensure_ascii=False))
