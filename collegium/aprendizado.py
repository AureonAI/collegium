"""Aprendizado GOVERNADO (T052): as decisões humanas do resíduo viram propostas de regra.

Nada aprende sozinho em produção. O ciclo é:
  1. minerar: decisões humanas -> Proposta (com suporte mínimo e sem contradição);
  2. backtest: reexecuta o histórico com a regra nova; conta pares automáticos que CONTRADIZEM uma
     decisão humana (tem de ser zero) e quanto o resíduo cai;
  3. aplicar: gera o REGIMENTO novo (seção parametros_oficio) e o HASH que o quórum do Patronus
     assina (Art. 12). Sem assinatura, o LEX recusa o REGIMENTO novo. Desfazer = assinar o anterior.
Envenenamento (OWASP ASI06): poucas decisões falsas não movem regra — o minerador exige suporte
mínimo absoluto E relativo; o limite residual é declarado no experimento T8.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Callable

from .lex import _h


@dataclass
class Proposta:
    oficio: str
    parametro: str
    atual: Any
    proposto: Any
    evidencia: dict
    backtest: dict = field(default_factory=dict)

    @property
    def aprovavel(self) -> bool:
        b = self.backtest
        if not b or b.get("residuo_depois", 1) >= b.get("residuo_antes", 0):
            return False
        if b.get("alfa") is None:  # padrão: estrito, nenhuma contradição
            return b.get("contradicoes", 1) == 0
        # tolerância estatística (um erro humano honesto não trava o aprendizado para sempre):
        return b["limite_superior_contradicao"] <= b["alfa"]


def backtest(prop: Proposta, casos: list[dict], rodar: Callable[[dict, dict], tuple[set, int]],
             parametros_atuais: dict, alfa: float | None = None) -> dict:
    """casos: [{"entrada": ..., "decisoes_humanas": {item: par_ou_None}}].
    rodar(params, entrada) -> (pares_automaticos, tamanho_do_residuo)."""
    novos = {**parametros_atuais, prop.parametro: prop.proposto}
    res_a = res_d = contr = novos_auto = 0
    exemplos = []
    for c in casos:
        pa, ra = rodar(parametros_atuais, c["entrada"])
        pd, rd = rodar(novos, c["entrada"])
        res_a, res_d = res_a + ra, res_d + rd
        hum = c["decisoes_humanas"]
        for b, r in pd - pa:
            novos_auto += 1
            if b in hum and hum[b] != r:  # o humano decidiu OUTRA coisa para este item
                contr += 1
                exemplos.append((b, r, hum[b]))
    from .garantia import clopper_pearson_sup
    prop.backtest = {"casos": len(casos), "residuo_antes": res_a, "residuo_depois": res_d,
                     "pares_automaticos_novos": novos_auto, "contradicoes": contr, "exemplos": exemplos[:5],
                     "alfa": alfa, "limite_superior_contradicao": round(clopper_pearson_sup(contr, novos_auto), 5)
                     if novos_auto else 1.0}
    return prop.backtest


def aplicar(regimento: dict, prop: Proposta, nova_versao: str) -> tuple[dict, str]:
    """REGIMENTO novo + hash a assinar. Recusa proposta não aprovável (falha fechada)."""
    if not prop.aprovavel:
        raise PermissionError(f"proposta não aprovável: {prop.backtest}")
    r = copy.deepcopy(regimento)
    r["versao"] = nova_versao
    r.setdefault("parametros_oficio", {}).setdefault(prop.oficio, {})[prop.parametro] = prop.proposto
    r.setdefault("aprendizado", []).append({"parametro": f"{prop.oficio}.{prop.parametro}", "de": prop.atual,
                                            "para": prop.proposto, "evidencia": prop.evidencia,
                                            "backtest": {k: v for k, v in prop.backtest.items() if k != "exemplos"}})
    return r, _h(r)
