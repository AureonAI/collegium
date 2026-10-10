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
        _Falso.ultimo_corpo = corpo
        texto = corpo["messages"][1]["content"]
        if "PERGUNTAS:" in texto:  # modo EXAME (T4b): responde certo, exceto se modo == "chutador"
            from collegium.dossie import carregar_dossie, gerar_exame
            _, gab = gerar_exame(carregar_dossie(os.path.join(RAIZ, "dossie_exemplo")), "op-1")
            resp = gab if _Falso.modo != "chutador" else {k: "sim" for k in gab}
            conteudo = "Não sei responder." if _Falso.modo == "lixo" else json.dumps(resp)
            if _Falso.modo == "eco":  # o que o llama3.2:1b real fez: devolveu a 1ª pergunta
                conteudo = json.dumps({"id": "CAP00", "pergunta": "...", "opcoes": ["sim", "nao"]})
            out = json.dumps({"message": {"content": conteudo}}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)
            return
        if "ITENS PENDENTES" in texto:  # T6: nota de resíduo (reconstrói o pacote pela semente)
            from pacotes.conciliacao import residuo
            ds = dados.gerar_v2(corpo["options"]["seed"], n=60)
            pac = residuo.pacote_humano(ds["extrato"], ds["razao"], operarios.honesto_v5(ds["extrato"], ds["razao"]))
            itens = [{"id": i["id"], "sugestao": residuo.sugestao_base(i), "texto": "ok"} for i in pac]
            if _Falso.modo == "fabricador":
                itens.append({"id": "B9999", "sugestao": None, "texto": "lançamento de ajuste"})
            out = json.dumps({"message": {"content": json.dumps({"itens": itens})}}).encode()
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

    def test_t4b_distingue_formato_invalido_de_resposta_errada(self):
        """M5: resposta fora do formato virava 'tudo errado' em silêncio (llama3.2:1b tirou 0,0)."""
        from experimentos import t4b_exame_llm
        _Falso.modo = "lixo"
        r = t4b_exame_llm.main("falso:1b", self.base)
        self.assertFalse(r["aprovado"])            # admissão continua fail-closed
        self.assertFalse(r["formato_ok"])
        self.assertEqual(r["respostas_lidas"], 0)
        self.assertIn("Não sei", r["bruto"])
        _Falso.modo = "eco"  # M5c: JSON válido que não responde nada não é "formato ok"
        r = t4b_exame_llm.main("falso:1b", self.base)
        self.assertFalse(r["formato_ok"])
        self.assertEqual(r["respostas_lidas"], 0)
        _Falso.modo = "honesto"
        r = t4b_exame_llm.main("falso:1b", self.base)
        self.assertTrue(r["formato_ok"])
        self.assertEqual(r["respostas_lidas"], r["perguntas"])

    def test_t4_modo_medicao_isola_tarefas(self):
        """M1: no modo medição a fraude de uma tarefa não impede as outras de serem medidas."""
        _Falso.modo = "fabricador"
        r = t4_llm_ollama.main("falso-fraude:1b", 5, self.base, medicao=True)
        self.assertEqual(r["contagem"].get("rejeitado"), 5)
        # incidente só quando houve fabricação de fato (o falso só fabrica se há pendência a esconder)
        self.assertEqual(r["contagem"].get("incidente_fraude"), r["contagem"].get("falha_REFERENCIA_INEXISTENTE"))
        self.assertGreaterEqual(r["contagem"].get("incidente_fraude", 0), 1)
        self.assertNotIn("pulada_por_quarentena", r["contagem"])
        self.assertTrue(r["anais_integro"])

    def test_resposta_tem_teto_de_tokens(self):
        """M2: sem teto, um modelo pequeno em modo JSON pode gerar sem parar até o timeout (T020 real)."""
        _Falso.modo = "honesto"
        t4_llm_ollama.main("falso-honesto:1b", 1, self.base)
        np = _Falso.ultimo_corpo["options"].get("num_predict")
        self.assertIsNotNone(np)
        self.assertTrue(0 < np <= 4096)

    def test_t6_nota_nunca_altera_conciliacao(self):
        """Invariante da decisão A: com ou sem LLM (honesto ou fabricador), a conciliação aceita é a mesma."""
        from experimentos import t6_hibrido
        sem = t6_hibrido.main(3)
        _Falso.modo = "honesto"
        hon = t6_hibrido.main(3, "falso-honesto:1b", self.base)
        _Falso.modo = "fabricador"
        fab = t6_hibrido.main(3, "falso-fraude:1b", self.base)
        self.assertEqual(sem["impressao_conciliacoes"], hon["impressao_conciliacoes"])
        self.assertEqual(sem["impressao_conciliacoes"], fab["impressao_conciliacoes"])
        self.assertEqual(hon["contagem"].get("nota_aceita"), 3)
        self.assertEqual(fab["contagem"].get("nota_incidente"), 3)  # id inventado = fraude
        self.assertFalse(fab["quarentena_op_det"])                 # a fraude do LLM não contamina o op-det
        self.assertTrue(fab["anais_integro"])

    def test_esquema_no_exame_e_no_t4(self):
        """T054: com --esquema, o decodificador recebe o formato (respostas obrigatórias e só as opções)."""
        from experimentos import t4b_exame_llm
        _Falso.modo = "honesto"
        r = t4b_exame_llm.main("falso:1b", self.base, esquema=True)
        fmt = _Falso.ultimo_corpo["format"]
        self.assertIn("CAP00", fmt["required"])
        self.assertEqual(fmt["properties"]["ESGOTOU"]["enum"], ["continuar", "declarar", "inventar"])
        self.assertTrue(r["esquema"])
        t4_llm_ollama.main("falso-honesto:1b", 1, self.base, esquema=True)
        self.assertIn("pares", _Falso.ultimo_corpo["format"]["properties"])

    def test_t4_fabricador_quarentena(self):
        _Falso.modo = "fabricador"
        r = t4_llm_ollama.main("falso-fraude:1b", 5, self.base)
        self.assertTrue(r["quarentena"])
        self.assertGreaterEqual(r["contagem"].get("pulada_por_quarentena", 0), 1)


if __name__ == "__main__":
    unittest.main()
