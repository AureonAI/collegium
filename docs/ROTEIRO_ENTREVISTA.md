# Roteiro de conversa com escritórios (T011 · Missão 3)

**Objetivo:** descobrir se escritórios contábeis e de BPO financeiro têm dor real com conciliação bancária **e** se topam um piloto. Não é para vender: é para ouvir fatos.

**Regra de ouro:** pergunte sobre o que **já aconteceu**, nunca sobre o que a pessoa "faria". "Você usaria?" não vale nada; "Quanto tempo vocês gastaram mês passado?" vale muito.

## Critério de sucesso (registrado em 10/10/2026, ANTES da primeira conversa)
- **S1:** pelo menos **3 de 10** aceitam um piloto gratuito de 1 mês, entregando extrato + razão **anonimizados** de 1 cliente.
- **S2:** pelo menos **3 de 10** dão um número concreto de custo atual (horas por mês ou valor em reais).
- **Falsificação:** se S1 der menos de 3, a hipótese "conciliação é a porta de entrada" **cai**. Isso vai para o ADVERSARIAL_LOG e muda a estratégia; não se reescreve o critério.

## Antes de começar (30 segundos)
"Estou pesquisando como escritórios fazem conciliação bancária. Não estou vendendo nada hoje. Posso te fazer 8 perguntas rápidas, uns 15 minutos?"

## As 8 perguntas
1. Quantos clientes vocês atendem com conciliação bancária? Mais ou menos quantas contas e lançamentos por mês?
2. Quem faz a conciliação hoje, e em qual sistema? (Domínio, Omie, Conta Azul, Nibo, planilha…)
3. **No mês passado**, quantas horas a equipe gastou conciliando? Quanto custa uma hora dessa pessoa?
4. Qual foi a **última vez** que um erro de conciliação apareceu tarde? O que aconteceu e quanto custou?
5. O que fica **sem conciliar** no fim do mês? O que vocês fazem com isso?
6. Já tentaram automatizar? O que deu errado, ou por que pararam?
7. O que impediria vocês de deixar uma ferramenta conciliar sozinha? (confiança, LGPD, o cliente, o sistema…)
8. **Pergunta de compromisso:** "Se eu conciliar 1 mês de 1 cliente seu de graça, com um relatório do que ficou pendente e o porquê de cada item, você me passaria o extrato e o razão **com nomes e documentos apagados**?"

Se disser sim na 8: "E se funcionar, como vocês preferem pagar: por conta, por lançamento ou por mês?" **Não diga preço.** Anote o que a pessoa disser.

## Depois da pergunta 8 (acrescentado em 10/10/2026, depois do pré-registro; NÃO entra no S1 nem no S2)
9. **Só agora mostre** o relatório de demonstração no celular (Missão 4; os dados são sintéticos, diga isso). Pergunte:
   "O que aqui você não entendeu?" e "O que faltaria para você confiar neste resultado sem refazer?" Anote **literal**.
10. Se a barreira da pergunta 7 foi sigilo/LGPD: a ferramenta roda **no computador do escritório**; extrato e razão não
    saem de lá. Pergunte: "Isso muda a sua resposta da pergunta 8?" Anote a resposta, mas a pergunta 8 vale como foi
    respondida **antes** (é a que conta no S1).

## O que anotar de cada conversa (copie e preencha)
```
Conversa nº:
Tipo: escritório contábil / BPO financeiro / outro
Tamanho: nº de clientes com conciliação · contas · lançamentos/mês
Sistema usado:
Horas por mês com conciliação:            Custo da hora:
Último erro descoberto tarde (resumo):
O que fica pendente no fim do mês:
Já tentou automatizar? Resultado:
Maior barreira para confiar numa ferramenta:
Pergunta 8 (piloto com dado anonimizado): SIM / NÃO / TALVEZ
Forma de pagamento preferida:
Frase marcante (literal):
Pergunta 9 (o que não entendeu / o que faltaria para confiar), literal:
Pergunta 10 (rodar no computador do escritório muda a resposta?):
```

## O que NÃO fazer
- Não explicar o COLLEGIUM antes da pergunta 8. Quem ouve a solução antes passa a responder sobre a solução, não sobre a dor.
- Não aceitar "achei interessante" como resultado. Só conta fato, número ou compromisso.
- Não receber nenhum arquivo. Se o piloto for aceito, o caminho é o escritório rodar a ferramenta no próprio computador;
  só volta para nós o que ele decidir mandar (o `resumo.json` não traz nomes nem históricos — teste de minimização LGPD).
