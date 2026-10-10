"""Publica a cabeça do pré-registro e da reprodução como ANOTAÇÃO do GitHub (testemunha externa, T061)."""
import hashlib
import json
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
reg = os.path.join(RAIZ, "preregistros", "REGISTRO.jsonl")
if os.path.exists(reg):
    with open(reg, encoding="utf-8") as f:
        linhas = [x for x in f if x.strip()]
    ult = json.loads(linhas[-1])
    print(f"::notice title=Pré-registro (testemunha)::{len(linhas)} registros; cabeça {ult['selo']}")
with open(os.path.join(RAIZ, "resultados", "HASHES.txt"), "rb") as f:
    print(f"::notice title=Hashes da evidência::sha256 {hashlib.sha256(f.read().replace(b'\r\n', b'\n')).hexdigest()}")
