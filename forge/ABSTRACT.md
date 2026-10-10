# ABSTRACT (1 página, linguagem do comprador)

**COLLEGIUM: conciliação bancária em que nada é aceito na palavra, com recibo que o seu cliente confere sozinho.**

**O problema.** Um escritório que faz o financeiro terceirizado de dezenas de pequenas empresas gasta horas de analista casando extrato com lançamento. Ferramentas de IA prometem "fazer sozinhas", mas em 2026 a própria OpenAI documentou agentes que, sob pressão, trapacearam, insistiram fora do escopo e inventaram dados. Ninguém assina um balanço em cima disso.

**O que entregamos.** O escritório roda a ferramenta **no próprio computador** (o extrato e o razão não saem de lá) e recebe: os pares casados, as pendências com o motivo de cada uma, planilhas que o Excel soma e um **recibo**: uma marca digital que prova o que foi entregue, quem conferiu e quem aprovou, e que qualquer auditor confere sem acesso ao sistema. Quatro garantias, testadas em laboratório:
1. **Nunca inventa para fechar.** Se não há par, fica pendente. Inventar um lançamento tira o executor do trabalho na hora (capturado em 190 de 190 tentativas simuladas).
2. **Quem faz não confere.** O casamento é feito por código determinístico; um verificador independente confere cada conciliação, e a conta tem de fechar centavo a centavo.
3. **Quando o arquivo não serve, diz.** Saldo que não fecha, período diferente, razão de outra conta ou o mesmo arquivo dos dois lados: a conciliação é BLOQUEADA, com o motivo. Nada sai como se estivesse certo.
4. **Nada da história fica escondido.** O recibo prova que mostra TUDO o que aconteceu com aquele trabalho, inclusive uma recusa do seu analista.

**IA, com honestidade.** Modelos de linguagem pequenos, testados em conciliação real de laboratório, não fizeram o trabalho (0 de 79). Por isso o casamento é feito por código. A IA fica opcional, só para anotar as pendências, e o valor disso ainda **não** foi medido.

**O que ainda NÃO provamos.** Nenhum arquivo real de cliente passou pela ferramenta. Nos dados de laboratório, de 5% a 14% dos itens voltam para o analista; no kit de demonstração, que imita as armadilhas de arquivos reais (valores repetidos, histórico sem documento), **24% dos lançamentos do extrato** voltam, acima da meta de 15%. É precisão comprada com trabalho do analista: valor repetido sem documento não é casado por palpite. Nós mostramos esse número em vez de escondê-lo.

**Métrica de valor para o comprador.** Horas de analista por conciliação, antes e depois, e o percentual de itens que ainda exigem decisão humana. Serão medidos no piloto; não são promessa.

**Comprador.** Sócio ou gestor de escritório de BPO financeiro ou de contabilidade que concilia contas de 20 ou mais clientes por mês.

**Proposta de piloto.** 1 mês, 1 cliente do escritório, sem custo, rodando no computador do escritório. Se funcionar, a forma de pagamento é a que o escritório disser na entrevista (por conta, por lançamento ou por mês).

---

**Roteiro e critério pré-registrado da Missão 3:** `docs/ROTEIRO_ENTREVISTA.md` (enviado ao GitHub no commit 47c6d3a, em 10/10/2026, antes de qualquer conversa). Ele **substitui** o roteiro que ficava aqui desde 09/10/2026, cuja pergunta 5 explicava a solução antes de ouvir a dor (erro de método, R6-23). Os dois continuam no histórico do repositório.
