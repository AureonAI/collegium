"""Adaptadores de modelo (C3). Só biblioteca padrão. O LEX não sabe que eles existem:
o adaptador devolve texto, o operário converte em Acao/entrega, o LEX governa.

Ollama: https://github.com/ollama/ollama/blob/main/docs/api.md  (POST /api/chat, stream=false)
"""
from __future__ import annotations

import json
import re
import urllib.request


class Ollama:
    def __init__(self, modelo: str, base: str = "http://localhost:11434", timeout: float = 600):
        self.modelo, self.base, self.timeout = modelo, base.rstrip("/"), timeout
        self.ultimo_uso: dict = {}

    @property
    def familia(self) -> str:
        """Família = prefixo do nome (qwen2.5-coder:1.5b -> qwen). Usada pela lei L3."""
        return re.split(r"[0-9.:\-]", self.modelo, maxsplit=1)[0].lower() or self.modelo

    def digest(self) -> str:
        """T048: impressão digital dos pesos que o Ollama vai rodar (via /api/tags), como 'sha256:<hex>'.
        Quem chama é o ORQUESTRADOR, que então informa ao LEX (Lex.atestar_modelo)."""
        req = urllib.request.Request(self.base + "/api/tags")
        local = any(h in self.base for h in ("localhost", "127.0.0.1", "[::1]"))
        abrir = urllib.request.build_opener(urllib.request.ProxyHandler({})).open if local else urllib.request.urlopen
        with abrir(req, timeout=60) as r:
            modelos = json.loads(r.read().decode("utf-8")).get("models", [])
        for m in modelos:
            if self.modelo in (m.get("name"), m.get("model")):
                d = str(m.get("digest", ""))
                return d if d.startswith("sha256:") else "sha256:" + d
        raise LookupError(f"modelo {self.modelo} não está instalado no Ollama")

    def conversar(self, sistema: str, usuario: str, temperatura: float = 0.0, semente: int = 0,
                  max_tokens: int = 2048, esquema: dict | None = None) -> str:
        """esquema (T054): JSON Schema da resposta; o Ollama restringe a GERAÇÃO a ele (decodificação
        restrita). Elimina a classe de falha "resposta fora do formato" (ex.: o eco do llama3.2:1b)."""
        # M2 (10/10/2026): sem teto, modelo pequeno em modo JSON pode gerar sem parar até o timeout.
        corpo = json.dumps({
            "model": self.modelo, "stream": False, "format": esquema if esquema else "json",
            "options": {"temperature": temperatura, "seed": semente, "num_predict": max_tokens},
            "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
        }).encode("utf-8")
        req = urllib.request.Request(self.base + "/api/chat", data=corpo,
                                     headers={"Content-Type": "application/json"})
        local = any(h in self.base for h in ("localhost", "127.0.0.1", "[::1]"))
        abrir = urllib.request.build_opener(urllib.request.ProxyHandler({})).open if local else urllib.request.urlopen
        with abrir(req, timeout=self.timeout) as r:
            resp = json.loads(r.read().decode("utf-8"))
        # T056: consumo medido pelo próprio servidor, para o LEX cobrar orçamento real
        self.ultimo_uso = {"tokens_entrada": int(resp.get("prompt_eval_count") or 0),
                           "tokens_saida": int(resp.get("eval_count") or 0),
                           "segundos": round(float(resp.get("total_duration") or 0) / 1e9, 3)}
        return resp["message"]["content"]


def extrair_json(texto: str) -> dict | None:
    """Tolerante a lixo em volta; nunca 'conserta' conteúdo (isso seria fabricar)."""
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", texto, re.S)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
