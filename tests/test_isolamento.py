"""T046 (executor): ambiente limpo, rede cortada, falha fechada, tempo esgotado."""
import os
import platform
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collegium import isolamento as iso  # noqa: E402

PY = sys.executable
TEM_UNSHARE = "unshare" in iso.disponiveis()


class TestIsolamento(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_segredo_do_orquestrador_nao_vaza_para_o_agente(self):
        os.environ["COLLEGIUM_CHAVE_PATRONUS"] = "segredo-que-nao-pode-vazar"
        try:
            r = iso.executar([PY, "-c", "import os,json;print(json.dumps(sorted(os.environ)))"], self.tmp.name,
                             {"exigido": "nenhum"}, ficha="v1.x.y")
        finally:
            del os.environ["COLLEGIUM_CHAVE_PATRONUS"]
        self.assertNotIn("COLLEGIUM_CHAVE_PATRONUS", r.saida)
        self.assertIn("COLLEGIUM_FICHA", r.saida)
        self.assertEqual(r.backend, "direto")

    def test_falha_fechada(self):
        with self.assertRaises(iso.IsolamentoIndisponivel):
            iso.executar([PY, "-c", "print(1)"], self.tmp.name, {"exigido": "container"}, disp=set())
        with self.assertRaises(iso.IsolamentoIndisponivel):
            iso.executar([PY, "-c", "print(1)"], self.tmp.name, None, disp=set())   # padrão = rede
        with self.assertRaises(iso.IsolamentoIndisponivel):
            iso.escolher({"exigido": "mais-ou-menos"}, {"docker"})

    def test_escolha_de_backend(self):
        self.assertEqual(iso.escolher({"exigido": "rede"}, {"docker", "unshare"}), ("rede", "docker"))
        self.assertEqual(iso.escolher({"exigido": "rede"}, {"unshare"}), ("rede", "unshare"))
        self.assertEqual(iso.escolher({"exigido": "container"}, {"docker"}), ("container", "docker"))

    def test_comando_docker_fecha_rede_disco_e_privilegio(self):
        c = iso.comando("docker", ["python", "agente.py"], self.tmp.name)
        for item in ("--network", "none", "--read-only", "--cap-drop", "ALL", "no-new-privileges", "65534:65534"):
            self.assertIn(item, c)

    @unittest.skipUnless(TEM_UNSHARE, "precisa de Linux com unshare")
    def test_rede_cortada_de_verdade(self):
        codigo = ("import socket;s=socket.socket();s.settimeout(3);"
                  "print('CONECTOU' if s.connect_ex(('1.1.1.1',53))==0 else 'SEM_REDE')")
        r = iso.executar([PY, "-c", codigo], self.tmp.name, {"exigido": "rede"}, disp={"unshare"})
        self.assertEqual(r.backend, "unshare")
        self.assertIn("SEM_REDE", r.saida)

    def test_tempo_esgotado(self):
        r = iso.executar([PY, "-c", "import time;time.sleep(5)"], self.tmp.name, {"exigido": "nenhum"}, timeout=0.5)
        self.assertEqual(r.erro, "TEMPO_ESGOTADO")


if __name__ == "__main__":
    unittest.main()
