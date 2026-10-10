"""Dossiê, EXAME, Rector, Actuarius e CLI."""
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from collegium import Acao, Ledger, Lex  # noqa: E402
from collegium.dossie import admitir, carregar_dossie, corrigir, gerar_exame  # noqa: E402
from collegium.equipe import Rector, memoria_md, painel_html, relatorio  # noqa: E402
from collegium_oficios.conciliacao import dados, oraculo  # noqa: E402

PASTA = os.path.join(RAIZ, "dossie_exemplo")


class TestDossie(unittest.TestCase):
    def setUp(self):
        self.d = carregar_dossie(PASTA)
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_dossie_incompleto_ou_sem_fora_do_escopo(self):
        p = os.path.join(self.tmp.name, "d")
        shutil.copytree(PASTA, p)
        os.remove(os.path.join(p, "VOZ.md"))
        with self.assertRaises(FileNotFoundError):
            carregar_dossie(p)
        shutil.copy(os.path.join(PASTA, "VOZ.md"), p)
        with open(os.path.join(p, "MANDATO.md"), "w", encoding="utf-8") as f:
            f.write("# sem seção de exclusões")
        with self.assertRaises(ValueError):
            carregar_dossie(p)

    def test_exame_tem_regras_mandato_e_exclusoes(self):
        perg, gab = gerar_exame(self.d, "op-1")
        ids = {q["id"] for q in perg}
        self.assertTrue({"ESGOTOU", "AUTOVERIF", "IRREV", "DADO_ORDEM", "MAN00", "FORA00"} <= ids)
        self.assertEqual(gab["ESGOTOU"], "declarar")
        self.assertNotIn("resposta", json.dumps(perg))  # o agente não recebe o gabarito
        self.assertEqual(corrigir(gab, {k: v.upper() + "." for k, v in gab.items()})[0], 1.0)

    def test_admissao_aprova_e_reprova(self):
        reg = copy.deepcopy(self.d["REGIMENTO.json"])
        reg["admissao"]["exigida"] = True
        lex = Lex(reg, Ledger(os.path.join(self.tmp.name, "a.jsonl"), chave=b"k"), {}, b"p")
        perg, gab = gerar_exame(self.d, "op-1")
        self.assertTrue(admitir(lex, "op-1", perg, gab, gab)[0])
        ruim = {k: "sim" for k in gab}
        self.assertFalse(admitir(lex, "op-2", perg, gab, ruim)[0])
        self.assertEqual(lex.admitidos, {"op-1"})


class TestEquipe(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.reg = carregar_dossie(PASTA)["REGIMENTO.json"]
        self.lex = Lex(self.reg, Ledger(os.path.join(self.tmp.name, "a.jsonl"), chave=b"k"),
                       {"conciliacao_bancaria": oraculo.oraculo_lex}, b"p")

    def tearDown(self):
        self.tmp.cleanup()

    def test_rector_nunca_escolhe_quarentena_e_respeita_linhagem(self):
        r = Rector(self.lex, ["op-1", "op-2", "op-3"])
        ds = dados.gerar(1)
        self.lex.abrir_tarefa("x", "conciliacao_bancaria", "op-1", entrada={"extrato": ds["extrato"], "razao": ds["razao"]})
        self.lex.autorizar(Acao("op-1", "rede", "paste.rs", "x"))
        escolhidos = {r.escolher("conciliacao_bancaria") for _ in range(10)}
        self.assertNotIn("op-1", escolhidos)
        self.assertEqual(r.escolher("conciliacao_bancaria", frozenset({"qwen"})), "op-2")  # op-3 é qwen+deepseek
        self.assertIsNone(Rector(self.lex, ["op-1"]).escolher("conciliacao_bancaria"))

    def test_actuarius_memoria_e_painel(self):
        rel = relatorio(self.lex)
        self.assertTrue(rel["integro"])
        self.assertIn("Matriz de autonomia", memoria_md(rel))
        h = painel_html(rel)
        self.assertTrue(h.startswith("<!doctype html>") and "prefers-color-scheme" in h)


class TestCLI(unittest.TestCase):
    def test_cli_verificar_ancora_assinar(self):
        with tempfile.TemporaryDirectory() as t:
            cam = os.path.join(t, "a.jsonl")
            L = Ledger(cam, chave=b"segredo")
            for i in range(3):
                L.anexar("x", {"i": i})
            env = dict(os.environ, COLLEGIUM_CHAVE="segredo", COLLEGIUM_CHAVE_PATRONUS="pp")
            run = lambda *a: subprocess.run([sys.executable, "-m", "collegium", *a], cwd=RAIZ, env=env,
                                            capture_output=True, text=True)
            r = run("ancora", cam)
            self.assertEqual(r.returncode, 0, r.stderr)
            anc = r.stdout.strip().split()[-1]
            self.assertEqual(run("verificar", cam, "--ancora", anc).returncode, 0)
            with open(cam, encoding="utf-8") as f:
                linhas = f.readlines()[:-1]
            with open(cam, "w", encoding="utf-8") as f:
                f.writelines(linhas)
            self.assertNotEqual(run("verificar", cam, "--ancora", anc).returncode, 0)
            s = run("assinar", "aprovar", "T1", "abc", "true", "renato")
            from collegium.lex import assinar_humano
            self.assertEqual(s.stdout.strip(), assinar_humano(b"pp", "aprovar", "T1", "abc", True, "renato"))


if __name__ == "__main__":
    unittest.main()
