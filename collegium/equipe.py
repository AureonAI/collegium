"""EQUIPE: Rector (distribui) + Actuarius (registra para humanos).

Rector é CÓDIGO determinístico, não um "CEO-agente": no Project Vend o CEO-agente agregou pouco
e compartilhava os pontos cegos do subordinado. Ele só roteia, nunca aprova nem verifica.
Política (pré-registrada):
  1. elegíveis = admitidos (se exigido) e fora de quarentena;
  2. escolhe o de MAIOR nível de autonomia na classe; empate -> menos tarefas atribuídas;
  3. tarefa REJEITADA (erro honesto) ou DECLARADA impossível ganha UMA segunda opinião de um
     elegível de OUTRA linhagem de modelo; se não houver, vai ao humano;
  4. sem elegível -> fila do humano (nunca força um agente em quarentena).

Actuarius lê o ANAIS e escreve a MEMÓRIA legível (Markdown) e o PAINEL (HTML estático),
com os tokens do docs/4_DESIGN.md. Não escreve no ANAIS: só lê.
"""
from __future__ import annotations

import html
from collections import Counter, defaultdict

from .lex import Lex


class Rector:
    def __init__(self, lex: Lex, operarios: list[str]):
        self.lex, self.operarios = lex, list(operarios)
        self.carga: Counter = Counter()

    def elegiveis(self, classe: str, excluir_linhagem: frozenset = frozenset()) -> list[str]:
        exige = self.lex.r.get("admissao", {}).get("exigida")
        out = [o for o in self.operarios
               if o not in self.lex.quarentena and (not exige or o in self.lex.admitidos)
               and not (self.lex._linhagem(o) & excluir_linhagem)]
        return sorted(out, key=lambda o: (-self.lex.nivel_autonomia(o, classe), self.carga[o], o))

    def escolher(self, classe: str, excluir_linhagem: frozenset = frozenset()) -> str | None:
        e = self.elegiveis(classe, excluir_linhagem)
        if not e:
            return None
        self.carga[e[0]] += 1
        return e[0]


def relatorio(lex: Lex) -> dict:
    regs = list(lex.anais.registros())
    tipos = Counter(r["corpo"]["tipo"] for r in regs)
    recibos = [r["corpo"]["dados"] for r in regs if r["corpo"]["tipo"] == "recibo"]
    incid = [r["corpo"]["dados"] for r in regs if r["corpo"]["tipo"] == "incidente"]
    por_agente = defaultdict(lambda: [0, 0])
    for d in recibos:
        por_agente[d["produtor"]][0] += int(d["aceito"])
        por_agente[d["produtor"]][1] += 1
    fila = sorted(t.id for t in lex.tarefas.values() if t.estado == "AGUARDA_HUMANO")
    declaradas = sorted(t.id for t in lex.tarefas.values() if t.estado == "DECLARADA")
    matriz = {ag: {cl: lex.nivel_autonomia(ag, cl) for cl in lex.r["classes_tarefa"]}
              for ag, d in lex.r["agentes"].items() if lex._linhagem(ag) != {"humano"}}
    n, selo = lex.anais.ancora()
    exige = lex.r.get("admissao", {}).get("exigida")
    ativos = [a for a, d in lex.r["agentes"].items() if lex.r["papeis"][d["papel"]].get("capacidades")
              and "conciliacao.propor" in lex.r["papeis"][d["papel"]]["capacidades"]
              and a not in lex.quarentena and (not exige or a in lex.admitidos)]
    minimo = int(lex.r.get("equipe", {}).get("minimo_operarios", 2))
    alerta = (f"EQUIPE ABAIXO DO MÍNIMO: {len(ativos)} operário(s) ativo(s) < {minimo}; "
              f"revise as quarentenas") if len(ativos) < minimo else None
    return {"alerta_equipe": alerta, "operarios_ativos": ativos,"registros": len(regs), "tipos": dict(tipos), "recibos": len(recibos),
            "aceitos": sum(int(d["aceito"]) for d in recibos), "incidentes": incid,
            "por_agente": {k: {"aceitos": v[0], "total": v[1]} for k, v in sorted(por_agente.items())},
            "fila_humano": fila, "declaradas": declaradas, "matriz_autonomia": matriz,
            "quarentena": sorted(lex.quarentena), "ancora": {"n": n, "selo": selo},
            "integro": lex.anais.verificar()[0]}


def memoria_md(rel: dict) -> str:
    l = ["# MEMÓRIA gerada pelo Actuarius (lida do ANAIS; não editar à mão)", "",
         f"- ANAIS íntegro: **{'sim' if rel['integro'] else 'NÃO'}** · registros: {rel['registros']}",
         f"- Âncora para publicar fora: `{rel['ancora']['n']}:{rel['ancora']['selo']}`",
         f"- Recibos: {rel['recibos']} (aceitos {rel['aceitos']})",
         f"- Fila do humano: {', '.join(rel['fila_humano']) or 'vazia'}",
         f"- Declaradas impossíveis/bloqueadas: {', '.join(rel['declaradas']) or 'nenhuma'}",
         f"- Em quarentena: {', '.join(rel['quarentena']) or 'ninguém'}",
         f"- **{rel['alerta_equipe']}**" if rel["alerta_equipe"] else "- Equipe acima do mínimo", "",
         "## Matriz de autonomia", "", "| agente | " + " | ".join(next(iter(rel["matriz_autonomia"].values()), {})) + " |",
         "|---|" + "---|" * len(next(iter(rel["matriz_autonomia"].values()), {}))]
    for ag, cls in rel["matriz_autonomia"].items():
        l.append(f"| {ag} | " + " | ".join(f"L{v}" for v in cls.values()) + " |")
    l += ["", "## Incidentes", ""] + [f"- {i['agente']}: {i['codigo']} — {i['motivo']}" for i in rel["incidentes"]]
    return "\n".join(l) + "\n"


def painel_html(rel: dict) -> str:
    e = html.escape
    linhas = "".join(f"<tr><td>{e(a)}</td>" + "".join(f"<td class='n'>L{v}</td>" for v in c.values()) + "</tr>"
                     for a, c in rel["matriz_autonomia"].items())
    cab = "".join(f"<th>{e(c)}</th>" for c in next(iter(rel["matriz_autonomia"].values()), {}))
    inc = "".join(f"<li><b>⛔ {e(i['agente'])}</b> {e(i['codigo'])} — {e(i['motivo'])}</li>" for i in rel["incidentes"]) \
        or "<li>nenhum</li>"
    fila = "".join(f"<li>⏸ {e(t)}</li>" for t in rel["fila_humano"]) or "<li>vazia</li>"
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>COLLEGIUM · Painel</title>
<style>:root{{--tinta:#1B1F24;--papel:#F7F5F0;--linha:#D9D4C7;--selo:#7A2E1F;--aceito:#2F6B3F;--pendente:#8A6D1A;--incidente:#A1261B;--neutro:#5E636B}}
@media (prefers-color-scheme:dark){{:root{{--tinta:#E8E6E1;--papel:#121417;--linha:#2A2E33;--selo:#C9644E;--aceito:#6FBF84;--pendente:#D8B44A;--incidente:#F0715F;--neutro:#9AA0A8}}}}
body{{background:var(--papel);color:var(--tinta);font:16px/1.5 Inter,system-ui,sans-serif;margin:0;padding:16px;max-width:960px}}
h1{{font-family:Fraunces,Georgia,serif;color:var(--selo)}}table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid var(--linha);padding:6px;text-align:left}}
.n,code{{font-family:"JetBrains Mono",monospace;font-variant-numeric:tabular-nums}}.ok{{color:var(--aceito)}}.mau{{color:var(--incidente)}}.pend{{color:var(--pendente)}}</style></head><body>
<h1>COLLEGIUM · Painel</h1>
<p>ANAIS íntegro: <b class="{'ok' if rel['integro'] else 'mau'}">{'✓ sim' if rel['integro'] else '✗ NÃO'}</b> ·
recibos {rel['recibos']} (aceitos <span class="ok">{rel['aceitos']}</span>) ·
âncora <code>{rel['ancora']['n']}:{e(rel['ancora']['selo'][:12])}…</code></p>
{f'<p class="mau"><b>⚠ {e(rel["alerta_equipe"])}</b></p>' if rel["alerta_equipe"] else ''}
<h2 class="pend">Fila do Patronus</h2><ul>{fila}</ul>
<h2>Matriz de autonomia</h2><table><tr><th>agente</th>{cab}</tr>{linhas}</table>
<h2 class="mau">Incidentes</h2><ul>{inc}</ul></body></html>"""
