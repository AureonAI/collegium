"""Portão antes de QUALQUER envio (P-A4/P-A6 viraram código em vez de disciplina).

Roda a suíte inteira com três sementes de hash do Python (0, 1 e 4242: ordem de dicionário e de
conjunto muda, e foi assim que o defeito P-A3 apareceu só em 4 de 12 máquinas) e, com --completo,
também `reproduzir.py --conferir`. Sai com código diferente de zero se QUALQUER etapa falhar —
nada de `| tail` escondendo o código de saída.

Uso:  python ferramentas/pre_envio.py            (suíte × 3 sementes, ~1 min)
      python ferramentas/pre_envio.py --completo (+ instalação limpa e reprodução dos hashes, ~6 min)
"""
import os
import subprocess
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def etapa(nome: str, cmd: list[str], env_extra: dict | None = None) -> bool:
    t0 = time.time()
    env = dict(os.environ, **(env_extra or {}))
    r = subprocess.run(cmd, cwd=RAIZ, env=env, capture_output=True, text=True, errors="replace")
    ok = r.returncode == 0
    print(f"{'OK   ' if ok else 'FALHA'} {nome} [{time.time() - t0:.0f}s]")
    if not ok:
        print("\n".join((r.stdout + r.stderr).strip().splitlines()[-25:]))
    return ok


if __name__ == "__main__":
    py = sys.executable
    # W-5: a semente 1 roda com saída em cp1252, como os processos-filho no Windows; foi assim que o CI
    # pegou o que este portão não pegava (passo verde no Linux, vermelho nas 4 máquinas Windows).
    win = {"PYTHONIOENCODING": "cp1252"}
    etapas = [(f"suíte, PYTHONHASHSEED={s}{' + saída cp1252' if s == '1' else ''}", [py, "ferramentas/testes_ci.py"],
               dict({"PYTHONHASHSEED": s}, **(win if s == "1" else {}))) for s in ("0", "1", "4242")]
    if "--completo" in sys.argv:
        etapas.append(("instalação como estranho (saída cp1252)", [py, "ferramentas/instalacao_limpa.py"], win))
        etapas.append(("reproduzir.py --conferir", [py, "reproduzir.py", "--conferir"], None))
    falhas = [n for n, c, e in etapas if not etapa(n, c, e)]
    print("PODE ENVIAR" if not falhas else f"NÃO ENVIE: {falhas}")
    sys.exit(1 if falhas else 0)
