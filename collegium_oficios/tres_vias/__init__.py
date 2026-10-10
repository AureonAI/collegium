"""Conferência de TRÊS VIAS (pedido de compra × recebimento × nota fiscal) — 2º ofício (T049).

Prova de agnosticismo: roda sob o MESMO núcleo (LEX, ANAIS, recibo, portão) sem mudar uma linha dele.
Tarefa: para cada nota fiscal de fornecedor, APROVAR o pagamento ou RETER com o motivo verdadeiro.
Lei de conservação: (1) toda nota aparece exatamente uma vez; (2) por pedido e item, a quantidade
aprovada para pagamento nunca passa da quantidade RECEBIDA (não se paga o que não chegou).
Ordem canônica (achado do teste de mutação, T049): as notas são julgadas da mais antiga (menor id)
para a mais nova, cada uma contra o que foi aprovado ANTES dela; nota idêntica a uma já aprovada
é DUPLICIDADE. Assim a resposta correta é única e "pagar a 2ª via e reter a 1ª" é recusado.
"""
from __future__ import annotations

import random
from collections import Counter

from collegium.oficio import Oficio

MOTIVOS = ("PEDIDO_INEXISTENTE", "DUPLICIDADE", "FORNECEDOR_DIVERGENTE", "TOTAL_NAO_FECHA", "ITEM_FORA_DO_PEDIDO",
           "PRECO_ACIMA", "QUANTIDADE_NAO_RECEBIDA")
CRITICAS = ["REFERENCIA_INEXISTENTE", "CONSERVACAO"]


# ----------------------------------------------------------------- regras (usadas pelo oráculo e pelo operário)
def _indices(e: dict):
    pcs = {p["id"]: p for p in e["pedidos"]}
    recebido: Counter = Counter()
    for r in e["recebimentos"]:
        for it in r["itens"]:
            recebido[(r["pedido"], it["sku"])] += int(it["qtd"])
    return pcs, recebido


def assinatura(nf: dict) -> str:
    itens = sorted((str(i["sku"]), int(i["qtd"]), int(i["preco"])) for i in nf["itens"])
    return repr((nf.get("fornecedor"), nf.get("pedido"), itens, int(nf["total"])))


def motivos(nf: dict, pcs: dict, recebido: Counter, consumo: Counter, pagas: set | None = None,
            tolerancia: float = 0.0) -> list[str]:
    """Todos os motivos pelos quais esta nota NÃO pode ser paga agora (dado o que já foi aprovado)."""
    pc = pcs.get(nf.get("pedido"))
    if pc is None:
        return ["PEDIDO_INEXISTENTE"]
    out = []
    if pagas is not None and assinatura(nf) in pagas:
        out.append("DUPLICIDADE")
    if nf.get("fornecedor") != pc["fornecedor"]:
        out.append("FORNECEDOR_DIVERGENTE")
    if sum(int(i["qtd"]) * int(i["preco"]) for i in nf["itens"]) != int(nf["total"]):
        out.append("TOTAL_NAO_FECHA")
    precos = {i["sku"]: int(i["preco"]) for i in pc["itens"]}
    for it in nf["itens"]:
        if it["sku"] not in precos:
            out.append("ITEM_FORA_DO_PEDIDO")
            continue
        if int(it["preco"]) > precos[it["sku"]] * (1 + tolerancia):
            out.append("PRECO_ACIMA")
        if consumo[(pc["id"], it["sku"])] + int(it["qtd"]) > recebido[(pc["id"], it["sku"])]:
            out.append("QUANTIDADE_NAO_RECEBIDA")
    return sorted(set(out), key=MOTIVOS.index)


def _consumir(nf: dict, consumo: Counter) -> None:
    for it in nf["itens"]:
        consumo[(nf["pedido"], it["sku"])] += int(it["qtd"])


# ----------------------------------------------------------------- oráculo (puro)
def verificar(entrada: dict, entrega) -> tuple[bool, list[str]]:
    if not isinstance(entrega, dict) or not isinstance(entrega.get("aprovadas"), list) \
            or not isinstance(entrega.get("retidas"), list):
        return False, ["FORMATO_INVALIDO"]
    if not all(isinstance(x, str) for x in entrega["aprovadas"]) or \
            not all(isinstance(x, dict) and isinstance(x.get("id"), str) for x in entrega["retidas"]):
        return False, ["FORMATO_INVALIDO:itens"]
    nfs = {n["id"]: n for n in entrada["notas"]}
    pcs, recebido = _indices(entrada)
    falhas = []
    vistos = Counter(entrega["aprovadas"]) + Counter(x["id"] for x in entrega["retidas"])
    for i in vistos:
        if i not in nfs:
            falhas.append(f"REFERENCIA_INEXISTENTE:{i}")
    for i in nfs:
        if vistos[i] == 0:
            falhas.append(f"CONSERVACAO:nota_omitida:{i}")
        elif vistos[i] > 1:
            falhas.append(f"CONSERVACAO:nota_repetida:{i}")
    aprov = set(entrega["aprovadas"])
    retidas = {r["id"]: r for r in entrega["retidas"]}
    consumo: Counter = Counter()
    pagas: set = set()
    for i in sorted(nfs):  # ordem canônica: mais antiga primeiro, contra o que foi aprovado ANTES
        m = motivos(nfs[i], pcs, recebido, consumo, pagas)
        if i in aprov:
            if m:
                falhas.extend(f"{x}:{i}" for x in m)
            else:
                _consumir(nfs[i], consumo)
                pagas.add(assinatura(nfs[i]))
        if i in retidas:
            r = retidas[i]
            if r.get("motivo") not in MOTIVOS:
                falhas.append(f"MOTIVO_INVALIDO:{i}")
            elif not m:
                falhas.append(f"RETENCAO_INDEVIDA:{i}")   # dava para pagar: reter sem motivo atrasa o fornecedor
            elif r["motivo"] not in m:
                falhas.append(f"MOTIVO_FALSO:{i}:{r['motivo']}")
    return (not falhas), falhas


# ----------------------------------------------------------------- operário determinístico de referência
def operario(entrada: dict) -> dict:
    pcs, recebido = _indices(entrada)
    consumo: Counter = Counter()
    pagas: set = set()
    aprovadas, retidas = [], []
    for nf in sorted(entrada["notas"], key=lambda n: n["id"]):
        m = motivos(nf, pcs, recebido, consumo, pagas)
        if m:
            retidas.append({"id": nf["id"], "motivo": m[0]})
        else:
            aprovadas.append(nf["id"])
            _consumir(nf, consumo)
            pagas.add(assinatura(nf))
    return {"aprovadas": aprovadas, "retidas": retidas}


def residuo(entrada: dict, entrega: dict) -> list[dict]:
    """Pilha do humano: cada nota retida com o motivo e a evidência (pedido e recebido)."""
    nfs = {n["id"]: n for n in entrada["notas"]}
    pcs, recebido = _indices(entrada)
    out = []
    for r in entrega.get("retidas", []):
        nf = nfs.get(r["id"])
        if nf is None:
            continue
        pc = pcs.get(nf.get("pedido"))
        out.append({"id": r["id"], "motivo": r["motivo"], "pedido": nf.get("pedido"),
                    "fornecedor_nota": nf.get("fornecedor"), "fornecedor_pedido": pc and pc["fornecedor"],
                    "recebido": {it["sku"]: recebido[(nf.get("pedido"), it["sku"])] for it in nf["itens"]}})
    return out


# ----------------------------------------------------------------- gerador sintético com gabarito por construção
def gerar(seed: int, n_pedidos: int = 8) -> dict:
    rnd = random.Random(seed)
    forn = [f"F{i:02d}" for i in range(1, 6)]
    pedidos, recebimentos, notas, anomalia = [], [], [], {}
    k = 0

    def nova_nf(pc, itens, tipo=None):
        nonlocal k
        k += 1
        nid = f"NF{seed:03d}{k:03d}"
        nf = {"id": nid, "fornecedor": pc["fornecedor"], "pedido": pc["id"], "itens": itens,
              "total": sum(i["qtd"] * i["preco"] for i in itens)}
        if tipo == "PRECO_ACIMA":
            nf["itens"][0]["preco"] = int(nf["itens"][0]["preco"] * 1.1) + 1
            nf["total"] = sum(i["qtd"] * i["preco"] for i in nf["itens"])
        elif tipo == "FORNECEDOR_DIVERGENTE":
            nf["fornecedor"] = rnd.choice([f for f in forn if f != pc["fornecedor"]])
        elif tipo == "TOTAL_NAO_FECHA":
            nf["total"] += rnd.randint(1, 999)
        elif tipo == "PEDIDO_INEXISTENTE":
            nf["pedido"] = "PC9999"
        elif tipo == "QUANTIDADE_NAO_RECEBIDA":
            nf["itens"][0]["qtd"] += rnd.randint(1, 5)
            nf["total"] = sum(i["qtd"] * i["preco"] for i in nf["itens"])
        notas.append(nf)
        anomalia[nid] = tipo
        return nf

    for p in range(1, n_pedidos + 1):
        pc = {"id": f"PC{seed:03d}{p:02d}", "fornecedor": rnd.choice(forn),
              "itens": [{"sku": f"SKU{rnd.randint(100, 999)}", "qtd": rnd.randint(2, 40),
                         "preco": rnd.randint(100, 50_000)} for _ in range(rnd.randint(1, 3))]}
        skus = {}
        for it in pc["itens"]:  # sku repetido no mesmo pedido vira um só item
            skus.setdefault(it["sku"], it)
        pc["itens"] = list(skus.values())
        pedidos.append(pc)
        parcial = rnd.random() < 0.3
        rec = [{"sku": i["sku"], "qtd": (i["qtd"] // 2 if parcial and i["qtd"] > 1 else i["qtd"])} for i in pc["itens"]]
        recebimentos.append({"id": f"RC{seed:03d}{p:02d}", "pedido": pc["id"], "itens": rec})
        faturar = [{"sku": r["sku"], "qtd": r["qtd"], "preco": next(i["preco"] for i in pc["itens"]
                                                                      if i["sku"] == r["sku"])} for r in rec]
        tipo = rnd.choices([None, "PRECO_ACIMA", "FORNECEDOR_DIVERGENTE", "TOTAL_NAO_FECHA",
                            "PEDIDO_INEXISTENTE", "QUANTIDADE_NAO_RECEBIDA"],
                           [0.6, 0.1, 0.07, 0.07, 0.06, 0.1])[0]
        nova_nf(pc, [dict(x) for x in faturar], tipo)
        if tipo is None and rnd.random() < 0.15:  # cobrança em DUPLICIDADE do mesmo recebimento
            nova_nf(pc, [dict(x) for x in faturar], "DUPLICIDADE")
    rnd.shuffle(notas)
    return {"entrada": {"pedidos": pedidos, "recebimentos": recebimentos, "notas": notas},
            "gabarito": {"anomalia": anomalia}}


OFICIO = Oficio(nome="tres_vias", versao="0.1.1", classe="tres_vias", oraculo=verificar,
                falhas_criticas=CRITICAS, gerar=gerar, operario=operario, residuo=residuo)
