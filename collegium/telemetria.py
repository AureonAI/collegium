"""Telemetria (T058) no formato de span do OpenTelemetry, com as convenções GenAI.
ATENÇÃO: em 2026 as convenções GenAI do OpenTelemetry ainda estão em DESENVOLVIMENTO (não estáveis);
`gen_ai.provider.name` substituiu `gen_ai.system` na v1.37. Os nomes podem mudar: estão isolados aqui.
Sem dependência: grava JSON por linha, que um coletor OpenTelemetry (receptor filelog) lê.
Nunca grava conteúdo de prompt/resposta (só contagens e códigos) — minimização de dados (LGPD art. 6º, III).
"""
from __future__ import annotations

import json
import os
import secrets
import threading
import time

PREFIXO = "io.github.aureonai."


def _span(nome: str, atributos: dict, inicio_ns: int, fim_ns: int, traco: str | None = None) -> dict:
    return {"name": nome, "kind": "CLIENT", "trace_id": traco or secrets.token_hex(16),
            "span_id": secrets.token_hex(8), "start_time_unix_nano": int(inicio_ns),
            "end_time_unix_nano": int(fim_ns), "attributes": {k: v for k, v in atributos.items() if v is not None}}


def chamada_modelo(provedor: str, modelo: str, uso: dict, agente: str, tarefa: str,
                   inicio_ns: int, fim_ns: int, erro: str | None = None) -> dict:
    return _span(f"chat {modelo}", {
        "gen_ai.operation.name": "chat", "gen_ai.provider.name": provedor, "gen_ai.request.model": modelo,
        "gen_ai.usage.input_tokens": uso.get("tokens_entrada"), "gen_ai.usage.output_tokens": uso.get("tokens_saida"),
        "gen_ai.agent.name": agente, PREFIXO + "tarefa": tarefa, "error.type": erro}, inicio_ns, fim_ns)


def chamada_ferramenta(ferramenta: str, agente: str, tarefa: str, decisao: str, permitido: bool,
                       inicio_ns: int, fim_ns: int) -> dict:
    return _span(f"execute_tool {ferramenta}", {
        "gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": ferramenta, "gen_ai.agent.name": agente,
        PREFIXO + "tarefa": tarefa, PREFIXO + "decisao": decisao, PREFIXO + "permitido": permitido,
        "error.type": None if permitido else decisao}, inicio_ns, fim_ns)


class Exportador:
    """Grava spans em JSON por linha. Thread-safe. Desligado = None no portão."""

    def __init__(self, caminho: str):
        self.caminho, self._trava = caminho, threading.Lock()

    def __call__(self, span: dict) -> None:
        linha = json.dumps(span, ensure_ascii=False, sort_keys=True)
        with self._trava, open(self.caminho, "a", encoding="utf-8") as f:
            f.write(linha + "\n")


def agora_ns() -> int:
    return time.time_ns()


def ler(caminho: str) -> list[dict]:
    if not os.path.exists(caminho):
        return []
    with open(caminho, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]
