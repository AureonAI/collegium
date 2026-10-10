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


class RegimentoInvalido(ValueError):
    pass


def _h(obj: Any) -> str:
    return hashlib.sha256(canonico(obj)).hexdigest()


def assinar_humano(chave: bytes, *campos: Any) -> str:
    """Assinatura que só quem tem a chave do Patronus produz (HMAC-SHA256).
    Limite declarado: chave simétrica; o LEX também a conhece. Assinatura assimétrica
    (Ed25519) exige dependência externa — prevista para quando houver juiz externo."""
    return hmac.new(chave, canonico(list(campos)), hashlib.sha256).hexdigest()


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
        anterior = self._reconstruir()
        # G4: MUDAR o REGIMENTO de um ANAIS existente exige assinatura do Patronus sobre o novo hash.
        # (O primeiro REGIMENTO de um ANAIS novo é o ato de fundação e fica selado.)
        if anterior is not None and anterior != self.hash_regimento:
            if not (self._chave_patronus and assinatura_regimento and hmac.compare_digest(
                    assinatura_regimento, assinar_humano(self._chave_patronus, "regimento", self.hash_regimento))):
                raise RegimentoInvalido("REGIMENTO mudou desde a última execução e a mudança não está "
                                        "assinada pelo Patronus (assinar regimento HASH)")
        self.anais.anexar("regimento", {"versao": self.r["versao"], "hash": self.hash_regimento,
                                        "anterior": anterior, "oraculos": sorted(self.oraculos)})

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
            if tipo == "recibo" and "produtor" in d:
                self._hist(d["produtor"], d["classe"]).registrar(bool(d["aceito"]))
                t = self.tarefas.get(d["tarefa"])
                if t:
                    t.estado = "ACEITA" if d["aceito"] else "REJEITADA"
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
                                                    entrada_hash=d.get("entrada"))
            elif tipo == "decisao" and d.get("tarefa") in self.tarefas:
                t = self.tarefas[d["tarefa"]]
                if d["permitido"] and d["codigo"] == "OK":
                    t.passos += 1
                elif d["codigo"] == "DECLARADO":
                    t.estado, t.declaracao = "DECLARADA", {"status": d["alvo"]}
                elif d["codigo"] == "SUBMETIDA":
                    t.estado, t.entrega_hash = "SUBMETIDA", d["motivo"]
                elif d["codigo"] in {"LIBERADA", "AGUARDA_HUMANO"} or (d["codigo"] == "REJEITADA" and
                                                                         d["tipo"] == "aprovacao"):
                    t.estado = d["codigo"]
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

    def _assinatura_ok(self, assinatura: str | None, *campos: Any) -> bool:
        if not self.r["autonomia"].get("exigir_assinatura_humana", True):
            return True
        if not self._chave_patronus or not assinatura:
            return False
        return hmac.compare_digest(assinatura, assinar_humano(self._chave_patronus, *campos))

    def nivel_autonomia(self, agente: str, classe: str) -> int:
        return nivel(self._hist(agente, classe), self.r["autonomia"])

    # ------------------------------------------------------------ atos humanos (assinados)
    def reabilitar(self, agente: str, humano: str, motivo: str, assinatura: str | None = None) -> Decisao:
        """Só um humano tira um agente da quarentena; o histórico NÃO volta (recomeça de L0)."""
        acao = Acao(humano, "reabilitacao", "reabilitar", None, {"agente": agente})
        if not self._eh_humano(humano) or not self._assinatura_ok(assinatura, "reabilitar", agente, humano):
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
                     irreversivel: bool = False, valor: float = 0.0, entrada: Any = None) -> None:
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
        self.tarefas[tarefa_id] = _Tarefa(tarefa_id, classe, produtor, irreversivel=irreversivel,
                                          valor=valor, entrada=entrada, entrada_hash=eh)
        self.anais.anexar("tarefa_aberta", {"tarefa": tarefa_id, "classe": classe, "produtor": produtor,
                                            "irreversivel": irreversivel, "valor": valor, "entrada": eh})

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

    def autorizar(self, acao: Acao) -> Decisao:
        if acao.agente in self.quarentena:
            return self._decidir(acao, False, "QUARENTENA", "agente em quarentena após violação crítica")
        papel = self._papel(acao.agente)
        if papel is None:
            return self._violacao(acao, "NAO_ADMITIDO", "agente fora do REGIMENTO")
        if acao.tipo not in TIPOS:
            return self._violacao(acao, "TIPO_DESCONHECIDO", f"tipo de ação '{acao.tipo}' inexistente")

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
            t.estado, t.declaracao = "DECLARADA", {"status": acao.alvo, **acao.payload}
            self.anais.anexar("declaracao", {"tarefa": t.id, "agente": acao.agente, "status": acao.alvo,
                                             "evidencia": str(acao.payload.get("evidencia", ""))[:1000]})
            return self._decidir(acao, True, "DECLARADO", f"tarefa declarada {acao.alvo}")
        if t is not None:
            if t.estado != "ABERTA":
                return self._violacao(acao, "PERSISTENCIA", f"ação após tarefa {t.estado}")
            orc = int(self.r["classes_tarefa"][t.classe]["orcamento_passos"])
            if t.passos >= orc:
                return self._violacao(acao, "PERSISTENCIA",
                                      f"orçamento de {orc} passos esgotado; única ação válida é declarar")

        # L1 — negação por padrão
        if acao.tipo == "ferramenta" and acao.alvo not in papel.get("capacidades", []):
            return self._violacao(acao, "CAPACIDADE_NEGADA", f"capacidade '{acao.alvo}' fora do papel")
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
        t = self.tarefas[tarefa_id]
        acao = Acao(agente, "ferramenta", "submeter", tarefa_id)
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
                assinatura, "aprovar", tarefa_id, t.entrega_hash, bool(aprovado), humano):
            return self._violacao(acao, "FALSO_HUMANO", "aprovação exige humano registrado E assinatura "
                                  "válida sobre (tarefa, entrega, decisão)")
        if t.estado != "AGUARDA_HUMANO":
            return self._decidir(acao, False, "ESTADO_INVALIDO", f"tarefa {t.estado}")
        t.estado = "LIBERADA" if aprovado else "REJEITADA"
        return self._decidir(acao, True, t.estado, f"decisão humana de {humano} sobre {t.entrega_hash}")
