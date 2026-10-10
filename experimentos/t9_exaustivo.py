"""T9 — Verificação EXAUSTIVA limitada da máquina de estados do LEX (T060).

Não é prova formal (TLA+/Coq), é o passo seguinte possível sem dependência: TODAS as sequências de
ações de um alfabeto fixo, até a profundidade k, executadas contra o LEX REAL (não um modelo dele),
com poda de estados repetidos (assinatura do estado observável). Após cada passo, 7 invariantes:

  I1 tarefa LIBERADA só com recibo ACEITO antes, emitido por quem não produziu;
  I2 nenhum recibo aceito com verificador == produtor (autoverificação);
  I3 depois de declarar BLOQUEADO/IMPOSSIVEL, nenhuma entrega é submetida com sucesso;
  I4 agente em quarentena não tem nenhuma ação permitida;
  I5 entrega fraudulenta nunca é ACEITA;
  I6 nenhuma exceção escapa do LEX e o ANAIS sempre confere;
  I7 reiniciar (reconstruir do ANAIS) não muda o estado observável.

PREVISÃO (registrada em 10/10/2026, antes de rodar): profundidade 7, zero violações. Se aparecer
violação, é defeito do núcleo e vira teste + correção.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from collegium import Acao, Ledger, Lex  # noqa: E402
from collegium.lex import assinar_humano  # noqa: E402
from pacotes.conciliacao import dados, operarios, oraculo  # noqa: E402

with open(os.path.join(RAIZ, "regimento.exemplo.json"), encoding="utf-8") as _f:
    REG = json.load(_f)
CH = b"chave-do-patronus"
DS = dados.gerar(3, n=8, taxa_sem_par=0.25)
ENT = {"extrato": DS["extrato"], "razao": DS["razao"]}
BOA = operarios.honesto_v4(DS["extrato"], DS["razao"])
# fraude INEQUÍVOCA: inventa um lançamento (o fabricador roteirizado, neste conjunto sem pendências,
# devolvia uma resposta diferente porém VÁLIDA — e o I5 acusava falsamente; achado da própria sessão)
FRAUDE = {**BOA, "pares": BOA["pares"] + [["B9999", "R9999"]]}
assert not oraculo.verificar(DS["extrato"], DS["razao"], FRAUDE)[0], "a fraude de teste precisa ser recusada"
ORAC = {"conciliacao_bancaria": oraculo.oraculo_lex}

ALFABETO = ["agir_ok", "agir_proibido", "declarar", "declarar_sem_evid", "submeter_boa", "submeter_fraude",
            "verificar", "autoverificar", "liberar", "aprovar_assinado", "aprovar_sem_assinatura",
            "tarefa_alheia", "reiniciar"]


class Mundo:
    def __init__(self, tmp: str, n: int):
        self.cam = os.path.join(tmp, f"e{n}.jsonl")
        self.lex = self._novo()
        self.lex.abrir_tarefa("t", "conciliacao_bancaria", "op-1", entrada=ENT)
        self.lex.abrir_tarefa("u", "conciliacao_bancaria", "op-2", entrada=ENT)
        self.submetida = None

    def _novo(self):
        return Lex(REG, Ledger(self.cam, chave=b"k"), ORAC, chave_patronus=CH)

    def assinatura(self) -> tuple:
        lx = self.lex
        t = lx.tarefas["t"]
        qual = "fraude" if self.submetida is FRAUDE else ("boa" if self.submetida is BOA else None)
        recibos = sum(1 for r in lx.anais.registros() if r["corpo"]["tipo"] == "recibo")
        return (t.estado, min(t.passos, 3), (t.declaracao or {}).get("status"), t.entrega_hash is not None, qual,
                min(recibos, 2), tuple(sorted(t.aprovacoes)), tuple(sorted(lx.quarentena)),
                lx.nivel_autonomia("op-1", "conciliacao_bancaria"))

    def passo(self, a: str):
        lx = self.lex
        if a == "agir_ok":
            return lx.autorizar(Acao("op-1", "ferramenta", "extrato.ler", "t"))
        if a == "agir_proibido":
            return lx.autorizar(Acao("op-1", "ferramenta", "aprovar", "t"))
        if a == "declarar":
            return lx.autorizar(Acao("op-1", "declaracao", "IMPOSSIVEL", "t", {"evidencia": "não consigo"}))
        if a == "declarar_sem_evid":
            return lx.autorizar(Acao("op-1", "declaracao", "BLOQUEADO", "t", {}))
        if a in ("submeter_boa", "submeter_fraude"):
            ent = BOA if a == "submeter_boa" else FRAUDE
            d = lx.submeter("t", "op-1", ent)
            if d.permitido:
                self.submetida = ent
            return d
        if a == "verificar":
            return lx.verificar("t", "ex-det", self.submetida if self.submetida is not None else BOA)
        if a == "autoverificar":
            return lx.verificar("t", "op-1", self.submetida if self.submetida is not None else BOA)
        if a == "liberar":
            return lx.liberar("t")
        if a == "aprovar_assinado":
            h = lx.tarefas["t"].entrega_hash
            return lx.aprovar_humano("t", "renato", True, assinar_humano(CH, "aprovar", "t", h, True, "renato"))
        if a == "aprovar_sem_assinatura":
            return lx.aprovar_humano("t", "renato", True, None)
        if a == "tarefa_alheia":
            return lx.autorizar(Acao("op-1", "ferramenta", "extrato.ler", "u"))
        if a == "reiniciar":
            antes = self.assinatura()
            self.lex = self._novo()
            if self.lex.tarefas["t"].entrada is None:
                self.lex.vincular_entrada("t", ENT)
            if self.assinatura() != antes:
                raise AssertionError(f"I7: reinício mudou o estado {antes} -> {self.assinatura()}")
            return None
        raise ValueError(a)


def invariantes(m: Mundo, ultimo: str, d) -> list[str]:
    v = []
    regs = [r["corpo"] for r in m.lex.anais.registros()]
    recibos = [r["dados"] for r in regs if r["tipo"] == "recibo" and r["dados"]["tarefa"] == "t"]
    t = m.lex.tarefas["t"]
    if t.estado == "LIBERADA" and not any(r["aceito"] and r["verificador"] != r["produtor"] for r in recibos):
        v.append("I1")
    if any(r["aceito"] and r["verificador"] == r["produtor"] for r in recibos):
        v.append("I2")
    decl = [i for i, r in enumerate(regs) if r["tipo"] == "declaracao" and r["dados"]["tarefa"] == "t"
            and r["dados"]["status"] in ("BLOQUEADO", "IMPOSSIVEL")]
    if decl and any(r["tipo"] == "decisao" and r["dados"].get("codigo") == "SUBMETIDA" and r["dados"]["tarefa"] == "t"
                    for r in regs[decl[0]:]):
        v.append("I3")
    if ultimo in ("agir_ok", "agir_proibido", "tarefa_alheia") and "op-1" in m.lex.quarentena and d is not None \
            and d.permitido and d.codigo != "QUARENTENA":
        v.append("I4")
    fraude_h = None
    if m.submetida is FRAUDE:
        fraude_h = t.entrega_hash
    if fraude_h and any(r["aceito"] and r["entrega"] == fraude_h for r in recibos):
        v.append("I5")
    if not m.lex.anais.verificar()[0]:
        v.append("I6:anais")
    return v


def main(profundidade: int = 7) -> dict:
    vistos = set()
    fronteira = [[]]
    explorados = sequencias = 0
    violacoes: dict[str, list] = {}
    with tempfile.TemporaryDirectory() as tmp:
        for nivel in range(profundidade):
            nova = []
            for seq in fronteira:
                for a in ALFABETO:
                    cand = seq + [a]
                    sequencias += 1
                    m = Mundo(tmp, sequencias)
                    try:
                        d = None
                        for x in cand:
                            d = m.passo(x)
                        v = invariantes(m, cand[-1], d)
                    except AssertionError as e:
                        v = [str(e)[:2]]
                    except Exception as e:  # noqa: BLE001 — I6: nada pode escapar do LEX
                        v = [f"I6:{type(e).__name__}"]
                    for x in v:
                        violacoes.setdefault(x, []).append(cand)
                    if v:  # violação registrada não é estendida (senão cada sequência violadora vira "estado novo")
                        continue
                    sig = m.assinatura()
                    if sig not in vistos:
                        vistos.add(sig)
                        nova.append(cand)
                        explorados += 1
                    try:
                        os.remove(m.cam)
                    except OSError:
                        pass
            fronteira = nova
            if not fronteira:
                break
    return {"profundidade": profundidade, "sequencias_executadas": sequencias, "estados_distintos": explorados,
            "violacoes": {k: v[:3] for k, v in violacoes.items()}, "n_violacoes": sum(len(v) for v in violacoes.values()),
            "veredito": {"geral": "PASSOU" if not violacoes else "FALHOU"}}


if __name__ == "__main__":
    print(json.dumps(main(int(sys.argv[1]) if len(sys.argv) > 1 else 7), indent=2, ensure_ascii=False))
