"""Ed25519 (RFC 8032) só com a biblioteca padrão — T042.

Por que existe: com HMAC, o núcleo conhecia a chave do humano e podia forjar uma aprovação.
Com Ed25519, o núcleo guarda só a chave PÚBLICA; quem assina é o humano, fora do sistema.

Verificação estrita (escolhas declaradas):
  - codificação de ponto não canônica (y >= p, ou x = 0 com bit de sinal) é recusada;
  - S >= L é recusado (maleabilidade);
  - A ou R de ordem pequena é recusado;
  - equação sem cofator: [S]B == R + [k]A (a RFC 8032, §5.1.7, admite as duas formas).
Limite declarado: Python puro NÃO é tempo constante. Serve para assinar atos humanos em
máquina do próprio humano (baixo volume); não serve para assinar em servidor exposto a
medição de tempo. Velocidade: alguns milissegundos por operação.
"""
from __future__ import annotations

import hashlib
import secrets

p = 2 ** 255 - 19
L = 2 ** 252 + 27742317777372353535851937790883648493
_d = -121665 * pow(121666, p - 2, p) % p
_I = pow(2, (p - 1) // 4, p)  # raiz quadrada de -1 mod p


def _inv(x: int) -> int:
    return pow(x, p - 2, p)


def _recuperar_x(y: int, sinal: int) -> int | None:
    if y >= p:
        return None
    x2 = (y * y - 1) * _inv(_d * y * y + 1) % p
    if x2 == 0:
        return None if sinal else 0
    x = pow(x2, (p + 3) // 8, p)
    if (x * x - x2) % p:
        x = x * _I % p
    if (x * x - x2) % p:
        return None
    if (x & 1) != sinal:
        x = p - x
    return x


_Gy = 4 * _inv(5) % p
_Gx = _recuperar_x(_Gy, 0)
_G = (_Gx, _Gy, 1, _Gx * _Gy % p)
_ZERO = (0, 1, 1, 0)


def _somar(P, Q):
    A = (P[1] - P[0]) * (Q[1] - Q[0]) % p
    B = (P[1] + P[0]) * (Q[1] + Q[0]) % p
    C = 2 * P[3] * Q[3] * _d % p
    D = 2 * P[2] * Q[2] % p
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F % p, G * H % p, F * G % p, E * H % p)


def _mult(s: int, P):
    Q = _ZERO
    while s > 0:
        if s & 1:
            Q = _somar(Q, P)
        P = _somar(P, P)
        s >>= 1
    return Q


def _igual(P, Q) -> bool:
    return (P[0] * Q[2] - Q[0] * P[2]) % p == 0 and (P[1] * Q[2] - Q[1] * P[2]) % p == 0


def _comprimir(P) -> bytes:
    zi = _inv(P[2])
    x, y = P[0] * zi % p, P[1] * zi % p
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _descomprimir(s: bytes):
    if len(s) != 32:
        return None
    y = int.from_bytes(s, "little")
    sinal, y = y >> 255, y & ((1 << 255) - 1)
    x = _recuperar_x(y, sinal)
    return None if x is None else (x, y, 1, x * y % p)


def _h512(*partes: bytes) -> int:
    return int.from_bytes(hashlib.sha512(b"".join(partes)).digest(), "little")


def _expandir(privada: bytes) -> tuple[int, bytes]:
    if not isinstance(privada, (bytes, bytearray)) or len(privada) != 32:
        raise ValueError("chave privada Ed25519 tem 32 bytes")
    h = hashlib.sha512(bytes(privada)).digest()
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def gerar_privada() -> bytes:
    return secrets.token_bytes(32)


def publica(privada: bytes) -> bytes:
    a, _ = _expandir(privada)
    return _comprimir(_mult(a, _G))


def assinar(privada: bytes, msg: bytes) -> bytes:
    a, prefixo = _expandir(privada)
    A = _comprimir(_mult(a, _G))
    r = _h512(prefixo, msg) % L
    R = _comprimir(_mult(r, _G))
    k = _h512(R, A, msg) % L
    return R + int.to_bytes((r + k * a) % L, 32, "little")


def _ordem_pequena(P) -> bool:
    return _igual(_mult(8, P), _ZERO)


def verificar(publica_: bytes, msg: bytes, assinatura: bytes) -> bool:
    try:
        if len(publica_) != 32 or len(assinatura) != 64:
            return False
        A, R = _descomprimir(bytes(publica_)), _descomprimir(bytes(assinatura[:32]))
        if A is None or R is None or _ordem_pequena(A) or _ordem_pequena(R):
            return False
        S = int.from_bytes(assinatura[32:], "little")
        if S >= L:
            return False
        k = _h512(bytes(assinatura[:32]), bytes(publica_), msg) % L
        return _igual(_mult(S, _G), _somar(R, _mult(k, A)))
    except (TypeError, ValueError):
        return False
