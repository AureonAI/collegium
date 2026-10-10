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
| T011 | — | **Missão 3 (Renato):** 10 conversas com escritórios, roteiro em `docs/ROTEIRO_ENTREVISTA.md` | 🔶 roteiro pronto | S1: ≥3/10 aceitam piloto com dado anonimizado · S2: ≥3/10 dão custo concreto (registrado em 10/10/2026) |
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
| T039 | — | Decisão A: operário determinístico sob o LEX + pacote do humano (motivo e candidatos por pendência) | ✅ (`collegium_oficios/conciliacao/residuo.py`, `tests/test_residuo.py`) |
| T040 | — | Classe `nota_residuo`: LLM anota o resíduo; oráculo barra id inventado, sugestão fora da lista e omissão | ✅ (invariante: a nota nunca altera a conciliação) |
| T041 | — | T6 híbrido: parte determinística no `reproduzir.py`; parte LLM na máquina do Renato | ✅ (gemma3:4b: 13/20 notas aceitas; nenhum ganho sobre a base) |
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

## Fase SA: estado da arte (pedido de 10/10/2026; ver a resposta da sessão e `forge/ADVERSARIAL_LOG.md`)

Critério geral: cada item só fica ✅ com teste que falharia sem ele e com um ataque registrado contra ele. Nível 0 = sem isto não é estado da arte; Nível 1 = completa o que o projeto promete; Nível 2 = método e confiança.

| ID | Nível | Item | Pronto quando | Status |
|---|---|---|---|---|
| T042 | 0 | Ed25519 só com biblioteca padrão (RFC 8032) + chave pública do humano no REGIMENTO + quórum m-de-n + revogação | vetores oficiais da RFC passam; o núcleo não conhece chave privada humana | ✅ (`collegium/ed25519.py`, vetores RFC 8032; `tests/test_patronus.py`) |
| T043 | 0 | Recibo verificável offline: árvore de Merkle (RFC 9162), cabeça assinada, provas de inclusão e consistência | um verificador sem acesso ao sistema confere um recibo e detecta reescrita do histórico | ✅ (`collegium/merkle.py`, `collegium/recibo.py`; raízes de referência do CT) |
| T044 | 1 | Anonimizador BR (CPF/CNPJ com dígito verificador, e-mail, telefone, conta, nomes) com pseudônimo por titular | falha fechada: arquivo com risco residual não sai sem revisão | ✅ (`collegium/privacidade.py`; CNPJ alfanumérico; conciliação idêntica antes e depois) |
| T045 | 1 | Cofre de titulares: eliminação LGPD (art. 18) por destruição de chave, sem tocar no ANAIS | após eliminar, o pseudônimo não é mais ligável ao titular | ✅ (`Cofre.eliminar`; ANAIS intocado) |
| T046 | 0 | Portão: servidor MCP mediador, tokens efêmeros por tarefa, executor isolado que falha fechado | agente sem o portão não tem ferramenta; token fora da tarefa é negado | ✅ código (`collegium/portao.py` MCP 2026-07-28 + legado; `collegium/isolamento.py`); 🔶 Docker real = missão no Windows (T016) |
| T047 | 0 | Plano selado na abertura (fluxo de controle confiável) + destinos confiáveis para argumentos | injeção no dado não muda capacidade nem destino | ✅ (`plano` na abertura; `destinos` no REGIMENTO; saída marcada `nao_confiavel`) |
| T048 | 0 | Identidade de modelo por impressão digital (digest); admissão caduca com troca de modelo | "qwen-falso" não herda a linhagem qwen | ✅ (`modelo.digest` + `Lex.atestar_modelo`; `Ollama.digest()`) |
| T049 | 0 | Kit de ofício + suíte de conformidade com escore de mutação + 2º ofício | dois ofícios passam na mesma suíte, sem mudar o núcleo | ✅ (`collegium/oficio.py` + `collegium_oficios/tres_vias`; 2 ofícios conformes, mutação 741/741 não equivalentes em 200 sementes; controle negativo) |
| T050 | 0 | Garantia estatística para classes sem oráculo (júri calibrado, Learn-then-Test, SPRT) | simulação: taxa de violação da garantia ≤ δ | ✅ (`collegium/garantia.py`, T7: G1/G2 passaram; G3 falsificada e reconfirmada com semente nova) |
| T051 | 0 | Atacante adaptativo contra o LEX (busca guiada pelas decisões) + missão AgentDojo | 0 ações proibidas autorizadas; AgentDojo = missão externa | ✅ código (A6: 6 quebras + 1 burla corrigidas; 2ª confirmatória 0 vitórias); 🔶 AgentDojo = missão externa |
| T052 | 1 | Aprendizado governado: decisões humanas do resíduo viram propostas de regra, com backtest e assinatura | regra aprendida reduz o resíduo sem par errado no backtest | ✅ (`collegium/aprendizado.py` + minerador de janela; T8: L1–L4 passaram; regra só entra com quórum) |
| T053 | 1 | Tentativas com devolutiva só de código e checagens ocultas | fraude continua sem segunda chance | ✅ (reabertura com devolutiva só de códigos; `falhas_ocultas`; fraude não reabre; T9 com tentativas: 0 violações; `--tentativas` no T4) |
| T054 | 1 | Saída estruturada por esquema JSON no adaptador | — | ✅ (`esquema=` no adaptador; `--esquema` no T4/T4b — efeito real = missão) |
| T055 | 1 | Admissão por conduta (tarefas-isca) + canários sorteados em produção | canário errado gera incidente | ✅ (`abrir_canario`, `sortear_canario`, `collegium/conduta.py`, iscas da conciliação) |
| T056 | 1 | Orçamento de tokens, tempo e custo por tarefa com corte duro | estouro = BLOQUEADO selado | ✅ (`registrar_consumo`; orçamento por classe; `Ollama.ultimo_uso`) |
| T057 | 1 | Fila do humano: evidência, prazo, 4 olhos acima da alçada, medida de "carimbo" | — | ✅ (quatro olhos + veto no LEX; `collegium/fila.py` com prazo e medida de carimbo) |
| T058 | 1 | ANAIS em SQLite por ente + telemetria (convenções GenAI) + backup verificado | mesma cadeia e mesma raiz Merkle que o JSONL | ✅ (`collegium/ledger_sqlite.py` idêntico ao JSONL; concorrência; `backup_verificado`; `collegium/telemetria.py`) |
| T059 | 1 | Importadores CNAB 240 (extrato) e Open Finance Brasil | prova de saldo em ambos | ✅ (`ler_cnab240` Segmento E com prova de saldo e somatórios; `ler_open_finance` com fuso de Brasília) |
| T060 | 2 | Verificação exaustiva limitada da máquina de estados do LEX + fuzzing das leis | nenhuma sequência viola os invariantes até a profundidade k | ✅ (`experimentos/t9_exaustivo.py`: profundidade 7, 0 violações; 4 defeitos plantados encontrados) |
| T061 | 2 | Pré-registro selado com testemunha externa | — | ✅ (`collegium/preregistro.py`; testemunha = anotação do GitHub a cada envio); limite: sem RFC 3161 |
| T062 | 2 | Cadeia de suprimentos: SECURITY.md, SBOM, release assinada (LICENSE = decisão do Renato) | — | ✅ (`SECURITY.md`, `ferramentas/release.py`: pacote reprodutível e assinado + SBOM CycloneDX); 🔶 LICENSE = decisão do Renato |
| T063 | 2 | Mapa de conformidade (OWASP ASI01–ASI10, LGPD) | — | ✅ (`docs/CONFORMIDADE.md`: OWASP ASI01–10, LGPD, PL 2338, AI Act) |
| T064 | 2 | Métricas de valor + fatura derivada dos recibos | fatura conferível pelo cliente | ✅ (`collegium/fatura.py`: métricas do ANAIS + fatura conferível pelo cliente) |

## Fase P: do núcleo ao produto (10/10/2026, rodada 6 do Red Team)

Critério: o trabalho que se vende roda de ponta a ponta, por quem não é o autor, fora da pasta do projeto.

| ID | Item | Pronto quando | Status |
|---|---|---|---|
| T065 | Planilha real de banco e ERP: cabeçalho achado sozinho, CP-1252, BOM, D/C, total e saldo; convenção de sinal pelos dados | os ataques R6-1..R6-5 falham | ✅ (`ler_planilha`, `detectar_convencao`; `tests/test_planilha_real.py`) |
| T066 | `collegium conciliar`: arquivos → relatório, pendências, pares, resumo, recibo; sanidade S1/S2/S3 com BLOQUEADO declarado | kit de demonstração com 0 par errado contra a verdade | ✅ (`piloto.py`, `execucao.py`; `tests/test_piloto.py`; oráculo v0.1.5 = R6-6) |
| T067 | Prova de completude: mapa assinado de tarefas no recibo e na fatura; auditoria da cabeça | recibo não esconde a recusa humana; fatura não cobra canário nem recusada | ✅ (`collegium/mapa.py`; `tests/test_mapa.py`; R6-7, R6-8; fecha R-1 e F-L) |
| T068 | Instalável por `pip`, comando `collegium`, kit empacotado (`collegium exemplo`), versão única | ciclo inteiro rodado como estranho no CI de 3 sistemas | ✅ (`pyproject.toml`; `ferramentas/instalacao_limpa.py`; R6-9..R6-12) · 🔶 prova no Windows do Renato = Missão 4 |
| T069 | Documentação na v0.3.0 (README produto primeiro, ARQUITETURA, ADR 025–028, EVIDENCE, MEMÓRIA, ADVERSARIAL_LOG) | nenhum documento contradiz o código | ✅ |
| T070 | Red Team rodada 6, continuação: arquivos hostis e usuário descuidado | cada ataque vira teste | ✅ (`tests/test_rodada6_hostil.py`; R6-14..R6-18; sondagem com 13 ataques, 5 venceram) |
| T072 | Escala: conciliação de dezenas de milhares de lançamentos em segundos, com resultado idêntico | 10 mil < 3 s; teste diferencial contra a versão antiga | ✅ (`tests/test_escala.py`; 30 mil: 60 s → 7,8 s) |
| T071 | `collegium aprovar`: humano com chave Ed25519 registrado no 1º uso; aprovação assinada → LIBERADA → aparece no recibo | ciclo conciliar → aprovar → recibo conferido offline | ✅ (`execucao.aprovar`; `tests/test_piloto.py`, `instalacao_limpa.py`) |

## Missão atual (uma de cada vez)

> **MISSÃO 4: o produto no SEU Windows, como um cliente faria (T068), Renato**
> 1. Abra o PowerShell (não precisa estar na pasta do projeto). Rode, um de cada vez:
>    `python -m pip install https://github.com/AureonAI/collegium/archive/refs/heads/main.zip`
>    `cd ([Environment]::GetFolderPath("Desktop"))`   (vai para a sua Área de Trabalho, com ou sem OneDrive)
>    `python -m collegium exemplo demo`
>    `python -m collegium conciliar --extrato demo\extrato.ofx --razao demo\razao_contabil.csv --saida resultado`
> 2. Abra `resultado\relatorio.html` (duplo clique na Área de Trabalho). Mande o arquivo para o seu celular e abra lá também.
> 3. **Como validar:** a 1ª linha da resposta deve começar com `CONCILIADO: 47 casamentos`. O relatório deve abrir sem nada
>    quebrado e mostrar os números 47, 15 e 12.
> 4. **O que me relatar:** cole a saída do PowerShell inteira; diga se o relatório abriu no computador e no celular, e a
>    primeira coisa que você não entendeu ao olhar para ele (essa é a pergunta que o cliente vai fazer).
> **Por que importa:** é a primeira prova do produto fora das máquinas do GitHub, e é o que você vai MOSTRAR nas entrevistas.
> Depois dela: Missão 3 (entrevistas, `docs/ROTEIRO_ENTREVISTA.md`), agora com o relatório aberto na mesa.
> Missões 1, 2 e 2b concluídas: ver MEMÓRIA.
