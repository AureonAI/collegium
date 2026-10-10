# 5 · TAREFAS: fases, prioridade e status

**Formato** (herdado do spec-kit): `[ID] [P?] [Hist] Descrição`. `[P]` marca o que pode correr em paralelo e `[Hist]` aponta a história do PRD.
**Status:** ✅ feito (com prova) · 🔶 parcial · ⬜ a fazer · ⛔ bloqueado.
**Regra:** uma tarefa só fica ✅ quando a coluna "Prova" aponta um comando reproduzível. Novas tarefas entram **no fim** (nunca se renumera).

## Fase F-1: Fundação (09/10/2026)

| ID | Hist | Descrição | Status | Prova |
|---|---|---|---|---|
| T001 | — | Ratificar o vídeo alegação por alegação | ✅ | `forge/ANALISE_VIDEO.md` |
| T002 | — | Incorporar o spec-kit (constituição, incerteza explícita, converge só por acréscimo) | ✅ | `forge/ANALISE_VIDEO.md` §4 |
| T003 | H1 | ANAIS: append-only + HMAC + âncora | ✅ | T2 |
| T004 | H2,H3 | LEX: 4 leis + ciclo da tarefa | ✅ | T1 |
| T005 | H4 | Autonomia calculada | ✅ | T3 |
| T006 | H1 | Pacote conciliação: gerador + oráculo + operários | ✅ | A4 |
| T007 | H2 | Goodhart no oráculo → erratas v0.1.1 → v0.1.3 | ✅ | ADVERSARIAL_LOG A4 |
| T008 | H6 | Adaptador Ollama + T4 (encanamento testado com servidor falso) | ✅ | `tests/test_adaptador.py` |
| T008b | — | Defeitos D1–D3 da autocrítica | ✅ | T1 E15/E16 |

## Fase F-1b: rodada GPT-Red (09/10/2026, v0.1.3–v0.1.4)

| ID | Hist | Descrição | Status | Prova |
|---|---|---|---|---|
| T028 | H2 | R1–R5: tarefa obrigatória, Mandato, assinatura humana, sorteio L1 imprevisível, canal tipado | ✅ | T1 E18–E20; `TestCorrecoes` |
| T029 | H4 | Autonomia com estabilidade + janela recente (A7b falsificado → confirmatório) | ✅ | T3 + `resultados/historico/` |
| T030 | — | ANAIS com trava entre processos (C1) | ✅ | `test_C1b_*` (4 processos) |
| T031 | H1 | Oráculo v0.1.4: grupos N:1, "revisar", parâmetros da entidade, índice | ✅ | A5 |
| T032 | H1 | G1–G5: falha fechada, entrega inválida, evidência selada, REGIMENTO assinado, admissão caduca | ✅ | `TestGPTRedFinal` |
| T033 | — | Reprodução em Python 3.10–3.13 com hashes idênticos | ✅ | `reproduzir.py --conferir` |
| T034 | — | Workflow multiplataforma (Windows/macOS/Linux) | ✅ 12/12 verdes (execução 38018942381) | `.github/workflows/evidencia.yml` |

## Fase F0: Validação de mercado e de reprodução (PRIORIDADE MÁXIMA)

| ID | Hist | Descrição | Status | Critério pré-registrado |
|---|---|---|---|---|
| T009 | — | **Missão 1 (Renato):** `python reproduzir.py --conferir` no Windows | 🔶 Windows já confirmado pelo GitHub (T034); rodar na máquina do Renato vira apenas preparação da Missão 2 | Todos "IGUAL" |
| T010 | H6 | **Missão 2 (Renato):** T4 (conciliação) e T4b (EXAME) com `qwen2.5-coder:1.5b`, `gemma3:4b`, `llama3.2:1b` | ⬜ | Previsões P1–P5 |
| T011 | — | **Missão 3 (Renato):** 10 conversas com escritórios | ⬜ | ≥ 3 SIM ao piloto pago |
| T012 | — | Busca de marca COLLEGIUM no INPI (classes 9 e 42) | ⬜ | Sem colidência |
| T013 | — | Consulta jurídica sobre a conciliação automatizada | ⬜ | Parecer escrito |
| T035 | — | Publicar o repositório (conta AureonAI) para o workflow rodar nas máquinas do GitHub | ✅ `github.com/AureonAI/collegium`, 12/12 verdes | 12 combinações verdes = primeira âncora externa |

## Fase F1: Do laboratório ao dado real (TRL 3 → 4)

| ID | Hist | Descrição | Status |
|---|---|---|---|
| T014 | H1 | Importadores OFX e CSV do ERP | ✅ (`tests/test_importadores.py`; falta testar com arquivos de bancos reais) |
| T015 | H1 | Repetir A4/A5 com **dados reais anonimizados** de 1 escritório (auditoria amostral como gabarito) | ⬜ |
| T016 | — | Isolamento C0 (`docker --network none` + egress por lista) com LLM real tentando sair | ⬜ |
| T017 | H1 | Âncora: comando `python -m collegium ancora` | 🔶 (falta publicar automaticamente) |
| T036 | — | PaddleOCR real com extratos escaneados (instalar no Windows; medir taxa de "revisar" e de saldo que não fecha) | ⬜ |

## Fase F2: Admissão por prova

| ID | Hist | Descrição | Status |
|---|---|---|---|
| T018 | H5 | Esquema do Dossiê | ✅ (`collegium/dossie.py`, `dossie_exemplo/`) |
| T019 | H5 | Gerador de EXAME; gabarito fora do agente | ✅ |
| T020 | H5 | Admissão = nota ≥ mínimo; caduca quando o REGIMENTO muda | ✅ |
| T037 | H5 | Medir se a nota do EXAME prevê a taxa de aceite (com LLM real) | ⬜ |

## Fase F3: Equipe completa e painel

| ID | Hist | Descrição | Status |
|---|---|---|---|
| T021 | H6 | [P] Adaptadores OpenAI-compatível e Anthropic | ⬜ |
| T022 | — | Rector e Actuarius | ✅ (`collegium/equipe.py`, T5) |
| T023 | — | Painel HTML | ✅ estático (`python -m collegium relatorio`) |
| T024 | — | Mensagens tipadas no `forum` | ✅ (todas as mensagens, não só a partir de L2) |
| T038 | — | Assinatura assimétrica (Ed25519) para o Patronus | ⬜ (exige dependência; decidir) |

## Fase F4: Piloto pago (TRL 4 → 6)

| ID | Descrição | Status |
|---|---|---|
| T025 | Piloto de 30 dias com 1 escritório, cobrando por conciliação aceita | ⬜ |
| T026 | Juiz externo: auditor independente confere amostra de recibos | ⬜ |
| T027 | Segundo pacote de ofício **só se** T025 pagar | ⬜ |

## Missão atual (uma de cada vez)

> **MISSÃO 1: reproduzir a evidência no seu Windows (cerca de 15 minutos)**
> 1. Descompacte o arquivo `COLLEGIUM_v0.1.4.zip` em `D:\COLLEGIUM`.
> 2. Abra o **Prompt de Comando** (tecla Windows → digite `cmd` → Enter).
> 3. Digite `cd /d D:\COLLEGIUM\collegium` e tecle Enter.
> 4. Digite `python -m unittest discover -s tests` e tecle Enter. **Esperado:** a última linha diz `OK` (60 testes).
> 5. Digite `python reproduzir.py --conferir` e tecle Enter. Leva de 5 a 10 minutos; o T3 é o mais demorado.
> 6. **Me reporte:** a primeira linha (versão do Python) e as 6 linhas. Cada uma deve terminar em `IGUAL`.
> **Por que importa:** é a primeira vez que o código roda num sistema operacional diferente do meu. Se algo der `DIVERGE`, isso também é resultado: me mande a linha exata.
