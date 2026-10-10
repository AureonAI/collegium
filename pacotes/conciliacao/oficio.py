"""Conciliação bancária como OFÍCIO (T049): só embrulha o que já existe, sem mudar comportamento."""
from __future__ import annotations

from collegium.oficio import Oficio

from . import dados, operarios, oraculo, residuo

PARAM = {"padroes_documento": [r"NF\d+", r"BOL\d+", r"PED\d+"]}


def _gerar(seed: int) -> dict:
    ds = dados.gerar_v2(seed, n=40)
    return {"entrada": {"extrato": ds["extrato"], "razao": ds["razao"]}, "gabarito": ds["gabarito"]}


OFICIO = Oficio(
    nome="conciliacao_bancaria", versao="0.1.4", classe="conciliacao_bancaria",
    oraculo=oraculo.fabricar_oraculo(PARAM),
    falhas_criticas=["REFERENCIA_INEXISTENTE", "CONSERVACAO"],
    gerar=_gerar,
    operario=lambda e: operarios.honesto_v5(e["extrato"], e["razao"], PARAM),
    residuo=lambda e, p: residuo.pacote_humano(e["extrato"], e["razao"], p, PARAM),
)
