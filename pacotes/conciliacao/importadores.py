"""Importadores de dado REAL (GAP G1: até a v0.1.2 só existia dado sintético).

Regra de conservação na entrada (P0): um extrato só entra se
    saldo_inicial + Σ lançamentos == saldo_final   (quando os saldos são conhecidos).
Se não fecha, NÃO se concilia: a tarefa deve ser declarada BLOQUEADA com essa evidência.
Valores sempre em CENTAVOS inteiros via Decimal — nunca float (1,10 + 2,20 != 3,30 em float).

Fontes suportadas:
  - OFX 1.x (SGML) e 2.x (XML), o formato que os bancos exportam;
  - CSV do ERP / planilha (separador, colunas e formato de data configuráveis);
  - Imagem/PDF escaneado via PaddleOCR (opcional; dependência pesada, NÃO usada nos testes):
    cada número lido com confiança abaixo do limiar vira item "revisar" — o oráculo proíbe
    casá-lo. OCR errado com confiança alta é pego pela prova de saldo.
"""
from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

# ------------------------------------------------------------------ números e datas BR

_NUM = re.compile(r"^\(?-?\s*(R\$\s*)?[\d.]+(,\d{1,2})?\)?-?$|^-?\d+(\.\d{1,2})?$")


def centavos(texto: str) -> int:
    """'1.234,56' | '-1.234,56' | '(1.234,56)' | '1234.56' | '1.234,56-' -> centavos (int)."""
    t = str(texto).strip().replace("R$", "").replace(" ", "")
    negativo = t.startswith("-") or t.endswith("-") or (t.startswith("(") and t.endswith(")"))
    t = t.strip("()-")
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif t.count(".") > 1:
        t = t.replace(".", "")
    try:
        v = (Decimal(t) * 100).quantize(Decimal("1"))
    except InvalidOperation as e:
        raise ValueError(f"valor monetário ilegível: {texto!r}") from e
    return -int(v) if negativo else int(v)


def data_iso(texto: str, formatos=("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%Y%m%d")) -> str:
    for f in formatos:
        try:
            return datetime.strptime(texto.strip()[:10 if "-" in texto or "/" in texto else 8], f).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"data ilegível: {texto!r}")


# ------------------------------------------------------------------ prova de saldo (P0)

def checar_saldo(extrato: list[dict], saldo_inicial: int | None, saldo_final: int | None) -> tuple[bool, str]:
    if saldo_inicial is None or saldo_final is None:
        return True, "SALDOS_DESCONHECIDOS: conservação não verificável (declarar no recibo)"
    soma = sum(x["valor"] for x in extrato)
    if saldo_inicial + soma != saldo_final:
        return False, f"SALDO_NAO_FECHA: {saldo_inicial} + {soma} = {saldo_inicial + soma} != {saldo_final}"
    return True, "SALDO_FECHA"


# ------------------------------------------------------------------ OFX

def _tag(bloco: str, nome: str) -> str | None:
    m = re.search(rf"<{nome}>([^<\r\n]*)", bloco, re.I)
    return m.group(1).strip() if m else None


def ler_ofx(conteudo: str | bytes) -> dict:
    """Retorna {"extrato": [...], "saldo_final": int|None, "saldo_inicial": int|None}."""
    if isinstance(conteudo, bytes):
        for enc in ("utf-8", "cp1252", "latin-1"):
            try:
                conteudo = conteudo.decode(enc)
                break
            except UnicodeDecodeError:
                continue
    extrato, vistos = [], set()
    for bloco in re.findall(r"<STMTTRN>(.*?)(?:</STMTTRN>|(?=<STMTTRN>)|(?=</BANKTRANLIST>))", conteudo, re.S | re.I):
        fitid = _tag(bloco, "FITID")
        if not fitid or fitid in vistos:
            raise ValueError(f"OFX com FITID ausente ou repetido: {fitid!r}")
        vistos.add(fitid)
        desc = " ".join(x for x in (_tag(bloco, "NAME"), _tag(bloco, "MEMO"), _tag(bloco, "CHECKNUM")) if x)
        extrato.append({"id": f"B-{fitid}", "data": data_iso(_tag(bloco, "DTPOSTED")[:8], ("%Y%m%d",)),
                        "valor": centavos(_tag(bloco, "TRNAMT")), "desc": desc})
    bal = re.search(r"<LEDGERBAL>(.*?)(?:</LEDGERBAL>|<AVAILBAL>|$)", conteudo, re.S | re.I)
    saldo_final = centavos(_tag(bal.group(1), "BALAMT")) if bal and _tag(bal.group(1), "BALAMT") else None
    return {"extrato": extrato, "saldo_final": saldo_final, "saldo_inicial": None}


# ------------------------------------------------------------------ CSV (ERP / planilha)

def ler_csv(conteudo: str, colunas: dict, prefixo: str, sep: str = ";") -> list[dict]:
    """colunas = {"id": "Num", "data": "Data", "valor": "Valor", "doc": "Documento"} (ou "desc").
    Débito/crédito em colunas separadas: {"debito": "Saída", "credito": "Entrada"}."""
    linhas = csv.DictReader(io.StringIO(conteudo), delimiter=sep)
    out, vistos = [], set()
    for i, ln in enumerate(linhas):
        ln = {k.strip(): (v or "").strip() for k, v in ln.items() if k}
        ident = ln.get(colunas.get("id", ""), "") or str(i)
        if ident in vistos:
            raise ValueError(f"id repetido no CSV: {ident}")
        vistos.add(ident)
        if "valor" in colunas:
            valor = centavos(ln[colunas["valor"]])
        else:
            cred = ln.get(colunas["credito"], "") or "0"
            deb = ln.get(colunas["debito"], "") or "0"
            valor = centavos(cred) - abs(centavos(deb))
        item = {"id": f"{prefixo}-{ident}", "data": data_iso(ln[colunas["data"]]), "valor": valor}
        if "doc" in colunas:
            item["doc"] = ln.get(colunas["doc"], "")
        if "desc" in colunas:
            item["desc"] = ln.get(colunas["desc"], "")
        out.append(item)
    return out


# ------------------------------------------------------------------ OCR (PaddleOCR, opcional)

_DATA = re.compile(r"^\d{2}/\d{2}(/\d{2,4})?$")
_VALOR = re.compile(r"^-?\(?(R\$)?\s*\d{1,3}(\.\d{3})*,\d{2}\)?-?[CD]?$")


def extrato_de_ocr(tokens: list[tuple[str, float, list[float]]], ano: int, limiar: float = 0.95,
                   tolerancia_y: float = 8.0) -> dict:
    """tokens = [(texto, confiança, [x0, y0, x1, y1]), ...] na ordem do motor de OCR.
    Agrupa por linha (centro vertical), lê data / histórico / valor, e marca "revisar" quando
    a data ou o valor vieram com confiança < limiar. Reconhece SALDO ANTERIOR / SALDO FINAL."""
    linhas: list[list[tuple[str, float, list[float]]]] = []
    for tok in sorted(tokens, key=lambda t: ((t[2][1] + t[2][3]) / 2, t[2][0])):
        cy = (tok[2][1] + tok[2][3]) / 2
        if linhas and abs(cy - (linhas[-1][0][2][1] + linhas[-1][0][2][3]) / 2) <= tolerancia_y:
            linhas[-1].append(tok)
        else:
            linhas.append([tok])
    extrato, saldo_ini, saldo_fim, n = [], None, None, 0
    for ln in linhas:
        ln.sort(key=lambda t: t[2][0])
        textos = [t[0] for t in ln]
        texto = " ".join(textos).upper()
        valores = [t for t in ln if _VALOR.match(t[0].replace(" ", ""))]
        if "SALDO" in texto and valores:
            v = centavos(valores[-1][0].rstrip("CD") if not valores[-1][0].endswith("D")
                         else "-" + valores[-1][0].rstrip("D"))
            if "ANTERIOR" in texto or "INICIAL" in texto:
                saldo_ini = v
            else:
                saldo_fim = v
            continue
        datas = [t for t in ln if _DATA.match(t[0])]
        if not datas or not valores:
            continue
        dt, vl = datas[0], valores[-1]
        bruto = vl[0].replace(" ", "")
        negativo = bruto.endswith("D") or bruto.startswith("-") or bruto.endswith("-")
        valor = abs(centavos(bruto.rstrip("CD"))) * (-1 if negativo else 1)
        d = dt[0] if dt[0].count("/") == 2 else f"{dt[0]}/{ano}"
        desc = " ".join(t[0] for t in ln if t is not dt and t is not vl)
        item = {"id": f"B-OCR{n:04d}", "data": data_iso(d), "valor": valor, "desc": desc,
                "confianca": round(min(dt[1], vl[1]), 4)}
        if min(dt[1], vl[1]) < limiar:
            item["revisar"] = True
        extrato.append(item)
        n += 1
    return {"extrato": extrato, "saldo_inicial": saldo_ini, "saldo_final": saldo_fim}


def ler_imagem_paddle(caminho: str, ano: int, limiar: float = 0.95, motor=None) -> dict:
    """Usa PaddleOCR 3.x (Apache-2.0) se instalado: `pip install paddleocr` + motor de inferência.
    Não é dependência do núcleo. `motor` permite injetar um OCR falso nos testes."""
    if motor is None:
        from paddleocr import PaddleOCR  # import tardio: só quem usa OCR paga o custo
        motor = PaddleOCR(lang="pt", use_doc_orientation_classify=False, use_doc_unwarping=False,
                          use_textline_orientation=False)
    tokens = []
    for res in motor.predict(caminho):
        dados = res.json.get("res", res.json) if hasattr(res, "json") else res
        for txt, sc, bx in zip(dados["rec_texts"], dados["rec_scores"], dados["rec_boxes"]):
            tokens.append((str(txt), float(sc), [float(v) for v in bx]))
    return extrato_de_ocr(tokens, ano, limiar)
