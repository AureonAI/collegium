"""Árvore de Merkle do ANAIS no padrão RFC 9162 (Certificate Transparency v2) — T043.

Por que: a cadeia linear exige o livro inteiro E a chave HMAC para conferir um registro.
A árvore permite provar UM registro com ~log2(n) hashes (prova de inclusão) e provar que o
livro de hoje ESTENDE o de ontem sem reescrevê-lo (prova de consistência). Biblioteca padrão.

Hash de folha = SHA-256(0x00 || dado); de nó = SHA-256(0x01 || esquerda || direita).
Algoritmos de geração e verificação seguem as seções 2.1.1, 2.1.3 e 2.1.4 da RFC 9162.
"""
from __future__ import annotations

import hashlib


def _h(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def folha(dado: bytes) -> bytes:
    return _h(b"\x00" + dado)


def no(esq: bytes, dir_: bytes) -> bytes:
    return _h(b"\x01" + esq + dir_)


def _k(n: int) -> int:
    """Maior potência de 2 estritamente menor que n (n >= 2)."""
    k = 1
    while k << 1 < n:
        k <<= 1
    return k


class Arvore:
    """Árvore sobre uma lista de hashes de folha (já calculados)."""

    def __init__(self, folhas: list[bytes]):
        self.f = list(folhas)
        self._cache: dict[tuple[int, int], bytes] = {}

    def __len__(self) -> int:
        return len(self.f)

    def raiz(self, ini: int = 0, fim: int | None = None) -> bytes:
        fim = len(self.f) if fim is None else fim
        n = fim - ini
        if n == 0:
            return _h(b"")
        if n == 1:
            return self.f[ini]
        if (ini, fim) not in self._cache:
            k = _k(n)
            self._cache[(ini, fim)] = no(self.raiz(ini, ini + k), self.raiz(ini + k, fim))
        return self._cache[(ini, fim)]

    def prova_inclusao(self, m: int, n: int | None = None) -> list[bytes]:
        """PATH(m, D[0:n]) da RFC 9162 §2.1.3.1."""
        n = len(self.f) if n is None else n
        if not 0 <= m < n <= len(self.f):
            raise IndexError("índice fora da árvore")

        def path(m, ini, fim):
            if fim - ini == 1:
                return []
            k = _k(fim - ini)
            if m < k:
                return path(m, ini, ini + k) + [self.raiz(ini + k, fim)]
            return path(m - k, ini + k, fim) + [self.raiz(ini, ini + k)]
        return path(m, 0, n)

    def prova_consistencia(self, m: int, n: int | None = None) -> list[bytes]:
        """PROOF(m, D[0:n]) da RFC 9162 §2.1.4.1 (0 < m <= n)."""
        n = len(self.f) if n is None else n
        if not 0 < m <= n <= len(self.f):
            raise IndexError("tamanhos inválidos para prova de consistência")

        def sub(m, ini, fim, b):
            if m == fim - ini:
                return [] if b else [self.raiz(ini, fim)]
            k = _k(fim - ini)
            if m <= k:
                return sub(m, ini, ini + k, b) + [self.raiz(ini + k, fim)]
            return sub(m - k, ini + k, fim, False) + [self.raiz(ini, ini + k)]
        return sub(m, 0, n, True)


def verificar_inclusao(hash_folha: bytes, indice: int, tamanho: int, prova: list[bytes], raiz: bytes) -> bool:
    """RFC 9162 §2.1.3.2."""
    if not 0 <= indice < tamanho:
        return False
    fn, sn, r = indice, tamanho - 1, hash_folha
    for p in prova:
        if sn == 0:
            return False
        if fn & 1 or fn == sn:
            r = no(p, r)
            if not fn & 1:
                while not fn & 1 and fn != 0:
                    fn >>= 1
                    sn >>= 1
        else:
            r = no(r, p)
        fn >>= 1
        sn >>= 1
    return sn == 0 and r == raiz


def verificar_consistencia(m: int, raiz_m: bytes, n: int, raiz_n: bytes, prova: list[bytes]) -> bool:
    """RFC 9162 §2.1.4.2: a árvore de tamanho n ESTENDE a de tamanho m (nada reescrito)."""
    if not 0 < m <= n:
        return False
    if m == n:
        return not prova and raiz_m == raiz_n
    if m & (m - 1) == 0:  # m é potência exata de 2
        prova = [raiz_m] + list(prova)
    if not prova:
        return False
    fn, sn = m - 1, n - 1
    while fn & 1:
        fn >>= 1
        sn >>= 1
    fr = sr = prova[0]
    for c in prova[1:]:
        if sn == 0:
            return False
        if fn & 1 or fn == sn:
            fr, sr = no(c, fr), no(c, sr)
            if not fn & 1:
                while not fn & 1 and fn != 0:
                    fn >>= 1
                    sn >>= 1
        else:
            sr = no(sr, c)
        fn >>= 1
        sn >>= 1
    return sn == 0 and fr == raiz_m and sr == raiz_n
