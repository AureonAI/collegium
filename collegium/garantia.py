"""Garantia estatística para classes SEM oráculo (T050). Só biblioteca padrão.

Problema: a maior parte do trabalho real não tem lei de conservação. Sem oráculo, "um júri de outra
família concordou" não diz QUANTO se pode confiar. Aqui a confiança vira número com garantia:

1. Calibração: um conjunto com veredito HUMANO conhecido (o gabarito fica fora do agente).
2. Learn-then-Test (Angelopoulos et al., 2021) em sequência fixa: as políticas de aceite automático
   são testadas da mais conservadora para a mais frouxa; cada uma só é liberada se o teste binomial
   rejeitar "erro entre os aceitos > α" com nível δ. Para na primeira que não passa.
   Garantia: com probabilidade >= 1-δ, a política escolhida erra no máximo α entre o que aceita.
   Pressuposto declarado: calibração e produção vêm da MESMA distribuição (trocas exigem recalibrar).
3. Vigia sequencial (SPRT de Wald) em produção: auditorias por amostragem; se o erro subir de p0 para
   p1, revoga a política (volta tudo para o humano).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


def _log_binom_pmf(k: int, n: int, p: float) -> float:
    if p <= 0.0:
        return 0.0 if k == 0 else -math.inf
    if p >= 1.0:
        return 0.0 if k == n else -math.inf
    return (math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
            + k * math.log(p) + (n - k) * math.log1p(-p))


def binom_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k), X ~ Bin(n, p), em espaço logarítmico (estável para n grande)."""
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    termos = [_log_binom_pmf(i, n, p) for i in range(k + 1)]
    m = max(termos)
    if m == -math.inf:
        return 0.0
    return min(1.0, math.exp(m) * sum(math.exp(t - m) for t in termos))


def p_valor_risco(erros: int, n: int, alfa: float) -> float:
    """H0: taxa de erro > alfa. p = P(Bin(n, alfa) <= erros). Pequeno => há evidência de erro <= alfa."""
    if n == 0:
        return 1.0
    return binom_cdf(erros, n, alfa)


def clopper_pearson_sup(k: int, n: int, confianca: float = 0.95) -> float:
    """Limite SUPERIOR exato (unilateral) da taxa, por bisseção sobre a CDF binomial."""
    if n == 0:
        return 1.0
    if k >= n:
        return 1.0
    a = 1 - confianca
    lo, hi = k / n, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if binom_cdf(k, n, mid) > a:
            lo = mid
        else:
            hi = mid
    return hi


def kappa_cohen(a: list[bool], b: list[bool]) -> float:
    """Concordância de um verificador com o gabarito humano, descontado o acaso."""
    n = len(a)
    if n == 0:
        return 0.0
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


@dataclass
class Calibracao:
    """votos[i] = lista de vereditos (True = aceitar) dos jurados; humano[i] = veredito do gabarito."""
    votos: list[list[bool]]
    humano: list[bool]

    def __post_init__(self):  # rodada 5: zip cortaria em silêncio e a garantia ficaria falsa
        if len(self.votos) != len(self.humano):
            raise ValueError(f"calibração com {len(self.votos)} votos e {len(self.humano)} vereditos humanos")
        if self.votos and len({len(v) for v in self.votos}) != 1:
            raise ValueError("todas as linhas de votos precisam ter o mesmo número de jurados")

    def risco(self, minimo_votos: int) -> tuple[int, int]:
        """(aceitos automaticamente, aceitos errados) para 'aceita se >= minimo_votos dizem sim'."""
        n = erros = 0
        for v, h in zip(self.votos, self.humano):
            if sum(v) >= minimo_votos:
                n += 1
                erros += not h
        return n, erros


@dataclass
class Escolha:
    minimo_votos: int | None          # None = nenhuma política liberada: tudo vai ao humano
    testes: list[dict] = field(default_factory=list)


def learn_then_test(cal: Calibracao, alfa: float, delta: float, n_min: int = 30) -> Escolha:
    jurados = len(cal.votos[0]) if cal.votos else 0
    escolha = Escolha(None)
    for m in range(jurados, 0, -1):  # sequência fixa: unanimidade primeiro, depois mais frouxas
        n, e = cal.risco(m)
        p = p_valor_risco(e, n, alfa) if n >= n_min else 1.0
        escolha.testes.append({"minimo_votos": m, "aceitos": n, "errados": e, "p_valor": round(p, 6),
                               "limite_superior_95": round(clopper_pearson_sup(e, n), 4) if n else None})
        if p <= delta:
            escolha.minimo_votos = m
        else:
            break
    return escolha


class Vigia:
    """SPRT de Wald sobre auditorias de itens aceitos automaticamente.
    H0: erro = p0 (aceitável); H1: erro = p1 (piorou). Erros do teste: falso alarme a, omissão b."""

    def __init__(self, p0: float, p1: float, a: float = 0.05, b: float = 0.02):  # b=0,02: ver T7 (G3)
        if not 0 < p0 < p1 < 1:
            raise ValueError("exige 0 < p0 < p1 < 1")
        self.l1, self.l0 = math.log(p1 / p0), math.log((1 - p1) / (1 - p0))
        self.sup, self.inf = math.log((1 - b) / a), math.log(b / (1 - a))
        self.llr, self.n, self.estado = 0.0, 0, "continuar"

    def registrar(self, errado: bool) -> str:
        if self.estado != "continuar":
            return self.estado
        self.n += 1
        self.llr += self.l1 if errado else self.l0
        if self.llr >= self.sup:
            self.estado = "revogar"           # o erro subiu: tudo volta ao humano
        elif self.llr <= self.inf:
            self.estado = "manter"            # evidência suficiente de que segue no nível aceitável
        return self.estado

    def reiniciar(self) -> None:
        self.llr, self.n, self.estado = 0.0, 0, "continuar"
