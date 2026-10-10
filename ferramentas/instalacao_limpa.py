"""T068 · prova de instalação COMO ESTRANHO: venv limpo, `pip install` do projeto, e o ciclo inteiro do
produto rodado FORA da pasta do projeto, só pelo comando `collegium` instalado:
  exemplo → conciliar (com humano e chave) → aprovar → cabeca → recibo → conferir-recibo → auditar-cabeca.
Roda no CI em Windows, macOS e Linux. Sai com código ≠ 0 e anotação ::error:: se qualquer passo falhar.
Uso: python ferramentas/instalacao_limpa.py
"""
import json
import locale
import os
import subprocess
import sys
import tempfile
import venv

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def falhar(passo: str, r: subprocess.CompletedProcess | None = None, msg: str = "") -> None:
    det = msg or ((r.stdout or "") + (r.stderr or "")).strip().replace("\n", " | ")[-600:]
    print(f"::error::instalacao_limpa: {passo}: {det}")
    sys.exit(1)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        venv.EnvBuilder(with_pip=True).create(os.path.join(tmp, "v"))
        bindir = os.path.join(tmp, "v", "Scripts" if os.name == "nt" else "bin")
        py = os.path.join(bindir, "python.exe" if os.name == "nt" else "python")
        r = subprocess.run([py, "-m", "pip", "install", "-q", RAIZ], capture_output=True, text=True)
        if r.returncode:
            falhar("pip install", r)
        exe = os.path.join(bindir, "collegium.exe" if os.name == "nt" else "collegium")
        fora = os.path.join(tmp, "cliente")
        os.makedirs(fora)
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "COLLEGIUM_CHAVE")}

        def c(passo: str, *args: str, codigo: int = 0) -> str:
            # decodifica como o Windows entrega (página de código local); JSON de máquina sai em ASCII (R6-10)
            r = subprocess.run([exe, *args], cwd=fora, capture_output=True, text=True,
                               encoding=locale.getpreferredencoding(False), errors="replace", env=env)
            if r.returncode != codigo:
                falhar(f"{passo} (saída {r.returncode}, esperado {codigo})", r)
            return r.stdout

        c("versao", "--versao")
        c("exemplo", "exemplo", "demo")
        pub = c("gerar-chave", "gerar-chave", "chave.priv").strip().splitlines()[-1]
        c("conciliar", "conciliar", "--extrato", os.path.join("demo", "extrato.ofx"),
          "--razao", os.path.join("demo", "razao_contabil.csv"), "--saida", "res", "--anais", "anais.jsonl",
          "--chave", "chave.priv", "--humano", "ana", "--chave-publica", pub)
        with open(os.path.join(fora, "res", "resumo.json"), encoding="utf-8") as f:
            resumo = json.load(f)
        if resumo.get("status") != "CONCILIADO" or not resumo.get("pares") or not resumo.get("anais_integro"):
            falhar("resumo", msg=json.dumps({k: resumo.get(k) for k in ("status", "pares", "anais_integro")}))
        t = resumo["tarefa"]
        c("aprovar", "aprovar", "--anais", "anais.jsonl", "--tarefa", t, "--humano", "ana", "--chave", "chave.priv")
        with open(os.path.join(fora, "cab.json"), "w", encoding="utf-8") as f:
            f.write(c("cabeca", "cabeca", "anais.jsonl", "chave.priv", "Empresa Demo"))
        with open(os.path.join(fora, "rec.json"), "w", encoding="utf-8") as f:
            f.write(c("recibo", "recibo", "anais.jsonl", t, "cab.json"))
        out = json.loads(c("conferir-recibo", "conferir-recibo", "rec.json", pub))
        if not out["valido"] or out["resumo"]["estado_final"] != "LIBERADA":
            falhar("conferir-recibo", msg=json.dumps(out, ensure_ascii=False)[:600])
        if not json.loads(c("auditar-cabeca", "auditar-cabeca", "anais.jsonl", "cab.json", pub))["confere"]:
            falhar("auditar-cabeca")
        c("repetir a mesma entrada é recusado", "conciliar", "--extrato", os.path.join("demo", "extrato.ofx"),
          "--razao", os.path.join("demo", "razao_contabil.csv"), "--saida", "res2", "--anais", "anais.jsonl",
          codigo=1)
    print("OK: instalado como estranho; exemplo → conciliar → aprovar → recibo LIBERADA conferido e auditado")


if __name__ == "__main__":
    main()
