"""V-1: o produto não deixa a chave privada nem o dado do cliente a um `git add .` de ser publicado.

Origem: o fluxo básico que todo curso de git ensina (editar, `git add`, `git commit`, `git push`). Rodar o
COLLEGIUM dentro de uma cópia de repositório e depois fazer `git add .` levava `chave.priv` e a pasta de
resultado (relatório, pendências, ANAIS, com os históricos do cliente) para o próximo push. Desfazer depois
não desfaz: `git revert` cria um commit novo, mas o arquivo continua no histórico; seria preciso reescrever
o histórico e trocar a chave. Por isso a checagem acontece ANTES de gravar.

Só biblioteca padrão. Sem git instalado, ou se a checagem falhar, considera PUBLICÁVEL (falha fechada).
"""
from __future__ import annotations

import os
import shutil
import subprocess


def _raiz_git(caminho: str) -> str | None:
    d = os.path.dirname(os.path.abspath(caminho))
    while not os.path.isdir(d):  # destino ainda não existe: sobe até um diretório que existe
        pai = os.path.dirname(d)
        if pai == d:
            return None
        d = pai
    d = os.path.realpath(d)
    while True:
        if os.path.exists(os.path.join(d, ".git")):  # pasta (repositório) ou arquivo (worktree, submódulo)
            return d
        pai = os.path.dirname(d)
        if pai == d:
            return None
        d = pai


def risco_git(caminho: str) -> dict | None:
    """None = fora de repositório git. Senão {"raiz", "publicavel"}: publicável = NÃO está no .gitignore."""
    raiz = _raiz_git(caminho)
    if raiz is None:
        return None
    alvo = os.path.realpath(os.path.abspath(caminho))  # funciona também para caminho que ainda não existe
    publicavel = True
    git = shutil.which("git")
    if git:
        try:
            rel = os.path.relpath(alvo, raiz)
            r = subprocess.run([git, "-C", raiz, "check-ignore", "-q", "--no-index", rel],
                               capture_output=True, timeout=10)
            publicavel = r.returncode != 0  # 0 = ignorado; 1 = não ignorado; outro = erro (assume publicável)
        except (OSError, ValueError, subprocess.SubprocessError):
            publicavel = True
    return {"raiz": raiz, "publicavel": publicavel}


def aviso(caminho: str, oque: str) -> str | None:
    r = risco_git(caminho)
    if not r or not r["publicavel"]:
        return None
    return (f"ATENÇÃO: {oque} está dentro de um repositório git ({r['raiz']}) e NÃO está no .gitignore. "
            "Um `git add .` seguido de `git push` publicaria isso, e apagar depois não tira do histórico. "
            "Grave fora do repositório ou acrescente o caminho ao .gitignore.")
