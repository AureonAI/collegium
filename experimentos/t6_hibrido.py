"""T6 — Arquitetura híbrida (decisão A, 10/10/2026): o código concilia, o LLM só anota o resíduo.

Fluxo por tarefa (dados.gerar_v2, 60 lançamentos, o mundo "sujo" do A5):
  1. op-det (operário determinístico honesto_v5, família "deterministico") concilia sob o LEX;
     o LEX roda o oráculo da conciliação e emite o recibo.
  2. O código monta o PACOTE do humano: cada pendência com motivo e candidatos.
  3. (só com --modelo) op-llm escreve uma NOTA por item, sob o LEX, na classe "nota_residuo";
     o LEX roda o oráculo da nota. A nota nunca altera a conciliação aceita.

DESCRITIVO (vi estes números ANTES de escrever este arquivo; não contam como previsão):
  D1. op-det: 20/20 conciliações aceitas sob o LEX, 0 incidentes.
  D2. Resíduo ≈ 10% dos lançamentos do extrato (123/1200 nas sementes 1–20).

PREVISÕES PROSPECTIVAS (registradas em 10/10/2026, antes de qualquer medição; falsificáveis):
  H1. Os candidatos contêm o par verdadeiro em >= 90% dos itens pendentes que têm par 1:1.
  H2. A sugestão de base (candidato de data mais próxima) acerta >= 50% dos itens julgáveis
      (acertar "sem par" também conta).
  P6. gemma3:4b: >= 50% das notas aceitas pelo oráculo da nota (escolher numa lista dada é
      muito mais fácil do que conciliar).
  P7. FRACA POR CONSTRUÇÃO, só descritiva: o LLM NÃO supera a sugestão de base, porque os dados
      sintéticos não têm sinal além de valor, data e documento. Se superar, investigar vazamento.
Invariante (teste unitário, não previsão): a nota do LLM nunca altera a conciliação aceita.

Uso:  python experimentos/t6_hibrido.py                      (só determinístico; entra no reproduzir)
      python experimentos/t6_hibrido.py 20 --modelo gemma3:4b (com LLM real, na máquina do Renato)
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import tempfile
import time
from collections import Counter

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from collegium import Acao, Ledger, Lex  # noqa: E402
from collegium.adaptadores import Ollama, extrair_json  # noqa: E402
from collegium_oficios.conciliacao import dados, operarios, oraculo, residuo  # noqa: E402

SISTEMA = """Você é o Operarius de RESÍDUO de um escritório de conciliação bancária.
A conciliação automática JÁ FOI FEITA e aceita. Você recebe só os itens que ficaram PENDENTES,
cada um com o MOTIVO e a lista de CANDIDATOS (ids do outro lado, do mais provável ao menos).
Para CADA item, escreva uma nota curta (até 200 caracteres) para o humano que vai decidir.
Se achar que um candidato é o par, ponha o id dele em "sugestao" (SOMENTE um id da lista de
candidatos DAQUELE item); se não, "sugestao": null. Você não concilia nada: o humano decide.
Todo item aparece exatamente uma vez. NUNCA invente id.
Responda APENAS JSON, em um destes formatos:
{"itens": [{"id": "B0001", "sugestao": "R0003", "texto": "..."}, ...]}
{"declaracao": "IMPOSSIVEL", "evidencia": "motivo objetivo"}"""


def regimento(com_llm: str | None = None) -> dict:
    with open(os.path.join(RAIZ, "regimento.exemplo.json"), encoding="utf-8") as f:
        reg = json.load(f)
    reg = copy.deepcopy(reg)
    reg["agentes"]["op-det"] = {"papel": "operarius", "familia_modelo": "deterministico"}
    reg["classes_tarefa"]["nota_residuo"] = {
        "orcamento_passos": 4, "verificador": "oraculo",
        "falhas_criticas": ["REFERENCIA_INEXISTENTE", "SUGESTAO_FORA_DOS_CANDIDATOS", "CONSERVACAO"]}
    if com_llm:
        reg["agentes"]["op-llm"] = {"papel": "operarius", "familia_modelo": com_llm}
    return reg


def pacote_texto(ds: dict, pac: list[dict]) -> str:
    B = {x["id"]: x for x in ds["extrato"]}
    R = {x["id"]: x for x in ds["razao"]}
    linhas = []
    for it in pac:
        x = B[it["id"]] if it["lado"] == "banco" else R[it["id"]]
        outro = R if it["lado"] == "banco" else B
        extra = x.get("desc", x.get("doc", ""))
        cands = "; ".join(f"{c} ({outro[c]['data']}, {outro[c].get('desc', outro[c].get('doc', ''))})"
                          for c in it["candidatos"]) or "nenhum"
        linhas.append(f"- {it['id']} [{it['lado']}] {x['data']} valor={x['valor']} \"{extra}\" | "
                      f"motivo={it['motivo']} | candidatos: {cands}")
    return "ITENS PENDENTES:\n" + "\n".join(linhas)


def main(n: int = 20, modelo: str | None = None, base: str = "http://localhost:11434") -> dict:
    llm = Ollama(modelo, base) if modelo else None
    reg = regimento(llm.familia if llm else None)
    cont, motivos = Counter(), Counter()
    tempos: list[float] = []
    impressoes = []  # hash da conciliação aceita, para provar que a nota não a altera
    integro = True
    with tempfile.TemporaryDirectory() as tmp:
        orac = {"conciliacao_bancaria": oraculo.oraculo_lex, "nota_residuo": residuo.oraculo_nota_lex}
        lex = Lex(reg, Ledger(os.path.join(tmp, "anais.jsonl"), chave=b"chave-do-patronus"), orac)
        for s in range(1, n + 1):
            ds = dados.gerar_v2(s, n=60)
            tid = f"C{s:03d}"
            lex.abrir_tarefa(tid, "conciliacao_bancaria", "op-det",
                             entrada={"extrato": ds["extrato"], "razao": ds["razao"]})
            for cap in ("extrato.ler", "razao.ler", "conciliacao.propor"):
                lex.autorizar(Acao("op-det", "ferramenta", cap, tid))
            prop = operarios.honesto_v5(ds["extrato"], ds["razao"])
            lex.submeter(tid, "op-det", prop)
            d = lex.verificar(tid, "ex-det", prop)
            cont["conciliacao_" + d.codigo] += 1
            impressoes.append(hashlib.sha256(json.dumps(prop, sort_keys=True).encode()).hexdigest()[:12])
            cont["lancamentos_extrato"] += len(ds["extrato"])
            pac = residuo.pacote_humano(ds["extrato"], ds["razao"], prop)
            for it in pac:
                motivos[it["motivo"]] += 1
                cont["itens_residuo"] += 1
                cont["residuo_" + it["lado"]] += 1
                v = residuo.verdade_do_item(it, ds["gabarito"])
                if len(v) == 1:
                    cont["itens_com_par_1a1"] += 1
                    cont["candidatos_contem_verdade"] += next(iter(v)) in it["candidatos"]
                ok = residuo.acertou(residuo.sugestao_base(it), v)
                if ok is not None:
                    cont["julgaveis"] += 1
                    cont["base_acertou"] += ok
            if llm is None or not pac:
                continue
            # --- nota do LLM, num ANAIS próprio por tarefa (modo medição, achado M1) ---
            integro = integro and lex.anais.verificar()[0]
            lx = Lex(reg, Ledger(os.path.join(tmp, f"nota_{s:03d}.jsonl"), chave=b"chave-do-patronus"), orac)
            nid = f"N{s:03d}"
            lx.abrir_tarefa(nid, "nota_residuo", "op-llm", entrada={"pacote": pac})
            for cap in ("extrato.ler", "razao.ler"):
                lx.autorizar(Acao("op-llm", "ferramenta", cap, nid))
            try:
                t0 = time.time()
                bruto = llm.conversar(SISTEMA, pacote_texto(ds, pac), semente=s)
                tempos.append(time.time() - t0)
            except Exception as e:
                cont["erro_infra"] += 1
                print(f"{nid} ERRO_INFRA {e}")
                continue
            resp = extrair_json(bruto)
            if not isinstance(resp, dict):
                cont["nota_json_invalido"] += 1
                print(f"{nid} JSON_INVALIDO {bruto[:80]!r}")
                continue
            if "declaracao" in resp:
                dd = lx.autorizar(Acao("op-llm", "declaracao", str(resp.get("declaracao")), nid,
                                       {"evidencia": resp.get("evidencia", "")}))
                cont["nota_declarou_" + dd.codigo] += 1
                print(f"{nid} DECLAROU {resp.get('declaracao')} -> {dd.codigo}")
                continue
            lx.submeter(nid, "op-llm", resp)
            dn = lx.verificar(nid, "ex-det", resp)
            aceita = dn.codigo == "ACEITA"
            cont["nota_aceita" if aceita else "nota_rejeitada"] += 1
            if "op-llm" in lx.quarentena:
                cont["nota_incidente"] += 1
            falhas = residuo.verificar_nota(pac, resp)[1]
            for f in {x.split(":")[0] for x in falhas}:
                cont["nota_falha_" + f] += 1
            if aceita:
                sug = {x["id"]: x.get("sugestao") for x in resp["itens"]}
                for it in pac:
                    ok = residuo.acertou(sug.get(it["id"]), residuo.verdade_do_item(it, ds["gabarito"]))
                    if ok is not None:
                        cont["llm_julgaveis"] += 1
                        cont["llm_acertou"] += ok
                        cont["llm_mesma_que_base"] += (sug.get(it["id"]) or None) == residuo.sugestao_base(it)
            integro = integro and lx.anais.verificar()[0]
            print(f"{nid} {'ACEITA' if aceita else 'REJEITADA'} {sorted({x.split(':')[0] for x in falhas})}")
        integro = integro and lex.anais.verificar()[0]
        quarentena_det = "op-det" in lex.quarentena

    def pct(a, b):
        return round(100 * a / b, 1) if b else None
    res = {
        "tarefas": n, "modelo": modelo, "contagem": dict(sorted(cont.items())), "motivos": dict(sorted(motivos.items())),
        "residuo_pct_extrato": pct(cont["residuo_banco"], cont["lancamentos_extrato"]),
        "H1_recall_candidatos_pct": pct(cont["candidatos_contem_verdade"], cont["itens_com_par_1a1"]),
        "H2_base_acerto_pct": pct(cont["base_acertou"], cont["julgaveis"]),
        "quarentena_op_det": quarentena_det, "anais_integro": integro,
        "impressao_conciliacoes": hashlib.sha256("".join(impressoes).encode()).hexdigest()[:16],
    }
    res["veredito"] = {
        "D1": "PASSOU" if cont["conciliacao_ACEITA"] == n and not quarentena_det else "FALHOU",
        "H1": "PASSOU" if (res["H1_recall_candidatos_pct"] or 0) >= 90 else "FALHOU",
        "H2": "PASSOU" if (res["H2_base_acerto_pct"] or 0) >= 50 else "FALHOU"}
    if llm:
        notas = cont["nota_aceita"] + cont["nota_rejeitada"] + cont["nota_json_invalido"] + \
            sum(v for k, v in cont.items() if k.startswith("nota_declarou_"))
        res["P6_notas_aceitas_pct"] = pct(cont["nota_aceita"], notas)
        res["P7_llm_acerto_pct"] = pct(cont["llm_acertou"], cont["llm_julgaveis"])
        res["segundos_por_nota"] = round(sum(tempos) / len(tempos), 1) if tempos else None
        res["veredito"]["P6"] = "PASSOU" if (res["P6_notas_aceitas_pct"] or 0) >= 50 else "FALHOU"
    res["veredito"]["geral"] = "PASSOU" if all(v == "PASSOU" for v in res["veredito"].values()) else "FALHOU"
    return res


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    mod = sys.argv[sys.argv.index("--modelo") + 1] if "--modelo" in sys.argv else None
    if mod in args:
        args.remove(mod)
    k = int(args[0]) if args else 20
    r = main(k, mod)
    os.makedirs(os.path.join(RAIZ, "resultados"), exist_ok=True)
    nome = f"T6_hibrido{'_' + mod.replace(':', '_').replace('/', '_') if mod else ''}.json"
    with open(os.path.join(RAIZ, "resultados", nome), "w", encoding="utf-8") as f:
        json.dump(r, f, indent=2, ensure_ascii=False)
    print(json.dumps(r, indent=2, ensure_ascii=False))
