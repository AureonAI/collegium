# COLLEGIUM v0.2.0

**Núcleo de governança para equipes de trabalho de IA (agentes, código ou pessoas): admitidas por conduta, governadas por constituição executável, com autonomia conquistada por histórico medido e trabalho entregue com recibo que o cliente confere sozinho.**

Nasceu da inversão do incidente OpenAI/Hugging Face (2026). Lá, agentes que "se recusaram a falhar" trapacearam. Aqui, declarar "impossível" é dever, e inventar é fraude.

[![evidencia](https://github.com/AureonAI/collegium/actions/workflows/evidencia.yml/badge.svg)](https://github.com/AureonAI/collegium/actions/workflows/evidencia.yml)

## Rodar (Windows, Linux, macOS; Python 3.10+; nenhuma instalação extra)

```
python -m unittest discover -s tests             # suíte completa → OK
python reproduzir.py --conferir                  # refaz toda a evidência e compara com resultados/HASHES.txt
python -m collegium                              # todos os comandos (assinar, recibo, fatura, anonimizar, portão…)
python -m collegium conformidade tres_vias       # um ofício passa na suíte de conformidade?
python experimentos/t4_llm_ollama.py gemma3:4b 20 --medicao [--esquema] [--tentativas 3]   # LLM real (Ollama)
```

## O que existe (v0.2.0)

| Camada | O quê | Onde |
|---|---|---|
| **Constituição executável** | LEX: negação por padrão, dever de declarar, separação de poderes (o LEX roda o oráculo), autonomia medida, plano selado, destinos e argumentos confiáveis, orçamento real, tentativas com devolutiva, canários, quatro olhos | `collegium/lex.py` |
| **Registro e prova** | ANAIS encadeado (JSONL ou SQLite, idênticos), árvore de Merkle RFC 9162, recibo e fatura que o cliente confere offline | `collegium/ledger*.py`, `merkle.py`, `recibo.py`, `fatura.py` |
| **Identidade** | Ed25519 só com biblioteca padrão (vetores RFC 8032), quórum para mudar regras, revogação, digest do modelo | `collegium/ed25519.py`, `lex.py` |
| **Mediação** | Portão MCP (especificação 2026-07-28 + legado) com ficha efêmera; executor isolado com falha fechada | `collegium/portao.py`, `isolamento.py` |
| **Agnosticismo** | Kit de ofício + suíte de conformidade com teste de mutação; 2 ofícios no mesmo núcleo | `collegium/oficio.py`, `pacotes/conciliacao`, `pacotes/tres_vias` |
| **Sem oráculo** | Garantia estatística (Learn-then-Test, Clopper-Pearson, vigia SPRT), júri e canários | `collegium/garantia.py` |
| **Aprender o nicho** | Decisões humanas → proposta → backtest → só entra com quórum | `collegium/aprendizado.py` |
| **Privacidade** | Anonimizador BR (CPF, CNPJ alfanumérico, telefone, conta, nomes) e cofre com eliminação LGPD | `collegium/privacidade.py` |
| **Entrada BR** | OFX, CSV, OCR (opcional), CNAB 240 Segmento E, Open Finance Brasil | `pacotes/conciliacao/importadores.py` |
| **Humano** | Fila com prazo, quatro olhos, medida de "carimbo"; admissão por conduta | `collegium/fila.py`, `conduta.py` |
| **Confiança** | Atacante adaptativo, verificação exaustiva limitada, pré-registro selado, pacote reprodutível e assinado + SBOM | `experimentos/a6_*`, `t9_*`, `collegium/preregistro.py`, `ferramentas/release.py` |

Mapas: `docs/2_ARQUITETURA.md` (estrutura e decisões) · `docs/CONFORMIDADE.md` (OWASP ASI01–10, LGPD) · `SECURITY.md`.

## Estado honesto
**TRL medido: 3.** Tudo acima roda e se reproduz em **Windows, macOS e Linux × Python 3.10–3.13** em máquinas do GitHub.
Com LLM real (3 modelos ≤4B, na máquina do autor): a contenção segurou 100% das fraudes, mas **nenhum modelo fez o trabalho**
(0/79 conciliações); um código determinístico faz 20/20 — por isso a conciliação é feita por código e o LLM fica no resíduo.
**Ainda sem dado real e sem cliente pagante.** Cada ataque que venceu está em `forge/ADVERSARIAL_LOG.md`, com data.

## In English (summary)
COLLEGIUM is a model-agnostic, dependency-free governance kernel for AI work teams: deny-by-default actions behind an MCP gateway,
a duty to declare impossibility, separation of powers (the kernel runs the oracle), earned autonomy, Ed25519 human sign-off with quorum,
Merkle receipts and invoices the client verifies offline, Brazilian PII pseudonymization with erasure, statistical guarantees for
oracle-less work, governed learning, adaptive red-teaming and bounded exhaustive checking. Status: TRL 3 (lab). Real small LLMs were
contained but could not do the work; no real data or paying customer yet.

Licença: **pendente de decisão do autor** (até lá, todos os direitos reservados).
