"""Executor isolado do agente (T046, segunda metade; fecha o A1 até onde o código alcança).

O processo do agente roda com AMBIENTE LIMPO (nenhum segredo herdado: só PATH, HOME, idioma e a
ficha do portão) e com o nível de isolamento que o REGIMENTO exige — FALHA FECHADA:
  "container": Docker com --network none, sistema de arquivos só-leitura, sem capacidades do
               kernel, usuário sem privilégio, limites de memória/CPU/processos. Isola rede E disco.
  "rede":      sem rede (Docker; ou, no Linux, namespace de rede via `unshare -rn`).
               ATENÇÃO: o `unshare` isola SÓ a rede; o disco do usuário continua visível.
  "nenhum":    só ambiente limpo. Precisa estar ESCRITO no REGIMENTO (que é assinado); nunca é padrão.
Sem a seção, o padrão é "rede". Se o nível exigido não estiver disponível, nada roda.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass

NIVEIS = ("container", "rede", "nenhum")


class IsolamentoIndisponivel(RuntimeError):
    pass


def _ok(cmd: list[str]) -> bool:
    try:
        return subprocess.run(cmd, capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def disponiveis() -> set[str]:
    b = set()
    if shutil.which("docker") and _ok(["docker", "info"]):
        b.add("docker")
    if platform.system() == "Linux" and shutil.which("unshare") and _ok(["unshare", "-rn", "true"]):
        b.add("unshare")
    return b


def comando(backend: str, cmd: list[str], pasta: str, imagem: str = "python:3.12-slim",
            memoria: str = "1g", cpus: str = "1") -> list[str]:
    if backend == "docker":
        return ["docker", "run", "--rm", "-i", "--network", "none", "--read-only",
                "--tmpfs", "/tmp:rw,size=64m", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                "--pids-limit", "128", "--memory", memoria, "--cpus", cpus, "--user", "65534:65534",
                "-v", f"{os.path.abspath(pasta)}:/trabalho", "-w", "/trabalho",
                "-e", "COLLEGIUM_FICHA", "-e", "HOME=/trabalho", imagem, *cmd]
    if backend == "unshare":
        return ["unshare", "-rn", "--", *cmd]
    if backend == "direto":
        return list(cmd)
    raise ValueError(f"backend desconhecido: {backend}")


@dataclass
class Resultado:
    nivel: str
    backend: str
    codigo: int
    saida: str
    erro: str


def escolher(politica: dict | None, disp: set[str]) -> tuple[str, str]:
    """Devolve (nível, backend) ou levanta IsolamentoIndisponivel. Política vem do REGIMENTO."""
    nivel = (politica or {}).get("exigido", "rede")
    if nivel not in NIVEIS:
        raise IsolamentoIndisponivel(f"nível de isolamento desconhecido: {nivel}")
    if nivel == "container":
        if "docker" in disp:
            return nivel, "docker"
        raise IsolamentoIndisponivel("REGIMENTO exige container e o Docker não está disponível: nada roda")
    if nivel == "rede":
        for b in ("docker", "unshare"):
            if b in disp:
                return nivel, b
        raise IsolamentoIndisponivel("REGIMENTO exige isolamento de rede e não há Docker nem unshare: nada roda")
    return nivel, "direto"


def executar(cmd: list[str], pasta: str, politica: dict | None, ficha: str | None = None,
             timeout: float = 600, disp: set[str] | None = None, entrada: str | None = None) -> Resultado:
    nivel, backend = escolher(politica, disponiveis() if disp is None else disp)
    env = {"PATH": os.defpath if os.name != "nt" else os.environ.get("PATH", ""), "HOME": os.path.abspath(pasta),
           "LANG": "C.UTF-8", "PYTHONIOENCODING": "utf-8"}
    if os.name == "nt":  # o Windows precisa destas para iniciar processos; não carregam segredo
        for k in ("SYSTEMROOT", "COMSPEC", "PATHEXT", "TEMP", "TMP"):
            if k in os.environ:
                env[k] = os.environ[k]
    if ficha:
        env["COLLEGIUM_FICHA"] = ficha
    try:
        p = subprocess.run(comando(backend, cmd, pasta), cwd=pasta, env=env, capture_output=True, text=True,
                           timeout=timeout, input=entrada)
        return Resultado(nivel, backend, p.returncode, p.stdout, p.stderr)
    except subprocess.TimeoutExpired as e:
        return Resultado(nivel, backend, -9, (e.stdout or "") if isinstance(e.stdout, str) else "", "TEMPO_ESGOTADO")
