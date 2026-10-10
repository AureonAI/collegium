# Política de segurança

## Como relatar uma vulnerabilidade
Use o **relato privado de vulnerabilidade do GitHub**: aba **Security** deste repositório → **Report a vulnerability**.
Não abra issue pública para falhas de segurança.

Inclua: versão (commit), passo a passo para reproduzir e o impacto que você observou.
Ataques que valem relatório: qualquer forma de fazer o LEX **permitir** uma ação proibida, **aceitar** fabricação,
**derrubar** o núcleo com exceção (falha aberta), forjar recibo, cabeça ou aprovação humana, ou fazer o
anonimizador **vazar** dado pessoal.

## O que esperar
- Projeto pequeno, sem equipe dedicada: confirmação de recebimento em até **7 dias**, sem promessa de prazo de correção.
- Toda vulnerabilidade confirmada vira: teste que a reproduz → correção → registro datado em `forge/ADVERSARIAL_LOG.md`.
- Não há programa de recompensa.

## Escopo e limites já declarados (não precisam ser relatados de novo)
Ver `forge/EVIDENCE.md` (Limites) e `forge/ADVERSARIAL_LOG.md`: Ed25519 em Python puro não é tempo constante (E-1);
`unshare` isola só a rede (I-1); o recibo não prova ausência de linha posterior (R-1).
