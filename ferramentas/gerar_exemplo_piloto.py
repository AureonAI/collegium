"""Regrava exemplos/piloto/ a partir do gerador empacotado (collegium_oficios.conciliacao.exemplo).
Uso: python ferramentas/gerar_exemplo_piloto.py"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from collegium_oficios.conciliacao.exemplo import escrever, gerar  # noqa: E402,F401

DESTINO = os.path.join(RAIZ, "exemplos", "piloto")

if __name__ == "__main__":
    for c in escrever(DESTINO):
        print(c)
