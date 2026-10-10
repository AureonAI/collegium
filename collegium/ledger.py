"""ANAIS — livro-razão append-only encadeado por hash (opcionalmente autenticado por HMAC).

Invariante (P0 conservação de história): nenhum registro pode ser alterado, removido,
reordenado ou inserido sem que verificar() aponte o primeiro índice corrompido.
Somente biblioteca padrão: auditável e roda em Windows/Linux/macOS sem dependências.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from contextlib import contextmanager
from typing import Any, Iterator

if os.name == "nt":  # Windows
    import msvcrt

    @contextmanager
    def _trava(caminho: str):
        with open(caminho + ".lock", "a+b") as f:
            f.seek(0)
            while True:
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
                    break
                except OSError:
                    time.sleep(0.01)
            try:
                yield
            finally:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
else:  # Linux / macOS
    import fcntl

    @contextmanager
    def _trava(caminho: str):
        with open(caminho + ".lock", "a+b") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

GENESE = "0" * 64


def canonico(obj: Any) -> bytes:
    """Serialização determinística (mesma entrada -> mesmos bytes em qualquer SO)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _selo(prev: str, corpo: dict, chave: bytes | None) -> str:
    material = prev.encode("ascii") + canonico(corpo)
    if chave:
        return hmac.new(chave, material, hashlib.sha256).hexdigest()
    return hashlib.sha256(material).hexdigest()


class Ledger:
    """Livro-razão em JSON Lines. Cada linha: {"i", "prev", "selo", "corpo"}."""

    def __init__(self, caminho: str, chave: bytes | None = None, relogio=time.time, duravel: bool = True):
        self.caminho = caminho
        self.chave = chave
        self.relogio = relogio
        self.duravel = duravel  # False só em experimentos descartáveis (fsync no Windows é lento); produção: True
        self._ultimo = GENESE
        self._n = 0
        if os.path.exists(caminho):
            ok, ruim = self.verificar()
            if not ok:
                raise ValueError(f"ANAIS corrompido no registro {ruim}; recuso-me a continuar escrevendo")
            for reg in self.registros():
                self._ultimo, self._n = reg["selo"], reg["i"] + 1

    def _ressincronizar(self) -> None:
        """Lê só o ÚLTIMO registro do arquivo (outro escritor pode ter anexado) e confere o selo dele.
        Correção do GAP C1: dois escritores no mesmo ANAIS bifurcavam a cadeia."""
        if not os.path.exists(self.caminho) or os.path.getsize(self.caminho) == 0:
            self._ultimo, self._n = GENESE, 0
            return
        with open(self.caminho, "rb") as f:
            f.seek(0, os.SEEK_END)
            pos, bloco = f.tell(), b""
            while pos > 0 and bloco.count(b"\n") < 2:
                passo = min(4096, pos)
                pos -= passo
                f.seek(pos)
                bloco = f.read(passo) + bloco
        ultima = [x for x in bloco.split(b"\n") if x.strip()][-1]
        reg = json.loads(ultima.decode("utf-8"))
        if not hmac.compare_digest(reg["selo"], _selo(reg["prev"], reg["corpo"], self.chave)):
            raise ValueError("último registro do ANAIS com selo inválido; recuso-me a continuar")
        self._ultimo, self._n = reg["selo"], reg["i"] + 1

    def anexar(self, tipo: str, dados: dict) -> dict:
        corpo = {"tipo": tipo, "t": round(self.relogio(), 6), "dados": dados}
        with _trava(self.caminho):
            self._ressincronizar()
            reg = {"i": self._n, "prev": self._ultimo, "selo": _selo(self._ultimo, corpo, self.chave),
                   "corpo": corpo}
            with open(self.caminho, "a", encoding="utf-8") as f:
                f.write(json.dumps(reg, ensure_ascii=False, sort_keys=True) + "\n")
                f.flush()
                if self.duravel:
                    os.fsync(f.fileno())
            self._ultimo, self._n = reg["selo"], self._n + 1
        return reg

    def linhas(self) -> list[str]:
        """Linhas brutas (sem quebra), na ordem: o que a árvore de Merkle do recibo assina (T043/T058)."""
        if not os.path.exists(self.caminho):
            return []
        with open(self.caminho, encoding="utf-8") as f:
            return [ln.rstrip("\n") for ln in f if ln.strip()]

    def registros(self) -> Iterator[dict]:
        if not os.path.exists(self.caminho):
            return
        with open(self.caminho, encoding="utf-8") as f:
            for linha in f:
                if linha.strip():
                    yield json.loads(linha)

    def verificar(self, ancora: tuple[int, str] | None = None) -> tuple[bool, int | None]:
        """Retorna (True, None) se íntegro; senão (False, índice do primeiro registro inválido).

        ancora = (n, selo) publicado FORA do sistema (testemunha externa). Sem âncora, apagar
        os registros MAIS RECENTES é indetectável por qualquer cadeia de hash — ver
        ADVERSARIAL_LOG A2 (ataque que venceu o T2 v0.1.0)."""
        prev, esperado = GENESE, 0
        selos: dict[int, str] = {}
        try:
            for reg in self.registros():
                if reg.get("i") != esperado or reg.get("prev") != prev:
                    return False, esperado
                if not hmac.compare_digest(reg.get("selo", ""), _selo(prev, reg["corpo"], self.chave)):
                    return False, esperado
                if ancora and esperado == ancora[0] - 1:
                    selos[esperado] = reg["selo"]
                prev, esperado = reg["selo"], esperado + 1
        except (json.JSONDecodeError, KeyError, TypeError):
            return False, esperado
        if ancora:
            n, selo = ancora
            if esperado < n or not hmac.compare_digest(selos.get(n - 1, ""), selo):
                return False, min(esperado, n - 1)
        return True, None

    @staticmethod
    def chave_de_ambiente(variavel: str = "COLLEGIUM_CHAVE") -> bytes | None:
        """A chave HMAC vem do ambiente do ORQUESTRADOR, nunca do REGIMENTO nem do agente."""
        v = os.environ.get(variavel)
        return v.encode("utf-8") if v else None

    def ancora(self) -> tuple[int, str]:
        """(quantidade, selo da cabeça) — publique isto fora (e-mail, repositório público, cartório)."""
        return self._n, self._ultimo

    @property
    def cabeca(self) -> str:
        """Selo do último registro: âncora que pode ser publicada fora (testemunha externa)."""
        return self._ultimo

    def __len__(self) -> int:
        return self._n
