# PRIMITIVE: o que é fundação reutilizável e o que é folha

## Fundação (primitivo): `collegium/` (cerca de 4.000 linhas na v0.3.0, eram 1.035 na v0.1.4; só biblioteca padrão)

| Peça | O que resolve, em qualquer sistema de agentes | Interface |
|---|---|---|
| **ANAIS** (`ledger.py`) | Histórico que o agente não consegue reescrever nem encurtar sem ser pego | `anexar(tipo, dados)`, `verificar(ancora)`, `ancora()` |
| **LEX** (`lex.py`) | Constituição executável: negação por padrão, dever de declarar, separação de poderes, liberação condicionada | `autorizar(Acao)`, `abrir_tarefa`, `submeter`, `verificar`, `liberar`, `aprovar_humano` |
| **Autonomia** (`autonomia.py`) | Transformar histórico de recibos em permissão (Wilson + estabilidade + janela recente) e retirá-la num incidente | `nivel(Historico, cfg)`, `wilson_inferior` |
| **Mandato + assinatura** (`lex.py`) | Agente só age em nome próprio; humano prova identidade por Ed25519 (HMAC só sem chave pública registrada); REGIMENTO só muda com quórum assinado | `lex.mandato(ag)`, `assinar_humano_ed25519(...)` |
| **Recibo + mapa** (`merkle.py`, `mapa.py`, `recibo.py`) | Cliente confere sozinho que um trabalho existe, que a história dele está COMPLETA e que o histórico só cresceu | `cabeca`, `emitir_recibo`, `conferir_recibo`, `auditar_cabeca` |
| **Executor de ofício** (`execucao.py`) | Rodar QUALQUER ofício sob o LEX de ponta a ponta, ou declará-lo BLOQUEADO | `executar`, `bloquear`, `aprovar` |
| **Dossiê + EXAME** (`dossie.py`) | Admissão por prova antes de tocar dado real; caduca quando as regras mudam | `carregar_dossie`, `gerar_exame`, `admitir` |
| **Equipe** (`equipe.py`) | Roteamento sem "CEO-agente"; memória e painel gerados do ANAIS | `Rector`, `relatorio`, `memoria_md`, `painel_html` |

**Por que é primitivo:** não sabe o que é conciliação, nem que modelo existe, nem qual framework orquestra os agentes. Dá para colocá-lo por trás de qualquer orquestrador (organograma, grafo, MCP) como a **alfândega** de cada ação. É a peça que sobrevive se o produto mudar de ofício, de comprador ou de modelo.

**Contrato de estabilidade:** códigos de decisão (`EGRESSO_NEGADO`, `PERSISTENCIA`, `AUTOVERIFICACAO`, `FABRICACAO`…) são API pública e não mudam de nome. Leis novas entram como L5 em diante, nunca alterando o significado de L1–L4.

## Folhas (específicas, descartáveis)

| Folha | Depende do primitivo | Troca-se quando |
|---|---|---|
| `collegium_oficios/conciliacao/` (oráculo v0.1.3, gerador, operários) | sim | muda o ofício (contas a pagar, folha, faturamento…) |
| `collegium/adaptadores.py` (Ollama) | não, é usada pelos agentes | muda o provedor de modelo |
| `collegium_oficios/conciliacao/importadores.py` (OFX, CSV, PaddleOCR) | não | muda o formato de entrada do cliente |
| `experimentos/` | sim | a hipótese muda |
| Painel, Rector, Actuarius (F3) | sim | muda a interface com o humano |

## Regra de construção
**Não construir a catedral.** Cada folha nova só nasce se: (1) tiver oráculo determinístico ou humano; (2) declarar sua lei de conservação; (3) vier com um ataque de Goodhart próprio, como o A4. Se a folha não tem verificador, ela é copiloto, nunca autopiloto.
