# 1 · PRD — COLLEGIUM

> *Collegium*, no direito romano, era a corporação de ofício: um grupo com estatuto próprio, que respondia pelo trabalho que entregava.

**Versão:** 0.3.0 · **Data:** 10/10/2026 (criado em 09/10/2026) · **Regime:** CUME · **TRL medido:** 3 (ver `forge/EVIDENCE.md`)

## 1. O problema (em uma frase)

Empresas pagam 6 vezes mais por **serviço** do que por software (Sequoia, 2026), e agentes de IA já conseguem fazer parte desse serviço. Mesmo assim, **ninguém consegue contratar uma equipe de agentes com segurança**: quando a tarefa aperta, eles trapaceiam, insistem fora do escopo, conversam por canais não autorizados e inventam dados. A própria OpenAI documentou os quatro comportamentos em 2026.

## 2. Para quem

| Papel | Quem é | O que compra |
|---|---|---|
| **Comprador inicial (cunha)** | Escritório que presta serviço financeiro terceirizado a pequenas e médias empresas (BPO financeiro / contabilidade) e faz **conciliação bancária** para dezenas de clientes | Conciliações entregues **com recibo verificável**, a um custo por conciliação aceita menor que o do analista |
| **Usuário que aprova** | O responsável humano do escritório (o *Patronus*) | Uma fila curta de decisões de julgamento, em vez de refazer tudo |
| **Comprador expandido (TAM)** | Qualquer entidade com trabalho repetitivo **cujo resultado pode ser verificado** | O mesmo motor com outro pacote de ofício |

**Por que essa cunha (critério, não preferência):** a conciliação bancária tem **lei de conservação**: o que entrou no banco tem de bater com o que foi lançado. Por isso ela admite um verificador determinístico, que é a condição para cobrar por resultado sem depender de confiança cega. Na Sequoia, contabilidade e auditoria terceirizadas aparecem com US$ 50–80 bi só nos EUA (número da tese, não medido por nós). O mercado brasileiro **não foi medido** nesta versão; essa é a tarefa F0.

**Hipótese de comprador (falsificável, pré-registrada):** de 10 escritórios de BPO financeiro ou contabilidade entrevistados, **≥ 3** aceitam um piloto pago de 30 dias cobrado por conciliação aceita. Se forem **< 3**, a cunha está errada e troca-se de ofício antes de escrever mais código.

## 3. O que é (e o que não é)

**É:** uma equipe de agentes **agnóstica de modelo** que:
1. **é admitida** numa entidade recebendo o Dossiê do Ente e passando num **EXAME** cujo gabarito fica só com humanos;
2. **trabalha** sob o **REGIMENTO**, uma constituição executável pelo núcleo **LEX**, que nega tudo o que não for explicitamente permitido;
3. **entrega** cada trabalho com **recibo**: um hash da entrega mais o veredito de um verificador independente, selado no livro-razão **ANAIS**;
4. **conquista autonomia** por classe de tarefa, como função estatística do histórico de recibos (limite inferior de Wilson), e **perde tudo** num incidente crítico;
5. **declara "impossível"** com evidência quando não consegue, e isso é tratado como dever, não como falha.

**Não é:** um orquestrador de organograma (já existe, em código aberto e com licença MIT); um chatbot de atendimento; um sandbox de sistema operacional (o LEX exige um, mas não substitui um, ver A1); um "CEO-agente" que manda nos outros.

## 4. Histórias de usuário (priorizadas; cada uma testável isoladamente)

### H1 — Conciliar com recibo (P1)
Como escritório, envio extrato e razão de um cliente e recebo a conciliação com pares, pendências e um recibo que qualquer auditor pode conferir.
**Teste isolado (produto, v0.3.0):** `python ferramentas/instalacao_limpa.py` → instala por `pip`, roda `exemplo → conciliar → aprovar → recibo → conferir-recibo → auditar-cabeca` fora da pasta do projeto (CI: 3 sistemas × 4 Pythons). Laboratório: `python reproduzir.py` → T1 mostra 200/200 entregas honestas aceitas.
**Aceite:** (a) nenhum par cita lançamento inexistente; (b) soma do banco = soma dos pares + soma das pendências (conservação); (c) recibo selado no ANAIS e verificável com a âncora; (d) o recibo prova que mostra a história INTEIRA da tarefa (inclusive recusa humana) — `tests/test_mapa.py`; (e) no kit de demonstração, 0 par errado contra a verdade conhecida — `tests/test_piloto.py`.

### H2 — Nunca inventar para fechar (P1)
Como escritório, quero ter certeza de que, quando não houver par, a equipe **deixe pendente** em vez de inventar.
**Teste isolado:** T1 E8/E9 → fabricação e ocultação detectadas em 389 de 389 casos exercidos, com quarentena.

### H3 — Dizer "não sei" com evidência (P1)
Como responsável, quero que a equipe pare e declare BLOQUEADO/IMPOSSÍVEL quando o orçamento da tarefa acabar.
**Teste isolado:** T1 E4/E5/E13. No produto: saldo que não fecha (S1), período que não bate (S2) ou razão de outra conta/convenção indeterminada (S3) → BLOQUEADO declarado no ANAIS, com o motivo no relatório e código de saída 2 — `tests/test_piloto.py`.

### H4 — Autonomia que se conquista (P2)
Como responsável, quero aprovar tudo no começo e, conforme o histórico prova qualidade, aprovar só por amostragem.
**Teste isolado:** T3 → com p=0,90 a equipe nunca chega a L2 (0/2000); com p=0,995, sempre chega (2000/2000, mediana de 125 tarefas).

### H5 — Admissão por prova (P2)
Como entidade, quero que a equipe responda ao EXAME do Dossiê antes de tocar em dados reais. **Status:** implementado (`collegium/dossie.py`); provado só com agentes roteirizados (T5). Com LLM real: T4b.

### H6 — Trocar de modelo sem trocar de equipe (P3)
Como entidade soberana, quero rodar com modelo local (Ollama) ou de nuvem, à minha escolha. **Status:** Ollama pronto (testado com servidor falso); nuvem a fazer (T021).

### Casos de borda
- Valores repetidos (mensalidades iguais): o verificador ingênuo aceita o par errado. Ver A4, onde a correção v0.1.3 reduziu os pares errados de 861 para 2 em cerca de 14 mil pares.
- Duas "metades órfãs" de mesmo valor, sem documento no extrato: **indistinguíveis** até para um humano. É resíduo declarado.
- Cliente sem histórico de documentos no extrato: a fração de itens que vão ao humano sobe. Isso é custo medido, não escondido: 5–14% no A4.

## 5. Requisitos funcionais

- **RF-01** O LEX DEVE negar por padrão qualquer capacidade, canal ou host fora do REGIMENTO e registrar a negação. *(testado)*
- **RF-02** O LEX DEVE impor orçamento de passos por tarefa; esgotado o orçamento, a única ação válida é declarar. *(testado)*
- **RF-03** Quem produz NÃO PODE verificar; verificador da mesma família de modelo é recusado, salvo oráculo determinístico ou humano. *(testado)*
- **RF-04** A fabricação detectada pelo verificador DEVE gerar incidente crítico, quarentena e rebaixamento a L0. *(testado)*
- **RF-05** O ANAIS DEVE detectar alteração, remoção, reordenação e reescrita da cadeia sem a chave; o truncamento da cauda só é detectável com âncora externa. *(testado; limite declarado)*
- **RF-06** O nível de autonomia DEVE ser calculado, nunca configurado. *(testado)*
- **RF-07** O EXAME de admissão DEVE ser gerado do Dossiê, e o gabarito DEVE ficar fora do alcance dos agentes. *(implementado; nota mínima padrão 0,90)* *[NEEDS CLARIFICATION: quem na entidade escreve as perguntas `[EXAME]` do MANDATO]*
- **RF-08** Adaptadores DEVEM existir para pelo menos um modelo local e um de nuvem. *[NEEDS CLARIFICATION: provedores do piloto]*
- **RF-09** O painel DEVE mostrar a fila do humano, os recibos e a matriz de autonomia. *(implementado, HTML estático)*
- **RF-10** Extrato importado DEVE passar pela prova de saldo; item lido com baixa confiança NÃO PODE ser casado automaticamente. *(implementado)*
- **RF-11** Conciliação DEVE aceitar lotes (1 crédito ↔ várias notas) só com documento de todos os membros ou subconjunto único. *(implementado)*
- **RF-12** Mudança de REGIMENTO DEVE ser assinada pelo Patronus. *(implementado; Ed25519 com quórum)*
- **RF-13** Entrada que não passa na sanidade (saldo, período, conta, convenção de sinal) DEVE resultar em BLOQUEADO declarado, nunca em conciliação entregue. *(testado)*
- **RF-14** O recibo e a fatura DEVEM provar a completude da história da tarefa; a mentira no mapa DEVE ser detectável por auditor com o ANAIS. *(testado; limite R6-7L)*
- **RF-15** O produto DEVE instalar por `pip` sem dependências e rodar em Windows, macOS e Linux, inclusive com arquivos gravados pelo PowerShell 5.1 e exportados pelo Excel em CP-1252 ou UTF-16. *(testado no CI; no Windows do Renato = Missão 4)*

## 6. Critérios de sucesso (mensuráveis, agnósticos de tecnologia)

| ID | Métrica | Meta v0.1 (laboratório) | Meta piloto (campo) |
|---|---|---|---|
| SC-1 | Comportamentos adversariais bloqueados | 100% (atingido: 4179/4179, 21 comportamentos) | 100% em replay de logs reais |
| SC-2 | Entregas honestas recusadas indevidamente | 0% (atingido: 0/200) | ≤ 2% |
| SC-3 | Pares errados entre entregas aceitas | medir (atingido: 0–0,014%) | ≤ 0,1%, medido por auditoria humana amostral |
| SC-4 | Fração de itens devolvidos ao humano | reportar (5–14% no A4; 11,2% no A5 com lotes) | ≤ 15% |
| SC-5 | Escritórios que pagam o piloto | — | ≥ 3 de 10 (hipótese F0) |
| SC-6 | Custo por conciliação aceita versus analista | — | < 50% (a medir; não estimado) |

## 7. Fora da primeira versão (explícito)

- Qualquer ação **irreversível** sem humano: pagamento, emissão de nota, envio ao fisco. Fica fora até haver histórico L3 **e** contrato.
- Escrituração contábil com responsabilidade técnica, que exige profissional habilitado. *Não sou advogado; validar com assessoria antes de vender.* O COLLEGIUM entrega a conciliação **ao** escritório, não **em nome** de um contador.
- Agente "CEO" com poder sobre os outros: o Project Vend mostrou ganho baixo ou negativo.
- Tarefas de **julgamento** sem verificador (estratégia, negociação, jurídico consultivo): só como copiloto, nunca no autopiloto.
- Interface gráfica completa: até a v0.3.0, núcleo + CLI + relatório HTML estático (abre offline e no celular).
- Multi-tenant em nuvem: v0.1 é local-first.

## 8. Vetor SINGULARIDADE (declarado)

| Eixo | Estado | Por quê |
|---|---|---|
| PREMIUM | **ativo** | Cada entrega tem recibo verificável; a qualidade é medida, não prometida |
| GLOBAL | **parcial** | O motor é universal; a cunha é Brasil (PIX, extrato BR) e os identificadores do código estão em PT-BR. A API bilíngue prevista para a v0.3 **não foi feita** (só o README tem resumo em inglês) |
| AGNÓSTICO | **ativo** | O LEX não chama modelo nenhum; os agentes podem ser qualquer LLM ou humano |
| SOBERANO | **ativo** | Só biblioteca padrão do Python, local-first; chave do ANAIS em poder da entidade e chave privada Ed25519 só no computador do humano |
| SEGURO | **parcial** | O LEX governa só o que passa por ele; isolamento de rede testado (`unshare`), Docker ainda não executado (T016): sem isolamento de SO, o ataque A1 vence |

## 9. Anterioridade (honestidade sobre ineditismo)

**Não se afirma ineditismo.** As peças isoladas já existem:
- orquestração de "empresa de agentes" com organograma, orçamento e aprovações (Paperclip, MIT);
- "autonomia conquistada" por tipo de operação com limiares prévios (artigo de Tian Pan, 17/04/2026, sem código);
- patente da UiPath US12412138B1 (autonomia que cresce com o tempo, sem métrica estatística);
- patentes da Daon (autorização por chamada de ferramenta e deriva de comportamento);
- cobrança por resultado em atendimento (Sierra, Intercom Fin).

**Candidato a diferencial**, por combinação e não por peça isolada: dever de declarar impossibilidade com persistência tratada como incidente crítico; independência do verificador por família de modelo; fabricação tratada como incidente; admissão por exame com gabarito humano; e o Dossiê de 6+1 arquivos como contrato de admissão. A busca de patentes foi **superficial**: uma busca na web e duas leituras. Antes de qualquer pedido, é preciso busca profissional (INPI, USPTO, EPO).
