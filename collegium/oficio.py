"""Kit de ofício + suíte de conformidade (T049) — o que torna o COLLEGIUM agnóstico de fato.

Um OFÍCIO é tudo o que um nicho precisa fornecer para rodar sob o mesmo núcleo, sem mudá-lo:
  classe, oráculo puro, falhas críticas, operário determinístico de referência, pilha do humano
  (resíduo) e um gerador sintético com gabarito para testes.

A suíte de conformidade cobra de QUALQUER ofício:
  C1 pureza: o oráculo dá o mesmo veredito duas vezes e não altera entrada nem entrega;
  C2 referência: o operário de referência é aceito em todas as sementes;
  C3 falha fechada: entrega lixo nunca é aceita (exceção conta como recusa, como no LEX);
  C4 mutação: estragos plantados numa entrega correta são recusados (escore de mutação);
  C5 classificação: inventar referência e omitir item caem em FALHA CRÍTICA (o LEX trata como fraude);
  C6 determinismo do gerador; C7 resíduo sem item repetido.
Mutantes equivalentes (estragos que não mudam o significado) existem; por isso o escore é medido,
não presumido, e os sobreviventes são listados para um humano olhar.
"""
from __future__ import annotations

import copy
import json
import random
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Oficio:
    nome: str
    versao: str
    classe: str
    oraculo: Callable[[dict, Any], tuple[bool, list[str]]]
    falhas_criticas: list[str]
    gerar: Callable[[int], dict]                      # -> {"entrada": ..., "gabarito": ...}
    operario: Callable[[dict], Any] | None = None
    residuo: Callable[[dict, Any], list[dict]] | None = None
    mutantes_extra: list[Callable] = field(default_factory=list)
    # forma canônica da entrega (padrão: listas viram conjuntos ordenados). Mutante com a mesma forma
    # canônica é EQUIVALENTE (não muda o significado) e não entra no escore.
    normalizar: Callable[[Any], Any] | None = None

    def classe_regimento(self, orcamento_passos: int = 12) -> dict:
        return {self.classe: {"orcamento_passos": orcamento_passos, "verificador": "oraculo",
                              "falhas_criticas": list(self.falhas_criticas)}}


def _seguro(of: Oficio, entrada, entrega) -> tuple[bool, list[str]]:
    try:
        ok, f = of.oraculo(entrada, entrega)
        return bool(ok), list(f)
    except Exception as e:  # mesma regra do LEX (Art. 11): exceção é recusa
        return False, [f"ENTREGA_MALFORMADA:{type(e).__name__}"]


def _ids(obj) -> set[str]:
    out = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "id" and isinstance(v, str):
                out.add(v)
            out |= _ids(v)
    elif isinstance(obj, list):
        for v in obj:
            out |= _ids(v)
    return out


def _listas(obj, caminho=()):
    """Todas as listas não vazias dentro da entrega, com o caminho até elas."""
    if isinstance(obj, list):
        if obj:
            yield caminho, obj
        for i, v in enumerate(obj):
            yield from _listas(v, caminho + (i,))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _listas(v, caminho + (k,))


def _folhas_id(obj, ids, caminho=()):
    if isinstance(obj, str) and obj in ids:
        yield caminho
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _folhas_id(v, ids, caminho + (i,))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _folhas_id(v, ids, caminho + (k,))


def _pegar(obj, caminho):
    for c in caminho:
        obj = obj[c]
    return obj


def _por(obj, caminho, valor):
    alvo = _pegar(obj, caminho[:-1])
    alvo[caminho[-1]] = valor


def mutantes_genericos(entrada: dict, entrega: Any, rnd: random.Random) -> list[tuple[str, Any]]:
    """(tipo, entrega_mutada). 'omitir' e 'inventar' DEVEM cair em falha crítica (C5)."""
    out = []
    listas = [(c, lst) for c, lst in _listas(entrega) if c and isinstance(c[-1], str)]  # listas de 1º nível útil
    if listas:
        c, lst = rnd.choice(listas)
        m = copy.deepcopy(entrega)
        del _pegar(m, c)[rnd.randrange(len(lst))]
        out.append(("omitir", m))
        m = copy.deepcopy(entrega)
        alvo = _pegar(m, c)
        alvo.append(copy.deepcopy(alvo[rnd.randrange(len(alvo))]))
        out.append(("duplicar", m))
    ids = _ids(entrada)
    folhas = list(_folhas_id(entrega, ids))
    if folhas:
        c = rnd.choice(folhas)
        m = copy.deepcopy(entrega)
        original = _pegar(m, c)
        novo = original[:1] + "9" * 7 + "X"
        while novo in ids:
            novo += "X"
        _por(m, c, novo)
        out.append(("inventar", m))
    # trocar: dois ids do MESMO tipo (mesmo prefixo) em posições diferentes — o erro sutil, não o grosseiro
    por_tipo: dict[str, list] = {}
    for c in folhas:
        por_tipo.setdefault(str(_pegar(entrega, c))[:1], []).append(c)
    candidatos = [v for v in por_tipo.values() if len(v) >= 2]
    if candidatos:
        a, b = rnd.sample(rnd.choice(candidatos), 2)
        m = copy.deepcopy(entrega)
        va, vb = _pegar(m, a), _pegar(m, b)
        if va != vb:
            _por(m, a, vb)
            _por(m, b, va)
            out.append(("trocar", m))
    return out


def _canonica(obj):
    if isinstance(obj, dict):
        return {k: _canonica(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return sorted((_canonica(v) for v in obj), key=lambda x: json.dumps(x, sort_keys=True, default=str))
    return obj


LIXO = [None, [], {}, "x", 0, {"x": 1}, [[None]], {"pares": 5}]


def conformidade(of: Oficio, sementes=range(1, 21)) -> dict:
    rel = {"oficio": f"{of.nome}@{of.versao}", "classe": of.classe, "falhas": [], "mutacao": {},
           "sobreviventes": []}
    mortos: dict = {}
    aplicados = {}
    for s in sementes:
        caso = of.gerar(s)
        caso2 = of.gerar(s)
        if json.dumps(caso, sort_keys=True, default=str) != json.dumps(caso2, sort_keys=True, default=str):
            rel["falhas"].append(f"C6:gerador_nao_deterministico:{s}")
        entrada = caso["entrada"]
        if of.operario is None:
            continue
        entrega = of.operario(copy.deepcopy(entrada))
        e0, d0 = copy.deepcopy(entrada), copy.deepcopy(entrega)
        r1, r2 = _seguro(of, entrada, entrega), _seguro(of, entrada, entrega)
        if r1 != r2:
            rel["falhas"].append(f"C1:veredito_instavel:{s}")
        if entrada != e0 or entrega != d0:
            rel["falhas"].append(f"C1:oraculo_alterou_dados:{s}")
        if not r1[0]:
            rel["falhas"].append(f"C2:referencia_recusada:{s}:{r1[1][:3]}")
            continue
        for lixo in LIXO:
            if _seguro(of, entrada, copy.deepcopy(lixo))[0]:
                rel["falhas"].append(f"C3:lixo_aceito:{s}:{lixo!r}")
        if of.residuo is not None:
            pac = of.residuo(entrada, entrega)
            ids_pac = [x.get("id") for x in pac]
            if len(ids_pac) != len(set(ids_pac)):
                rel["falhas"].append(f"C7:residuo_repetido:{s}")
        rnd = random.Random(s)
        muts = mutantes_genericos(entrada, entrega, rnd) + [m for g in of.mutantes_extra
                                                            for m in g(entrada, entrega, rnd)]
        norm = of.normalizar or _canonica
        base = norm(entrega)
        for tipo, m in muts:
            if norm(m) == base:
                rel.setdefault("equivalentes", 0)
                rel["equivalentes"] += 1
                continue
            aplicados[tipo] = aplicados.get(tipo, 0) + 1
            ok, falhas = _seguro(of, entrada, m)
            if ok:
                rel["sobreviventes"].append({"semente": s, "tipo": tipo})
                continue
            mortos[tipo] = mortos.get(tipo, 0) + 1
            if tipo in ("omitir", "inventar"):
                cods = {f.split(":")[0] for f in falhas}
                if not cods & set(of.falhas_criticas):
                    rel["falhas"].append(f"C5:{tipo}_nao_e_critico:{s}:{sorted(cods)}")
    for tipo, n in sorted(aplicados.items()):
        rel["mutacao"][tipo] = {"aplicados": n, "mortos": mortos.get(tipo, 0)}
    tot = sum(aplicados.values())
    rel["escore_mutacao"] = round(sum(mortos.values()) / tot, 4) if tot else None
    rel["conforme"] = not rel["falhas"] and (rel["escore_mutacao"] or 0) >= 0.9
    return rel
