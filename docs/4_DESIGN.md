# 4 · DESIGN — cores, fonte e componentes

**Princípio:** o COLLEGIUM vende **confiança verificável**. O desenho tem de parecer um livro contábil bem mantido, não um brinquedo de IA. Nada de robôs sorridentes, gradientes neon ou "magia". Cada número na tela leva ao recibo que o prova.

## 1. Paleta (tokens)

| Token | Claro | Escuro | Uso |
|---|---|---|---|
| `--tinta` | `#1B1F24` | `#E8E6E1` | texto principal |
| `--papel` | `#F7F5F0` | `#121417` | fundo (papel de livro-razão) |
| `--linha` | `#D9D4C7` | `#2A2E33` | divisórias, bordas de tabela |
| `--selo` | `#7A2E1F` (vermelho-lacre) | `#C9644E` | marca, selo de recibo, chamadas primárias |
| `--aceito` | `#2F6B3F` | `#6FBF84` | recibo ACEITO, autonomia conquistada |
| `--pendente` | `#8A6D1A` | `#D8B44A` | aguarda humano, pendências |
| `--incidente` | `#A1261B` | `#F0715F` | quarentena, fabricação, violação |
| `--neutro` | `#5E636B` | `#9AA0A8` | metadados, hashes |

**Regra de acessibilidade:** a cor nunca carrega o significado sozinha. Todo estado tem também ícone e palavra (ex.: `✓ ACEITO`, `⏸ AGUARDA HUMANO`, `⛔ QUARENTENA`). O contraste mínimo é AA (4,5:1) para o texto.

## 2. Tipografia

| Papel | Fonte | Por quê |
|---|---|---|
| Títulos | **Fraunces** (serifa, Google Fonts, OFL) | tom de documento institucional |
| Texto | **Inter** (OFL) | legibilidade em telas pequenas |
| Números, hashes, códigos | **JetBrains Mono** (OFL) | alinhamento tabular; o hash é lido caractere a caractere |

Escala: 12 / 14 / 16 / 20 / 28 / 40 px. Números sempre com `font-variant-numeric: tabular-nums`.

## 3. Componentes

| Componente | Conteúdo | Regra |
|---|---|---|
| **Selo de recibo** | hash curto (12 caracteres) + veredito + verificador + família | clicar abre o registro do ANAIS; nunca aparece sem um hash |
| **Fila do Patronus** | tarefas em `AGUARDA_HUMANO`, ordenadas por valor e prazo | é a tela inicial; o humano decide com 2 cliques (aprovar ou rejeitar com motivo) |
| **Matriz de autonomia** | linhas = agentes, colunas = classes de tarefa, célula = L0–L3 + n + limite de Wilson | mostra **quanto falta** para o próximo nível ("faltam 37 aceites") |
| **Cartão de declaração** | BLOQUEADO/IMPOSSÍVEL + evidência | cor `--pendente`, nunca `--incidente`: declarar é virtude |
| **Faixa de incidente** | agente, código, hora, link para o ANAIS | fica visível até o humano reconhecer |
| **Conciliação** | 3 colunas: pares · pendências do banco · pendências do razão; rodapé com a **conservação** (Σ banco = Σ pares + Σ pendências) | se a conservação não fecha, a tela inteira bloqueia |
| **Âncora** | `n` + selo da cabeça + botão "copiar para publicar" | lembrete semanal para publicar fora (A2) |
| **Alerta de equipe** | "EQUIPE ABAIXO DO MÍNIMO" quando operários ativos < mínimo | faixa `--incidente` no topo do painel (implementado em `collegium/equipe.py`) |

## 4. Voz (textos de interface)

- Fala como um auditor educado: **afirmação + evidência**. "12 pendências sem par; 3 aguardam sua decisão." Não "Tudo pronto! 🎉".
- Nunca antropomorfiza ("o agente acha que…"). Diz "o Operarius op-1 propôs…".
- Erro é factual: "Recusado: R9001 não existe no razão (REFERENCIA_INEXISTENTE)."

## 5. Identidade

- **Nome:** COLLEGIUM. **Marca:** um selo de lacre circular com um "C" e uma linha de livro-razão cortando o centro.
- **Assinatura:** *"Trabalho entregue com recibo."*
- O nome precisa de busca de marca no INPI (classes 9 e 42) antes do uso comercial. Não foi feita.
