"""Testa o encanamento do T4 com um servidor Ollama FALSO (sem rede externa).
Não mede LLM nenhum: só prova que adaptador + LEX + oráculo conversam corretamente."""
import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from collegium.adaptadores import Ollama, extrair_json  # noqa: E402
from experimentos import t4_llm_ollama  # noqa: E402
from pacotes.conciliacao import dados, operarios  # noqa: E402


class _Falso(BaseHTTPRequestHandler):
    modo = "honesto"

    def log_message(self, *a):
        pass

    def do_POST(self):
        corpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        texto = corpo["messages"][1]["content"]
        if "PERGUNTAS:" in texto:  # modo EXAME (T4b): responde certo, exceto se modo == "chutador"
            from collegium.dossie import carregar_dossie, gerar_exame
            _, gab = gerar_exame(carregar_dossie(os.path.join(RAIZ, "dossie_exemplo")), "op-1")
            resp = gab if _Falso.modo != "chutador" else {k: "sim" for k in gab}
            out = json.dumps({"message": {"content": json.dumps(resp)}}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)
            return
        # reconstrói o dataset a partir da semente embutida no fluxo do T4
        s = corpo["options"]["seed"]
        ds = dados.gerar(1000 + s, n=12, taxa_sem_par=0.15, taxa_duplicata=0.15)
        assert ds["extrato"][0]["id"] in texto
        if _Falso.modo == "honesto":
            resp = operarios.honesto_v4(ds["extrato"], ds["razao"])
        else:
            resp = operarios.fabricador(ds["extrato"], ds["razao"])
        out = json.dumps({"message": {"content": "ok:\n" + json.dumps(resp)}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


class TestAdaptador(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), _Falso)
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def test_familia(self):
        self.assertEqual(Ollama("qwen2.5-coder:1.5b").familia, "qwen")
        self.assertEqual(Ollama("gemma3:4b").familia, "gemma")
        self.assertEqual(Ollama("llama3.2:1b").familia, "llama")

    def test_extrair_json(self):
        self.assertEqual(extrair_json('lixo {"a": 1} fim'), {"a": 1})
        self.assertIsNone(extrair_json("sem json"))

    def test_t4_honesto_aceito(self):
        _Falso.modo = "honesto"
        r = t4_llm_ollama.main("falso-honesto:1b", 5, self.base)
        self.assertEqual(r["contagem"].get("aceito"), 5)
        self.assertTrue(r["anais_integro"])

    def test_t4b_exame_encanamento(self):
        from experimentos import t4b_exame_llm
        _Falso.modo = "honesto"
        self.assertTrue(t4b_exame_llm.main("falso:1b", self.base)["aprovado"])
        _Falso.modo = "chutador"
        r = t4b_exame_llm.main("falso:1b", self.base)
        self.assertFalse(r["aprovado"])
        self.assertFalse(r["acertou_DADO_ORDEM"] is False and "DADO_ORDEM" not in r["erradas"])

    def test_t4_fabricador_quarentena(self):
        _Falso.modo = "fabricador"
        r = t4_llm_ollama.main("falso-fraude:1b", 5, self.base)
        self.assertTrue(r["quarentena"])
        self.assertGreaterEqual(r["contagem"].get("pulada_por_quarentena", 0), 1)


if __name__ == "__main__":
    unittest.main()
