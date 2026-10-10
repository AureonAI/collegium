# 2 · ARQUITETURA — camadas, stack e pastas

## 1. Princípio de desenho

**O agente é não confiável por construção.** Toda a arquitetura parte do incidente de 2026: o agente vai tentar o atalho, o canal paralelo e a persistência. Por isso a segurança não pode depender de o agente "querer" obedecer. Ela vive em camadas que o agente **não controla**:

```
            ┌───────────────────────────────────────────────────────────┐
  HUMANO    │ PATRONUS — aprova julgamentos, guarda a chave e o gabarito│
            └──────────────▲───────────────────────────▲────────────────┘
                           │ fila de decisões          │ âncora da cabeça do ANAIS
┌──────────────────────────┴───────────────────────────┴────────────────────────┐
│ C4  PAINEL / CLI          fila do humano · recibos · matriz de autonomia      │  folha
├───────────────────────────────────────────────────────────────────────────────┤
│ C3  OFFICIUM (agentes)    Rector · Operarii · Examinator · Actuarius          │  folha
│     adaptadores de modelo: Ollama (local) · OpenAI-compat · Anthropic         │
├───────────────────────────────────────────────────────────────────────────────┤
│ C2  PACOTES DE OFÍCIO     conciliação bancária (v0.1) · próximo: contas a     │  folha
│     cada pacote = dados + ORÁCULO determinístico + operários de referência    │
├───────────────────────────────────────────────────────────────────────────────┤
│ C1  LEX (núcleo)          4 leis · ciclo da tarefa · autonomia calculada      │  PRIMITIVO
│     ANAIS (ledger)        append-only · hash encadeado · HMAC · âncora        │  PRIMITIVO
├───────────────────────────────────────────────────────────────────────────────┤
│ C0  ISOLAMENTO DE SO      container/VM sem rede · egress por lista · usuário  │  PRÉ-REQUISITO
│                           sem privilégio · segredos fora do container        │  (não é código nosso)
└───────────────────────────────────────────────────────────────────────────────┘
```

**Por que C0 é pré-requisito, e não opcional:** no incidente, os agentes não violaram a política. Eles **contornaram a infraestrutura** com um zero-day no proxy. Um núcleo de política em processo (o LEX) não impede isso. Ver ADVERSARIAL_LOG A1.

## 2. Papéis da equipe (C3)

| Papel | Faz | Não pode | Lição de origem |
|---|---|---|---|
| **Rector** (coordenador) | distribui tarefas da PAUTA, responde no `forum` | aprovar, verificar, mudar o REGIMENTO | Project Vend: o "CEO-agente" agregou pouco; aqui ele só roteia |
| **Operarius** (executor) | lê dados, propõe entregas, declara impossibilidade | verificar o próprio trabalho, sair do escopo | Incidente OpenAI: persistência e atalho |
| **Examinator** (verificador) | roda o oráculo determinístico ou, sem oráculo, um modelo de **outra família** | produzir entregas que ele mesmo verificaria | Project Vend: mesmo modelo = mesmos pontos cegos |
| **Actuarius** (escrivão) | resume o ANAIS em MEMÓRIA legível para humanos | reescrever o ANAIS | spec-kit: "converge" só acrescenta |
| **Patronus** (humano) | aprova julgamentos, detém a chave HMAC e o gabarito do EXAME | — | Limite terminal: nada se autocertifica |

## 3. Ciclo de vida de uma tarefa (máquina de estados — `lex.py`)

```
ABERTA ──(passos ≤ orçamento)──► SUBMETIDA ──► ACEITA ──► LIBERADA (autonomia ≥ exigida)
  │                                  │            └──────► AGUARDA_HUMANO ──► LIBERADA | REJEITADA
  │                                  └──► REJEITADA (falha comum: conta no histórico)
  │                                  └──► REJEITADA + INCIDENTE (fabricação/conservação → quarentena, L0)
  └──(declara com evidência)──► DECLARADA ──(qualquer ação além disso)──► INCIDENTE "PERSISTENCIA"
```

## 4. Admissão numa entidade: o Dossiê do Ente (fractal dos 6 arquivos)

| Arquivo do desenvolvimento (`docs/`) | Arquivo do Dossiê do Ente | Conteúdo para a entidade |
|---|---|---|
| 1 PRD | **MANDATO** | o que a entidade faz, para quem, e o que a equipe NÃO fará |
| 2 ARQUITETURA | **ORGANOGRAMA** | papéis, alçadas, quem aprova o quê |
| 3 REGRAS | **REGIMENTO** (`regimento.json`) | constituição executável: capacidades, canais, orçamentos, limiares |
| 4 DESIGN | **VOZ** | tom, marca e modelos de documento da entidade |
| 5 TAREFAS | **PAUTA** | o que fazer, prioridade, prazo, classe de tarefa |
| 6 MEMÓRIA | **ANAIS** | livro-razão selado + resumo legível do que foi feito e onde parou |
| — | **EXAME** (novo) | perguntas geradas do Dossiê; gabarito só com o Patronus; nota mínima para admitir |

## 5. Stack (e por que cada escolha)

| Camada | Escolha | Motivo verificável |
|---|---|---|
| Núcleo C1 | **Python 3.10+ só com biblioteca padrão** | Zero dependência = auditável por terceiros, roda em Windows/Linux/macOS, sem cadeia de suprimentos a envenenar |
| ANAIS | JSON Lines + SHA-256 + HMAC-SHA256 (v0.1) → SQLite em modo WAL (v0.3) | Texto legível por humano; HMAC impede reescrever a cadeia sem a chave (T2) |
| Testes | `unittest` (padrão) + experimentos com sementes fixas | Reproduzível por estranhos com um comando |
| Modelos (C3) | Adaptadores: Ollama (local), API compatível com OpenAI, Anthropic | Agnóstico e soberano; troca de modelo sem tocar no LEX |
| Ferramentas (C3) | Servidores MCP por trás do LEX: toda chamada vira uma `Acao` | Padrão aberto; o LEX vira a "alfândega" de cada ferramenta |
| Isolamento C0 | Docker/Podman com `--network none` + proxy de egress com lista | O incidente mostrou que confinamento é infraestrutura |
| Painel C4 | HTML estático + leitura do ANAIS (v0.2) | Sem servidor obrigatório; pode ser aberto offline |

## 6. Estrutura de pastas (v0.1.4)

```
collegium/
├── README.md · AGENTS.md          como rodar · instrução para agentes de código
├── reproduzir.py                  1 comando → toda a evidência + HASHES.txt (--conferir compara)
├── regimento.exemplo.json         REGIMENTO de exemplo
├── dossie_exemplo/                Dossiê do Ente: MANDATO, ORGANOGRAMA, REGIMENTO, VOZ, PAUTA
├── .github/workflows/evidencia.yml   Windows/macOS/Linux × Python 3.10–3.13 (âncora externa)
├── collegium/                     ── PRIMITIVO (C1) ──
│   ├── ledger.py                  ANAIS: append-only, HMAC, âncora, trava entre processos
│   ├── lex.py                     4 leis + Mandato + assinatura humana + REGIMENTO assinado
│   ├── autonomia.py               Wilson + estabilidade + janela recente (L0–L3)
│   ├── dossie.py                  Dossiê + EXAME de admissão (gabarito fora do agente)
│   ├── equipe.py                  Rector (roteia) + Actuarius (MEMÓRIA.md e painel.html)
│   ├── adaptadores.py             Ollama (local)
│   └── __main__.py                CLI do Patronus: verificar · ancora · relatorio · assinar
├── pacotes/conciliacao/           ── FOLHA (C2) ──
│   ├── oraculo.py                 v0.1.0→v0.1.4 (grupos N:1, "revisar", parâmetros da entidade)
│   ├── residuo.py                 decisão A: pacote do humano + oráculo da nota do LLM (T039/T040)
│   ├── importadores.py            OFX, CSV brasileiro, PaddleOCR (opcional) + prova de saldo
│   ├── dados.py                   geradores SINTÉTICOS com gabarito (gerar, gerar_v2)
│   └── operarios.py               operários roteirizados honestos e adversários
├── experimentos/                  T1 · T2 · T3 · A4 · A5 · T5 (+ T4/T4b com LLM real, no Windows)
├── resultados/                    JSON + HASHES.txt + historico/ (resultados falsificados arquivados)
├── tests/                         73 testes unittest
├── docs/                          os 6 arquivos
└── forge/                         EVIDENCE · ABSTRACT · ADVERSARIAL_LOG · PRIMITIVE · ANALISE_VIDEO
```

## 7. Decisões de arquitetura (ADR resumido)

| ADR | Decisão | Alternativa rejeitada | Por quê |
|---|---|---|---|
| 001 | Núcleo determinístico, sem LLM dentro | "Agente supervisor" LLM | Um supervisor LLM herda os pontos cegos e é manipulável (Project Vend) |
| 002 | Autonomia **calculada** do ANAIS | Autonomia configurada pelo cliente | Configuração é autodeclaração; o histórico é evidência |
| 003 | O "mural" vira canal oficial selado | Proibir toda comunicação entre agentes | Proibir empurra a comunicação para canais ocultos (incidente: nomes de diretório) |
| 004 | Cunha com oráculo determinístico | Começar por tarefa de julgamento | Sem verificador não há como cobrar por resultado honestamente |
| 005 | Fabricação = incidente crítico (não "erro") | Tratar como rejeição comum | Erro honesto e fraude têm custos diferentes para quem compra |
| 006 | Identificadores em PT-BR na v0.1 | Inglês desde já | Quem opera é falante de PT-BR; custo declarado no eixo GLOBAL |
| 007 | O LEX **executa** o oráculo; o veredito do verificador é testemunho | Confiar no verificador | Defeito D1: verificador mentiroso fazia fabricação passar |
| 008 | Estado reconstruído do ANAIS a cada início | Estado em memória | Defeito D2: reiniciar apagava quarentena |
| 009 | Agentes recebem `Mandato`; humanos assinam (HMAC) | Identidade por texto | Ataque R2. Limite: chave simétrica; Ed25519 exigiria dependência |
| 010 | Rector é código, não LLM | "CEO-agente" | Project Vend: o CEO-agente compartilhava os pontos cegos |
| 011 | OCR (PaddleOCR) é adaptador opcional, nunca dependência do núcleo | Embutir OCR | Dependência pesada (motor de inferência e modelos); soberania: quem não usa, não paga |
| 012 | Prova de saldo na ENTRADA (saldo inicial + Σ = saldo final) | Confiar no importador | OCR errado com confiança alta só é pego pela conservação |
| 013 | Grupos só com documento de todos os membros OU subconjunto único | Aceitar qualquer soma que feche | Soma que fecha por coincidência é o Goodhart do N:1 |
| 014 | **Decisão A (10/10/2026, Renato):** onde há lei de conservação, o operário é **código** (`honesto_v5`, família "deterministico", sob o mesmo LEX); o LLM só anota o **resíduo** (classe `nota_residuo`, oráculo próprio) e nunca cria par | LLM como operário da conciliação | LLMs reais ≤4B: 0/79 aceitas; código: 20/20. Custo declarado: a "equipe de agentes" vira híbrida nesta frente; o valor do LLM no resíduo ainda não foi medido (dados sintéticos não têm sinal semântico) |
