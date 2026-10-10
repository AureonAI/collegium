"""Reproduz TODA a evidência do COLLEGIUM com sementes fixas.

Uso (Windows/Linux/macOS, Python 3.10+, sem dependências):
    python reproduzir.py              # roda tudo, grava resultados/*.json e resultados/HASHES.txt
    python reproduzir.py --conferir   # roda tudo e COMPARA com resultados/HASHES.txt (sai 1 se divergir)
Um estranho que rode o mesmo comando deve obter os MESMOS hashes. Se divergir, reporte a
versão do Python e o sistema: é resultado, não erro a esconder.
"""
import hashlib
import json
import os
import platform
import sys
import time

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)
from experimentos import a4_goodhart, a6_adaptativo, a5_mundo_sujo, t1_contencao, t2_anais, t3_autonomia, t5_equipe, t6_hibrido, t7_garantia  # noqa: E402

PLANO = [("T1_contencao", lambda: t1_contencao.main(200)),
         ("T2_anais", lambda: t2_anais.main(600)),
         ("T3_autonomia", lambda: t3_autonomia.main(2000)),
         ("A4_goodhart", lambda: a4_goodhart.main(300)),
         ("A5_mundo_sujo", lambda: a5_mundo_sujo.main(300)),
         ("T5_equipe", lambda: t5_equipe.main(200)),
         ("T6_hibrido", lambda: t6_hibrido.main(20)),  # T041: decisão A, só a parte determinística
         ("T7_garantia", lambda: t7_garantia.main()),  # T050: garantia estatística sem oráculo
         ("A6_adaptativo", lambda: a6_adaptativo.main(4000, 2028))]  # T051: atacante adaptativo (0 vitórias)


def _ler_hashes(caminho):
    if not os.path.exists(caminho):
        return {}
    with open(caminho, encoding="utf-8") as f:
        return dict(ln.split() for ln in f if ln.strip() and not ln.startswith("#"))


if __name__ == "__main__":
    conferir = "--conferir" in sys.argv
    pasta = os.path.join(RAIZ, "resultados")
    os.makedirs(pasta, exist_ok=True)
    esperado = _ler_hashes(os.path.join(pasta, "HASHES.txt"))
    obtidos, divergentes = {}, []
    print(f"Python {platform.python_version()} | {platform.system()}")
    for nome, fn in PLANO:
        t0 = time.time()
        r = fn()
        txt = json.dumps(r, indent=2, ensure_ascii=False, sort_keys=True)
        h = hashlib.sha256(txt.encode()).hexdigest()[:16]
        obtidos[nome] = h
        if not conferir:
            with open(os.path.join(pasta, f"{nome}.json"), "w", encoding="utf-8") as f:
                f.write(txt + "\n")
        veredito = r.get("veredito", r.get("resumo", ""))
        if isinstance(veredito, dict):
            veredito = veredito.get("geral", veredito)
        marca = ""
        if conferir:
            marca = "  IGUAL" if esperado.get(nome) == h else f"  DIVERGE (esperado {esperado.get(nome)})"
            if esperado.get(nome) != h:
                divergentes.append(nome)
        print(f"{nome:14s} sha256={h}  {veredito}  [{time.time() - t0:.0f}s]{marca}")
    if conferir:
        sys.exit(1 if divergentes else 0)
    with open(os.path.join(pasta, "HASHES.txt"), "w", encoding="utf-8") as f:
        f.write(f"# Python {platform.python_version()} | {platform.system()}\n")
        f.writelines(f"{k} {v}\n" for k, v in obtidos.items())
