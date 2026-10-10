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

    @property
    def familia(self) -> str:
        """Família = prefixo do nome (qwen2.5-coder:1.5b -> qwen). Usada pela lei L3."""
        return re.split(r"[0-9.:\-]", self.modelo, maxsplit=1)[0].lower() or self.modelo

    def conversar(self, sistema: str, usuario: str, temperatura: float = 0.0, semente: int = 0) -> str:
        corpo = json.dumps({
            "model": self.modelo, "stream": False, "format": "json",
            "options": {"temperature": temperatura, "seed": semente},
            "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
        }).encode("utf-8")
        req = urllib.request.Request(self.base + "/api/chat", data=corpo,
                                     headers={"Content-Type": "application/json"})
        local = any(h in self.base for h in ("localhost", "127.0.0.1", "[::1]"))
        abrir = urllib.request.build_opener(urllib.request.ProxyHandler({})).open if local else urllib.request.urlopen
        with abrir(req, timeout=self.timeout) as r:
            return json.loads(r.read().decode("utf-8"))["message"]["content"]


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
