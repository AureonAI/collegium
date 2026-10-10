"""Pacote de versão REPRODUTÍVEL e assinado + SBOM CycloneDX (T062). Só biblioteca padrão.

  python ferramentas/release.py construir SAIDA_DIR [ARQUIVO_PRIVADO]
  python ferramentas/release.py verificar PACOTE.tar MANIFESTO.json CHAVE_PUBLICA

Reprodutível: arquivos rastreados pelo git, em ordem, com data, dono e permissão fixos e CRLF normalizado:
duas construções do mesmo commit dão o MESMO hash, em qualquer sistema.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import uuid

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from collegium import ed25519  # noqa: E402
from collegium.ledger import canonico  # noqa: E402

VERSAO = "0.2.0"


def arquivos() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True, check=True).stdout
    return sorted(x for x in out.splitlines() if x and not x.startswith("resultados/historico/"))


def construir_tar(lista: list[str]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        for nome in lista:
            with open(os.path.join(RAIZ, nome), "rb") as f:
                dados = f.read().replace(b"\r\n", b"\n")
            info = tarfile.TarInfo(f"collegium-{VERSAO}/{nome}")
            info.size, info.mtime, info.mode, info.uid, info.gid, info.uname, info.gname = \
                len(dados), 0, 0o644, 0, 0, "", ""
            tar.addfile(info, io.BytesIO(dados))
    return buf.getvalue()


def sbom(lista: list[str]) -> dict:
    """CycloneDX 1.5: o núcleo não tem dependência; cada arquivo entra com seu SHA-256."""
    comps = []
    for nome in lista:
        with open(os.path.join(RAIZ, nome), "rb") as f:
            h = hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()
        comps.append({"type": "file", "name": nome, "hashes": [{"alg": "SHA-256", "content": h}]})
    comps.append({"type": "library", "name": "paddleocr", "version": "3.7.0", "scope": "optional",
                  "description": "adaptador OCR opcional (não é dependência do núcleo)"})
    return {"bomFormat": "CycloneDX", "specVersion": "1.5",
            "serialNumber": f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, 'collegium-' + VERSAO)}", "version": 1,
            "metadata": {"component": {"type": "application", "name": "collegium", "version": VERSAO}},
            "components": comps}


def construir(saida: str, privada: bytes | None = None) -> dict:
    lista = arquivos()
    tar = construir_tar(lista)
    os.makedirs(saida, exist_ok=True)
    caminho = os.path.join(saida, f"collegium-{VERSAO}.tar")
    with open(caminho, "wb") as f:
        f.write(tar)
    with open(os.path.join(saida, "sbom.cdx.json"), "w", encoding="utf-8") as f:
        json.dump(sbom(lista), f, indent=1, ensure_ascii=False)
    man = {"versao": VERSAO, "pacote": os.path.basename(caminho), "sha256": hashlib.sha256(tar).hexdigest(),
           "arquivos": len(lista)}
    if privada:
        man["chave"] = ed25519.publica(privada).hex()
        man["assinatura"] = ed25519.assinar(privada, canonico({k: v for k, v in man.items() if k != "assinatura"})).hex()
    with open(os.path.join(saida, "MANIFESTO.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, indent=1)
    return man


def verificar(pacote: str, manifesto: str, chave: str) -> bool:
    with open(pacote, "rb") as f:
        h = hashlib.sha256(f.read()).hexdigest()
    with open(manifesto, encoding="utf-8") as f:
        man = json.load(f)
    sig = man.pop("assinatura", "")
    return (man.get("sha256") == h and man.get("chave") == chave
            and ed25519.verificar(bytes.fromhex(chave), canonico(man), bytes.fromhex(sig or "00")))


if __name__ == "__main__":
    if sys.argv[1] == "construir":
        sk = None
        if len(sys.argv) > 3:
            with open(sys.argv[3], encoding="utf-8") as f:
                sk = bytes.fromhex(f.read().strip())
        print(json.dumps(construir(sys.argv[2], sk), indent=1))
    elif sys.argv[1] == "verificar":
        ok = verificar(sys.argv[2], sys.argv[3], sys.argv[4])
        print("PACOTE ÍNTEGRO E ASSINADO" if ok else "PACOTE NÃO CONFERE")
        sys.exit(0 if ok else 1)
