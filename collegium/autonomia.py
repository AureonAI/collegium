"""Autonomia conquistada: o nível de um agente numa classe de tarefa é FUNÇÃO do histórico
medido no ANAIS, nunca de configuração ou de autodeclaração.

L0 = toda entrega exige aprovação humana
L1 = humano aprova por amostragem (sorteio imprevisível); irreversíveis sempre com humano
L2 = liberação automática de ações reversíveis
L3 = liberação automática inclusive irreversíveis, até a alçada de valor do REGIMENTO

Critério de um nível (pré-registrado no REGIMENTO):
  (1) limite inferior de Wilson da taxa de aceite >= lb_min, com n >= n_min;
  (2) ESTABILIDADE (v0.1.3): o critério (1) vale em CADA um dos últimos `estabilidade`
      pontos do histórico — sequência de sorte não promove (ataque A7);
  (3) JANELA RECENTE (v0.1.3): a taxa bruta das últimas `janela_recente` tarefas >= lb_min
      — reputação antiga não protege agente que piorou (ataque R4);
  (4) zero incidentes críticos na janela de incidente.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


def wilson_inferior(aceitos: int, total: int, z: float = 1.96) -> float:
    if total <= 0:
        return 0.0
    p = aceitos / total
    den = 1 + z * z / total
    centro = p + z * z / (2 * total)
    margem = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    return max(0.0, (centro - margem) / den)


@dataclass
class Historico:
    resultados: list[int] = field(default_factory=list)   # 1 = aceito, 0 = rejeitado
    acumulado: list[int] = field(default_factory=lambda: [0])  # soma prefixada (O(1) por ponto)
    tarefas_desde_incidente: int = 10**9

    @property
    def total(self) -> int:
        return len(self.resultados)

    @property
    def aceitos(self) -> int:
        return self.acumulado[-1]

    def registrar(self, aceito: bool) -> None:
        self.resultados.append(int(aceito))
        self.acumulado.append(self.acumulado[-1] + int(aceito))
        self.tarefas_desde_incidente += 1

    def incidente(self) -> None:
        """Incidente crítico: zera o histórico inteiro (rebaixamento duro)."""
        self.resultados.clear()
        self.acumulado[:] = [0]
        self.tarefas_desde_incidente = 0


def _criterio(h: Historico, n: int, regra: dict, z: float) -> bool:
    return n >= regra["n_min"] and wilson_inferior(h.acumulado[n], n, z) >= regra["lb_min"]


def nivel(h: Historico, cfg: dict) -> int:
    if h.tarefas_desde_incidente < cfg.get("janela_incidente", 200):
        return 0
    z = cfg.get("confianca_z", 1.96)
    estab = int(cfg.get("estabilidade", 1))
    janela = int(cfg.get("janela_recente", 0))
    n = h.total
    alcancado = 0
    for regra in sorted(cfg["niveis"], key=lambda r: r["nivel"]):
        pontos = range(max(1, n - estab + 1), n + 1)
        ok = n >= regra["n_min"] + estab - 1 and all(_criterio(h, k, regra, z) for k in pontos)
        if ok and janela and n >= janela:
            ok = (h.acumulado[n] - h.acumulado[n - janela]) / janela >= regra["lb_min"]
        if not ok:
            break  # níveis cumulativos: não se pula degrau
        alcancado = regra["nivel"]
    return alcancado
