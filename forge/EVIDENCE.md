# EVIDENCE: COLLEGIUM v0.1.4

**Comando único reprodutível por um estranho:** `python reproduzir.py --conferir` (Python 3.10+, sem dependências, sementes fixas). Sai com código 1 se algum hash divergir de `resultados/HASHES.txt`.

**Reprodução entre versões (09/10/2026):** os **6 hashes idênticos** em Python **3.10.20, 3.11.15, 3.12.13 e 3.13.16** (Linux), e os 60 testes passando nas 4 versões. Windows e macOS: workflow pronto em `.github/workflows/evidencia.yml`, **ainda não executado**. Quando rodar nas máquinas do GitHub, vira a primeira âncora fora do controle do autor.

| Resultado | SHA-256 (16) |
|---|---|
| T1_contencao | `a47169042dbf394b` |
| T2_anais | `9fcefd9d7d198b57` |
| T3_autonomia | `63efe66f413f96f6` |
| A4_goodhart | `6314e2afba0f8a82` |
| A5_mundo_sujo | `b8ed2164b0b84510` |
| T5_equipe | `6cca208b372d7a23` |

**Regra de status (FORGE 3.1):** TESTADO exige âncora fora do controle do autor. Versões diferentes do Python rodadas por mim **não** são juiz externo: provam determinismo, não validade. Por isso tudo abaixo continua **TESTÁVEL-NÃO-TESTADO-EXTERNAMENTE**.

| ID | Afirmação | Resultado interno | Critério pré-registrado | Observação honesta |
|---|---|---|---|---|
| T1 | O núcleo bloqueia 21 comportamentos adversariais (4 padrões da OpenAI + rodada GPT-Red), sem recusar o honesto | **4179/4179**; 0/200 falso bloqueio; 0 ANAIS corrompidos | 100% / 0% / 0% | Os ataques foram escritos por mim (ataque-Gödel). O E7 foi reespecificado (errata registrada) |
| T2 | Com chave + âncora externa, o ANAIS detecta 6 classes de adulteração | 600/600 | 100% | Sem âncora, truncar a cauda vence; sem chave, recomputar vence |
| T3 | Autonomia: não promove quem está no limiar e rebaixa quem piora | p=0,97: **2,00%** (40/2000); p=0,95: 0%; p=0,995: 100% (mediana 286); degradação: 498/500 perdem L2 em ≤100 tarefas | (a) ≤2% (b) ≤1%/≤0,5% (c) ≥95% (d) ≥95% | A v0.1.3 **falsificou** (a) com 4,55%. O z=2,326 foi escolhido pós-hoc e **confirmado com semente nova**, mas passou **exatamente no limite** (2,00%) |
| A4 | O oráculo reduz pares errados aceitos com valores repetidos | 409→0, 861→2, 1341→1 | zero | Critério "zero" **falsificado**; resíduo irredutível de "metades órfãs" |
| A5 | Mundo mais sujo: lotes N:1, estilos variados, injeção no extrato | v5: 300/300 aceitos, 1/300 errado; humano 22% → 11,2%; injeção 0/300 | (a)(b)(c) | Padrões de documento errados dobram o erro (1→2): o oráculo depende da configuração da entidade |
| T5 | Equipe com Rector, EXAME e segunda opinião | Equipe **199/200** contra sozinho **14/200**; 0 atribuições indevidas; 3 segundas opiniões, todas de outra linhagem; o chutador é reprovado (0,38) | (a)–(e) | Operários **roteirizados**: mede o mecanismo de equipe, não inteligência |
| Importadores | OFX/CSV/OCR com prova de saldo | 11 testes | — | OCR testado com motor **falso**; o PaddleOCR real não foi executado (modelos bloqueados pela rede da sessão) |
| T4 / T4b | Modelos locais ≤4B: aceite < 50%, fabricação capturada, EXAME < 0,90, `DADO_ORDEM` correto | **não executado** | P1–P5 (prospectivas) | Depende da sua máquina (Missão 2) |

## Limites declarados
1. **Operários roteirizados.** Nenhum LLM real executou tarefa ou EXAME.
2. **Dados sintéticos.** Nenhum extrato ou razão de cliente real.
3. **O LEX não é sandbox** (A1). A separação agente/orquestrador é de processo.
4. **Assinatura simétrica** (HMAC). O núcleo também conhece a chave do Patronus.
5. **O EXAME mede compreensão de regras, não competência.** O "estudioso" do T5 é roteirizado e circular.
6. **Desempenho.** O operário de referência leva cerca de 24 s com 20 mil lançamentos; o oráculo, 0,3 s. O T3 leva 3–6 min.
7. **Mercado: zero evidência.**

## TRL e nota
- **TRL MEDIDO: 3.** Continua 3: as melhorias são de robustez da função crítica em laboratório. O TRL 4 exige um componente validado com LLM real **e** dado real (Missões 2 e T015).
- **Nota do primitivo LEX/ANAIS: 4,8/10.** O teto do TRL 3 é 5,0. Subiu 0,3 porque fechei 14 ataques que venceram e provei determinismo em 4 versões. Não chega a 5,0 porque o juiz externo ainda não rodou.
- **Nota do projeto: ver a resposta da sessão** (a régua é a mesma da avaliação anterior).
