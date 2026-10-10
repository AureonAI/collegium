"""Piloto de conciliação (T066): do arquivo do banco e do ERP ao relatório que o humano assina.

    python -m collegium conciliar --extrato EXTRATO --razao RAZAO --saida PASTA [opções]

Entradas aceitas — extrato: OFX, CNAB 240, JSON do Open Finance ou planilha CSV/TXT;
razão: planilha CSV/TXT exportada do ERP (cabeçalho encontrado sozinho; ver importadores.ler_planilha).

Antes de conciliar, três checagens de SANIDADE (Art. 3, dever de declarar). Se qualquer uma falhar,
a tarefa é DECLARADA BLOQUEADA no ANAIS com a evidência, e o relatório diz o que corrigir:
  S1 prova de saldo do extrato (saldo inicial + lançamentos = saldo final), quando os saldos existem;
  S2 períodos: a sobreposição das datas cobre >= 50% do período do extrato;
  S3 convenção de sinal do razão (bancária x contábil) decidida pelos dados (detectar_convencao);
     "indeterminado" quase sempre significa razão de OUTRA conta — o sistema não chuta.

Saídas na PASTA: relatorio.html (para o humano ler e aprovar), pendencias.csv e pares.csv (Excel,
sem fórmula executável), resumo.json (máquina) e, com --chave, cabeca.json + recibo.json (o cliente
confere sem acesso ao sistema). O ANAIS (padrão PASTA/anais.jsonl) guarda cada decisão selada.
"""
from __future__ import annotations

import csv
import dataclasses
import hashlib
import html
import io
import json
import os
import re
from datetime import date, datetime, timezone

from collegium import execucao
from collegium import recibo as rc
from collegium.ledger import Ledger

from . import importadores as imp
from . import operarios, oraculo, residuo
from .oficio import OFICIO

PADROES = [r"NF\d+", r"BOL\d+", r"PED\d+", r"DUP\d+"]
SOBREPOSICAO_MINIMA = 0.5   # S2, pré-registrado em 10/10/2026
MOTIVOS = {
    "SEM_CANDIDATO_1A1": "Sem lançamento correspondente de mesmo valor e data próxima",
    "VALOR_REPETIDO_SEM_DOC": "Valor repetido e nenhum documento que diga qual é o par",
    "DOC_CONTRADIZ": "O histórico cita um documento diferente do candidato",
    "ITEM_REVISAR": "Leitura incerta (OCR): confira o valor no documento",
    "CANDIDATO_UNICO_NAO_CASADO": "Um único candidato, não casado automaticamente: confira",
}

# ---------------------------------------------------------------- documentos em forma canônica
# H-DOC (hipótese a validar com dado real): bancos e ERPs escrevem "NF 000123", "NF-e 123",
# "Nota Fiscal nº 123". Tudo vira "NF123" dos dois lados, para a evidência documental funcionar.
_DOC_RX = [
    (re.compile(r"\b(?:NFS?\s*-?\s*E?|NOTA(?:\s+FISCAL)?)\s*(?:N[º°O.]?\s*)?[:#.\-]*\s*0*(\d{1,12})\b", re.I), "NF"),
    (re.compile(r"\bBOL(?:ETO)?\s*(?:N[º°O.]?\s*)?[:#.\-]*\s*0*(\d{1,20})\b", re.I), "BOL"),
    (re.compile(r"\bPED(?:IDO)?\s*(?:N[º°O.]?\s*)?[:#.\-]*\s*0*(\d{1,12})\b", re.I), "PED"),
    (re.compile(r"\bDUP(?:LICATA)?\s*(?:N[º°O.]?\s*)?[:#.\-]*\s*0*(\d{1,12})\b", re.I), "DUP"),
]


def docs_canonicos(texto: str) -> list[str]:
    out: list[str] = []
    for rx, pref in _DOC_RX:
        for m in rx.finditer(texto or ""):
            tok = pref + (m.group(1) or "0")
            if tok not in out:
                out.append(tok)
    return out


def _canonizar(extrato: list[dict], razao: list[dict]) -> tuple[list[dict], list[dict]]:
    ext = []
    for b in extrato:
        b = dict(b)
        toks = docs_canonicos(b.get("desc", ""))
        b["desc_original"] = b.get("desc", "")
        b["desc"] = " ".join([b.get("desc", "")] + [t for t in toks if t not in b.get("desc", "").split()]).strip()
        ext.append(b)
    raz = []
    for r in razao:
        r = dict(r)
        fonte = " ".join(x for x in (r.get("doc", ""), r.get("desc", "")) if x)
        toks = docs_canonicos(r.get("doc", "")) or docs_canonicos(r.get("desc", ""))
        r["doc_original"] = r.get("doc", "")
        r["doc"] = toks[0] if toks else (r.get("doc", "") or "").strip()
        if not fonte:
            r["doc"] = ""
        raz.append(r)
    return ext, raz


# ---------------------------------------------------------------- leitura de arquivos

def _ler_bytes(caminho: str, papel: str) -> bytes:
    with open(caminho, "rb") as f:
        dados = f.read()
    if not dados.strip():  # R6-17
        raise imp.ImportacaoInvalida(f"o arquivo do {papel} está vazio: {os.path.basename(caminho)}")
    return dados


def _exigir_lancamentos(r: dict, papel: str) -> dict:
    if not r["itens"]:  # R6-17: antes, IndexError lá na frente
        raise imp.ImportacaoInvalida(f"o {papel} está sem lançamentos: exporte o período com movimento")
    return r


def carregar_extrato(caminho: str) -> dict:
    return _exigir_lancamentos(_carregar_extrato(_ler_bytes(caminho, "extrato"), caminho), "extrato")


def _carregar_extrato(dados: bytes, caminho: str) -> dict:
    cab = dados[:4000].upper()
    if b"<OFX" in cab or b"OFXHEADER" in cab:
        r = imp.ler_ofx(dados)
        return {"itens": r["extrato"], "saldo_inicial": r["saldo_inicial"], "saldo_final": r["saldo_final"],
                "formato": "OFX", "ignoradas": [], "avisos": r.get("avisos", [])}
    if caminho.lower().endswith(".json"):
        r = imp.ler_open_finance(json.loads(dados.decode("utf-8-sig")))
        return {"itens": r["extrato"], "saldo_inicial": None, "saldo_final": None, "formato": "Open Finance",
                "ignoradas": [{"linha": None, "texto": f"{len(r.get('fora_por_nao_efetivada', []))} transações "
                               "não efetivadas ficaram fora"}] if r.get("fora_por_nao_efetivada") else []}
    linhas = [ln for ln in dados.splitlines() if ln.strip()]
    if linhas and all(len(ln.rstrip(b"\r")) == 240 for ln in linhas):
        r = imp.ler_cnab240(dados)
        return {"itens": r["extrato"], "saldo_inicial": r["saldo_inicial"], "saldo_final": r["saldo_final"],
                "formato": "CNAB 240", "ignoradas": [], "conferencia": r.get("conferencia")}
    r = imp.ler_planilha(dados, "B")
    return {"itens": r["itens"], "saldo_inicial": r["saldo_inicial"], "saldo_final": r["saldo_final"],
            "formato": f"planilha ({r['encoding']}, separador {r['separador']!r}, colunas {r['mapa']})",
            "ignoradas": r["ignoradas"]}


def carregar_razao(caminho: str) -> dict:
    r = imp.ler_planilha(_ler_bytes(caminho, "razão"), "R")
    return _exigir_lancamentos({"itens": r["itens"], "saldo_inicial": r["saldo_inicial"], "saldo_final": r["saldo_final"],
            "formato": f"planilha ({r['encoding']}, separador {r['separador']!r}, colunas {r['mapa']})",
            "ignoradas": r["ignoradas"]}, "razão")


# ---------------------------------------------------------------- sanidade (S0–S3)

def _periodo(itens):
    ds = sorted(date.fromisoformat(x["data"]) for x in itens)
    return ds[0], ds[-1]


def sanidade(ext: dict, raz: dict, sinal: str) -> dict:
    """Devolve {"bloqueio": motivo|None, "avisos": [...], "convencao": ..., "razao_itens": ...}."""
    avisos: list[str] = list(ext.get("avisos", []))
    chave = lambda xs: sorted((x["data"], x["valor"], x.get("desc", "")) for x in xs)  # noqa: E731
    if chave(ext["itens"]) == chave(raz["itens"]):  # R6-15: o mesmo arquivo dos dois lados dava "CONCILIADO"
        return {"bloqueio": "S0 MESMO_CONTEUDO: o extrato e o razão têm exatamente os mesmos lançamentos; "
                            "provavelmente o mesmo arquivo foi escolhido duas vezes. Use o extrato do BANCO e o "
                            "razão do ERP.", "avisos": avisos}
    ok, msg = imp.checar_saldo(ext["itens"], ext["saldo_inicial"], ext["saldo_final"])
    if not ok:
        return {"bloqueio": f"S1 {msg}. O extrato está incompleto ou foi lido errado: exporte de novo o período inteiro.",
                "avisos": avisos}
    if msg.startswith("SALDOS_DESCONHECIDOS"):
        avisos.append("O extrato não traz saldo inicial e final: a prova de saldo (S1) NÃO pôde ser feita.")
    (e0, e1), (r0, r1) = _periodo(ext["itens"]), _periodo(raz["itens"])
    sobre = max(0, (min(e1, r1) - max(e0, r0)).days + 1) / ((e1 - e0).days + 1)
    if sobre < SOBREPOSICAO_MINIMA:
        return {"bloqueio": f"S2 PERIODOS_DIFERENTES: extrato {e0}..{e1}, razão {r0}..{r1} "
                            f"(sobreposição {sobre:.0%} < {SOBREPOSICAO_MINIMA:.0%}). Exporte o MESMO período.",
                "avisos": avisos}
    det = imp.detectar_convencao(ext["itens"], raz["itens"])
    itens_r = raz["itens"]
    if sinal == "auto":
        if det["convencao"] == "indeterminado":
            return {"bloqueio": f"S3 CONVENCAO_INDETERMINADA: só {max(det['casam_direto'], det['casam_invertido'])} "
                                f"lançamentos do razão têm par no extrato com qualquer sinal (mínimo {det['minimo']}). "
                                "Causas comuns: razão de OUTRA conta; datas no formato mês/dia ou valores no formato "
                                "1,234.56 (sistema configurado em inglês); exportação incompleta. Se tiver certeza "
                                "de que é a mesma conta e o mesmo formato, rode de novo com --sinal-razao bancaria "
                                "ou --sinal-razao contabil.",
                    "avisos": avisos, "convencao": det}
        conv = det["convencao"]
    else:
        conv = sinal
    if conv == "contabil":
        itens_r = imp.inverter(itens_r)
        avisos.append("O razão foi lido na convenção CONTÁBIL (entrada no banco = débito) e os sinais foram "
                      f"invertidos para comparar com o extrato ({det['casam_invertido']} casamentos invertidos contra "
                      f"{det['casam_direto']} diretos). Confira se isso faz sentido para este ERP.")
    if raz["saldo_inicial"] is not None and raz["saldo_final"] is not None:
        soma = sum(x["valor"] for x in itens_r)
        fecha = any(si + soma == sf for si, sf in ((raz["saldo_inicial"], raz["saldo_final"]),
                                                   (-raz["saldo_inicial"], -raz["saldo_final"])))
        if not fecha:
            avisos.append("O razão traz saldos que NÃO fecham com os lançamentos lidos: confira se a exportação "
                          "está completa (aviso, não bloqueio: a convenção de saldo varia entre ERPs).")
    return {"bloqueio": None, "avisos": avisos, "convencao": dict(det, usada=conv), "razao_itens": itens_r}


# ---------------------------------------------------------------- formatação segura

def reais(c: int) -> str:
    s = "-" if c < 0 else ""
    c = abs(int(c))
    inteiro = f"{c // 100:,}".replace(",", ".")
    return f"{s}R$ {inteiro},{c % 100:02d}"


def dbr(iso: str) -> str:
    """Data no formato do contador brasileiro: 2026-09-26 -> 26/09/2026."""
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if len(iso) == 10 and iso[4] == "-" else iso


class NumeroBR(str):
    """R6-21: número gerado POR NÓS (de um int em centavos), no formato do Excel em português: '-18071,82'.
    É o único conteúdo que passa sem apóstrofo, e só se casar com o padrão estrito."""


_NUMERO_BR = re.compile(r"-?\d+,\d{2}")


def num_br(c: int) -> NumeroBR:
    return NumeroBR(f"{'-' if c < 0 else ''}{abs(int(c)) // 100},{abs(int(c)) % 100:02d}")


def _celula(v) -> str:
    """CWE-1236: texto que começa com = + - @ TAB CR vira fórmula no Excel. Neutraliza com apóstrofo."""
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def _csv(linhas: list[list], cabecalho: list[str]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(cabecalho)
    for ln in linhas:
        w.writerow([x if isinstance(x, (int, float)) or (isinstance(x, NumeroBR) and _NUMERO_BR.fullmatch(x))
                    else _celula(x) for x in ln])  # qualquer outro texto que comece com - é neutralizado
    return buf.getvalue()


# ---------------------------------------------------------------- execução

def conciliar_arquivos(extrato: str, razao: str, saida: str, ente: str = "Cliente", sinal: str = "auto",
                       padroes_extra: list[str] | None = None, anais: str | None = None,
                       chave_hmac: bytes | None = None, chave_privada: bytes | None = None,
                       humanos: dict[str, str] | None = None) -> dict:
    if sinal not in ("auto", "bancaria", "contabil"):
        raise ValueError("--sinal-razao deve ser auto, bancaria ou contabil")
    os.makedirs(saida, exist_ok=True)
    ext, raz = carregar_extrato(extrato), carregar_razao(razao)
    s = sanidade(ext, raz, sinal)
    params = {"padroes_documento": PADROES + list(padroes_extra or [])}
    itens_r = s.get("razao_itens", raz["itens"])
    e_can, r_can = _canonizar(ext["itens"], itens_r)
    entrada = {"extrato": e_can, "razao": r_can}
    of = dataclasses.replace(
        OFICIO, oraculo=oraculo.fabricar_oraculo(params),
        operario=lambda e: operarios.honesto_v5(e["extrato"], e["razao"], params),
        residuo=lambda e, p: residuo.pacote_humano(e["extrato"], e["razao"], p, params))
    caminho_anais = anais or os.path.join(saida, "anais.jsonl")
    led = Ledger(caminho_anais, chave=chave_hmac)
    resumo = {"ente": ente, "extrato": os.path.basename(extrato), "razao": os.path.basename(razao),
              "formato_extrato": ext["formato"], "formato_razao": raz["formato"],
              "lancamentos_extrato": len(ext["itens"]), "lancamentos_razao": len(raz["itens"]),
              "linhas_ignoradas": {"extrato": ext["ignoradas"], "razao": raz["ignoradas"]},
              "avisos": s["avisos"], "convencao": s.get("convencao"), "anais": os.path.abspath(caminho_anais),
              "anais_com_chave": chave_hmac is not None,
              "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if s["bloqueio"]:
        r = execucao.bloquear(of, led, entrada, ente, s["bloqueio"], humanos)
        resumo.update(status="BLOQUEADO", motivo=s["bloqueio"], tarefa=r["tarefa"], anais_integro=r["anais_integro"])
    else:
        r = execucao.executar(of, led, entrada, ente, humanos=humanos)
        prop = r["entrega"]
        casados = len(prop["pares"]) + sum(len(g["banco"]) for g in prop.get("grupos", []))
        resumo.update(status="CONCILIADO" if r["estado"] == "ACEITA" else "ERRO_INTERNO", tarefa=r["tarefa"],
                      falhas=r["falhas"], pares=len(prop["pares"]), grupos=len(prop.get("grupos", [])),
                      pendencias_extrato=len(prop["pendentes_banco"]), pendencias_razao=len(prop["pendentes_razao"]),
                      cobertura_extrato=round(casados / max(len(e_can), 1), 4),
                      entrada_sha256=r["entrada_sha256"], entrega_sha256=r["entrega_sha256"],
                      liberacao=r.get("liberacao"), anais_integro=r["anais_integro"])
        _escrever_tabelas(saida, entrada, prop, r.get("residuo", []))
    resumo["humanos"] = sorted(_humanos_registrados(led))  # DEPOIS da execução que os registra
    if chave_privada is not None:
        cab = rc.cabeca(caminho_anais, chave_privada, ente, datetime.now(timezone.utc).isoformat(timespec="seconds"))
        with open(os.path.join(saida, "cabeca.json"), "w", encoding="utf-8") as f:
            json.dump(cab, f, ensure_ascii=False, indent=1)
        with open(os.path.join(saida, "recibo.json"), "w", encoding="utf-8") as f:
            json.dump(rc.emitir_recibo(caminho_anais, resumo["tarefa"], cab), f, ensure_ascii=False, indent=1)
        resumo["recibo"] = "recibo.json (conferir com: python -m collegium conferir-recibo recibo.json CHAVE_PUBLICA)"
    with open(os.path.join(saida, "resumo.json"), "w", encoding="utf-8") as f:
        json.dump(resumo_publico(resumo, extrato, razao), f, ensure_ascii=False, indent=1)
    with open(os.path.join(saida, "relatorio.html"), "w", encoding="utf-8") as f:
        f.write(relatorio_html(resumo, entrada, r))
    return resumo


def _sha256_arquivo(caminho: str) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 16), b""):
            h.update(bloco)
    return h.hexdigest()


def resumo_publico(resumo: dict, extrato: str, razao: str) -> dict:
    """R6-13: resumo.json é o arquivo que pode SAIR do escritório. Só números, códigos e hashes: sem nome de
    arquivo (costuma ter nome do cliente), sem caminho (tem o nome do usuário) e sem texto das linhas do
    cliente. O relatório local (relatorio.html) continua mostrando tudo para quem está no computador."""
    p = dict(resumo)
    p.pop("extrato", None)
    p.pop("razao", None)
    p["extrato_sha256"], p["razao_sha256"] = _sha256_arquivo(extrato), _sha256_arquivo(razao)
    p["anais"] = os.path.basename(resumo["anais"])
    p["linhas_ignoradas"] = {lado: [{"linha": x.get("linha")} for x in xs]
                             for lado, xs in resumo["linhas_ignoradas"].items()}
    return p


def _humanos_registrados(led: Ledger) -> list[str]:
    cam = led.caminho + ".regimento.json"
    if not os.path.exists(cam):
        return []
    with open(cam, encoding="utf-8") as f:
        reg = json.load(f)
    return [n for n, d in reg["agentes"].items() if d.get("familia_modelo") == "humano"]


def _escrever_tabelas(saida: str, entrada: dict, prop: dict, pilha: list[dict]) -> None:
    B = {x["id"]: x for x in entrada["extrato"]}
    R = {x["id"]: x for x in entrada["razao"]}
    pend = []
    for it in pilha:
        x = B[it["id"]] if it["lado"] == "banco" else R[it["id"]]
        outro = R if it["lado"] == "banco" else B
        pend.append([it["lado"], it["id"], dbr(x["data"]), num_br(x["valor"]),
                     x.get("desc_original", x.get("desc", "")) or x.get("doc_original", x.get("doc", "")),
                     MOTIVOS.get(it["motivo"], it["motivo"]),
                     " | ".join(f"{c} {dbr(outro[c]['data'])} {reais(outro[c]['valor'])}" for c in it["candidatos"])])
    with open(os.path.join(saida, "pendencias.csv"), "w", encoding="utf-8-sig", newline="") as f:
        f.write(_csv(pend, ["lado", "id", "data", "valor", "historico_ou_documento", "motivo", "candidatos"]))
    pares = [[b, dbr(B[b]["data"]), num_br(B[b]["valor"]), B[b].get("desc_original", ""), r, dbr(R[r]["data"]),
              R[r].get("doc_original", R[r].get("doc", "")) or R[r].get("desc", "")] for b, r in prop["pares"]]
    for g in prop.get("grupos", []):
        for b in g["banco"]:
            for r in g["razao"]:
                pares.append([b, dbr(B[b]["data"]), num_br(B[b]["valor"]), B[b].get("desc_original", ""),
                              r, dbr(R[r]["data"]), f"(lote) {reais(R[r]['valor'])} {R[r].get('doc_original', '')}"])
    with open(os.path.join(saida, "pares.csv"), "w", encoding="utf-8-sig", newline="") as f:
        f.write(_csv(pares, ["extrato_id", "extrato_data", "valor", "extrato_historico", "razao_id", "razao_data",
                             "razao_documento"]))


# ---------------------------------------------------------------- relatório para o humano

def _como_aprovar(resumo: dict) -> str:
    e = html.escape
    if resumo["status"] != "CONCILIADO":
        return ""
    if not resumo.get("humanos"):
        return ("<section class='caixa pend'><b>Ninguém pode aprovar esta conciliação:</b> nenhum humano responsável "
                "foi registrado neste ANAIS. Na próxima conciliação use <code>--humano NOME --chave-publica CHAVE</code> "
                "(a chave sai de <code>python -m collegium gerar-chave</code>).</section>")
    return ("<section class='caixa'><b>Nada aqui é aprovado automaticamente.</b> Depois de decidir as pendências, "
            "o responsável aprova no próprio computador (a assinatura usa a chave privada dele):<br>"
            f"<code>python -m collegium aprovar --anais {e(resumo['anais'])} --tarefa {e(resumo['tarefa'])} "
            f"--humano {e(resumo['humanos'][0])} --chave ARQUIVO_DA_SUA_CHAVE</code><br>"
            "Para recusar a entrega, acrescente <code>--rejeitar</code>.</section>")


def relatorio_html(resumo: dict, entrada: dict, r: dict) -> str:
    e = html.escape
    st = resumo["status"]
    cor = {"CONCILIADO": "ok", "BLOQUEADO": "pend"}.get(st, "mau")
    B = {x["id"]: x for x in entrada["extrato"]}
    R = {x["id"]: x for x in entrada["razao"]}
    avisos = "".join(f"<li>{e(a)}</li>" for a in resumo["avisos"]) or "<li>nenhum</li>"
    ign = [(lado, x) for lado in ("extrato", "razao") for x in resumo["linhas_ignoradas"][lado]]
    ign_html = "".join(f"<li>{e(lado)}: linha {e(str(x.get('linha')))} — <code>{e(x['texto'])}</code></li>"
                       for lado, x in ign) or "<li>nenhuma</li>"
    corpo = ""
    if st == "BLOQUEADO":
        corpo = (f"<section class='caixa pend'><h2>⏸ Não conciliado: o sistema declarou BLOQUEADO</h2>"
                 f"<p>{e(resumo['motivo'])}</p><p>Nada foi entregue como se estivesse certo. Corrija a entrada "
                 f"e rode de novo.</p></section>")
    else:
        linhas = []
        for it in r.get("residuo", []):
            x = B[it["id"]] if it["lado"] == "banco" else R[it["id"]]
            outro = R if it["lado"] == "banco" else B
            txt = x.get("desc_original", x.get("desc", "")) or x.get("doc_original", x.get("doc", ""))
            cands = "<br>".join(f"<code>{e(c)}</code> <span class='n'>{e(dbr(outro[c]['data']))} "
                                f"{e(reais(outro[c]['valor']))}</span>" for c in it["candidatos"]) or "—"
            linhas.append(f"<tr><td data-r='lado'>{'banco' if it['lado'] == 'banco' else 'razão'}</td>"
                          f"<td data-r='id'><code>{e(it['id'])}</code></td><td data-r='data' class='n'>{e(dbr(x['data']))}</td>"
                          f"<td data-r='valor' class='n'>{e(reais(x['valor']))}</td><td data-r='histórico'>{e(txt)}</td>"
                          f"<td data-r='motivo'>{e(MOTIVOS.get(it['motivo'], it['motivo']))}</td>"
                          f"<td data-r='candidatos'>{cands}</td></tr>")
        tabela = ("<table><tr><th>lado</th><th>id</th><th>data</th><th>valor</th><th>histórico / documento</th>"
                  "<th>motivo</th><th>candidatos</th></tr>" + "".join(linhas) + "</table>") if linhas else \
            "<p class='ok'>Nenhuma pendência.</p>"
        corpo = (f"<section class='grade'>"
                 f"<div><b class='n'>{resumo['pares'] + resumo['grupos']}</b><span>pares e lotes casados</span></div>"
                 f"<div><b class='n'>{resumo['pendencias_extrato']}</b><span>pendências do extrato</span></div>"
                 f"<div><b class='n'>{resumo['pendencias_razao']}</b><span>pendências do razão</span></div>"
                 f"<div><b class='n'>{resumo['cobertura_extrato']:.1%}</b><span>do extrato casado</span></div>"
                 f"</section><h2>Pendências para sua decisão</h2>{tabela}"
                 f"<p>Pares casados: ver <code>pares.csv</code>. Pendências em planilha: <code>pendencias.csv</code>.</p>")
    rodape = (f"<p class='meta'>Tarefa <code>{e(resumo['tarefa'])}</code> · ANAIS "
              f"{'íntegro' if resumo.get('anais_integro') else 'NÃO íntegro'}"
              f"{'' if resumo['anais_com_chave'] else ' (sem chave HMAC: protege contra erro, não contra adulteração)'}"
              + (f" · entrada <code>{e(resumo['entrada_sha256'][:16])}</code> · entrega "
                 f"<code>{e(resumo['entrega_sha256'][:16])}</code>" if resumo.get("entrada_sha256") else "")
              + (" · recibo assinado: <code>recibo.json</code>" if resumo.get("recibo") else "")
              + f" · gerado em {e(resumo['gerado_em'])}</p>")
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<title>Conciliação · {e(resumo['ente'])}</title>
<style>:root{{--tinta:#1B1F24;--papel:#F7F5F0;--linha:#D9D4C7;--selo:#7A2E1F;--aceito:#2F6B3F;--pendente:#8A6D1A;--incidente:#A1261B;--neutro:#5E636B}}
@media (prefers-color-scheme:dark){{:root{{--tinta:#E8E6E1;--papel:#121417;--linha:#2A2E33;--selo:#C9644E;--aceito:#6FBF84;--pendente:#D8B44A;--incidente:#F0715F;--neutro:#9AA0A8}}}}
*{{box-sizing:border-box}}body{{background:var(--papel);color:var(--tinta);font:15px/1.5 Inter,system-ui,sans-serif;margin:0 auto;padding:16px;max-width:1100px}}
h1{{font-family:Fraunces,Georgia,serif;color:var(--selo);margin:.2em 0}}h2{{font-size:1.1em;margin-top:1.6em}}
table{{border-collapse:collapse;width:100%;font-size:.92em}}td,th{{border-bottom:1px solid var(--linha);padding:6px;text-align:left;vertical-align:top}}
.n,code{{font-family:"JetBrains Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums;white-space:nowrap}}
.ok{{color:var(--aceito)}}.mau{{color:var(--incidente)}}.pend{{color:var(--pendente)}}.meta{{color:var(--neutro);font-size:.85em}}
.selo{{display:inline-block;border:2px solid currentColor;border-radius:4px;padding:2px 10px;font-weight:700}}
.grade{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:16px 0}}
.grade div{{border:1px solid var(--linha);border-radius:6px;padding:10px}}.grade b{{font-size:1.6em;display:block}}
.caixa{{border:1px solid currentColor;border-radius:6px;padding:12px;margin:16px 0}}
@media (max-width:640px){{table,tbody,tr,td{{display:block;width:100%}}tr:first-child{{display:none}}
tr{{border:1px solid var(--linha);border-radius:6px;margin:0 0 10px;padding:6px 10px}}td{{border:0;padding:2px 0}}
td::before{{content:attr(data-r);display:block;color:var(--neutro);font-size:.78em}}}}</style></head><body>
<h1>Conciliação bancária · {e(resumo['ente'])}</h1>
<p><span class="selo {cor}">{e(st)}</span> extrato <code>{e(resumo['extrato'])}</code> ({e(str(resumo['lancamentos_extrato']))} lançamentos,
{e(resumo['formato_extrato'])}) × razão <code>{e(resumo['razao'])}</code> ({e(str(resumo['lancamentos_razao']))} lançamentos)</p>
{corpo}
<h2>Avisos</h2><ul>{avisos}</ul>
<h2>Linhas do arquivo que não são lançamentos (totais, saldos)</h2><ul>{ign_html}</ul>
{_como_aprovar(resumo)}
<p class="meta">O texto dos arquivos é tratado como dado, nunca como instrução.</p>
{rodape}</body></html>"""
