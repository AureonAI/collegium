"""Executor de ofício (T066): roda UM trabalho real de QUALQUER ofício sob o LEX, de ponta a ponta.

É a peça que faltava entre o núcleo e o produto: até a v0.2.0 havia 30 comandos de governança
e nenhum que fizesse o trabalho que se vende. O executor é agnóstico: recebe um `Oficio`
(collegium.oficio) e uma entrada já importada; quem lê arquivo e escreve relatório é o ofício.

Fluxo (todas as decisões ficam seladas no ANAIS):
  1. abre a tarefa com a ENTRADA vinculada (hash), produtor = operário determinístico "op-det";
  2. o operário produz a entrega; o LEX roda o ORÁCULO do ofício (o veredito não vem do operário);
  3. aceita -> calcula a pilha do humano (resíduo) e pede liberação: em L0 vai ao humano;
  4. se a entrada não serve (saldo que não fecha, conta trocada...), o ofício chama `bloquear`
     e a tarefa é DECLARADA BLOQUEADA com evidência (Art. 3): nada é entregue como se estivesse ok.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from typing import Any, Callable

from .ledger import Ledger, canonico
from .lex import Lex, RegimentoInvalido, assinar_humano_ed25519

REGIMENTO_BASE = {
    "versao": "execucao-0.2.1",
    "ente": "definido pelo chamador",
    "papeis": {
        "operarius": {"capacidades": ["entrada.ler", "entrega.propor"], "canais": [], "rede": []},
        "examinator": {"capacidades": ["entrada.ler", "verificar"], "canais": [], "rede": []},
        "patronus": {"capacidades": ["aprovar"], "canais": [], "rede": []},
    },
    "agentes": {
        "op-det": {"papel": "operarius", "familia_modelo": "deterministico"},
        "ex-det": {"papel": "examinator", "familia_modelo": "deterministico"},
    },
    "classes_tarefa": {},
    "autonomia": {"confianca_z": 2.326, "niveis": [{"nivel": 1, "n_min": 30, "lb_min": 0.9},
                                                    {"nivel": 2, "n_min": 100, "lb_min": 0.97},
                                                    {"nivel": 3, "n_min": 300, "lb_min": 0.99}],
                  "janela_incidente": 200, "amostragem_l1": 5, "alcada_valor_l3": 0,
                  "estabilidade": 50, "janela_recente": 100, "exigir_assinatura_humana": True},
}


def regimento_para(oficio, ente: str, humanos: dict[str, str] | None = None) -> dict:
    """humanos = {nome: chave pública Ed25519 em hex}. Sem humano registrado, nada pode ser LIBERADO."""
    reg = copy.deepcopy(REGIMENTO_BASE)
    reg["ente"] = ente
    reg["classes_tarefa"].update(oficio.classe_regimento())
    for nome, pub in (humanos or {}).items():
        reg["agentes"][nome] = {"papel": "patronus", "familia_modelo": "humano", "chave_publica": pub}
    if humanos:
        reg["patronus"] = {"chaves": dict(humanos), "quorum": 1}
    return reg


def _caminho_regimento(anais: Ledger) -> str:
    return anais.caminho + ".regimento.json"


def regimento_do_anais(oficio, anais: Ledger, ente: str, humanos: dict[str, str] | None = None) -> dict:
    """T071: o REGIMENTO fica GUARDADO junto do ANAIS. Na 1ª execução é criado; nas seguintes é
    relido, e pedir regras diferentes (outro humano, outro ente) é recusado: mudar regras exige o
    procedimento assinado (G4), não um parâmetro de linha de comando."""
    cam = _caminho_regimento(anais)
    if os.path.exists(cam):
        with open(cam, encoding="utf-8") as f:
            reg = json.load(f)
        if humanos and any(reg["agentes"].get(n, {}).get("chave_publica") != k for n, k in humanos.items()):
            raise RegimentoInvalido("este ANAIS já tem humanos registrados diferentes; mudar regras exige "
                                    "mudança de REGIMENTO assinada (hash-regimento + assinar-ed)")
        if reg.get("ente") != ente:
            raise RegimentoInvalido(f"este ANAIS pertence ao ente {reg.get('ente')!r}, não a {ente!r}")
        return reg
    reg = regimento_para(oficio, ente, humanos)
    if len(anais):  # ANAIS já usado SEM regimento guardado: não invento as regras do passado
        raise RegimentoInvalido("ANAIS existente sem o arquivo de REGIMENTO ao lado; restaure-o")
    fd = os.open(cam, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=1, sort_keys=True)
    return reg


def id_tarefa(oficio, entrada: Any) -> str:
    """Mesmo arquivo -> mesma tarefa: conciliar duas vezes a mesma entrada no mesmo ANAIS é recusado."""
    return f"{oficio.classe.upper()[:4]}-{hashlib.sha256(canonico(entrada)).hexdigest()[:12]}"


class JaExecutada(KeyError):
    pass


def abrir(oficio, anais: Ledger, entrada: Any, ente: str,
          humanos: dict[str, str] | None = None) -> tuple[Lex, str]:
    lex = Lex(regimento_do_anais(oficio, anais, ente, humanos), anais, {oficio.classe: oficio.oraculo})
    tid = id_tarefa(oficio, entrada)
    if tid in lex.tarefas:
        raise JaExecutada(f"esta entrada já foi processada neste ANAIS (tarefa {tid}); use outro ANAIS ou outro período")
    lex.abrir_tarefa(tid, oficio.classe, "op-det", entrada=entrada)
    return lex, tid


def bloquear(oficio, anais: Ledger, entrada: Any, ente: str, evidencia: str,
             humanos: dict[str, str] | None = None) -> dict:
    lex, tid = abrir(oficio, anais, entrada, ente, humanos)
    d = lex.mandato("op-det").declarar(tid, "BLOQUEADO", evidencia)
    return {"tarefa": tid, "estado": "BLOQUEADO", "evidencia": evidencia, "declaracao": d.codigo,
            "anais_integro": anais.verificar()[0]}


def executar(oficio, anais: Ledger, entrada: Any, ente: str,
             operario: Callable[[Any], Any] | None = None, humanos: dict[str, str] | None = None) -> dict:
    lex, tid = abrir(oficio, anais, entrada, ente, humanos)
    op = operario or oficio.operario
    if op is None:
        raise ValueError(f"o ofício {oficio.nome} não tem operário de referência")
    entrega = op(entrada)
    sub = lex.submeter(tid, "op-det", entrega)
    if not sub.permitido:
        return {"tarefa": tid, "estado": "REJEITADA", "falhas": [sub.codigo], "entrega": entrega}
    ver = lex.verificar(tid, "ex-det", entrega)
    aceito = ver.codigo == "ACEITA"
    try:
        _, falhas = oficio.oraculo(entrada, entrega)  # puro: só para o relatório; o veredito é o do LEX
    except Exception as e:  # noqa: BLE001 — mesma regra do LEX (falha fechada)
        falhas = [f"ENTREGA_MALFORMADA:{type(e).__name__}"]
    out = {"tarefa": tid, "estado": "ACEITA" if aceito else "REJEITADA", "falhas": list(falhas),
           "entrega": entrega, "incidente": "op-det" in lex.quarentena,
           "entrada_sha256": hashlib.sha256(canonico(entrada)).hexdigest(),
           "entrega_sha256": hashlib.sha256(canonico(entrega)).hexdigest()}
    if aceito:
        out["residuo"] = oficio.residuo(entrada, entrega) if oficio.residuo else []
        out["liberacao"] = lex.liberar(tid).codigo  # em L0: AGUARDA_HUMANO (o humano aprova pelo relatório)
    out["anais_integro"] = anais.verificar()[0]
    return out


def aprovar(oficio, anais: Ledger, tarefa: str, humano: str, privada: bytes, aprovado: bool = True) -> dict:
    """T071: o humano aprova (ou rejeita) a entrega. A assinatura Ed25519 é feita com a chave privada
    DELE, sobre (tarefa, hash da entrega, decisão): o núcleo não consegue forjá-la."""
    cam = _caminho_regimento(anais)
    if not os.path.exists(cam):
        raise RegimentoInvalido("ANAIS sem REGIMENTO guardado: não há humano registrado para aprovar")
    with open(cam, encoding="utf-8") as f:
        reg = json.load(f)
    lex = Lex(reg, anais, {oficio.classe: oficio.oraculo})
    if tarefa not in lex.tarefas:
        raise KeyError(f"tarefa {tarefa} não existe neste ANAIS")
    t = lex.tarefas[tarefa]
    sig = assinar_humano_ed25519(privada, "aprovar", tarefa, t.entrega_hash, bool(aprovado), humano)
    d = lex.aprovar_humano(tarefa, humano, bool(aprovado), sig)
    return {"tarefa": tarefa, "codigo": d.codigo, "permitido": d.permitido, "motivo": d.motivo,
            "estado": lex.tarefas[tarefa].estado, "anais_integro": anais.verificar()[0]}
