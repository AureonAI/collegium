"""ANAIS em SQLite (T058): mesma cadeia, mesmo selo e a MESMA linha byte a byte do JSONL — portanto a
mesma raiz Merkle e os mesmos recibos. Biblioteca padrão (sqlite3). Um arquivo por ENTE, com chave
própria por ente. Vários escritores: transação BEGIN IMMEDIATE (o SQLite serializa).
"""
from __future__ import annotations

import hmac
import json
import os
import re
import sqlite3
import time
from typing import Any, Iterator

from .ledger import GENESE, _selo


class LedgerSQLite:
    def __init__(self, caminho: str, chave: bytes | None = None, relogio=time.time):
        self.caminho, self.chave, self.relogio = caminho, chave, relogio
        self._db = sqlite3.connect(caminho, isolation_level=None, timeout=30)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("CREATE TABLE IF NOT EXISTS anais (i INTEGER PRIMARY KEY, linha TEXT NOT NULL)")
        ok, ruim = self.verificar()
        if not ok:
            raise ValueError(f"ANAIS corrompido no registro {ruim}; recuso-me a continuar escrevendo")

    def _ultimo(self) -> tuple[str, int]:
        row = self._db.execute("SELECT linha FROM anais ORDER BY i DESC LIMIT 1").fetchone()
        if row is None:
            return GENESE, 0
        reg = json.loads(row[0])
        if not hmac.compare_digest(reg["selo"], _selo(reg["prev"], reg["corpo"], self.chave)):
            raise ValueError("último registro do ANAIS com selo inválido; recuso-me a continuar")
        return reg["selo"], reg["i"] + 1

    def anexar(self, tipo: str, dados: dict) -> dict:
        corpo = {"tipo": tipo, "t": round(self.relogio(), 6), "dados": dados}
        self._db.execute("BEGIN IMMEDIATE")
        try:
            prev, n = self._ultimo()
            reg = {"i": n, "prev": prev, "selo": _selo(prev, corpo, self.chave), "corpo": corpo}
            self._db.execute("INSERT INTO anais (i, linha) VALUES (?, ?)",
                             (n, json.dumps(reg, ensure_ascii=False, sort_keys=True)))
            self._db.execute("COMMIT")
        except BaseException:
            self._db.execute("ROLLBACK")
            raise
        return reg

    def linhas(self) -> list[str]:
        return [r[0] for r in self._db.execute("SELECT linha FROM anais ORDER BY i")]

    def registros(self) -> Iterator[dict]:
        for ln in self.linhas():
            yield json.loads(ln)

    def verificar(self, ancora: tuple[int, str] | None = None) -> tuple[bool, int | None]:
        prev, esperado, selos = GENESE, 0, {}
        try:
            for i, ln in self._db.execute("SELECT i, linha FROM anais ORDER BY i"):
                reg = json.loads(ln)
                if i != esperado or reg.get("i") != esperado or reg.get("prev") != prev:
                    return False, esperado
                if not hmac.compare_digest(reg.get("selo", ""), _selo(prev, reg["corpo"], self.chave)):
                    return False, esperado
                selos[esperado] = reg["selo"]
                prev, esperado = reg["selo"], esperado + 1
        except (json.JSONDecodeError, KeyError, TypeError):
            return False, esperado
        if ancora:
            n, selo = ancora
            if esperado < n or not hmac.compare_digest(selos.get(n - 1, ""), selo):
                return False, min(esperado, n - 1)
        return True, None

    def ancora(self) -> tuple[int, str]:
        prev, n = self._ultimo()
        return n, prev

    @property
    def cabeca(self) -> str:
        return self._ultimo()[0]

    def __len__(self) -> int:
        return self._ultimo()[1]

    def fechar(self) -> None:
        self._db.close()


def abrir_ente(pasta: str, ente: str, chave: bytes | None) -> LedgerSQLite:
    """Um ANAIS por ente (multi-ente sem misturar dados); a chave vem do orquestrador, uma por ente."""
    import unicodedata
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", ente) if not unicodedata.combining(c))
    slug = re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-") or "ente"
    os.makedirs(pasta, exist_ok=True)
    return LedgerSQLite(os.path.join(pasta, f"{slug}.anais.db"), chave)


def backup_verificado(origem: Any, destino_sqlite: str) -> dict:
    """Copia o ANAIS (JSONL ou SQLite) para um SQLite novo e só aceita se a cópia reproduzir a MESMA raiz
    Merkle e a mesma cabeça. Backup que não confere é apagado (falha fechada)."""
    from .recibo import arvore
    a0, linhas = arvore(origem)
    if os.path.exists(destino_sqlite):
        raise FileExistsError(destino_sqlite)
    db = sqlite3.connect(destino_sqlite, isolation_level=None)
    db.execute("CREATE TABLE anais (i INTEGER PRIMARY KEY, linha TEXT NOT NULL)")
    db.execute("BEGIN")
    db.executemany("INSERT INTO anais (i, linha) VALUES (?, ?)", [(json.loads(ln)["i"], ln) for ln in linhas])
    db.execute("COMMIT")
    db.close()
    copia = LedgerSQLite(destino_sqlite, getattr(origem, "chave", None))
    a1, _ = arvore(copia)
    ok = a0.raiz() == a1.raiz() and len(a0) == len(a1) and copia.verificar()[0]
    copia.fechar()
    if not ok:
        os.remove(destino_sqlite)
        raise ValueError("backup não reproduz a raiz Merkle: descartado")
    return {"registros": len(a1), "raiz": a1.raiz().hex()}
