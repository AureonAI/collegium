"""T058: ANAIS em SQLite idêntico ao JSONL (linha, selo, raiz Merkle), escritores concorrentes,
adulteração, backup verificado e telemetria GenAI sem conteúdo."""
import json
import multiprocessing as mp
import os
import sqlite3
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from collegium import Ledger, Lex  # noqa: E402
from collegium import ed25519 as ed  # noqa: E402
from collegium import recibo as rc  # noqa: E402
from collegium.ledger_sqlite import LedgerSQLite, abrir_ente, backup_verificado  # noqa: E402
from collegium.telemetria import Exportador, chamada_modelo, ler  # noqa: E402
from collegium_oficios.conciliacao import dados, operarios, oraculo  # noqa: E402

with open(os.path.join(RAIZ, "regimento.exemplo.json"), encoding="utf-8") as _f:
    REG = json.load(_f)


def _escritor(caminho, k):
    L = LedgerSQLite(caminho, b"k")
    for i in range(50):
        L.anexar("x", {"escritor": k, "i": i})
    L.fechar()


class Relogio:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        self.t += 1.0
        return self.t


class TestSQLite(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_identico_ao_jsonl_byte_a_byte(self):
        j = Ledger(os.path.join(self.tmp.name, "a.jsonl"), b"k", relogio=Relogio())
        s = LedgerSQLite(os.path.join(self.tmp.name, "a.db"), b"k", relogio=Relogio())
        for L in (j, s):
            lex = Lex(REG, L, {"conciliacao_bancaria": oraculo.oraculo_lex})
            ds = dados.gerar(2)
            p = operarios.honesto_v4(ds["extrato"], ds["razao"])
            lex.abrir_tarefa("t", "conciliacao_bancaria", "op-1", entrada={"extrato": ds["extrato"], "razao": ds["razao"]})
            lex.submeter("t", "op-1", p)
            lex.verificar("t", "ex-det", p)
        self.assertEqual(j.linhas(), s.linhas())
        self.assertEqual(rc.arvore(j)[0].raiz(), rc.arvore(s)[0].raiz())
        cab = rc.cabeca(s, bytes([3]) * 32, "Ente", "x")
        ok, motivos, _ = rc.conferir_recibo(rc.emitir_recibo(s, "t", cab), ed.publica(bytes([3]) * 32).hex())
        self.assertTrue(ok, motivos)
        s.fechar()

    def test_escritores_concorrentes(self):
        cam = os.path.join(self.tmp.name, "c.db")
        LedgerSQLite(cam, b"k").fechar()
        ps = [mp.Process(target=_escritor, args=(cam, k)) for k in range(2)]
        for p in ps:
            p.start()
        for p in ps:
            p.join(60)
        L = LedgerSQLite(cam, b"k")
        self.assertEqual(len(L), 100)
        self.assertEqual(L.verificar(), (True, None))
        L.fechar()

    def test_adulteracao_detectada(self):
        cam = os.path.join(self.tmp.name, "d.db")
        L = LedgerSQLite(cam, b"k")
        for i in range(5):
            L.anexar("x", {"i": i})
        L.fechar()
        db = sqlite3.connect(cam)
        db.execute("UPDATE anais SET linha = replace(linha, '\"i\": 2}', '\"i\": 99}') WHERE i = 2")
        db.commit()
        db.close()
        with self.assertRaises(ValueError):
            LedgerSQLite(cam, b"k")

    def test_backup_verificado_e_um_arquivo_por_ente(self):
        j = Ledger(os.path.join(self.tmp.name, "b.jsonl"), b"k")
        for i in range(7):
            j.anexar("x", {"i": i})
        r = backup_verificado(j, os.path.join(self.tmp.name, "copia.db"))
        self.assertEqual(r["registros"], 7)
        with self.assertRaises(FileExistsError):
            backup_verificado(j, os.path.join(self.tmp.name, "copia.db"))
        a = abrir_ente(self.tmp.name, "Escritório Alfa Ltda", b"ka")
        self.assertTrue(a.caminho.endswith("escritorio-alfa-ltda.anais.db"))
        a.fechar()


class TestTelemetria(unittest.TestCase):
    def test_span_genai_sem_conteudo(self):
        with tempfile.TemporaryDirectory() as d:
            exp = Exportador(os.path.join(d, "spans.jsonl"))
            exp(chamada_modelo("ollama", "gemma3:4b", {"tokens_entrada": 120, "tokens_saida": 30}, "op-1", "T1", 1, 2))
            s = ler(os.path.join(d, "spans.jsonl"))[0]
            self.assertEqual(s["name"], "chat gemma3:4b")
            self.assertEqual(s["attributes"]["gen_ai.provider.name"], "ollama")
            self.assertEqual(s["attributes"]["gen_ai.usage.input_tokens"], 120)
            self.assertNotIn("error.type", s["attributes"])


if __name__ == "__main__":
    unittest.main()
