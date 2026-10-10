"""Roda a suíte e, em cada falha, emite uma ANOTAÇÃO do GitHub Actions (::error) com o nome do teste e a
última linha do erro. Anotações são legíveis pela API mesmo quando o domínio de logs está bloqueado."""
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "tests"))


def _limpo(texto: str) -> str:
    return texto.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")[:900]


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover(os.path.join(RAIZ, "tests"), top_level_dir=os.path.join(RAIZ, "tests"))
    r = unittest.TextTestRunner(verbosity=1).run(suite)
    for tipo, lista in (("FAIL", r.failures), ("ERROR", r.errors)):
        for teste, tb in lista:
            linhas = [x for x in tb.strip().splitlines() if x.strip()]
            print(f"::error title={tipo} {teste.id()}::{_limpo(' | '.join(linhas[-3:]))}")
    sys.exit(0 if r.wasSuccessful() else 1)
