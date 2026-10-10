# COLLEGIUM v0.3.0

**Conciliação bancária em que nada é aceito na palavra: o código concilia, um oráculo independente confere, o humano aprova com assinatura digital, e o cliente confere o recibo sozinho, sem acesso ao sistema.**

Por baixo, um núcleo de governança para equipes de trabalho de IA (agentes, código ou pessoas): admitidas por conduta, governadas por constituição executável, com autonomia conquistada por histórico medido. Nasceu da inversão do incidente OpenAI/Hugging Face (2026). Lá, agentes que "se recusaram a falhar" trapacearam. Aqui, declarar "impossível" é dever, e inventar é fraude.

[![evidencia](https://github.com/AureonAI/collegium/actions/workflows/evidencia.yml/badge.svg)](https://github.com/AureonAI/collegium/actions/workflows/evidencia.yml)

## Experimentar em 2 minutos (Windows, Linux, macOS; Python 3.10+; nenhuma dependência)

```
python -m pip install https://github.com/AureonAI/collegium/archive/refs/heads/main.zip
python -m collegium exemplo demo
python -m collegium conciliar --extrato demo/extrato.ofx --razao demo/razao_contabil.csv --saida resultado
```
(Não precisa de Git. Depois de instalado, `collegium ...` também funciona se a pasta de scripts do Python estiver no PATH.)
Abra `resultado/relatorio.html`. O kit de demonstração é **sintético**, mas traz as armadilhas de arquivos reais:
razão na convenção contábil (sinais invertidos), CP-1252, título antes da tabela, linha de total, documento escrito de
quatro jeitos e texto hostil (fórmula de Excel, `<script>`).

**O que entra:** extrato em OFX, CNAB 240, JSON do Open Finance Brasil ou planilha; razão do ERP em CSV/TXT
(UTF-8, CP-1252 ou "Texto Unicode" do Excel). **O que ainda não entra:** PDF (o texto de um PDF não garante os
números: exporte OFX ou CSV no internet banking) e .xlsx/.xls (no Excel, "Salvar como CSV"); a ferramenta diz isso
ao recusar. **O que sai:** relatório (abre no celular), `pendencias.csv`, `pares.csv`,
`resumo.json` e, com chave, `recibo.json` assinado. **Quando não serve, diz:** saldo que não fecha, período que não bate ou
razão de outra conta resultam em BLOQUEADO, com o motivo; nada é entregue como se estivesse certo.

Ciclo completo (aprovação humana assinada e recibo conferido pelo cliente): `collegium` sem argumentos mostra todos os comandos.

## Desenvolver e reproduzir a evidência

```
python -m unittest discover -s tests             # suíte completa → OK
python ferramentas/pre_envio.py --completo       # suíte em 3 sementes + instalação limpa + reprodução dos hashes
python reproduzir.py --conferir                  # refaz toda a evidência e compara com resultados/HASHES.txt
python -m collegium conformidade tres_vias       # um ofício passa na suíte de conformidade?
python experimentos/t4_llm_ollama.py gemma3:4b 20 --medicao [--esquema] [--tentativas 3]   # LLM real (Ollama)
```

## O que existe (v0.3.0)

| Camada | O quê | Onde |
|---|---|---|
| **Produto: conciliação** | `collegium conciliar` / `aprovar`: arquivos reais → relatório, pendências, recibo; convenção de sinal decidida pelos dados; sanidade (saldo, período, conta) com BLOQUEIO declarado | `collegium_oficios/conciliacao/piloto.py`, `collegium/execucao.py` |
| **Constituição executável** | LEX: negação por padrão, dever de declarar, separação de poderes (o LEX roda o oráculo), autonomia medida, plano selado, destinos e argumentos confiáveis, orçamento real, tentativas com devolutiva, canários, quatro olhos | `collegium/lex.py` |
| **Registro e prova** | ANAIS encadeado (JSONL ou SQLite, idênticos), árvore de Merkle RFC 9162, recibo e fatura que o cliente confere offline, com **prova de completude** (mapa assinado de tarefas: nada da história da tarefa pode ser escondido) e auditoria do mapa | `collegium/ledger*.py`, `merkle.py`, `mapa.py`, `recibo.py`, `fatura.py` |
| **Identidade** | Ed25519 só com biblioteca padrão (vetores RFC 8032), quórum para mudar regras, revogação, digest do modelo | `collegium/ed25519.py`, `lex.py` |
| **Mediação** | Portão MCP (especificação 2026-07-28 + legado) com ficha efêmera; executor isolado com falha fechada | `collegium/portao.py`, `isolamento.py` |
| **Agnosticismo** | Kit de ofício + suíte de conformidade com teste de mutação; 2 ofícios no mesmo núcleo | `collegium/oficio.py`, `collegium_oficios/conciliacao`, `collegium_oficios/tres_vias` |
| **Sem oráculo** | Garantia estatística (Learn-then-Test, Clopper-Pearson, vigia SPRT), júri e canários | `collegium/garantia.py` |
| **Aprender o nicho** | Decisões humanas → proposta → backtest → só entra com quórum | `collegium/aprendizado.py` |
| **Privacidade** | Anonimizador BR (CPF, CNPJ alfanumérico, telefone, conta, nomes) e cofre com eliminação LGPD | `collegium/privacidade.py` |
| **Entrada BR** | OFX, CSV, OCR (opcional), CNAB 240 Segmento E, Open Finance Brasil | `collegium_oficios/conciliacao/importadores.py` |
| **Humano** | Fila com prazo, quatro olhos, medida de "carimbo"; admissão por conduta | `collegium/fila.py`, `conduta.py` |
| **Confiança** | Atacante adaptativo, verificação exaustiva limitada, pré-registro selado, pacote reprodutível e assinado + SBOM | `experimentos/a6_*`, `t9_*`, `collegium/preregistro.py`, `ferramentas/release.py` |

Mapas: `docs/2_ARQUITETURA.md` (estrutura e decisões) · `docs/CONFORMIDADE.md` (OWASP ASI01–10, LGPD) · `SECURITY.md`.

## Estado honesto
**TRL medido: 3.** Tudo acima roda e se reproduz em **Windows, macOS e Linux × Python 3.10–3.14** em 15 máquinas do GitHub, incluindo instalação por `pip` e o ciclo do produto rodado fora da pasta do projeto.
Com LLM real (3 modelos ≤4B, na máquina do autor): a contenção segurou 100% das fraudes, mas **nenhum modelo fez o trabalho**
(0/79 conciliações); um código determinístico faz 20/20 — por isso a conciliação é feita por código e o LLM fica no resíduo.
**Ainda sem dado real e sem cliente pagante.** Cada ataque que venceu está em `forge/ADVERSARIAL_LOG.md`, com data.

## In English (summary)
COLLEGIUM is bank reconciliation where nothing is taken on trust (deterministic matching, independent oracle, signed human approval, receipts the client verifies offline with proof of completeness), built on a model-agnostic, dependency-free governance kernel for AI work teams: deny-by-default actions behind an MCP gateway,
a duty to declare impossibility, separation of powers (the kernel runs the oracle), earned autonomy, Ed25519 human sign-off with quorum,
Merkle receipts and invoices the client verifies offline, Brazilian PII pseudonymization with erasure, statistical guarantees for
oracle-less work, governed learning, adaptive red-teaming and bounded exhaustive checking. Status: TRL 3 (lab). Real small LLMs were
contained but could not do the work; no real data or paying customer yet.

Licença: **pendente de decisão do autor** (até lá, todos os direitos reservados).
