"""Privacidade: anonimizador brasileiro (T044) + cofre de titulares com eliminação (T045).

Ideia central: cada titular (um CPF, um CNPJ, um nome...) ganha uma CHAVE ALEATÓRIA própria no
COFRE, que fica só na máquina do escritório. O pseudônimo é HMAC(chave_do_titular, tipo).
  - Mesmo titular -> mesmo pseudônimo (o extrato e o razão continuam cruzando).
  - Eliminar o titular (LGPD art. 18) = apagar a chave dele. Os pseudônimos que já estão no
    ANAIS ou em arquivos exportados ficam IMPOSSÍVEIS de religar — sem reescrever o ANAIS.
Valores, datas e números de documento (NF...) são preservados: sem eles não há conciliação.

Termos honestos (LGPD art. 13, §4º): enquanto o cofre existir, isto é PSEUDONIMIZAÇÃO, não
anonimização — o dado continua pessoal para quem controla o cofre. Backups do cofre também
precisam ser destruídos para a eliminação valer.
Falha fechada: a exportação exige que um humano confirme a lista de palavras MANTIDAS.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import unicodedata
from collections import Counter
from typing import Any

from .ledger import canonico

# ----------------------------------------------------------------- dígitos verificadores


def _dv_mod11(valores: list[int], pesos: list[int]) -> int:
    r = sum(v * p for v, p in zip(valores, pesos)) % 11
    return 0 if r < 2 else 11 - r


def cpf_valido(s: str) -> bool:
    d = re.sub(r"\D", "", s)
    if len(d) != 11 or len(set(d)) == 1:
        return False
    n = [int(c) for c in d]
    return n[9] == _dv_mod11(n[:9], list(range(10, 1, -1))) and n[10] == _dv_mod11(n[:10], list(range(11, 1, -1)))


def cnpj_valido(s: str) -> bool:
    """CNPJ numérico e ALFANUMÉRICO (emitido desde jul/2026): valor = ASCII - 48, módulo 11."""
    c = re.sub(r"[.\-/\s]", "", s).upper()
    if not re.fullmatch(r"[0-9A-Z]{12}[0-9]{2}", c) or len(set(c)) == 1:
        return False
    v = [ord(x) - 48 for x in c]
    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    return v[12] == _dv_mod11(v[:12], p1) and v[13] == _dv_mod11(v[:13], [6] + p1)


# ----------------------------------------------------------------- cofre de titulares (T045)


class Cofre:
    """Mapa titular -> chave aleatória. Fica SÓ na máquina do escritório; nunca é exportado."""

    def __init__(self, caminho: str, chave_mestra: bytes, guardar_original: bool = False):
        if not chave_mestra or len(chave_mestra) < 16:
            raise ValueError("chave_mestra do cofre precisa de pelo menos 16 bytes")
        self.caminho, self._km, self.guardar_original = caminho, chave_mestra, guardar_original
        self._d: dict[str, dict] = {}
        if os.path.exists(caminho):
            with open(caminho, encoding="utf-8") as f:
                self._d = json.load(f)

    def _indice(self, tipo: str, valor: str) -> str:
        return hmac.new(self._km, f"{tipo}:{valor}".encode("utf-8"), hashlib.sha256).hexdigest()

    def _salvar(self) -> None:
        tmp = self.caminho + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._d, f, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.caminho)

    def pseudonimo(self, tipo: str, valor: str, variante: int = 0) -> str:
        i = self._indice(tipo, valor)
        if i not in self._d:
            self._d[i] = {"k": secrets.token_hex(32), "tipo": tipo}
            if self.guardar_original:
                self._d[i]["original"] = valor
            self._salvar()
        k = bytes.fromhex(self._d[i]["k"])
        # SÓ LETRAS (achado pelo CI): base32 tinha dígitos e às vezes formava 'PED7'/'NF2…', que o oráculo
        # lia como documento citado. Sem dígitos, padrões do tipo NF\d+ não podem casar.
        dig = hmac.new(k, f"{tipo}:{variante}".encode(), hashlib.sha256).digest()
        return f"{tipo}_" + "".join(chr(65 + b % 26) for b in dig[:12])

    def eliminar(self, tipo: str, valor: str) -> bool:
        """LGPD art. 18, VI: destrói a chave do titular. Pseudônimos antigos ficam órfãos para sempre."""
        i = self._indice(tipo, _normalizar(tipo, valor))
        if i in self._d:
            del self._d[i]
            self._salvar()
            return True
        return False

    def __len__(self) -> int:
        return len(self._d)


# ----------------------------------------------------------------- detecção (T044)

_RX = [  # ordem importa: o mais específico primeiro
    ("EMAIL", re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")),
    ("CHAVE", re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")),
    ("CNPJ", re.compile(r"\b[0-9A-Z]{2}\.?[0-9A-Z]{3}\.?[0-9A-Z]{3}/?[0-9A-Z]{4}-?\d{2}\b")),
    ("CPF", re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")),
    ("TEL", re.compile(r"(?:\+?55\s?)?\(?\b\d{2}\)?\s?9?\s?\d{4}[-\s]?\d{4}\b")),
]
_VALIDADOR = {"CNPJ": cnpj_valido, "CPF": cpf_valido}

VOCABULARIO = set("""
PIX TED DOC TEF RECEBIDO RECEBIDA RECEB ENVIADO ENVIADA ENV PAGAMENTO PAGTO PGTO PAG TRANSF TRANSFERENCIA
DEPOSITO DEP SAQUE TARIFA TAR JUROS IOF BOLETO TIT TITULO LIQUIDACAO COBRANCA CRED CREDITO DEB DEBITO
AUTOMATICO AUT ESTORNO DEVOLUCAO CHEQUE CH COMPENSADO APLICACAO RESGATE RENDIMENTO CDB POUPANCA FOLHA
SALARIO FORNECEDOR CLIENTE NF NFE NFS NFSE NOTA FISCAL FATURA DUPLICATA CONVENIO SISPAG LANCAMENTO
ENCARGOS MENSALIDADE ALUGUEL ENERGIA AGUA TELEFONE INTERNET SEGURO IMPOSTO DARF GPS DAS FGTS INSS ISS
ICMS IRRF IRPJ CSLL PIS COFINS SIMPLES NACIONAL LTDA ME EPP SA EIRELI BANCO AG AGENCIA CC CONTA CORRENTE
REF REFERENTE DE DA DO DAS DOS E A O EM PARA RECEBIMENTO VENDA COMPRA CARTAO VISA MASTER MASTERCARD ELO
PARCELA PARC LOTE PEDIDO PED BOL VENC VENCIMENTO MES ANO PRESTACAO SERVICO SERVICOS MANUTENCAO TAXA
QRCODE QR CODE ENTRE CONTAS MESMA TITULARIDADE SALDO ANTERIOR DIA TOTAL VALOR AJUSTE ACERTO
CPF CNPJ RG CHAVE EMAIL TEL CEL FAVORECIDO PAGADOR ORIGEM DESTINO
""".split())

_CONECTORES = {"DE", "DA", "DO", "DAS", "DOS", "E"}


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _normalizar(tipo: str, valor: str) -> str:
    if tipo in ("CPF", "CNPJ", "TEL", "NUM"):
        return re.sub(r"[^0-9A-Z]", "", valor.upper())
    if tipo in ("EMAIL", "CHAVE"):
        return valor.lower()
    return re.sub(r"\s+", " ", _sem_acento(valor).upper()).strip()


class Anonimizador:
    def __init__(self, cofre: Cofre, padroes_documento: list[str] | None = None,
                 vocabulario_extra: set[str] | None = None):
        self.cofre = cofre
        self.doc = [re.compile(p) for p in (padroes_documento or [r"NF\d+"])]
        self.vocab = VOCABULARIO | {_sem_acento(x).upper() for x in (vocabulario_extra or set())}
        self.cont: Counter = Counter()
        self.mantidos: set[str] = set()

    def _p(self, tipo: str, valor: str) -> str:
        self.cont[tipo] += 1
        for variante in range(16):  # padrão da entidade pode ser só de letras: nunca deixar parecer documento
            ps = self.cofre.pseudonimo(tipo, _normalizar(tipo, valor), variante)
            if not any(rx.search(ps) for rx in self.doc):
                return ps
        raise ValueError("pseudônimo colide com padrão de documento em todas as variantes (falha fechada)")

    def texto(self, s: str) -> str:
        if not isinstance(s, str) or not s:
            return s
        protegidos: dict[str, str] = {}

        def guardar(v: str) -> str:
            marca = f"\x00{len(protegidos)}\x00"
            protegidos[marca] = v
            return marca
        for rx in self.doc:  # documentos (NF...) ficam intactos: são a ponte da conciliação
            s = rx.sub(lambda m: guardar(m.group(0)), s)
        # datas e valores em reais também ficam (não identificam ninguém e servem ao humano)
        s = re.sub(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b", lambda m: guardar(m.group(0)), s)
        s = re.sub(r"(?:R\$\s?)?\b\d{1,3}(?:\.\d{3})*,\d{2}\b", lambda m: guardar(m.group(0)), s)
        # número depois de AG/CC/CONTA identifica a pessoa junto com o banco, qualquer que seja o tamanho
        s = re.sub(r"(?i)\b(AG(?:ENCIA|ÊNCIA)?|C/?C|CONTA(?:\s+CORRENTE)?)(\s*[:.]?\s*)(\d[\d\-]*)",
                   lambda m: m.group(1) + m.group(2) + guardar(self._p("NUM", m.group(3))), s)
        for tipo, rx in _RX:
            def troca(m, tipo=tipo):
                v = m.group(0)
                if tipo in _VALIDADOR and not _VALIDADOR[tipo](v):
                    return v  # não é CPF/CNPJ válido: segue para as regras seguintes
                return guardar(self._p(tipo, v))
            s = rx.sub(troca, s)
        # sequências longas de dígitos que sobraram (conta, CPF com DV inválido...) -> NUM
        s = re.sub(r"\d[\d.\-/]{4,}\d", lambda m: guardar(self._p("NUM", m.group(0)))
                   if len(re.sub(r"\D", "", m.group(0))) >= 6 else m.group(0), s)
        # palavras: fora do vocabulário = nome; nomes compostos viram UM pseudônimo
        s = re.sub(r"(\x00\d+\x00)", r" \1 ", s)  # marca protegida vira token próprio
        saida: list[str] = []
        nome: list[str] = []

        def fechar() -> None:
            cauda = []
            while nome and _sem_acento(nome[-1]).upper().strip(".,;:") in _CONECTORES:
                cauda.insert(0, nome.pop())
            if nome:
                saida.append(self._p("NOME", " ".join(nome)))
            saida.extend(cauda)
            nome.clear()
        for t in s.split():
            if t in protegidos:
                fechar()
                saida.append(t)
                continue
            limpo = _sem_acento(t).upper().strip(".,;:()[]-_/*#")
            if not limpo:
                fechar()
                saida.append(t)
                continue
            eh_palavra = bool(re.fullmatch(r"[A-Z][A-Z'\-]*", limpo))
            if eh_palavra and limpo in _CONECTORES and nome:
                nome.append(t)
            elif eh_palavra and limpo not in self.vocab:
                nome.append(t)
            elif re.search(r"[A-Z]", limpo) and re.search(r"\d", limpo):
                fechar()
                saida.append(self._p("COD", t))  # código misto desconhecido: pode identificar alguém
            else:
                fechar()
                saida.append(t)
                if eh_palavra:
                    self.mantidos.add(limpo)
        fechar()
        s = " ".join(saida)
        for marca, v in protegidos.items():
            s = s.replace(marca, v)
        return s

    def registros(self, regs: list[dict], campos: tuple[str, ...] = ("desc", "historico", "nome", "fornecedor",
                                                                       "cliente", "favorecido")) -> list[dict]:
        out = []
        for r in regs:
            r2 = dict(r)
            for c in campos:
                if c in r2:
                    r2[c] = self.texto(r2[c])
            out.append(r2)
        return out

    def relatorio(self) -> dict:
        mantidos = sorted(self.mantidos)
        return {"substituicoes": dict(sorted(self.cont.items())), "palavras_mantidas": mantidos,
                "confirmacao": hashlib.sha256(canonico(mantidos)).hexdigest()[:16]}


def exportar(dados: Any, relatorio: dict, confirmacao: str | None) -> Any:
    """Falha fechada: só exporta se um humano leu a lista de palavras MANTIDAS e confirmou o código."""
    if confirmacao != relatorio["confirmacao"]:
        raise PermissionError("revise 'palavras_mantidas' (nenhuma pode ser nome) e confirme com o código "
                              f"{relatorio['confirmacao']}")
    return dados
