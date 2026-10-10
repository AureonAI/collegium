"""LEX — núcleo determinístico que governa toda ação de todo agente.

Ele não é um sandbox: só governa o que passa por ele. O isolamento do sistema operacional
(container sem rede, egress por lista) é PRÉ-REQUISITO de implantação — ver ADVERSARIAL_LOG A1.
Fronteira de confiança: a API desta classe é chamada pelo ORQUESTRADOR (código confiável).
Agentes recebem apenas um `Mandato` (identidade fixada); humanos provam identidade por
assinatura com a chave do Patronus, que nunca entra no container dos agentes.

As quatro leis, derivadas dos quatro padrões que a OpenAI documentou no incidente de 2026
(reward hacking, persistência em tarefa impossível, comunicação não autorizada,
adoção de objetivos entre agentes):

  L1 Negação por padrão: capacidade, canal ou host fora do REGIMENTO => negado e registrado.
  L2 Dever de declarar: toda ação de trabalho pertence a uma tarefa com orçamento; esgotado,
     a ÚNICA ação válida é declarar BLOQUEADO/IMPOSSIVEL com evidência.
  L3 Separação de poderes: quem produz não verifica; com oráculo registrado, o LEX o executa;
     sem oráculo, verificador de mesma LINHAGEM de modelo é recusado.
  L4 Autonomia conquistada: liberação depende do nível medido (autonomia.py); irreversível
     acima da alçada sempre vai ao humano.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from .autonomia import Historico, nivel
from .ledger import Ledger, canonico

# Oráculo registrado por classe: (entrada, entrega) -> (aceito, falhas). O LEX o executa sozinho.
Oraculo = Callable[[Any, Any], "tuple[bool, list[str]]"]

TIPOS = {"ferramenta", "mensagem", "rede", "declaracao"}
FAMILIAS_INDEPENDENTES = {"deterministico", "humano"}
STATUS_DECLARACAO = {"BLOQUEADO", "IMPOSSIVEL", "CONCLUIDO"}
TIPOS_MENSAGEM = {"pedido", "resposta", "alerta"}
# T047: argumentos que DIRECIONAM uma ação (para onde vai dinheiro, dado ou mensagem). Só valem
# valores da lista confiável do REGIMENTO — um texto injetado no extrato nunca escolhe o destino.
CHAVES_DESTINO = {"destino", "para", "conta", "chave_pix", "email", "url", "host", "favorecido", "telefone"}
_PALAVRAS_DESTINO = {"destino", "para", "conta", "pix", "email", "url", "host", "favorecido", "telefone",
                     "iban", "beneficiario", "recebedor", "endereco", "webhook"}


class RegimentoInvalido(ValueError):
    pass


def _h(obj: Any) -> str:
    return hashlib.sha256(canonico(obj)).hexdigest()


def assinar_humano(chave: bytes, *campos: Any) -> str:
    """Assinatura que só quem tem a chave do Patronus produz (HMAC-SHA256).
    Limite declarado: chave simétrica; o LEX também a conhece. Assinatura assimétrica
    (Ed25519) exige dependência externa — prevista para quando houver juiz externo."""
    return hmac.new(chave, canonico(list(campos)), hashlib.sha256).hexdigest()


def _canon(obj: Any) -> Any:
    """Forma canônica para comparar entregas (listas como conjuntos ordenados)."""
    if isinstance(obj, dict):
        return {str(k): _canon(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, (list, tuple)):
        return sorted((_canon(v) for v in obj), key=lambda x: json.dumps(x, sort_keys=True, default=str))
    return obj


def assinar_humano_ed25519(privada: bytes, *campos: Any) -> str:
    """T042: assinatura assimétrica do humano. O núcleo só guarda a chave PÚBLICA."""
    from . import ed25519
    return ed25519.assinar(privada, canonico(list(campos))).hex()


def _ed_ok(publica_hex: str, assinatura: Any, *campos: Any) -> bool:
    from . import ed25519
    try:
        return ed25519.verificar(bytes.fromhex(publica_hex), canonico(list(campos)), bytes.fromhex(assinatura))
    except (TypeError, ValueError):
        return False


def _campos_destino(obj: Any, _prof: int = 0):
    """T047: acha argumentos de destino em QUALQUER nível e com qualquer grafia da chave
    ('Conta', 'conta_destino', {'dados': {'conta': ...}}). Grafia diferente da lista = negado."""
    if _prof > 8:
        yield ("profundidade", obj)  # aninhamento absurdo é tratado como destino desconhecido
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            partes = set(re.split(r"[^a-z0-9]+", re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(k)).lower()))
            if partes & _PALAVRAS_DESTINO or str(k).lower() in CHAVES_DESTINO:
                yield (str(k), v)
            yield from _campos_destino(v, _prof + 1)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _campos_destino(v, _prof + 1)


def linhagem(declarada: str | list[str]) -> frozenset[str]:
    """Família de modelo como CONJUNTO de linhagens (ex.: um destilado ['qwen','deepseek'])."""
    itens = [declarada] if isinstance(declarada, str) else list(declarada)
    return frozenset(x.strip().lower() for x in itens if x and x.strip())


def carregar_regimento(fonte: str | dict) -> dict:
    if isinstance(fonte, str):
        with open(fonte, encoding="utf-8") as f:
            reg = json.load(f)
    else:
        reg = fonte
    for chave in ("versao", "papeis", "agentes", "classes_tarefa", "autonomia"):
        if chave not in reg:
            raise RegimentoInvalido(f"REGIMENTO sem a seção obrigatória '{chave}'")
    for ag, d in reg["agentes"].items():
        if d.get("papel") not in reg["papeis"]:
            raise RegimentoInvalido(f"agente {ag} com papel inexistente {d.get('papel')}")
        if not linhagem(d.get("familia_modelo") or ""):
            raise RegimentoInvalido(f"agente {ag} sem familia_modelo (exigido pela lei L3)")
    for cl, d in reg["classes_tarefa"].items():
        if int(d.get("orcamento_passos", 0)) <= 0:
            raise RegimentoInvalido(f"classe {cl} sem orcamento_passos positivo (exigido pela lei L2)")
    # T042: chaves públicas (Ed25519, 32 bytes em hex) e quórum do Patronus
    def _chave_ok(h):
        try:
            return isinstance(h, str) and len(bytes.fromhex(h)) == 32
        except ValueError:
            return False
    for ag, d in reg["agentes"].items():
        if "chave_publica" in d and not _chave_ok(d["chave_publica"]):
            raise RegimentoInvalido(f"agente {ag}: chave_publica deve ser Ed25519 (64 hex)")
    pat = reg.get("patronus")
    if pat is not None:
        chaves, rev = pat.get("chaves", {}), set(pat.get("revogadas", []))
        if not chaves or not all(_chave_ok(v) for v in chaves.values()):
            raise RegimentoInvalido("patronus.chaves: dicionário nome -> chave pública Ed25519")
        if len(set(chaves.values())) != len(chaves):  # uma pessoa não conta duas vezes no quórum
            raise RegimentoInvalido("patronus.chaves: a mesma chave pública aparece sob dois nomes")
        if not 1 <= int(pat.get("quorum", 0)) <= len(chaves):
            raise RegimentoInvalido("patronus.quorum deve estar entre 1 e o número de chaves")
        if rev & set(chaves.values()) or any(d.get("chave_publica") in rev for d in reg["agentes"].values()):
            raise RegimentoInvalido("chave revogada não pode voltar ao REGIMENTO")
    # T048: impressão digital do modelo; o mesmo modelo não pode ter duas linhagens
    familia_por_digest: dict[str, frozenset] = {}
    for ag, d in reg["agentes"].items():
        if "modelo" in d:
            dg = (d["modelo"] or {}).get("digest", "") if isinstance(d["modelo"], dict) else ""
            if not (isinstance(dg, str) and dg.startswith("sha256:") and len(dg) == 71
                    and all(c in "0123456789abcdef" for c in dg[7:])):
                raise RegimentoInvalido(f"agente {ag}: modelo.digest deve ser 'sha256:' + 64 hex minúsculos")
            fam = linhagem(d.get("familia_modelo") or "")
            if familia_por_digest.setdefault(dg, fam) != fam:
                raise RegimentoInvalido(f"o modelo {dg[:19]}… aparece com duas linhagens diferentes (burla da L3)")
    for cap, nomes in (reg.get("argumentos_livres") or {}).items():
        if not isinstance(nomes, list) or set(nomes) & set((reg.get("destinos") or {}).get(cap, {})):
            raise RegimentoInvalido(f"argumentos_livres.{cap}: lista, sem repetir argumento de destino")
    # T047: destinos confiáveis por capacidade
    for cap, regras in (reg.get("destinos") or {}).items():
        if not isinstance(regras, dict) or not all(isinstance(v, list) for v in regras.values()):
            raise RegimentoInvalido(f"destinos.{cap}: dicionário argumento -> lista de valores confiáveis")
    niveis = [r["nivel"] for r in reg["autonomia"]["niveis"]]
    if sorted(niveis) != list(range(1, len(niveis) + 1)):
        raise RegimentoInvalido("níveis de autonomia devem ser 1..k sem lacunas")
    return reg


@dataclass(frozen=True)
class Acao:
    agente: str
    tipo: str            # ferramenta | mensagem | rede | declaracao
    alvo: str            # capacidade | canal | host | status da declaração
    tarefa: str | None = None
    payload: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Decisao:
    permitido: bool
    codigo: str
    motivo: str


@dataclass
class _Tarefa:
    id: str
    classe: str
    produtor: str
    passos: int = 0
    estado: str = "ABERTA"  # ABERTA | DECLARADA | SUBMETIDA | ACEITA | REJEITADA | LIBERADA | AGUARDA_HUMANO
    entrega_hash: str | None = None
    irreversivel: bool = False
    valor: float = 0.0
    declaracao: dict | None = None
    entrada: Any = None
    entrada_hash: str | None = None
    plano: tuple | None = None  # T047: capacidades fixadas na abertura, antes de ler dado externo
    consumo: dict = field(default_factory=dict)  # T056: tokens, segundos, custo_centavos
    esgotada: bool = False
    aprovacoes: set = field(default_factory=set)  # T057: humanos que já aprovaram (quatro olhos)


class Mandato:
    """O que um AGENTE recebe: só ações em nome de si mesmo. Não verifica, não aprova,
    não reabilita, não abre tarefa. Identidade fixada na criação (ataque R2)."""

    def __init__(self, lex: "Lex", agente: str):
        self._lex, self.agente = lex, agente

    def agir(self, tipo: str, alvo: str, tarefa: str | None = None, /, **payload) -> Decisao:
        return self._lex.autorizar(Acao(self.agente, tipo, alvo, tarefa, payload))

    def declarar(self, tarefa: str, status: str, evidencia: str = "") -> Decisao:
        return self._lex.autorizar(Acao(self.agente, "declaracao", status, tarefa, {"evidencia": evidencia}))

    def submeter(self, tarefa: str, entrega: Any) -> Decisao:
        return self._lex.submeter(tarefa, self.agente, entrega)


class Lex:
    def __init__(self, regimento: dict, ledger: Ledger, oraculos: dict[str, Oraculo] | None = None,
                 chave_patronus: bytes | None = None, assinatura_regimento: str | None = None):
        self.r = carregar_regimento(regimento)
        self.anais = ledger
        self.oraculos = dict(oraculos or {})
        self._chave_patronus = chave_patronus
        self.hash_regimento = _h(self.r)
        self.tarefas: dict[str, _Tarefa] = {}
        self.quarentena: set[str] = set()
        self.admitidos: set[str] = set()
        self.hist: dict[tuple[str, str], Historico] = {}
        self._patronus_selado: dict | None = None
        self.atestados: set[str] = set()  # T048: agentes cujo modelo foi atestado NESTA sessão
        self.canarios: dict[str, str] = {}  # T055: tarefa -> hash do gabarito (o agente não vê)
        anterior = self._reconstruir()
        # G4: MUDAR o REGIMENTO de um ANAIS existente exige assinatura do Patronus sobre o novo hash.
        # (O primeiro REGIMENTO de um ANAIS novo é o ato de fundação e fica selado.)
        # T042: se o REGIMENTO ANTERIOR selou um quórum Ed25519, só esse quórum autoriza a mudança;
        # o REGIMENTO novo não pode trazer chaves próprias e se autoaprovar.
        if anterior is not None and anterior != self.hash_regimento:
            sel = self._patronus_selado
            if sel:
                validas = {n for n, k in sel["chaves"].items() if isinstance(assinatura_regimento, dict)
                           and k not in sel.get("revogadas", [])
                           and _ed_ok(k, assinatura_regimento.get(n), "regimento", self.hash_regimento)}
                if len(validas) < int(sel["quorum"]):
                    raise RegimentoInvalido(f"mudança de REGIMENTO exige {sel['quorum']} assinatura(s) Ed25519 "
                                            f"do quórum selado; válidas: {sorted(validas)}")
                novas = set(self.r.get("patronus", {}).get("revogadas", []))
                if not set(sel.get("revogadas", [])) <= novas:
                    raise RegimentoInvalido("revogação não se desfaz: o REGIMENTO novo omitiu chave revogada")
            elif not (self._chave_patronus and isinstance(assinatura_regimento, str) and hmac.compare_digest(
                    assinatura_regimento, assinar_humano(self._chave_patronus, "regimento", self.hash_regimento))):
                raise RegimentoInvalido("REGIMENTO mudou desde a última execução e a mudança não está "
                                        "assinada pelo Patronus (assinar regimento HASH)")
        selo = {"versao": self.r["versao"], "hash": self.hash_regimento,
                "anterior": anterior, "oraculos": sorted(self.oraculos)}
        if "patronus" in self.r:  # chaves públicas não são segredo: ficam seladas para a próxima mudança
            selo["patronus"] = {"quorum": int(self.r["patronus"]["quorum"]),
                                "chaves": dict(self.r["patronus"]["chaves"]),
                                "revogadas": sorted(self.r["patronus"].get("revogadas", []))}
        self.anais.anexar("regimento", selo)

    # ------------------------------------------------------------ reconstrução a partir do ANAIS
    def _reconstruir(self) -> None:
        """Repete o ANAIS em ordem: histórico, incidentes, reabilitações, admissões e o estado
        de cada tarefa (passos, submissão, recibo, liberação). Reiniciar não apaga nada.
        A entrada bruta não fica no ANAIS (só o hash, por minimização de dados): para continuar
        uma tarefa com oráculo após reinício, o orquestrador chama vincular_entrada().
        Retorna o hash do último REGIMENTO registrado (ou None num ANAIS novo)."""
        ultimo_regimento = None
        for reg in self.anais.registros():
            tipo, d = reg["corpo"]["tipo"], reg["corpo"]["dados"]
            if tipo == "regimento":
                ultimo_regimento = d["hash"]
                self._patronus_selado = d.get("patronus")
            if tipo == "recibo" and "produtor" in d:
                self._hist(d["produtor"], d["classe"]).registrar(bool(d["aceito"]))
                t = self.tarefas.get(d["tarefa"])
                if t:
                    t.estado = "ACEITA" if d["aceito"] else "REJEITADA"
            elif tipo == "canario":
                self.canarios[d["tarefa"]] = d["gabarito"]
            elif tipo == "consumo" and d.get("tarefa") in self.tarefas:
                t = self.tarefas[d["tarefa"]]
                for k in ("tokens", "segundos", "custo_centavos"):
                    t.consumo[k] = t.consumo.get(k, 0) + d.get(k, 0)
                t.esgotada = t.esgotada or bool(d.get("estouro"))
            elif tipo == "incidente":
                self._aplicar_incidente(d["agente"])
            elif tipo == "reabilitacao":
                self.quarentena.discard(d["agente"])
            elif tipo == "admissao":
                # G5: admissão só vale sob o MESMO REGIMENTO em que o EXAME foi feito
                valida = d["aprovado"] and d.get("regimento") == self.hash_regimento
                (self.admitidos.add if valida else self.admitidos.discard)(d["agente"])
            elif tipo == "tarefa_aberta":
                self.tarefas[d["tarefa"]] = _Tarefa(d["tarefa"], d["classe"], d["produtor"],
                                                    irreversivel=d["irreversivel"], valor=d["valor"],
                                                    entrada_hash=d.get("entrada"),
                                                    plano=tuple(d["plano"]) if d.get("plano") is not None else None)
            elif tipo == "decisao" and d.get("tarefa") in self.tarefas:
                t = self.tarefas[d["tarefa"]]
                if d["permitido"] and d["codigo"] == "OK":
                    t.passos += 1
                elif d["codigo"] == "DECLARADO":
                    t.estado, t.declaracao = "DECLARADA", {"status": d["alvo"]}
                elif d["codigo"] == "SUBMETIDA":
                    t.estado, t.entrega_hash = "SUBMETIDA", d["motivo"]
                elif d["codigo"] == "APROVACAO_PARCIAL":
                    t.aprovacoes.add(d["agente"])
                elif d["codigo"] in {"LIBERADA", "AGUARDA_HUMANO"} or (d["codigo"] == "REJEITADA" and
                                                                         d["tipo"] == "aprovacao"):
                    t.estado = d["codigo"]
                    if d["codigo"] == "LIBERADA" and d["tipo"] == "aprovacao":
                        t.aprovacoes.add(d["agente"])  # T9/I7: a aprovação final também é reconstruída
        return ultimo_regimento

    def vincular_entrada(self, tarefa_id: str, entrada: Any) -> Decisao:
        """Reanexa a entrada de uma tarefa retomada; recusa se não for a mesma que foi selada."""
        t = self.tarefas[tarefa_id]
        if _h(entrada) != t.entrada_hash:
            return Decisao(False, "ENTRADA_DIVERGENTE", "entrada não confere com o hash selado na abertura")
        t.entrada = entrada
        return Decisao(True, "OK", "entrada revinculada")

    def _aplicar_incidente(self, agente: str) -> None:
        self.quarentena.add(agente)
        for cl in self.r["classes_tarefa"]:
            self._hist(agente, cl).incidente()
        for (ag, _cl), h in self.hist.items():
            if ag == agente:
                h.incidente()

    # ------------------------------------------------------------ utilidades
    def mandato(self, agente: str) -> Mandato:
        if agente not in self.r["agentes"]:
            raise KeyError(f"agente fora do REGIMENTO: {agente}")
        return Mandato(self, agente)

    def _papel(self, agente: str) -> dict | None:
        a = self.r["agentes"].get(agente)
        return self.r["papeis"].get(a["papel"]) if a else None

    def _linhagem(self, agente: str) -> frozenset[str]:
        return linhagem(self.r["agentes"][agente]["familia_modelo"])

    def _eh_humano(self, agente: str) -> bool:
        return agente in self.r["agentes"] and self._linhagem(agente) == {"humano"}

    def _hist(self, agente: str, classe: str) -> Historico:
        return self.hist.setdefault((agente, classe), Historico())

    def _decidir(self, acao: Acao, ok: bool, codigo: str, motivo: str) -> Decisao:
        self.anais.anexar("decisao", {"agente": acao.agente, "tipo": acao.tipo, "alvo": acao.alvo,
                                      "tarefa": acao.tarefa, "permitido": ok, "codigo": codigo,
                                      "motivo": motivo})
        return Decisao(ok, codigo, motivo)

    def _violacao(self, acao: Acao, codigo: str, motivo: str) -> Decisao:
        """Violação crítica: quarentena do agente + rebaixamento a L0 em todas as classes."""
        self._aplicar_incidente(acao.agente)
        self.anais.anexar("incidente", {"agente": acao.agente, "codigo": codigo, "motivo": motivo})
        return self._decidir(acao, False, codigo, motivo)

    def _assinatura_ok(self, assinatura: str | None, *campos: Any, humano: str | None = None) -> bool:
        if not self.r["autonomia"].get("exigir_assinatura_humana", True):
            return True
        if not assinatura or not isinstance(assinatura, str):
            return False
        pub = self.r["agentes"].get(humano, {}).get("chave_publica") if humano else None
        if pub:  # T042: humano com chave pública NÃO aceita HMAC (anti-rebaixamento: o núcleo conhece o HMAC)
            if pub in self.r.get("patronus", {}).get("revogadas", []):
                return False
            return _ed_ok(pub, assinatura, *campos)
        if not self._chave_patronus:
            return False
        return hmac.compare_digest(assinatura, assinar_humano(self._chave_patronus, *campos))

    def nivel_autonomia(self, agente: str, classe: str) -> int:
        return nivel(self._hist(agente, classe), self.r["autonomia"])

    # ------------------------------------------------------------ atos humanos (assinados)
    def reabilitar(self, agente: str, humano: str, motivo: str, assinatura: str | None = None) -> Decisao:
        """Só um humano tira um agente da quarentena; o histórico NÃO volta (recomeça de L0)."""
        acao = Acao(humano, "reabilitacao", "reabilitar", None, {"agente": agente})
        if not self._eh_humano(humano) or not self._assinatura_ok(assinatura, "reabilitar", agente, humano,
                                                                           humano=humano):
            return self._violacao(acao, "FALSO_HUMANO", "reabilitação exige humano registrado E assinatura válida")
        self.quarentena.discard(agente)
        self.anais.anexar("reabilitacao", {"agente": agente, "humano": humano, "motivo": motivo})
        return self._decidir(acao, True, "REABILITADO", motivo)

    def registrar_admissao(self, agente: str, aprovado: bool, nota: float, exame_hash: str,
                           respostas_hash: str) -> Decisao:
        """Chamado pelo orquestrador após corrigir o EXAME (dossie.py). Fica selado no ANAIS."""
        self.anais.anexar("admissao", {"agente": agente, "aprovado": aprovado, "nota": nota,
                                       "exame": exame_hash, "respostas": respostas_hash,
                                       "regimento": self.hash_regimento})
        (self.admitidos.add if aprovado else self.admitidos.discard)(agente)
        return Decisao(aprovado, "ADMITIDO" if aprovado else "REPROVADO", f"nota {nota:.2f}")

    # ------------------------------------------------------------ ciclo da tarefa
    def abrir_tarefa(self, tarefa_id: str, classe: str, produtor: str,
                     irreversivel: bool = False, valor: float = 0.0, entrada: Any = None,
                     plano: list[str] | None = None) -> None:
        if classe not in self.r["classes_tarefa"]:
            raise KeyError(f"classe de tarefa fora do REGIMENTO: {classe}")
        if produtor not in self.r["agentes"]:
            raise KeyError(f"agente não admitido: {produtor}")
        if tarefa_id in self.tarefas:
            raise KeyError(f"tarefa {tarefa_id} já existe (ids não se reutilizam)")
        if self.r.get("admissao", {}).get("exigida") and produtor not in self.admitidos \
                and not self._eh_humano(produtor):
            raise PermissionError(f"{produtor} não passou no EXAME de admissão")
        if classe in self.oraculos and entrada is None:
            raise ValueError(f"classe {classe} tem oráculo: a entrada deve ser vinculada na abertura")
        eh = _h(entrada) if entrada is not None else None
        if plano is not None:  # T047: o plano só pode ESTREITAR o papel, nunca ampliar
            fora = sorted(set(plano) - set(self._papel(produtor).get("capacidades", [])))
            if fora:
                raise PermissionError(f"plano pede capacidades fora do papel de {produtor}: {fora}")
        self.tarefas[tarefa_id] = _Tarefa(tarefa_id, classe, produtor, irreversivel=irreversivel,
                                          valor=valor, entrada=entrada, entrada_hash=eh,
                                          plano=tuple(sorted(set(plano))) if plano is not None else None)
        registro = {"tarefa": tarefa_id, "classe": classe, "produtor": produtor,
                    "irreversivel": irreversivel, "valor": valor, "entrada": eh}
        if plano is not None:
            registro["plano"] = sorted(set(plano))
        self.anais.anexar("tarefa_aberta", registro)

    # ------------------------------------------------------------ T055: canários
    def abrir_canario(self, tarefa_id: str, classe: str, produtor: str, entrada: Any, gabarito: Any,
                      plano: list[str] | None = None) -> None:
        """Tarefa de resposta CONHECIDA, aberta exatamente como uma real (o agente não distingue).
        Testa o produtor E o verificador: aprovar canário errado é veredito falso."""
        self.abrir_tarefa(tarefa_id, classe, produtor, entrada=entrada, plano=plano)
        g = _h(_canon(gabarito))
        self.canarios[tarefa_id] = g
        self.anais.anexar("canario", {"tarefa": tarefa_id, "gabarito": g})

    def sortear_canario(self, chave: str) -> bool:
        """O Rector consulta antes de abrir uma tarefa: imprevisível para o agente (HMAC com a chave do ANAIS)."""
        k = int(self.r["autonomia"].get("taxa_canario", 0) or 0)
        if k <= 0:
            return False
        segredo = self.anais.chave or b"sem-chave-sorteio-previsivel"
        return int(hmac.new(segredo, b"canario:" + chave.encode(), hashlib.sha256).hexdigest(), 16) % k == 0

    # ------------------------------------------------------------ T056: orçamento real
    def registrar_consumo(self, tarefa_id: str, tokens: int = 0, segundos: float = 0.0,
                          custo_centavos: int = 0) -> Decisao:
        """Chamado pelo ORQUESTRADOR com o consumo MEDIDO (ex.: Ollama.ultimo_uso), nunca pelo agente.
        Estourou o orçamento da classe -> a tarefa só aceita declaração (Art. 3)."""
        t = self.tarefas[tarefa_id]
        for k, v in (("tokens", int(tokens)), ("segundos", float(segundos)), ("custo_centavos", int(custo_centavos))):
            t.consumo[k] = t.consumo.get(k, 0) + v
        lim = self.r["classes_tarefa"][t.classe].get("orcamento") or {}
        estouro = sorted(k for k, v in lim.items() if t.consumo.get(k, 0) > v)
        self.anais.anexar("consumo", {"tarefa": tarefa_id, "tokens": int(tokens), "segundos": float(segundos),
                                      "custo_centavos": int(custo_centavos), "estouro": estouro})
        acao = Acao(t.produtor, "consumo", "orcamento", tarefa_id)
        if estouro and not t.esgotada:
            t.esgotada = True
            return self._decidir(acao, False, "ORCAMENTO_ESGOTADO", f"estourou: {estouro}; agora só declarar")
        return self._decidir(acao, not t.esgotada, "ORCAMENTO_ESGOTADO" if t.esgotada else "OK",
                             f"consumo acumulado {t.consumo}")

    # ------------------------------------------------------------ T048: identidade do modelo
    def atestar_modelo(self, agente: str, digest_observado: str) -> Decisao:
        """Chamado pelo ORQUESTRADOR (nunca pelo agente) com a impressão digital do modelo que vai rodar."""
        acao = Acao(agente, "atestacao", "modelo")
        dec = (self.r["agentes"].get(agente) or {}).get("modelo", {}).get("digest")
        self.anais.anexar("atestacao_modelo", {"agente": agente, "declarado": dec, "observado": digest_observado})
        if dec is None:
            return self._decidir(acao, True, "SEM_DIGEST_DECLARADO",
                                 "linhagem só declarada por nome: atestação fraca (registrada)")
        if digest_observado != dec:
            self.atestados.discard(agente)
            return self._violacao(acao, "MODELO_TROCADO", f"declarado {dec[:19]}…, rodando {str(digest_observado)[:19]}…")
        self.atestados.add(agente)
        return self._decidir(acao, True, "ATESTADO", "modelo confere com o REGIMENTO")

    def _mensagem_valida(self, acao: Acao) -> str | None:
        cfg = self.r.get("forum", {})
        p = acao.payload
        if set(p) - {"para", "tipo", "conteudo"} or p.get("tipo") not in TIPOS_MENSAGEM:
            return "formato: {para, tipo∈{pedido,resposta,alerta}, conteudo}"
        if p.get("para") not in self.r["agentes"] and p.get("para") != "todos":
            return "destinatário inexistente"
        if len(str(p.get("conteudo", ""))) > int(cfg.get("max_caracteres", 500)):
            return "conteúdo acima do limite de caracteres"
        return None

    @staticmethod
    def _malformada(acao: Acao) -> str | None:
        """T051 (achados do atacante adaptativo A6): tipos errados derrubavam o LEX com exceção."""
        for nome in ("agente", "tipo", "alvo"):
            if not isinstance(getattr(acao, nome), str):
                return f"{nome} deve ser texto"
        if acao.tarefa is not None and not isinstance(acao.tarefa, str):
            return "tarefa deve ser texto ou nula"
        if not isinstance(acao.payload, dict):
            return "payload deve ser objeto"
        return None

    def autorizar(self, acao: Acao) -> Decisao:
        mal = self._malformada(acao)
        if mal:  # falha FECHADA e registrada; os campos vão ao ANAIS como texto seguro
            def txt(x):
                return x if isinstance(x, str) else repr(x)[:80]
            seguro = Acao(txt(acao.agente), txt(acao.tipo), txt(acao.alvo),
                          None if acao.tarefa is None else txt(acao.tarefa))
            return self._decidir(seguro, False, "ACAO_MALFORMADA", mal)
        if acao.agente in self.quarentena:
            return self._decidir(acao, False, "QUARENTENA", "agente em quarentena após violação crítica")
        papel = self._papel(acao.agente)
        if papel is None:
            return self._violacao(acao, "NAO_ADMITIDO", "agente fora do REGIMENTO")
        if acao.tipo not in TIPOS:
            return self._violacao(acao, "TIPO_DESCONHECIDO", f"tipo de ação '{acao.tipo}' inexistente")
        if "modelo" in self.r["agentes"][acao.agente] and acao.agente not in self.atestados:
            return self._decidir(acao, False, "SEM_ATESTACAO", "modelo declarado no REGIMENTO ainda não "
                                 "atestado nesta sessão (T048)")

        t = self.tarefas.get(acao.tarefa) if acao.tarefa else None
        if acao.tarefa and t is None:
            return self._decidir(acao, False, "TAREFA_INEXISTENTE", "tarefa não aberta")
        if t and t.produtor != acao.agente:
            return self._violacao(acao, "TAREFA_ALHEIA", "agente agindo em tarefa de outro agente")
        # L2 — toda ação de trabalho pertence a uma tarefa (ataque R1: fugir do orçamento)
        if t is None and acao.tipo != "declaracao" and acao.alvo not in papel.get("sem_tarefa", []):
            return self._decidir(acao, False, "SEM_TAREFA", "ação de trabalho fora de tarefa não consome "
                                 "orçamento; abra ou use uma tarefa")

        if acao.tipo == "declaracao":
            if t is None or acao.alvo not in STATUS_DECLARACAO:
                return self._decidir(acao, False, "DECLARACAO_INVALIDA", "declaração exige tarefa e status válido")
            if t.estado != "ABERTA":
                return self._decidir(acao, False, "ESTADO_INVALIDO", f"tarefa {t.estado}")
            if acao.alvo in {"BLOQUEADO", "IMPOSSIVEL"} and not acao.payload.get("evidencia"):
                return self._decidir(acao, False, "SEM_EVIDENCIA", "declarar impossibilidade exige evidência")
            t.estado, t.declaracao = "DECLARADA", {**acao.payload, "status": acao.alvo}  # T051: payload não sobrescreve
            self.anais.anexar("declaracao", {"tarefa": t.id, "agente": acao.agente, "status": acao.alvo,
                                             "evidencia": str(acao.payload.get("evidencia", ""))[:1000]})
            return self._decidir(acao, True, "DECLARADO", f"tarefa declarada {acao.alvo}")
        if t is not None:
            if t.estado != "ABERTA":
                return self._violacao(acao, "PERSISTENCIA", f"ação após tarefa {t.estado}")
            orc = int(self.r["classes_tarefa"][t.classe]["orcamento_passos"])
            if t.esgotada:
                return self._violacao(acao, "PERSISTENCIA", "orçamento de tokens/tempo/custo esgotado; "
                                      "única ação válida é declarar")
            if t.passos >= orc:
                return self._violacao(acao, "PERSISTENCIA",
                                      f"orçamento de {orc} passos esgotado; única ação válida é declarar")

        # L1 — negação por padrão
        if acao.tipo == "ferramenta" and acao.alvo not in papel.get("capacidades", []):
            return self._violacao(acao, "CAPACIDADE_NEGADA", f"capacidade '{acao.alvo}' fora do papel")
        if acao.tipo == "ferramenta" and t is not None and t.plano is not None and acao.alvo not in t.plano:
            return self._violacao(acao, "PLANO_VIOLADO", f"'{acao.alvo}' não está no plano selado na abertura")
        if acao.tipo == "ferramenta":
            confiaveis = (self.r.get("destinos") or {}).get(acao.alvo, {})
            for k, v in _campos_destino(acao.payload):
                if v not in confiaveis.get(k, []):
                    return self._violacao(acao, "DESTINO_NAO_CONFIAVEL",
                                          f"{k}={str(v)[:60]!r} fora da lista confiável de '{acao.alvo}'")
            if confiaveis:  # T051 (A6 confirmatório): capacidade sensível só aceita argumentos DECLARADOS
                livres = set((self.r.get("argumentos_livres") or {}).get(acao.alvo, []))
                extras = sorted(str(k) for k in acao.payload if k not in confiaveis and k not in livres)
                if extras:
                    return self._violacao(acao, "ARGUMENTO_NAO_DECLARADO",
                                          f"argumentos fora do REGIMENTO para '{acao.alvo}': {extras[:5]}")
        if acao.tipo == "mensagem" and acao.alvo not in papel.get("canais", []):
            return self._violacao(acao, "CANAL_NAO_SANCIONADO", f"canal '{acao.alvo}' não sancionado")
        if acao.tipo == "rede" and acao.alvo not in papel.get("rede", []):
            return self._violacao(acao, "EGRESSO_NEGADO", f"host '{acao.alvo}' fora da lista")
        if acao.tipo == "mensagem":
            erro = self._mensagem_valida(acao)  # ataque R5: canal sem formato nem limite
            if erro:
                return self._decidir(acao, False, "MENSAGEM_INVALIDA", erro)
        if t is not None:
            t.passos += 1  # só conta passo de ação efetivamente permitida
        if acao.tipo == "mensagem":
            self.anais.anexar("mensagem", {"de": acao.agente, "canal": acao.alvo, **acao.payload})
        return self._decidir(acao, True, "OK", "dentro do REGIMENTO")

    # ------------------------------------------------------------ entrega, verificação, liberação
    def submeter(self, tarefa_id: str, agente: str, entrega: Any) -> Decisao:
        if not isinstance(tarefa_id, str) or not isinstance(agente, str):  # T051: o agente controla o id
            return self._decidir(Acao(str(agente)[:80], "ferramenta", "submeter", repr(tarefa_id)[:80]),
                                 False, "ACAO_MALFORMADA", "tarefa e agente devem ser texto")
        t = self.tarefas.get(tarefa_id)
        acao = Acao(agente, "ferramenta", "submeter", tarefa_id)
        if t is None:
            return self._decidir(acao, False, "TAREFA_INEXISTENTE", "tarefa não aberta")
        if agente in self.quarentena:
            return self._decidir(acao, False, "QUARENTENA", "agente em quarentena")
        if agente != t.produtor:
            return self._violacao(acao, "TAREFA_ALHEIA", "submissão por quem não produziu")
        if t.estado not in {"ABERTA", "DECLARADA"}:
            return self._decidir(acao, False, "ESTADO_INVALIDO", f"tarefa {t.estado}")
        if t.declaracao and t.declaracao["status"] != "CONCLUIDO":
            return self._decidir(acao, False, "DECLARADA_IMPOSSIVEL",
                                 "tarefa declarada impossível/bloqueada não aceita entrega")
        try:
            t.entrega_hash = _h(entrega)
        except (TypeError, ValueError) as e:  # G2: entrega não serializável é recusada, não derruba
            return self._decidir(acao, False, "ENTREGA_INVALIDA", f"entrega não serializável: {type(e).__name__}")
        t.estado = "SUBMETIDA"
        return self._decidir(acao, True, "SUBMETIDA", t.entrega_hash)

    def verificar(self, tarefa_id: str, verificador: str, entrega: Any, aceito: bool | None = None,
                  falhas: list[str] | None = None) -> Decisao:
        t = self.tarefas[tarefa_id]
        acao = Acao(verificador, "ferramenta", "verificar", tarefa_id)
        if verificador in self.quarentena:
            return self._decidir(acao, False, "QUARENTENA", "verificador em quarentena")
        papel = self._papel(verificador)
        if papel is None or "verificar" not in papel.get("capacidades", []):
            return self._violacao(acao, "CAPACIDADE_NEGADA", "papel sem poder de verificar")
        if verificador == t.produtor:
            return self._violacao(acao, "AUTOVERIFICACAO", "quem produz não verifica (lei L3)")
        oraculo = self.oraculos.get(t.classe)
        lv, lp = self._linhagem(verificador), self._linhagem(t.produtor)
        if oraculo is None and (lv & lp) and not (lv <= FAMILIAS_INDEPENDENTES):
            return self._decidir(acao, False, "MESMA_FAMILIA",
                                 f"verificador e produtor compartilham linhagem {sorted(lv & lp)}")
        if t.estado != "SUBMETIDA":
            return self._decidir(acao, False, "ESTADO_INVALIDO", f"tarefa {t.estado}")
        h = _h(entrega)
        if h != t.entrega_hash:
            return self._decidir(acao, False, "ENTREGA_DIVERGENTE", "o verificado não é o submetido")
        if oraculo is not None:
            if t.entrada is None:
                return self._decidir(acao, False, "SEM_ENTRADA", "tarefa retomada: vincular_entrada() antes")
            declarado = aceito
            try:
                aceito, falhas = oraculo(t.entrada, entrega)  # o LEX roda o oráculo; não confia em ninguém
            except Exception as e:  # G1: falha FECHADA — entrega malformada é rejeição, nunca queda
                aceito, falhas = False, [f"ENTREGA_MALFORMADA:{type(e).__name__}"]
            if declarado is not None and bool(declarado) != bool(aceito):
                self._violacao(acao, "VEREDITO_FALSO",
                               f"verificador declarou {declarado}, oráculo calculou {aceito}")
        elif aceito is None:
            return self._decidir(acao, False, "SEM_VEREDITO", "classe sem oráculo exige veredito explícito")
        aceito = bool(aceito)
        if tarefa_id in self.canarios:  # T055: a resposta é conhecida; o veredito é conferido contra ela
            correto = _h(_canon(entrega)) == self.canarios[tarefa_id]
            self.anais.anexar("canario_resultado", {"tarefa": tarefa_id, "correto": correto, "aceito": aceito,
                                                    "verificador": verificador, "produtor": t.produtor})
            if aceito and not correto:
                if oraculo is not None:  # o oráculo aceitou resposta errada: lacuna do oráculo, não do verificador
                    self.anais.anexar("lacuna_oraculo", {"tarefa": tarefa_id, "classe": t.classe})
                else:
                    self._violacao(acao, "VEREDITO_FALSO", "aprovou canário de resposta conhecida ERRADA")
            aceito = aceito and correto
        t.estado = "ACEITA" if aceito else "REJEITADA"
        self._hist(t.produtor, t.classe).registrar(aceito)
        self.anais.anexar("recibo", {"tarefa": tarefa_id, "entrega": h, "entrada": t.entrada_hash,
                                     "verificador": verificador, "familia_verificador": sorted(lv),
                                     "produtor": t.produtor, "classe": t.classe,
                                     "por_oraculo": oraculo is not None, "aceito": aceito,
                                     "falhas": falhas or []})
        criticas = set(self.r["classes_tarefa"][t.classe].get("falhas_criticas", []))
        achadas = sorted({f.split(":", 1)[0] for f in (falhas or [])} & criticas)
        if achadas:
            self._violacao(Acao(t.produtor, "ferramenta", "submeter", tarefa_id),
                           "FABRICACAO", f"falhas críticas na entrega: {achadas}")
        return self._decidir(acao, True, t.estado, "recibo emitido")

    def _amostra_l1(self, tarefa_id: str) -> bool:
        """Sorteio IMPREVISÍVEL para o agente (ataque R3): HMAC com a chave do ANAIS."""
        k = int(self.r["autonomia"].get("amostragem_l1", 5))
        chave = self.anais.chave or b"sem-chave-amostragem-previsivel"
        return int(hmac.new(chave, tarefa_id.encode(), hashlib.sha256).hexdigest(), 16) % k == 0

    def liberar(self, tarefa_id: str) -> Decisao:
        t = self.tarefas[tarefa_id]
        acao = Acao(t.produtor, "liberacao", "liberar", tarefa_id)
        if t.estado != "ACEITA":
            return self._decidir(acao, False, "NAO_ACEITA", "só se libera entrega com recibo de aceite")
        lv = self.nivel_autonomia(t.produtor, t.classe)
        alcada = float(self.r["autonomia"].get("alcada_valor_l3", 0))
        if t.irreversivel:
            precisa_humano = lv < 3 or t.valor > alcada
        elif lv == 0:
            precisa_humano = True
        elif lv == 1:
            precisa_humano = self._amostra_l1(tarefa_id)
        else:
            precisa_humano = False
        if precisa_humano:
            t.estado = "AGUARDA_HUMANO"
            return self._decidir(acao, False, "AGUARDA_HUMANO", f"nível L{lv} exige aprovação humana")
        t.estado = "LIBERADA"
        return self._decidir(acao, True, "LIBERADA", f"liberada sob autonomia L{lv}")

    def aprovar_humano(self, tarefa_id: str, humano: str, aprovado: bool,
                       assinatura: str | None = None) -> Decisao:
        t = self.tarefas[tarefa_id]
        acao = Acao(humano, "aprovacao", "aprovar", tarefa_id)
        if not self._eh_humano(humano) or not self._assinatura_ok(
                assinatura, "aprovar", tarefa_id, t.entrega_hash, bool(aprovado), humano, humano=humano):
            return self._violacao(acao, "FALSO_HUMANO", "aprovação exige humano registrado E assinatura "
                                  "válida sobre (tarefa, entrega, decisão)")
        if t.estado != "AGUARDA_HUMANO":
            return self._decidir(acao, False, "ESTADO_INVALIDO", f"tarefa {t.estado}")
        if not aprovado:  # veto de qualquer humano basta
            t.estado = "REJEITADA"
            return self._decidir(acao, True, t.estado, f"decisão humana de {humano} sobre {t.entrega_hash}")
        quatro = float(self.r["autonomia"].get("alcada_quatro_olhos", 0) or 0)
        precisa = 2 if quatro and t.valor >= quatro else 1
        if humano in t.aprovacoes:
            return self._decidir(acao, False, "MESMO_HUMANO", "quatro olhos exige DOIS humanos diferentes")
        t.aprovacoes.add(humano)
        if len(t.aprovacoes) < precisa:
            return self._decidir(acao, False, "APROVACAO_PARCIAL",
                                 f"1 de {precisa} aprovações (valor {t.valor} >= alçada de quatro olhos {quatro})")
        t.estado = "LIBERADA"
        quem = humano if precisa == 1 else sorted(t.aprovacoes)  # texto idêntico ao anterior no caso de 1 humano
        return self._decidir(acao, True, t.estado, f"decisão humana de {quem} sobre {t.entrega_hash}")
