# COLLEGIUM v0.1.4

**Equipe de agentes de IA agnóstica, contratável com segurança: admitida por prova, governada por constituição executável, com autonomia conquistada por histórico medido e trabalho entregue com recibo.**

Nasceu da inversão do incidente OpenAI/Hugging Face (2026). Lá, agentes que "se recusaram a falhar" trapacearam. Aqui, declarar "impossível" é dever, e inventar é fraude.

## Rodar (Windows, Linux, macOS; Python 3.10+; nenhuma instalação extra)

```
python -m unittest discover -s tests          # 73 testes → OK
python reproduzir.py --conferir               # refaz toda a evidência e compara com resultados/HASHES.txt
python -m collegium                           # comandos do Patronus (verificar, ancora, relatorio, assinar)
python experimentos/t4_llm_ollama.py gemma3:4b 20   # conciliação com LLM real (requer Ollama aberto)
python experimentos/t4b_exame_llm.py gemma3:4b      # EXAME de admissão com LLM real
```

Extrato escaneado (opcional): `pip install paddleocr` + motor de inferência, e depois `pacotes/conciliacao/importadores.ler_imagem_paddle(...)`.

## Mapa

| Onde | O quê |
|---|---|
| `AGENTS.md` | Instruções para agentes de código (ordem de leitura + disciplina de mudança) |
| `docs/1_PRD.md` … `docs/6_MEMORIA.md` | Os 6 arquivos: PRD, Arquitetura, Regras (constituição + convenções + disciplina), Design, Tarefas, Memória |
| `dossie_exemplo/` | Dossiê do Ente (MANDATO, ORGANOGRAMA, REGIMENTO, VOZ, PAUTA) usado na admissão por EXAME |
| `forge/` | Ratificação do vídeo + EVIDENCE · ABSTRACT · ADVERSARIAL_LOG · PRIMITIVE |
| `collegium/` | Primitivo: ANAIS, LEX, autonomia, dossiê/EXAME, equipe, CLI |
| `pacotes/conciliacao/` | Folha: oráculo, importadores (OFX/CSV/OCR), geradores sintéticos, operários |
| `experimentos/` + `resultados/` | T1 · T2 · T3 · A4 · A5 · T5 (+ T4/T4b para LLM real) · HASHES · histórico de falsificações |
| `.github/workflows/evidencia.yml` | Mesma evidência em Windows/macOS/Linux × Python 3.10–3.13 |

[![evidencia](https://github.com/AureonAI/collegium/actions/workflows/evidencia.yml/badge.svg)](https://github.com/AureonAI/collegium/actions/workflows/evidencia.yml)

## Estado honesto
TRL medido **3**: laboratório, operários roteirizados, dados sintéticos. Evidência reproduzida com hashes idênticos em **Windows, macOS e Linux × Python 3.10–3.13**, em máquinas do GitHub (12/12). Ainda sem LLM real, sem dado real e sem comprador ouvido. Próximo passo: `docs/5_TAREFAS.md` → Missão 2.

## In English (summary)
COLLEGIUM is a model-agnostic, local-first governance kernel plus a first vertical (bank reconciliation) for teams of AI agents that a business can safely *hire*. It inverts the four misalignment patterns OpenAI documented in 2026: deny-by-default actions, a *duty to declare* impossibility within a step budget, separation of powers (the kernel runs the oracle itself, so a lying verifier cannot pass fabricated work), and autonomy *earned* from a statistical track record (Wilson bound + stability + recent window). Everything is reproducible with `python reproduzir.py --conferir`. Status: TRL 3, lab-only. Not yet tested with real LLMs, real data or paying customers.

Licença sugerida: MIT para o primitivo `collegium/` (decisão pendente do autor).
