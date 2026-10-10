"""COLLEGIUM — conciliação bancária governada, com recibo que o cliente confere sozinho.
Uso: `collegium COMANDO ...` (instalado) ou `python -m collegium COMANDO ...` (na pasta do projeto).
Chaves SEMPRE por arquivo ou ambiente, nunca por argumento.

Começar em 2 minutos (dados de demonstração, sintéticos):
  collegium exemplo PASTA                      grava PASTA/extrato.ofx e PASTA/razao_contabil.csv
  collegium conciliar --extrato PASTA/extrato.ofx --razao PASTA/razao_contabil.csv --saida RESULTADO
      e abra RESULTADO/relatorio.html no navegador.

Conciliar arquivos reais (T066; o trabalho que se vende):
  collegium conciliar --extrato EXTRATO --razao RAZAO --saida PASTA [--ente "NOME"]
      [--sinal-razao auto|bancaria|contabil] [--doc REGEX ...] [--anais ANAIS.jsonl] [--chave ARQUIVO_PRIVADO]
      extrato: OFX, CNAB 240, JSON Open Finance ou planilha; razão: planilha do ERP (CSV/TXT).
      Saída: relatorio.html, pendencias.csv, pares.csv, resumo.json (+ cabeca.json e recibo.json com --chave).
      [--humano NOME --chave-publica CHAVE]   registra quem aprova (só na 1ª conciliação do ANAIS)
      Código de saída: 0 conciliado · 2 BLOQUEADO (o relatório diz o que corrigir) · 1 arquivo ilegível.
  collegium aprovar --anais ANAIS.jsonl --tarefa TAREFA --humano NOME --chave ARQUIVO_PRIVADO [--rejeitar]
  collegium --versao

Governança do ANAIS (ambiente: COLLEGIUM_CHAVE = chave HMAC; COLLEGIUM_CHAVE_PATRONUS = assinatura humana HMAC):
  collegium verificar ANAIS.jsonl [--ancora N:SELO]   integridade (+ cauda, com âncora)
  collegium ancora ANAIS.jsonl                         imprime N:SELO para publicar fora
  collegium relatorio ANAIS.jsonl REGIMENTO.json PASTA gera MEMORIA.md + painel.html
  collegium assinar aprovar TAREFA HASH_ENTREGA true|false HUMANO
  collegium assinar reabilitar AGENTE HUMANO

Assinatura assimétrica (T042, recomendada; a chave privada fica SÓ no computador do humano):
  collegium gerar-chave ARQUIVO_PRIVADO           cria a chave e imprime a PÚBLICA
  collegium hash-regimento REGIMENTO.json          hash a assinar numa mudança de regras
  collegium assinar-ed ARQUIVO_PRIVADO regimento HASH
  collegium assinar-ed ARQUIVO_PRIVADO aprovar TAREFA HASH_ENTREGA true|false HUMANO
  collegium assinar-ed ARQUIVO_PRIVADO reabilitar AGENTE HUMANO

Recibo verificável (T043; o cliente confere sem acesso ao sistema):
  collegium cabeca ANAIS.jsonl ARQUIVO_PRIVADO "NOME DO ENTE"   > cabeca.json
  collegium recibo ANAIS.jsonl TAREFA cabeca.json               > recibo.json
  collegium conferir-recibo recibo.json CHAVE_PUBLICA [ENTRADA.json]
  collegium auditar-cabeca ANAIS.jsonl cabeca.json CHAVE_PUBLICA   (auditor: mapa e raiz batem?)
  collegium consistencia ANAIS.jsonl TAMANHO_ANTIGO TAMANHO_NOVO > prova.json
  collegium conferir-consistencia antiga.json nova.json prova.json CHAVE_PUBLICA

Privacidade (T044/T045; COLLEGIUM_CHAVE_COFRE no ambiente, nunca em arquivo do projeto):
  collegium anonimizar ENTRADA.json SAIDA.json COFRE.json [--confirmo CODIGO] [--doc REGEX ...]
      1ª vez: mostra as palavras MANTIDAS e um código. Leia, confira que nenhuma é nome, e
      rode de novo com --confirmo CODIGO para gravar a SAIDA.
  collegium eliminar-titular COFRE.json TIPO VALOR     (TIPO: NOME, CPF, CNPJ, EMAIL, TEL...)

Portão MCP (T046; o cliente MCP do agente inicia este comando como servidor stdio):
  collegium portao REGIMENTO.json ANAIS.jsonl ENTRADA.json [--oficio conciliacao_bancaria|tres_vias]
      ambiente: COLLEGIUM_FICHA (emitida pelo orquestrador), COLLEGIUM_SEGREDO_PORTAO, COLLEGIUM_CHAVE
  collegium emitir-ficha AGENTE TAREFA CAP1,CAP2 VALIDADE_SEGUNDOS   (usa COLLEGIUM_SEGREDO_PORTAO)

Pré-registro selado (T061; rode ANTES do experimento, depois faça commit e envio):
  collegium preregistrar ARQUIVO ARQUIVO_PRIVADO
  collegium conferir-preregistro ARQUIVO CHAVE_PUBLICA

Métricas e fatura conferível pelo cliente (T064):
  collegium metricas ANAIS.jsonl
  collegium fatura ANAIS.jsonl cabeca.json INICIO_UNIX FIM_UNIX precos.json ARQUIVO_PRIVADO > fatura.json
  collegium conferir-fatura fatura.json CHAVE_PUBLICA

Kit de ofício (T049):
  collegium conformidade NOME_DO_OFICIO [SEMENTES]     roda a suíte (pureza, falha fechada, mutação)
"""
from __future__ import annotations

import os
import sys

from .equipe import memoria_md, painel_html, relatorio
from .ledger import Ledger
import json
from datetime import datetime, timezone

from . import ed25519
from . import recibo as rc
from .privacidade import Anonimizador, Cofre, exportar
from .lex import Lex, _h, assinar_humano, assinar_humano_ed25519, carregar_regimento


def _ler_texto(caminho: str) -> str:
    """R6-9: o PowerShell 5.1 grava `>` em UTF-16; o Bloco de Notas pode pôr BOM. Aceita os três."""
    with open(caminho, "rb") as f:
        b = f.read()
    if b[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return b.decode("utf-16")
    return b.decode("utf-8-sig")


def _ler_json(caminho: str):
    return json.loads(_ler_texto(caminho))


def _chave(var: str) -> bytes | None:
    return Ledger.chave_de_ambiente(var)


def _conciliar(args: list[str]) -> int:
    import argparse
    from collegium_oficios.conciliacao import importadores as imp
    from collegium_oficios.conciliacao import piloto
    ap = argparse.ArgumentParser(prog="collegium conciliar")
    ap.add_argument("--extrato", required=True)
    ap.add_argument("--razao", required=True)
    ap.add_argument("--saida", required=True)
    ap.add_argument("--ente", default="Cliente")
    ap.add_argument("--sinal-razao", default="auto", choices=["auto", "bancaria", "contabil"])
    ap.add_argument("--doc", action="append", default=[])
    ap.add_argument("--anais")
    ap.add_argument("--chave")
    ap.add_argument("--humano", help="nome do responsável que aprova (registrado só na 1ª conciliação do ANAIS)")
    ap.add_argument("--chave-publica", help="chave PÚBLICA Ed25519 do humano (saída de gerar-chave)")
    a = ap.parse_args(args)
    if bool(a.humano) != bool(a.chave_publica):
        print("--humano e --chave-publica vão juntos", file=sys.stderr)
        return 1
    humanos = {a.humano: a.chave_publica.strip().lower()} if a.humano else None
    privada = None
    if a.chave:
        privada = bytes.fromhex(_ler_texto(a.chave).strip())
    try:
        r = piloto.conciliar_arquivos(a.extrato, a.razao, a.saida, a.ente, a.sinal_razao, a.doc, a.anais,
                                      _chave("COLLEGIUM_CHAVE"), privada, humanos)
    except (imp.ImportacaoInvalida, imp.CNABInvalido, ValueError, KeyError) as e:  # RegimentoInvalido é ValueError
        print(f"ARQUIVO NÃO PÔDE SER LIDO: {e}", file=sys.stderr)
        return 1
    if r.get("motivo"):
        print(f"{r['status']}: {r['motivo']}")
    else:
        p, g = r.get("pares", 0), r.get("grupos", 0)
        print(f"{r['status']}: {p + g} casamentos ({p} pares 1:1 + {g} lotes), "
              f"{r.get('pendencias_extrato', 0)} pendências no extrato, {r.get('pendencias_razao', 0)} no razão")
    for av in r["avisos"]:
        print(f"AVISO: {av}")
    print(f"Abra: {os.path.join(a.saida, 'relatorio.html')}")
    return {"CONCILIADO": 0, "BLOQUEADO": 2}.get(r["status"], 3)


def _aprovar(args: list[str]) -> int:
    import argparse
    from collegium_oficios.registro import carregar
    from .execucao import aprovar
    ap = argparse.ArgumentParser(prog="collegium aprovar")
    ap.add_argument("--anais", required=True)
    ap.add_argument("--tarefa", required=True)
    ap.add_argument("--humano", required=True)
    ap.add_argument("--chave", required=True, help="arquivo da SUA chave privada (gerar-chave)")
    ap.add_argument("--rejeitar", action="store_true")
    ap.add_argument("--oficio", default="conciliacao_bancaria")
    a = ap.parse_args(args)
    sk = bytes.fromhex(_ler_texto(a.chave).strip())
    of, _ = carregar(a.oficio)
    try:
        r = aprovar(of, Ledger(a.anais, chave=_chave("COLLEGIUM_CHAVE")), a.tarefa, a.humano, sk, not a.rejeitar)
    except (KeyError, ValueError) as e:
        print(f"NÃO APROVADO: {e}", file=sys.stderr)
        return 1
    print(f"{r['codigo']}: {r['motivo']}")
    return 0 if r["permitido"] else 2


def _exemplo(args: list[str]) -> int:
    from collegium_oficios.conciliacao.exemplo import escrever
    if len(args) != 1:
        print("uso: collegium exemplo PASTA", file=sys.stderr)
        return 2
    ext, raz = escrever(args[0])
    saida = os.path.join(args[0], "resultado")
    print("Dados de DEMONSTRAÇÃO (sintéticos, com as armadilhas de arquivos reais) gravados em:")
    print(f"  {ext}\n  {raz}\nAgora rode:")
    print(f'  collegium conciliar --extrato "{ext}" --razao "{raz}" --saida "{saida}"')
    print(f"e abra {os.path.join(saida, 'relatorio.html')} no navegador.")
    return 0


def _registro_preregistro() -> str:
    """T068: instalado, a pasta do pacote não é lugar de dado. Padrão = preregistros/ do projeto (se existir);
    senão, COLLEGIUM_PREREGISTRO (caminho do REGISTRO.jsonl) é obrigatório."""
    amb = os.environ.get("COLLEGIUM_PREREGISTRO")
    if amb:
        return amb
    pasta = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "preregistros")
    if not os.path.isdir(pasta):
        raise FileNotFoundError("defina COLLEGIUM_PREREGISTRO com o caminho do REGISTRO.jsonl")
    return os.path.join(pasta, "REGISTRO.jsonl")


def cli() -> None:
    """Ponto de entrada do comando `collegium` instalado (pyproject.toml)."""
    raise SystemExit(main(sys.argv[1:]))


def main(argv: list[str]) -> int:
    for fluxo in (sys.stdout, sys.stderr):  # R6-10/R6-20: saída SEMPRE em UTF-8 (determinística para quem lê:
        try:                                # scripts, testes, outros programas); nunca derruba o comando
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    if not argv or argv[0] in ("-h", "--help", "ajuda"):
        print(__doc__)
        return 0 if argv else 2
    if argv[0] in ("--versao", "--version"):
        from . import __version__
        print(f"collegium {__version__}")
        return 0
    cmd = argv[0]
    if cmd == "verificar":
        L = Ledger.__new__(Ledger)
        L.caminho, L.chave = argv[1], _chave("COLLEGIUM_CHAVE")
        anc = None
        if "--ancora" in argv:
            n, selo = argv[argv.index("--ancora") + 1].split(":")
            anc = (int(n), selo)
        ok, ruim = L.verificar(anc)
        print("ÍNTEGRO" if ok else f"CORROMPIDO a partir do registro {ruim}")
        return 0 if ok else 1
    if cmd == "ancora":
        L = Ledger(argv[1], chave=_chave("COLLEGIUM_CHAVE"))
        n, selo = L.ancora()
        print(f"Publique fora (e-mail, repositório, cartório): {n}:{selo}")
        return 0
    if cmd == "relatorio":
        lex = Lex(argv[2], Ledger(argv[1], chave=_chave("COLLEGIUM_CHAVE")))
        rel = relatorio(lex)
        os.makedirs(argv[3], exist_ok=True)
        with open(os.path.join(argv[3], "MEMORIA.md"), "w", encoding="utf-8") as f:
            f.write(memoria_md(rel))
        with open(os.path.join(argv[3], "painel.html"), "w", encoding="utf-8") as f:
            f.write(painel_html(rel))
        print(f"gerados MEMORIA.md e painel.html em {argv[3]}")
        return 0
    if cmd == "assinar":
        chave = _chave("COLLEGIUM_CHAVE_PATRONUS")
        if not chave:
            print("defina COLLEGIUM_CHAVE_PATRONUS", file=sys.stderr)
            return 2
        campos: list = list(argv[1:])
        if campos[0] == "aprovar":
            campos[3] = campos[3].lower() == "true"
        print(assinar_humano(chave, *campos))
        return 0
    if cmd == "gerar-chave":
        if os.path.exists(argv[1]):
            print("arquivo já existe: não sobrescrevo chave", file=sys.stderr)
            return 2
        sk = ed25519.gerar_privada()
        fd = os.open(argv[1], os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(sk.hex())
        print(ed25519.publica(sk).hex())
        return 0
    if cmd == "hash-regimento":
        print(_h(carregar_regimento(argv[1])))
        return 0
    if cmd == "assinar-ed":
        sk = bytes.fromhex(_ler_texto(argv[1]).strip())
        campos = list(argv[2:])
        if campos and campos[0] == "aprovar":
            campos[3] = campos[3].lower() == "true"
        print(assinar_humano_ed25519(sk, *campos))
        return 0
    if cmd == "cabeca":
        sk = bytes.fromhex(_ler_texto(argv[2]).strip())
        agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
        print(json.dumps(rc.cabeca(argv[1], sk, argv[3], agora), ensure_ascii=True, indent=1))
        return 0
    if cmd == "recibo":
        cab = _ler_json(argv[3])
        print(json.dumps(rc.emitir_recibo(argv[1], argv[2], cab), ensure_ascii=True, indent=1))
        return 0
    if cmd == "conferir-recibo":
        rec = _ler_json(argv[1])
        entrada = None
        if len(argv) > 3:
            entrada = _ler_json(argv[3])
        ok, motivos, resumo = rc.conferir_recibo(rec, argv[2], entrada=entrada)
        print(json.dumps({"valido": ok, "motivos": motivos, "resumo": resumo}, ensure_ascii=False, indent=1))
        return 0 if ok else 1
    if cmd == "auditar-cabeca":
        cab = _ler_json(argv[2])
        ok, motivos = rc.auditar_cabeca(argv[1], cab, argv[3])
        print(json.dumps({"confere": ok, "motivos": motivos}, ensure_ascii=False, indent=1))
        return 0 if ok else 1
    if cmd == "consistencia":
        print(json.dumps(rc.prova_consistencia(argv[1], int(argv[2]), int(argv[3]))))
        return 0
    if cmd == "conferir-consistencia":
        objs = []
        for a in argv[1:4]:
            objs.append(_ler_json(a))
        ok = rc.conferir_consistencia(objs[0], objs[1], objs[2], argv[4])
        print("CONSISTENTE: o histórico só cresceu" if ok else "INCONSISTENTE: histórico reescrito ou cabeça inválida")
        return 0 if ok else 1
    if cmd in ("anonimizar", "eliminar-titular"):
        km = _chave("COLLEGIUM_CHAVE_COFRE")
        if not km:
            print("defina COLLEGIUM_CHAVE_COFRE (16+ caracteres)", file=sys.stderr)
            return 2
        if cmd == "eliminar-titular":
            ok = Cofre(argv[1], km).eliminar(argv[2].upper(), argv[3])
            print("ELIMINADO: pseudônimos antigos deste titular não são mais religáveis" if ok else "titular não encontrado")
            return 0 if ok else 1
        docs = [argv[i + 1] for i, a in enumerate(argv) if a == "--doc"] or None
        conf = argv[argv.index("--confirmo") + 1] if "--confirmo" in argv else None
        entrada = _ler_json(argv[1])
        an = Anonimizador(Cofre(argv[3], km), docs)
        saida = ({k: an.registros(v) if isinstance(v, list) else v for k, v in entrada.items()}
                 if isinstance(entrada, dict) else an.registros(entrada))
        rel = an.relatorio()
        try:
            exportar(saida, rel, conf)
        except PermissionError:
            print(json.dumps(rel, ensure_ascii=False, indent=1))
            print(f"\nNADA FOI GRAVADO. Confira 'palavras_mantidas' e rode com --confirmo {rel['confirmacao']}")
            return 3
        with open(argv[2], "w", encoding="utf-8") as f:
            json.dump(saida, f, ensure_ascii=False, indent=1)
        print(f"gravado {argv[2]}: {rel['substituicoes']}")
        return 0
    if cmd == "emitir-ficha":
        import time
        from .portao import emitir_ficha
        seg = _chave("COLLEGIUM_SEGREDO_PORTAO")
        if not seg:
            print("defina COLLEGIUM_SEGREDO_PORTAO", file=sys.stderr)
            return 2
        print(emitir_ficha(seg, argv[1], argv[2], argv[3].split(","), time.time() + float(argv[4])))
        return 0
    if cmd in ("preregistrar", "conferir-preregistro"):
        from .preregistro import conferir, preregistrar
        try:
            reg = _registro_preregistro()
        except FileNotFoundError as e:
            print(e, file=sys.stderr)
            return 2
        if cmd == "preregistrar":
            sk = bytes.fromhex(_ler_texto(argv[2]).strip())
            r = preregistrar(argv[1], sk, reg, datetime.now(timezone.utc).isoformat(timespec="seconds"))
            print(f"selado no índice {r['i']}: {r['corpo']['dados']['sha256'][:16]}… — faça commit e envio agora")
            return 0
        ok, info = conferir(argv[1], reg, argv[2])
        print(json.dumps({"selado": ok, "registro": info}, ensure_ascii=False, indent=1))
        return 0 if ok else 1
    if cmd in ("metricas", "fatura", "conferir-fatura"):
        from .fatura import conferir_fatura, emitir_fatura, metricas
        if cmd == "metricas":
            print(json.dumps(metricas(argv[1]), ensure_ascii=False, indent=1))
            return 0
        if cmd == "fatura":
            cab = _ler_json(argv[2])
            precos = _ler_json(argv[5])
            sk = bytes.fromhex(_ler_texto(argv[6]).strip())
            print(json.dumps(emitir_fatura(argv[1], cab, float(argv[3]), float(argv[4]), precos, sk),
                             ensure_ascii=True, indent=1))
            return 0
        fat = _ler_json(argv[1])
        ok, motivos, resumo = conferir_fatura(fat, argv[2])
        print(json.dumps({"valida": ok, "motivos": motivos, "resumo": resumo}, ensure_ascii=False, indent=1))
        return 0 if ok else 1
    if cmd == "exemplo":
        return _exemplo(argv[1:])
    if cmd == "conciliar":
        return _conciliar(argv[1:])
    if cmd == "aprovar":
        return _aprovar(argv[1:])
    if cmd == "conformidade":
        from collegium_oficios.registro import carregar
        from .oficio import conformidade
        n = int(argv[2]) if len(argv) > 2 else 40
        r = conformidade(carregar(argv[1])[0], range(1, n + 1))
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r["conforme"] else 1
    if cmd == "portao":
        import time
        from .portao import Portao
        from collegium_oficios.registro import carregar
        nome_oficio = argv[argv.index("--oficio") + 1] if "--oficio" in argv else "conciliacao_bancaria"
        oficio, ferramentas = carregar(nome_oficio)
        seg, ficha = _chave("COLLEGIUM_SEGREDO_PORTAO"), os.environ.get("COLLEGIUM_FICHA")
        if not seg or not ficha:
            print("defina COLLEGIUM_SEGREDO_PORTAO e COLLEGIUM_FICHA", file=sys.stderr)
            return 2
        entrada = _ler_json(argv[3])
        lex = Lex(argv[1], Ledger(argv[2], chave=_chave("COLLEGIUM_CHAVE")), {oficio.classe: oficio.oraculo})
        Portao(lex, ferramentas(entrada), seg, ficha, time.time).servir()
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
