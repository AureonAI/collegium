"""T054 (esquema na geração) e T056 (orçamento real de tokens/tempo/custo)."""
import copy
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from collegium import Acao, Ledger, Lex  # noqa: E402
from collegium.adaptadores import Ollama  # noqa: E402

with open(os.path.join(RAIZ, "regimento.exemplo.json"), encoding="utf-8") as _f:
    BASE = json.load(_f)


class _Srv(BaseHTTPRequestHandler):
    corpo = None

    def log_message(self, *a):
        pass

    def do_POST(self):
        _Srv.corpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        out = json.dumps({"message": {"content": "{}"}, "prompt_eval_count": 120, "eval_count": 30,
                          "total_duration": 2_500_000_000}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


class TestEsquemaEUso(unittest.TestCase):
    def test_esquema_vai_para_o_decodificador_e_uso_e_medido(self):
        srv = HTTPServer(("127.0.0.1", 0), _Srv)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            o = Ollama("x:1b", f"http://127.0.0.1:{srv.server_address[1]}")
            esq = {"type": "object", "properties": {"pares": {"type": "array"}}, "required": ["pares"]}
            o.conversar("s", "u", esquema=esq)
            self.assertEqual(_Srv.corpo["format"], esq)
            self.assertEqual(o.ultimo_uso, {"tokens_entrada": 120, "tokens_saida": 30, "segundos": 2.5})
            o.conversar("s", "u")
            self.assertEqual(_Srv.corpo["format"], "json")
        finally:
            srv.shutdown()
            srv.server_close()


class TestOrcamento(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        r = copy.deepcopy(BASE)
        r["classes_tarefa"]["revisao_documental"]["orcamento"] = {"tokens": 1000, "custo_centavos": 50}
        self.reg = r
        self.cam = os.path.join(self.tmp.name, "a.jsonl")
        self.lex = Lex(r, Ledger(self.cam, chave=b"k"), {})
        self.lex.abrir_tarefa("t", "revisao_documental", "op-1")

    def tearDown(self):
        self.tmp.cleanup()

    def test_estouro_so_permite_declarar(self):
        self.assertEqual(self.lex.registrar_consumo("t", tokens=600).codigo, "OK")
        self.assertTrue(self.lex.autorizar(Acao("op-1", "ferramenta", "extrato.ler", "t")).permitido)
        self.assertEqual(self.lex.registrar_consumo("t", tokens=600).codigo, "ORCAMENTO_ESGOTADO")
        self.assertEqual(self.lex.autorizar(Acao("op-1", "ferramenta", "extrato.ler", "t")).codigo, "PERSISTENCIA")
        self.assertIn("op-1", self.lex.quarentena)    # insistir depois do orçamento é incidente (Art. 3)

    def test_declarar_depois_do_estouro_e_valido(self):
        self.lex.registrar_consumo("t", custo_centavos=51)
        d = self.lex.autorizar(Acao("op-1", "declaracao", "BLOQUEADO", "t", {"evidencia": "orçamento esgotado"}))
        self.assertTrue(d.permitido)

    def test_consumo_sobrevive_ao_reinicio(self):
        self.lex.registrar_consumo("t", tokens=1001)
        novo = Lex(self.reg, Ledger(self.cam, chave=b"k"), {})
        self.assertTrue(novo.tarefas["t"].esgotada)
        self.assertEqual(novo.tarefas["t"].consumo["tokens"], 1001)

    def test_agente_nao_registra_consumo(self):
        self.assertFalse(hasattr(self.lex.mandato("op-1"), "registrar_consumo"))


if __name__ == "__main__":
    unittest.main()
