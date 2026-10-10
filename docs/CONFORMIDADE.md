# Mapa de conformidade (T063)

Cada linha aponta para **onde está** e **qual teste prova**. "Parcial" e "não coberto" são ditos sem rodeio.
Isto **não é certificação** (Art. 9: nenhum sistema se autocertifica); é o material que um auditor externo usaria.

## OWASP Top 10 para Aplicações Agênticas (2026, publicado em 09/12/2025)

| Risco | Situação | Como o COLLEGIUM trata | Prova |
|---|---|---|---|
| ASI01 Sequestro de objetivo | ✅ | Plano de capacidades selado ANTES de ler dado externo; saída de ferramenta marcada como não confiável; oráculo ignora texto livre; admissão por conduta com isca de injeção | `tests/test_fluxo_confiavel.py`, `tests/test_conduta.py` |
| ASI02 Uso indevido de ferramenta | ✅ | Portão MCP: toda chamada vira ação julgada pelo LEX antes de executar; destinos e argumentos de capacidade sensível só da lista do REGIMENTO | `tests/test_portao.py`, `tests/test_fluxo_confiavel.py` |
| ASI03 Abuso de identidade e privilégio | ✅ | Mandato fixo; ficha efêmera por tarefa; humano assina com Ed25519 (o núcleo só tem a chave pública); quórum para mudar regras; digest do modelo atestado | `tests/test_patronus.py`, `tests/test_fluxo_confiavel.py` |
| ASI04 Cadeia de suprimentos | 🔶 | Núcleo sem dependência; SBOM CycloneDX; pacote reprodutível e assinado; digest do modelo. **Falta:** licença (decisão pendente), assinatura de cada versão publicada | `tests/test_release.py` |
| ASI05 Execução inesperada de código | 🔶 | Executor com ambiente limpo e falha fechada; rede cortada (`unshare`/Docker). **Falta:** prova do nível `container` em máquina real (T016) | `tests/test_isolamento.py` |
| ASI06 Envenenamento de memória e contexto | 🔶 | Aprendizado só por proposta + backtest + quórum; minerador resiste a poucas decisões falsas. **Limite:** envenenamento coordenado bloqueia melhoria legítima (L-1) | `tests/test_aprendizado.py`, `experimentos/t8_aprendizado.py` |
| ASI07 Comunicação insegura entre agentes | ✅ | Canal único (`forum`), tipado, com limite de tamanho e destinatário existente | `tests/test_nucleo.py` |
| ASI08 Falhas em cascata | ✅ | Quarentena individual; fraude de um agente não contamina o operário determinístico; orçamento com corte duro | `tests/test_adaptador.py` (T6), `tests/test_orcamento_esquema.py` |
| ASI09 Exploração da confiança humana | 🔶 | Fila com evidência e prazo; quatro olhos acima da alçada; medida de "carimbo". **Falta:** interface gráfica e medição com humanos reais | `tests/test_fila.py` |
| ASI10 Agente desonesto | ✅ | Fabricação = incidente; canários (testam produtor e verificador); autonomia rebaixada por janela recente; atacante adaptativo sem vitórias na confirmatória | `tests/test_conduta.py`, `experimentos/a6_adaptativo.py` |

## LGPD (Lei 13.709/2018)

| Dispositivo | Como é atendido | Prova |
|---|---|---|
| Art. 6º, III (necessidade) e VII (segurança) | O ANAIS guarda hashes, não a entrada bruta; telemetria sem conteúdo de prompt, resposta ou argumento | `tests/test_portao.py::test_telemetria_execute_tool` |
| Art. 12 e art. 13, §4º (anonimização × pseudonimização) | O anonimizador **pseudonimiza** enquanto o cofre existir — isto é dito no módulo; não se vende como "anonimizado" | `collegium/privacidade.py` |
| Art. 18, VI (eliminação) | Destruir a chave do titular torna os pseudônimos antigos impossíveis de religar, sem reescrever o ANAIS | `tests/test_privacidade.py::TestCofre` |
| Art. 20 (revisão de decisão automatizada) | Toda decisão tem recibo com motivo; o resíduo vai a um humano; aprovação humana assinada | `tests/test_recibo.py`, `tests/test_fila.py` |
| Art. 37 (registro das operações) | ANAIS encadeado e assinado, com prova de inclusão e de consistência | `tests/test_merkle.py`, `tests/test_recibo.py` |
| Art. 46 (medidas de segurança) | Ver OWASP acima | — |

## Marco legal brasileiro de IA (PL 2338/2023)
Aprovado no Senado em 10/12/2024; na última fonte consultada (atualizada em 18/04/2026) aguardava a Câmara, sem data
de votação. **Não há obrigação vigente**; o mapa acima é preparação, não cumprimento. Confirmar a situação antes de qualquer afirmação comercial.

## União Europeia (Regulamento (UE) 2024/1689, "AI Act") — só se houver venda para lá
Art. 12 (manutenção de registros) ↔ ANAIS com recibos verificáveis; Art. 14 (supervisão humana) ↔ fila, quatro olhos,
veto e assinatura. **A classificação de risco do caso de uso não foi feita**; isto não é parecer jurídico.
