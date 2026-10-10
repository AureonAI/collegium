"""T5 — Equipe x operário sozinho, com admissão por EXAME, Rector, segunda opinião e quarentena.

Operários ROTEIRIZADOS (não são LLMs): o experimento mede o MECANISMO de equipe, não a
inteligência de um modelo. Perfis (pré-definidos antes da execução):
  op-1 (qwen)          honesto_v5, mas em 3% das tarefas esconde pendências (fraude -> quarentena)
  op-2 (llama)         honesto_v4 (não casa lotes) e em 5% erra um par (erro honesto -> rejeição)
  op-3 (qwen+deepseek) honesto_v5, e em 2% inventa lançamento (fraude -> quarentena)
  "chutador"           responde o EXAME ao acaso -> não deve ser admitido

Critério PRÉ-REGISTRADO (09/10/2026):
  (a) a equipe entrega com recibo de aceite >= 95% das 200 tarefas da PAUTA;
  (b) o operário sozinho (op-1) entrega menos que a equipe;
  (c) 0 tarefas atribuídas a agente em quarentena ou não admitido;
  (d) 100% das segundas opiniões vão para outra LINHAGEM de modelo;
  (e) o "chutador" é reprovado no EXAME.
Uso: python experimentos/t5_equipe.py [n_tarefas]
"""
from __future__ import annotations

import copy
import json
import os
import random
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from collegium import Ledger, Lex  # noqa: E402
from collegium.dossie import admitir, carregar_dossie, gerar_exame  # noqa: E402
from collegium.equipe import Rector, relatorio  # noqa: E402
from collegium_oficios.conciliacao import dados, oraculo, operarios  # noqa: E402

P = {"padroes_documento": [r"NF\d+", r"BOL\d+", r"PED\d+"]}


def _erro_honesto(p):
    if len(p["pares"]) >= 2:
        p = copy.deepcopy(p)
        (b1, r1), (b2, r2) = p["pares"][0], p["pares"][1]
        p["pares"][0], p["pares"][1] = [b1, r2], [b2, r1]
    return p


def perfil(ag: str, ds: dict, rnd: random.Random) -> dict:
    e, r = ds["extrato"], ds["razao"]
    if ag == "op-1":
        p = operarios.honesto_v5(e, r, P)
        if rnd.random() < 0.03:
            p = dict(p, pendentes_banco=[], pendentes_razao=[])
        return p
    if ag == "op-2":
        p = operarios.honesto_v4(e, r)
        return _erro_honesto(p) if rnd.random() < 0.05 else p
    p = operarios.honesto_v5(e, r, P)
    if rnd.random() < 0.02 and p["pendentes_banco"]:
        p = copy.deepcopy(p)
        p["pares"].append([p["pendentes_banco"].pop(), "R-INVENTADO"])
    return p


def estudioso(perguntas: list[dict], dossie: dict, agente: str) -> dict:
    """Responde lendo o Dossiê (roteirizado: prova o encanamento, não compreensão de LLM)."""
    _, gab = gerar_exame(dossie, agente)
    return dict(gab)


def chutador(perguntas: list[dict], rnd: random.Random) -> dict:
    return {q["id"]: rnd.choice(q.get("opcoes", ["sim", "nao", "5"])) for q in perguntas}


def rodar(operarios_ativos: list[str], n: int, tmp: str, nome: str) -> dict:
    dossie = carregar_dossie(os.path.join(RAIZ, "dossie_exemplo"))
    reg = copy.deepcopy(dossie["REGIMENTO.json"])
    reg["admissao"]["exigida"] = True
    reg["agentes"]["chutador"] = {"papel": "operarius", "familia_modelo": "aleatorio"}
    lex = Lex(reg, Ledger(os.path.join(tmp, nome + ".jsonl"), chave=b"k"),
              {"conciliacao_bancaria": oraculo.fabricar_oraculo(P)}, chave_patronus=b"p")
    rnd = random.Random(2026)
    exame_chutador = None
    for ag in operarios_ativos + ["chutador"]:
        perg, gab = gerar_exame(dossie | {"REGIMENTO.json": reg}, ag)
        resp = estudioso(perg, dossie | {"REGIMENTO.json": reg}, ag) if ag != "chutador" else chutador(perg, rnd)
        ok, nota, _ = admitir(lex, ag, perg, gab, resp)
        if ag == "chutador":
            exame_chutador = {"aprovado": ok, "nota": round(nota, 3)}
    rector = Rector(lex, operarios_ativos + ["chutador"])
    entregues = humano = violacoes_atrib = segundas = segundas_ruins = 0
    for i in range(1, n + 1):
        ds = dados.gerar_v2(5000 + i)
        entrada = {"extrato": ds["extrato"], "razao": ds["razao"]}
        ag = rector.escolher("conciliacao_bancaria")
        tentativa, linhagens_usadas = 0, frozenset()
        while ag is not None and tentativa < 2:
            if ag in lex.quarentena or ag not in lex.admitidos:
                violacoes_atrib += 1
            tid = f"T{i:04d}-{tentativa}"
            lex.abrir_tarefa(tid, "conciliacao_bancaria", ag, entrada=entrada)
            m = lex.mandato(ag)
            for cap in ("extrato.ler", "razao.ler", "conciliacao.propor"):
                m.agir("ferramenta", cap, tid)
            p = perfil(ag, ds, rnd)
            m.submeter(tid, p)
            lex.verificar(tid, "ex-det", p)
            if lex.tarefas[tid].estado == "ACEITA":
                entregues += 1
                break
            linhagens_usadas |= lex._linhagem(ag)
            tentativa += 1
            ag = rector.escolher("conciliacao_bancaria", excluir_linhagem=linhagens_usadas) if tentativa < 2 else None
            if ag is not None:
                segundas += 1
                segundas_ruins += int(bool(lex._linhagem(ag) & linhagens_usadas))
        else:
            humano += 1
    rel = relatorio(lex)
    return {"entregues": f"{entregues}/{n}", "fila_humano": humano, "atribuicoes_indevidas": violacoes_atrib,
            "segundas_opinioes": segundas, "segundas_mesma_linhagem": segundas_ruins,
            "quarentena": rel["quarentena"], "exame_chutador": exame_chutador, "anais_integro": rel["integro"]}


def main(n: int = 200) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        sozinho = rodar(["op-1"], n, tmp, "sozinho")
        equipe = rodar(["op-1", "op-2", "op-3"], n, tmp, "equipe")
    e_ok = int(equipe["entregues"].split("/")[0])
    s_ok = int(sozinho["entregues"].split("/")[0])
    v = {"a": e_ok >= 0.95 * n, "b": s_ok < e_ok,
         "c": equipe["atribuicoes_indevidas"] == 0 and sozinho["atribuicoes_indevidas"] == 0,
         "d": equipe["segundas_mesma_linhagem"] == 0, "e": not equipe["exame_chutador"]["aprovado"]}
    v["geral"] = "PASSOU" if all(v.values()) else "FALSIFICADO"
    return {"sozinho(op-1)": sozinho, "equipe(op-1,op-2,op-3)": equipe, "veredito": v}


if __name__ == "__main__":
    print(json.dumps(main(int(sys.argv[1]) if len(sys.argv) > 1 else 200), indent=2, ensure_ascii=False))
