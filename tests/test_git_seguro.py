"""V-1 (vídeo heliofilhou, 11/10/2026): o fluxo que todo curso de git ensina — `git add .`, `git commit`,
`git push` — publicava a CHAVE PRIVADA do humano e os DADOS DO CLIENTE quando o produto era rodado dentro de
uma cópia do repositório (que é público). E desfazer depois não desfaz: `git revert` cria um commit novo, mas
o arquivo continua no histórico. A proteção tem de vir ANTES do add."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from collegium import repositorio  # noqa: E402

TEM_GIT = shutil.which("git") is not None


def cli(*args, cwd):
    env = dict(os.environ, PYTHONPATH=RAIZ)
    return subprocess.run([sys.executable, "-m", "collegium", *args], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", env=env)


@unittest.skipUnless(TEM_GIT, "git não instalado")
class TestGitSeguro(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(self.repo)
        subprocess.run(["git", "init", "-q", self.repo], check=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_deteccao(self):
        dentro = os.path.join(self.repo, "sub", "chave.priv")
        self.assertEqual(repositorio.risco_git(dentro)["raiz"], os.path.realpath(self.repo))
        self.assertTrue(repositorio.risco_git(dentro)["publicavel"])
        self.assertIsNone(repositorio.risco_git(os.path.join(self.tmp, "fora", "chave.priv")))
        with open(os.path.join(self.repo, ".gitignore"), "w") as f:
            f.write("*.priv\n")
        self.assertFalse(repositorio.risco_git(dentro)["publicavel"])

    def test_gerar_chave_dentro_de_repositorio_e_recusado(self):
        r = cli("gerar-chave", "chave.priv", cwd=self.repo)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.repo, "chave.priv")))
        self.assertIn("git", r.stderr)
        r = cli("gerar-chave", os.path.join(self.tmp, "chave.priv"), cwd=self.repo)  # fora do repositório: ok
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(self.repo, ".gitignore"), "w") as f:
            f.write("*.priv\n")
        self.assertEqual(cli("gerar-chave", "chave.priv", cwd=self.repo).returncode, 0)  # ignorada: ok

    def test_conciliar_dentro_de_repositorio_avisa(self):
        cli("exemplo", os.path.join(self.tmp, "demo"), cwd=self.tmp)
        r = cli("conciliar", "--extrato", os.path.join(self.tmp, "demo", "extrato.ofx"),
                "--razao", os.path.join(self.tmp, "demo", "razao_contabil.csv"), "--saida", "resultado", cwd=self.repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("git add", r.stdout + r.stderr)
        r = cli("conciliar", "--extrato", os.path.join(self.tmp, "demo", "extrato.ofx"),
                "--razao", os.path.join(self.tmp, "demo", "razao_contabil.csv"), "--saida",
                os.path.join(self.tmp, "fora"), cwd=self.repo)
        self.assertNotIn("git add", r.stdout + r.stderr)

    def test_o_proprio_collegium_ignora_o_que_o_produto_grava(self):
        """No repositório PÚBLICO do projeto: chave e saídas do produto nunca entram num `git add .`."""
        if not os.path.isdir(os.path.join(RAIZ, ".git")):
            self.skipTest("não é uma cópia git")
        for p in ("chave.priv", "qualquer/coisa.priv", "demo/extrato.ofx", "resultado/relatorio.html",
                  "resultado_marco/pendencias.csv", "anais.jsonl", "x/anais.jsonl.regimento.json"):
            r = subprocess.run(["git", "-C", RAIZ, "check-ignore", "-q", "--no-index", p])
            self.assertEqual(r.returncode, 0, f"{p} NÃO está no .gitignore")
        # e o contrário: evidência e código NUNCA podem ficar ignorados (meu 1º padrão, /resultado*/, pegava
        # resultados/ e um resultado novo de experimento deixaria de ir para o GitHub em silêncio)
        for p in ("resultados/NOVO.json", "resultados/HASHES.txt", "exemplos/piloto/extrato.ofx",
                  "collegium/recibo.py", "regimento.exemplo.json", "preregistros/REGISTRO.jsonl"):
            r = subprocess.run(["git", "-C", RAIZ, "check-ignore", "-q", "--no-index", p])
            self.assertEqual(r.returncode, 1, f"{p} ficou IGNORADO por engano")


if __name__ == "__main__":
    unittest.main()
