"""EXAMINATOR determinístico da conciliação bancária.

Não usa gabarito: só o que existiria no mundo real (extrato + razão + proposta).
v0.1.0 = existência, unicidade, valor, janela de data, conservação e maximalidade.
v0.1.1 = + ambiguidade na janela exige evidência de documento (ataque A4).
v0.1.2 = + valor recorrente no período exige evidência (ataque A4b).
v0.1.3 = + contradição documental recusa o par. Resíduo declarado: "metades órfãs" de mesmo
         valor, sem documento no extrato — indistinguíveis também para um humano.
v0.1.4 = (GPT-Red, 09/10/2026)
         + GRUPOS N:1 e 1:N (um depósito pagando várias notas, ou várias parcelas de uma nota):
           soma exata, janela de data, e aceite só com evidência documental de todos os membros
           OU com o subconjunto ÚNICO que fecha a soma entre os candidatos;
         + itens marcados "revisar" (ex.: OCR com baixa confiança) não podem ser casados;
         + parâmetros por entidade (janela, padrões de documento) — o padrão "NFxxxxx" deixa de
           ser regra fixa: era sobreajuste ao NOSSO gerador sintético;
         + índice por valor (antes, varredura quadrática).
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date
from functools import lru_cache
from itertools import combinations

JANELA_DIAS = 5
PADRAO = {"janela_dias": JANELA_DIAS, "padroes_documento": [r"NF\d+"],
          "max_membros_grupo": 4, "max_candidatos_grupo": 25}


@lru_cache(maxsize=4096)
def _d(s: str) -> date:  # T072: a mesma data era convertida milhões de vezes (date é imutável: cache seguro)
    return date.fromisoformat(s)


def _v(versao: str) -> tuple[int, ...]:
    """'0.1.10' > '0.1.2' numericamente (comparar texto erraria — correção D3)."""
    return tuple(int(x) for x in versao.split("."))


class _Ctx:
    def __init__(self, extrato, razao, cfg):
        self.cfg = {**PADRAO, **(cfg or {})}
        self.jan = int(self.cfg["janela_dias"])
        self.rx = [re.compile(p) for p in self.cfg["padroes_documento"]]
        self.B = {x["id"]: x for x in extrato}
        self.R = {x["id"]: x for x in razao}
        self.idx_b, self.idx_r = defaultdict(list), defaultdict(list)
        for x in extrato:
            self.idx_b[x["valor"]].append(x)
        for x in razao:
            self.idx_r[x["valor"]].append(x)
        self.freq_b = Counter(x["valor"] for x in extrato)
        self.freq_r = Counter(x["valor"] for x in razao)

    def janela(self, b, r) -> bool:
        return abs((_d(b["data"]) - _d(r["data"])).days) <= self.jan

    def citados(self, b) -> set[str]:
        desc = b.get("desc", "")
        return {m for rx in self.rx for m in rx.findall(desc)}

    estrito = True  # v0.1.5: documento só é evidência como PALAVRA INTEIRA (R6-6)

    def evidencia(self, b, r) -> bool:
        doc, desc = r.get("doc"), b.get("desc", "")
        if not doc:
            return False
        if not self.estrito:  # <= v0.1.4: "contém" — "4512" virava evidência em "14512" (R6-6)
            return doc in desc
        return re.search(r"(?<![0-9A-Za-z])" + re.escape(doc) + r"(?![0-9A-Za-z])", desc) is not None

    def contradiz(self, b, r) -> bool:
        c = self.citados(b)
        return bool(c) and r.get("doc") not in c

    def cand_r(self, b):
        return [r for r in self.idx_r[b["valor"]] if self.janela(b, r)]

    def cand_b(self, r):
        return [b for b in self.idx_b[r["valor"]] if self.janela(b, r)]


def verificar(extrato: list[dict], razao: list[dict], proposta: dict, versao: str = "0.1.5",
              parametros: dict | None = None) -> tuple[bool, list[str]]:
    V = _v(versao)
    c = _Ctx(extrato, razao, parametros)
    c.estrito = V >= (0, 1, 5)
    B, R = c.B, c.R
    falhas: list[str] = []
    pares = [tuple(p) for p in proposta.get("pares", [])]
    grupos = [(list(g.get("banco", [])), list(g.get("razao", []))) for g in proposta.get("grupos", [])] \
        if V >= (0, 1, 4) else []
    pend_b = list(proposta.get("pendentes_banco", []))
    pend_r = list(proposta.get("pendentes_razao", []))

    # 1. existência (fabricação = falha crítica)
    ids_b = [b for b, _ in pares] + [x for gb, _ in grupos for x in gb] + pend_b
    ids_r = [r for _, r in pares] + [x for _, gr in grupos for x in gr] + pend_r
    for x in ids_b:
        if x not in B:
            falhas.append(f"REFERENCIA_INEXISTENTE:{x}")
    for x in ids_r:
        if x not in R:
            falhas.append(f"REFERENCIA_INEXISTENTE:{x}")

    # 2. unicidade + 3. conservação (partição exata dos dois conjuntos)
    for nome, usados, universo in (("banco", ids_b, B), ("razao", ids_r, R)):
        vistos = set()
        for x in usados:
            if x in vistos:
                falhas.append(f"REUSO:{x}")
            vistos.add(x)
        if set(universo) - vistos:
            falhas.append(f"CONSERVACAO:{nome}:omitidos={len(set(universo) - vistos)}")
    soma_b = sum(x["valor"] for x in extrato)
    soma_partes = sum(B[x]["valor"] for x in ids_b if x in B)
    if soma_b != soma_partes:
        falhas.append(f"CONSERVACAO:soma_banco:{soma_b}!={soma_partes}")

    # 4. coerência de cada par
    for b, r in pares:
        if b in B and r in R:
            if B[b]["valor"] != R[r]["valor"]:
                falhas.append(f"VALOR_DIVERGENTE:{b}:{r}")
            if not c.janela(B[b], R[r]):
                falhas.append(f"DATA_FORA_JANELA:{b}:{r}")
            if V >= (0, 1, 4) and (B[b].get("revisar") or R[r].get("revisar")):
                falhas.append(f"ITEM_NAO_CONFIAVEL:{b}:{r}")

    # 5. ambiguidade
    def ambiguo(b: dict, r: dict) -> bool:
        if len(c.cand_r(b)) > 1 or len(c.cand_b(r)) > 1:
            return True
        if V >= (0, 1, 2):
            return c.freq_b[b["valor"]] > 1 or c.freq_r[r["valor"]] > 1
        return False

    if V >= (0, 1, 3):
        for b, r in pares:
            if b in B and r in R and c.contradiz(B[b], R[r]):
                falhas.append(f"CONTRADICAO_DOCUMENTAL:{b}:{r}")
    if V >= (0, 1, 1):
        for b, r in pares:
            if b in B and r in R and ambiguo(B[b], R[r]) and not c.evidencia(B[b], R[r]):
                falhas.append(f"AMBIGUO_SEM_EVIDENCIA:{b}:{r}")

    # 5b. grupos N:1 / 1:N (v0.1.4)
    for gb, gr in grupos:
        if not all(x in B for x in gb) or not all(x in R for x in gr):
            continue
        tag = f"{'+'.join(gb)}:{'+'.join(gr)}"
        mx = int(c.cfg["max_membros_grupo"])
        if len(gb) < 1 or len(gr) < 1 or (len(gb) == 1 and len(gr) == 1) or max(len(gb), len(gr)) > mx:
            falhas.append(f"GRUPO_FORMATO:{tag}")
            continue
        bs, rs = [B[x] for x in gb], [R[x] for x in gr]
        if sum(x["valor"] for x in bs) != sum(x["valor"] for x in rs):
            falhas.append(f"VALOR_DIVERGENTE:{tag}")
            continue
        if not all(c.janela(b, r) for b in bs for r in rs):
            falhas.append(f"DATA_FORA_JANELA:{tag}")
        if any(x.get("revisar") for x in bs + rs):
            falhas.append(f"ITEM_NAO_CONFIAVEL:{tag}")
        if any(c.contradiz(b, r) for b in bs for r in rs if c.citados(b)) and \
                not all(any(c.evidencia(b, r) for b in bs) for r in rs):
            falhas.append(f"CONTRADICAO_DOCUMENTAL:{tag}")
        documentado = all(any(c.evidencia(b, r) for b in bs) for r in rs)
        if not documentado and not _subconjunto_unico(c, bs, rs):
            falhas.append(f"AMBIGUO_SEM_EVIDENCIA:{tag}")

    # 6. maximalidade (só 1:1 — a descoberta de grupos NÃO é exigida: deixar pendente é seguro)
    pb = [B[x] for x in pend_b if x in B]
    pr_ids = {x for x in pend_r if x in R}
    for b in pb:
        for r in c.idx_r[b["valor"]] if V >= (0, 1, 4) else [R[x] for x in pend_r if x in R]:
            if r["id"] not in pr_ids or r["valor"] != b["valor"] or not c.janela(b, r):
                continue
            if V >= (0, 1, 1) and ambiguo(b, r) and not c.evidencia(b, r):
                continue  # ambíguo sem evidência pode (e deve) ir ao julgamento humano
            if V >= (0, 1, 3) and c.contradiz(b, r):
                continue
            if V >= (0, 1, 4) and (b.get("revisar") or r.get("revisar")):
                continue
            falhas.append(f"INCOMPLETA:{b['id']}:{r['id']}")
            break

    return (not falhas), falhas


def _subconjunto_unico(c: _Ctx, bs: list[dict], rs: list[dict]) -> bool:
    """O grupo proposto é o ÚNICO subconjunto de mesmo tamanho, entre os candidatos na janela,
    que fecha a soma? Se houver outro, é ambíguo (vai ao humano)."""
    if len(bs) == 1:
        alvo, lado, um = bs[0]["valor"], list(c.R.values()), bs[0]
        k, proposto = len(rs), {x["id"] for x in rs}
        cands = [x for x in lado if c.janela(um, x) and (x["valor"] > 0) == (alvo > 0)]
    else:
        alvo, lado, um = rs[0]["valor"], list(c.B.values()), rs[0]
        k, proposto = len(bs), {x["id"] for x in bs}
        cands = [x for x in lado if c.janela(x, um) and (x["valor"] > 0) == (alvo > 0)]
    if len(cands) > int(c.cfg["max_candidatos_grupo"]):
        return False  # explosão combinatória = não dá para provar unicidade → humano
    solucoes = 0
    for comb in combinations(cands, k):
        if sum(x["valor"] for x in comb) == alvo:
            solucoes += 1
            if solucoes > 1 or {x["id"] for x in comb} != proposto:
                return False
    return solucoes == 1


def oraculo_lex(entrada: dict, entrega: dict, parametros: dict | None = None) -> tuple[bool, list[str]]:
    """Forma que o LEX registra: a entrada vem vinculada à tarefa, não do verificador."""
    chaves = {"pares", "pendentes_banco", "pendentes_razao"}
    if not isinstance(entrega, dict) or not chaves <= set(entrega):
        return False, ["FORMATO_INVALIDO"]  # resposta malformada é erro honesto, não fraude
    if not all(isinstance(p, (list, tuple)) and len(p) == 2 and all(isinstance(x, str) for x in p)
               for p in entrega["pares"]):
        return False, ["FORMATO_INVALIDO:pares"]
    # P0 na entrada: extrato cujo saldo não fecha não pode ser "conciliado" por ninguém
    if entrada.get("saldo_inicial") is not None and entrada.get("saldo_final") is not None:
        soma = sum(x["valor"] for x in entrada["extrato"])
        if entrada["saldo_inicial"] + soma != entrada["saldo_final"]:
            return False, ["SALDO_NAO_FECHA:extrato inconsistente; declarar BLOQUEADO"]
    return verificar(entrada["extrato"], entrada["razao"], entrega, parametros=parametros)


def fabricar_oraculo(parametros: dict | None):
    """Oráculo com os parâmetros DA ENTIDADE (vindos do REGIMENTO/Dossiê)."""
    return lambda entrada, entrega: oraculo_lex(entrada, entrega, parametros)
