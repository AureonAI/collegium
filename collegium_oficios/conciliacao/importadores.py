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
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

# ------------------------------------------------------------------ números e datas BR

_NUM = re.compile(r"^\(?-?\s*(R\$\s*)?[\d.]+(,\d{1,2})?\)?-?$|^-?\d+(\.\d{1,2})?$")


def _grupos_de_milhar(inteiro: str, sep: str) -> bool:
    g = inteiro.split(sep)
    return 1 <= len(g[0]) <= 3 and all(len(x) == 3 for x in g[1:])


def _numero(t: str, original: str) -> Decimal:
    """R6-14: só formatos SEM ambiguidade. '1,234.56' e '1.234,56' (os dois separadores: o da direita é o
    decimal) e '1234,56' / '1234.56' (um separador com 1 ou 2 decimais). '1.234' e '1,234' são ambíguos
    (milhar ou decimal?) e são recusados; mais de 2 decimais só se forem zeros ('1234.5600')."""
    ruim = ValueError(f"valor monetário ambíguo ou ilegível: {original!r} (use 1.234,56 ou 1234.56)")
    if not re.fullmatch(r"\d[\d.,]*\d|\d", t):
        raise ruim
    if "." in t and "," in t:
        dec = "," if t.rfind(",") > t.rfind(".") else "."
        inteiro, frac = t.rsplit(dec, 1)
        if dec in inteiro or not _grupos_de_milhar(inteiro, "." if dec == "," else ","):
            raise ruim
    elif "." in t or "," in t:
        sep = "." if "." in t else ","
        if t.count(sep) > 1:  # só separador de milhar: '1.234.567'
            if not _grupos_de_milhar(t, sep):
                raise ruim
            inteiro, frac = t.replace(sep, ""), ""
        else:
            inteiro, frac = t.split(sep)
            if len(frac) == 3:
                raise ruim
    else:
        inteiro, frac = t, ""
    inteiro = inteiro.replace(".", "").replace(",", "")
    if len(frac) > 2:
        if frac[2:].strip("0"):
            raise ValueError(f"valor com fração de centavo: {original!r}")
        frac = frac[:2]
    return Decimal(inteiro + "." + (frac or "0"))


def centavos(texto: str) -> int:
    """'1.234,56' | '-1.234,56' | '(1.234,56)' | '1234.56' | '1,234.56' | '1.234,56-' -> centavos (int).
    R6-4 (10/10/2026): sufixo de extrato/razão '1.234,56 D' (negativo) ou '1.234,56C' (positivo),
    na convenção BANCÁRIA (D = saída). A convenção contábil é tratada por detectar_convencao().
    R6-14: valor ambíguo ou fora de formato é RECUSADO (antes, '1,234.56' virava R$ 1,23 em silêncio)."""
    t = str(texto).strip().replace("R$", "").replace(" ", "")
    sufixo_d = bool(re.search(r"\d[Dd]$", t))
    if re.search(r"\d[CcDd]$", t):
        t = t[:-1]
    negativo = sufixo_d or t.startswith("-") or t.endswith("-") or (t.startswith("(") and t.endswith(")"))
    t = t.strip("()-")
    try:
        v = (_numero(t, str(texto)) * 100).quantize(Decimal("1"))
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


_OFX_ENTRADA = {"CREDIT", "DEP", "INT", "DIV", "DIRECTDEP"}  # R6-18: tipos que só podem ser entrada
_OFX_SAIDA = {"DEBIT", "FEE", "SRVCHG", "ATM", "POS", "CHECK", "PAYMENT", "CASH", "DIRECTDEBIT", "REPEATPMT"}


def ler_ofx(conteudo: str | bytes) -> dict:
    """Retorna {"extrato": [...], "saldo_final": int|None, "saldo_inicial": int|None}."""
    if isinstance(conteudo, bytes):
        for enc in ("utf-8", "cp1252", "latin-1"):
            try:
                conteudo = conteudo.decode(enc)
                break
            except UnicodeDecodeError:
                continue
    contas = re.findall(r"<(?:STMTRS|CCSTMTRS)>(.*?)(?:</(?:STMTRS|CCSTMTRS)>|(?=<(?:STMTRS|CCSTMTRS)>)|$)",
                        conteudo, re.S | re.I)
    if len(contas) > 1:  # R6-16: duas contas eram misturadas numa conciliação só
        ids = [(_tag(c, "ACCTID") or "?") for c in contas]
        raise ImportacaoInvalida(f"OFX com {len(contas)} contas ({', '.join(ids)}): exporte UMA conta por arquivo")
    extrato, vistos, contradiz = [], set(), 0
    for bloco in re.findall(r"<STMTTRN>(.*?)(?:</STMTTRN>|(?=<STMTTRN>)|(?=</BANKTRANLIST>))", conteudo, re.S | re.I):
        fitid = _tag(bloco, "FITID")
        if not fitid or fitid in vistos:
            raise ImportacaoInvalida(f"OFX com FITID ausente ou repetido: {fitid!r} (exportação sobreposta?)")
        vistos.add(fitid)
        desc = " ".join(x for x in (_tag(bloco, "NAME"), _tag(bloco, "MEMO"), _tag(bloco, "CHECKNUM")) if x)
        valor = centavos(_tag(bloco, "TRNAMT"))
        tipo = (_tag(bloco, "TRNTYPE") or "").upper()
        if (tipo in _OFX_ENTRADA and valor < 0) or (tipo in _OFX_SAIDA and valor > 0):
            contradiz += 1
        extrato.append({"id": f"B-{fitid}", "data": data_iso(_tag(bloco, "DTPOSTED")[:8], ("%Y%m%d",)),
                        "valor": valor, "desc": desc})
    if not extrato:
        raise ImportacaoInvalida("OFX sem lançamentos: o período exportado está vazio ou o arquivo está incompleto")
    bal = re.search(r"<LEDGERBAL>(.*?)(?:</LEDGERBAL>|<AVAILBAL>|$)", conteudo, re.S | re.I)
    saldo_final = centavos(_tag(bal.group(1), "BALAMT")) if bal and _tag(bal.group(1), "BALAMT") else None
    avisos = [f"OFX: em {contradiz} lançamento(s) o TRNTYPE contradiz o sinal do valor. Valeu o SINAL (regra da "
              "especificação OFX); confira esses itens, a exportação pode estar defeituosa."] if contradiz else []
    return {"extrato": extrato, "saldo_final": saldo_final, "saldo_inicial": None, "avisos": avisos}


# ------------------------------------------------------------------ CSV (ERP / planilha)

def ler_csv(conteudo: str, colunas: dict, prefixo: str, sep: str = ";") -> list[dict]:
    """colunas = {"id": "Num", "data": "Data", "valor": "Valor", "doc": "Documento"} (ou "desc").
    Débito/crédito em colunas separadas: {"debito": "Saída", "credito": "Entrada"}."""
    linhas = csv.DictReader(io.StringIO(conteudo), delimiter=sep)
    out, vistos = [], set()
    for i, ln in enumerate(linhas):
        ln = {k.strip().lstrip("\ufeff"): (v or "").strip() for k, v in ln.items() if k}  # R6-2: BOM do Excel
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


# ----------------------------------------------------------------- CNAB 240 (T059)
class CNABInvalido(ValueError):
    pass


def _dmy(s: str) -> str:
    s = s.strip()
    if not re.fullmatch(r"\d{8}", s) or s == "00000000":
        raise CNABInvalido(f"data inválida: {s!r}")
    iso = f"{s[4:8]}-{s[2:4]}-{s[0:2]}"
    try:
        date.fromisoformat(iso)  # 31/02 não existe: antes passava calado
    except ValueError:
        raise CNABInvalido(f"data inexistente: {s!r}")
    return iso


def _cents(s: str) -> int:
    s = s.strip() or "0"
    if not s.isdigit():
        raise CNABInvalido(f"valor inválido: {s!r}")
    return int(s)  # 9(16)V9(02): os dois últimos dígitos são centavos


def ler_cnab240(conteudo: str | bytes, prefixo: str = "B") -> dict:
    """Extrato CNAB 240 (FEBRABAN, Segmento E; posições conferidas no manual da CAIXA, layouts 030/040/089:
    data 143–150, valor 151–168, D/C 169, categoria 170–172, código 173–176, histórico 177–201,
    documento 202–208, complemento 209–240; saldo inicial no header de lote (registro 1, 143–169) e
    saldo final + somatórios no trailer de lote (registro 5, 143–169, 177–194, 195–212)).
    FALHA FECHADA: linha com mais de 240 posições, data/valor ilegível, ou mais de um lote."""
    if isinstance(conteudo, bytes):
        conteudo = conteudo.decode("latin-1")
    lotes: list[dict] = []
    atual: dict | None = None
    for n, bruta in enumerate(conteudo.splitlines(), 1):
        ln = bruta.rstrip("\r\n")
        if not ln.strip():
            continue
        if len(ln) > 240:
            raise CNABInvalido(f"linha {n} com {len(ln)} posições (máximo 240)")
        ln = ln.ljust(240)  # alguns sistemas cortam os brancos finais
        tipo = ln[7]
        if tipo == "1":
            sinal = -1 if ln[168] == "D" else 1
            atual = {"extrato": [], "saldo_inicial": sinal * _cents(ln[150:168]), "data_saldo_inicial": _dmy(ln[142:150]),
                     "saldo_final": None, "soma_debitos_trailer": None, "soma_creditos_trailer": None}
            lotes.append(atual)
        elif tipo == "3" and ln[13] == "E":
            if atual is None:
                raise CNABInvalido(f"linha {n}: detalhe antes do header de lote")
            dc = ln[168]
            if dc not in "DC":
                raise CNABInvalido(f"linha {n}: tipo de lançamento {dc!r} (esperado D ou C)")
            v = _cents(ln[150:168])
            desc = " ".join(x for x in (ln[176:201].strip(), ln[201:208].strip(), ln[208:240].strip()) if x)
            atual["extrato"].append({"id": f"{prefixo}{len(atual['extrato']) + 1:05d}", "data": _dmy(ln[142:150]),
                                     "valor": -v if dc == "D" else v, "desc": desc,
                                     "categoria": ln[169:172].strip(), "codigo_historico": ln[172:176].strip()})
        elif tipo == "5":
            if atual is None:
                raise CNABInvalido(f"linha {n}: trailer de lote sem header")
            sinal = -1 if ln[168] == "D" else 1
            atual["saldo_final"] = sinal * _cents(ln[150:168])
            atual["soma_debitos_trailer"] = _cents(ln[176:194])
            atual["soma_creditos_trailer"] = _cents(ln[194:212])
    if len(lotes) != 1:
        raise CNABInvalido(f"esperado 1 lote (uma conta); encontrados {len(lotes)} — separe por conta")
    lote = lotes[0]
    deb = sum(-x["valor"] for x in lote["extrato"] if x["valor"] < 0)
    cred = sum(x["valor"] for x in lote["extrato"] if x["valor"] > 0)
    lote["conferencia"] = {
        "saldo": checar_saldo(lote["extrato"], lote["saldo_inicial"], lote["saldo_final"])[1],
        "somatorios_trailer": "CONFERE" if (lote["soma_debitos_trailer"], lote["soma_creditos_trailer"]) == (deb, cred)
        else f"DIVERGE: trailer D={lote['soma_debitos_trailer']} C={lote['soma_creditos_trailer']}, lido D={deb} C={cred}"}
    return lote


# ----------------------------------------------------------------- Open Finance Brasil (T059)
_BRT = timezone(timedelta(hours=-3))  # horário de Brasília; sem horário de verão desde 2019


def ler_open_finance(resposta: dict | list, prefixo: str = "B") -> dict:
    """Transações de conta (Open Finance Brasil, API de contas v2: transactionId, creditDebitType,
    transactionAmount{amount 'NNN.NN[NN]', currency}, transactionDateTime em UTC).
    - Data convertida para o horário de Brasília (um PIX às 01h UTC do dia 30 é do dia 29).
    - Só TRANSACAO_EFETIVADA entra; lançamento futuro ou em processamento fica de fora (contado).
    - Valor com frações de centavo diferentes de zero, ou moeda diferente de BRL -> item "revisar"
      (falha fechada: o oráculo proíbe casar item "revisar")."""
    itens = resposta.get("data", []) if isinstance(resposta, dict) else resposta
    extrato, fora = [], 0
    for t in itens:
        if t.get("completedAuthorisedPaymentType") != "TRANSACAO_EFETIVADA":
            fora += 1
            continue
        revisar = False
        try:
            centav = Decimal(str(t["transactionAmount"]["amount"])) * 100
        except (InvalidOperation, KeyError, TypeError):
            raise ValueError(f"transação {t.get('transactionId')!r} sem valor legível")
        if centav != centav.to_integral_value() or t["transactionAmount"].get("currency") != "BRL":
            revisar = True
        v = int(centav.to_integral_value())
        if t.get("creditDebitType") == "DEBITO":
            v = -v
        elif t.get("creditDebitType") != "CREDITO":
            revisar = True
        dt = datetime.fromisoformat(str(t["transactionDateTime"]).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            revisar = True  # sem fuso: não dá para saber o dia em Brasília com certeza
            data = dt.date().isoformat()
        else:
            data = dt.astimezone(_BRT).date().isoformat()
        tid = re.sub(r"[^A-Za-z0-9\-]", "", str(t.get("transactionId", "")))[:40]
        item = {"id": f"{prefixo}{tid}", "data": data, "valor": v,
                "desc": f"{t.get('type', '')} {t.get('transactionName', '')}".strip()}
        if t.get("partieCnpjCpf"):
            item["contraparte"] = str(t["partieCnpjCpf"])
        if revisar:
            item["revisar"] = True
        extrato.append(item)
    return {"extrato": extrato, "fora_por_nao_efetivada": fora, "saldo_inicial": None, "saldo_final": None}


# ------------------------------------------------------------------ planilha real (T065, rodada 6)

class ImportacaoInvalida(ValueError):
    """Falha fechada com o NÚMERO DA LINHA: o humano sabe exatamente o que corrigir."""


ALIASES = {
    "data": ("data", "dt", "data lancamento", "data lanc", "data mov", "data movimento", "data movimentacao",
             "dt lanc", "dt lancamento", "data do lancamento", "data operacao"),
    "valor": ("valor", "valor r$", "valor (r$)", "montante", "quantia", "valor lancamento", "vlr", "vl"),
    "debito": ("debito", "debitos", "saida", "saidas", "deb", "valor debito", "vlr debito"),
    "credito": ("credito", "creditos", "entrada", "entradas", "cred", "valor credito", "vlr credito"),
    "desc": ("historico", "descricao", "complemento", "memo", "historico complementar"),
    "doc": ("documento", "doc", "n doc", "no doc", "num doc", "numero documento", "n documento", "nf",
            "nota", "nota fiscal", "num documento"),
    "id": ("id", "n", "no", "num", "numero", "sequencial", "seq", "codigo", "cod", "n lanc", "lancamento",
           "n lancamento", "numero lancamento", "lanc"),
}
_RODAPE = re.compile(r"^(total|totais|subtotal|sub total|saldo|soma|transporte|a transportar|de transporte)\b")


def _norm(t: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9$() ]+", " ", t)).strip()


def decodificar(conteudo: str | bytes) -> tuple[str, str]:
    """UTF-16 (Excel "Texto Unicode", R6-11), utf-8 (com ou sem BOM) e, se falhar, cp1252 (Excel
    brasileiro). Devolve (texto, encoding). UTF-16 sem BOM é reconhecido pelos zeros intercalados."""
    if isinstance(conteudo, str):
        return conteudo.lstrip("\ufeff"), "texto"
    if conteudo[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return conteudo.decode("utf-16").lstrip("\ufeff"), "utf-16"
    amostra = conteudo[:400]
    if len(amostra) >= 4 and b"\x00" in amostra:
        pares, impares = amostra[0::2].count(0), amostra[1::2].count(0)
        if max(pares, impares) > len(amostra) // 4 and min(pares, impares) == 0:
            enc = "utf-16-le" if impares else "utf-16-be"
            try:
                return conteudo.decode(enc), enc
            except UnicodeDecodeError:
                pass
    if b"\x00" in conteudo:
        raise ImportacaoInvalida("arquivo binário (bytes nulos): exporte como CSV ou texto")
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return conteudo.decode(enc), enc
        except UnicodeDecodeError:
            continue
    raise ImportacaoInvalida("arquivo não é texto em UTF-8 nem em CP-1252")


def _mapear(cabecalho: list[str], colunas: dict | None) -> dict | None:
    nomes = [_norm(c) for c in cabecalho]
    if colunas:  # mapeamento explícito: nomes do arquivo, comparados sem acento/caixa
        m = {}
        for chave, nome in colunas.items():
            if _norm(nome) not in nomes:
                return None
            m[chave] = nomes.index(_norm(nome))
        return m
    m = {}
    for chave, alias in ALIASES.items():
        for i, n in enumerate(nomes):
            if i not in m.values() and (n in alias or n.replace("$", "").strip() in alias):
                m[chave] = i
                break
    if "data" in m and ("valor" in m or ("debito" in m and "credito" in m)):
        return m
    return None


def _separador(linhas: list[str]) -> str:
    candidatos = [";", "\t", ",", "|"]
    contagem = {c: sum(ln.count(c) for ln in linhas[:30]) for c in candidatos}
    return max(candidatos, key=lambda c: (contagem[c], c == ";"))


def ler_planilha(conteudo: str | bytes, prefixo: str, colunas: dict | None = None, sep: str | None = None) -> dict:
    """Lê extrato ou razão exportado de banco/ERP como CSV/TXT. Robusto ao mundo real:
    BOM do Excel, CP-1252, título antes da tabela, separador ; , TAB |, valor com sufixo D/C,
    débito e crédito em colunas separadas, linhas de TOTAL/SALDO/TRANSPORTE no meio ou no fim.
    Linhas de saldo alimentam a prova de saldo; as demais de rodapé ficam listadas em 'ignoradas'.
    Qualquer outra linha não reconhecida = ImportacaoInvalida com o número da linha (falha fechada).
    Os valores saem na convenção BANCÁRIA (entrada positiva); ver detectar_convencao()."""
    texto, enc = decodificar(conteudo)
    linhas = texto.splitlines()
    sep = sep or _separador(linhas)
    tabela = list(csv.reader(linhas, delimiter=sep))
    inicio, mapa = None, None
    for i, celulas in enumerate(tabela[:50]):
        mapa = _mapear(celulas, colunas)
        if mapa:
            inicio = i
            break
    if inicio is None:
        raise ImportacaoInvalida("cabeçalho não encontrado nas 50 primeiras linhas: preciso de uma coluna de DATA "
                                 "e de VALOR (ou DÉBITO e CRÉDITO); informe o mapeamento de colunas")
    itens, ignoradas, vistos = [], [], set()
    saldo_ini = saldo_fim = None

    def cel(cs, chave):
        j = mapa.get(chave)
        return cs[j].strip() if j is not None and j < len(cs) else ""

    def valor_de(cs):
        if "valor" in mapa:
            return centavos(cel(cs, "valor"))
        cr, db = cel(cs, "credito"), cel(cs, "debito")
        if cr and db and centavos(cr) and centavos(db):
            raise ValueError("linha com débito E crédito preenchidos")
        return (abs(centavos(cr)) if cr else 0) - (abs(centavos(db)) if db else 0)

    for n, cs in enumerate(tabela[inicio + 1:], start=inicio + 2):
        if not any(c.strip() for c in cs):
            continue
        primeira = _norm(next(c for c in cs if c.strip()))
        if _RODAPE.match(primeira):
            ignoradas.append({"linha": n, "texto": sep.join(cs)[:200]})
            num = [c for c in cs if re.search(r"\d", c) and not re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", c)]
            if primeira.startswith("saldo") and num:
                try:
                    v = centavos(num[-1])
                    if any(k in primeira for k in ("anterior", "inicial", "abertura")):
                        saldo_ini = v
                    elif any(k in primeira for k in ("final", "atual", "fechamento")):
                        saldo_fim = v
                except ValueError:
                    pass
            continue
        try:
            dt = data_iso(cel(cs, "data"))
            v = valor_de(cs)
        except ValueError as e:
            raise ImportacaoInvalida(f"linha {n} não reconhecida ({e}): {sep.join(cs)[:120]!r}") from e
        ident = cel(cs, "id") or f"L{n}"
        if ident in vistos:
            raise ImportacaoInvalida(f"linha {n}: identificador repetido {ident!r}")
        vistos.add(ident)
        item = {"id": f"{prefixo}-{ident}", "data": dt, "valor": v}
        if "desc" in mapa:
            item["desc"] = cel(cs, "desc")
        if "doc" in mapa:
            item["doc"] = cel(cs, "doc")
        itens.append(item)
    if not itens:
        raise ImportacaoInvalida("nenhum lançamento encontrado depois do cabeçalho")
    return {"itens": itens, "ignoradas": ignoradas, "saldo_inicial": saldo_ini, "saldo_final": saldo_fim,
            "mapa": {k: tabela[inicio][j].strip() for k, j in mapa.items()}, "separador": sep, "encoding": enc,
            "linha_cabecalho": inicio + 1}


def detectar_convencao(extrato: list[dict], razao: list[dict], janela: int = 5) -> dict:
    """R6-1 (10/10/2026): o razão da conta BANCO, do ponto de vista contábil, registra a entrada
    como DÉBITO — o inverso do extrato. Lido sem cuidado, todo sinal sai trocado e nada casa, EM
    SILÊNCIO. Aqui a convenção é decidida pelos DADOS: conta quantos lançamentos do razão têm par
    de mesmo valor e data próxima no extrato com o sinal como está e com o sinal invertido.
    Regra pré-registrada: decide só se o vencedor tiver >= 2x os casamentos do perdedor E
    >= max(3, 20% do menor arquivo); senão 'indeterminado' (o humano precisa dizer)."""
    from collections import defaultdict
    idx = defaultdict(list)
    for b in extrato:
        idx[b["valor"]].append(date.fromisoformat(b["data"]))

    def casam(sinal):
        k = 0
        for r in razao:
            d = date.fromisoformat(r["data"])
            if any(abs((d - x).days) <= janela for x in idx.get(sinal * r["valor"], ())):
                k += 1
        return k
    direto, invertido = casam(1), casam(-1)
    minimo = max(3, int(0.2 * min(len(extrato), len(razao))))
    if direto >= 2 * invertido and direto >= minimo:
        conv = "bancaria"
    elif invertido >= 2 * direto and invertido >= minimo:
        conv = "contabil"
    else:
        conv = "indeterminado"
    return {"convencao": conv, "casam_direto": direto, "casam_invertido": invertido, "minimo": minimo}


def inverter(itens: list[dict]) -> list[dict]:
    return [dict(x, valor=-x["valor"]) for x in itens]
