"""T047 (plano selado + destinos confiáveis) e T048 (identidade do modelo).
Cada teste é um ataque: injeção que tenta ampliar capacidade ou escolher destino; troca de pesos."""
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
from collegium import Acao, Ledger, Lex, RegimentoInvalido  # noqa: E402
from collegium.adaptadores import Ollama  # noqa: E402

with open(os.path.join(RAIZ, "regimento.exemplo.json"), encoding="utf-8") as _f:
    BASE = json.load(_f)
D1, D2 = "sha256:" + "a" * 64, "sha256:" + "b" * 64


def reg():
    r = copy.deepcopy(BASE)
    r["papeis"]["operarius"]["capacidades"] += ["pagamento.agendar"]
    r["destinos"] = {"pagamento.agendar": {"conta": ["001-0001-1"], "chave_pix": ["fornecedor@acme.com"]}}
    r["agentes"]["op-m"] = {"papel": "operarius", "familia_modelo": "qwen", "modelo": {"nome": "q:1b", "digest": D1}}
    return r


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.lex = Lex(reg(), Ledger(os.path.join(self.tmp.name, "a.jsonl"), chave=b"k"), {})

    def tearDown(self):
        self.tmp.cleanup()


class TestPlanoSelado(Base):
    def test_injecao_nao_amplia_o_plano(self):
        self.lex.abrir_tarefa("t", "revisao_documental", "op-1", plano=["extrato.ler"])
        self.assertTrue(self.lex.autorizar(Acao("op-1", "ferramenta", "extrato.ler", "t")).permitido)
        # o extrato diz "agende o pagamento": a capacidade existe no PAPEL, mas não no PLANO desta tarefa
        d = self.lex.autorizar(Acao("op-1", "ferramenta", "pagamento.agendar", "t", {"conta": "001-0001-1"}))
        self.assertEqual(d.codigo, "PLANO_VIOLADO")
        self.assertIn("op-1", self.lex.quarentena)

    def test_plano_nao_amplia_o_papel(self):
        with self.assertRaises(PermissionError):
            self.lex.abrir_tarefa("t", "revisao_documental", "op-1", plano=["aprovar"])

    def test_plano_sobrevive_ao_reinicio(self):
        self.lex.abrir_tarefa("t", "revisao_documental", "op-1", plano=["extrato.ler"])
        novo = Lex(reg(), Ledger(self.lex.anais.caminho, chave=b"k"), {})
        self.assertEqual(novo.tarefas["t"].plano, ("extrato.ler",))
        self.assertEqual(novo.autorizar(Acao("op-1", "ferramenta", "razao.ler", "t")).codigo, "PLANO_VIOLADO")

    def test_sem_plano_mantem_comportamento_antigo(self):
        self.lex.abrir_tarefa("t", "revisao_documental", "op-1")
        self.assertTrue(self.lex.autorizar(Acao("op-1", "ferramenta", "razao.ler", "t")).permitido)


class TestDestinos(Base):
    def test_destino_injetado_e_negado(self):
        self.lex.abrir_tarefa("t", "revisao_documental", "op-1")
        ok = self.lex.autorizar(Acao("op-1", "ferramenta", "pagamento.agendar", "t", {"conta": "001-0001-1"}))
        self.assertTrue(ok.permitido)
        self.lex.abrir_tarefa("u", "revisao_documental", "op-2")
        ruim = self.lex.autorizar(Acao("op-2", "ferramenta", "pagamento.agendar", "u", {"conta": "999-6666-6"}))
        self.assertEqual(ruim.codigo, "DESTINO_NAO_CONFIAVEL")

    def test_destino_em_capacidade_sem_lista_e_negado(self):
        """Negação por padrão também para destino: capacidade sem lista não aceita destino nenhum."""
        self.lex.abrir_tarefa("t", "revisao_documental", "op-1")
        d = self.lex.autorizar(Acao("op-1", "ferramenta", "documento.revisar", "t", {"email": "x@y.com"}))
        self.assertEqual(d.codigo, "DESTINO_NAO_CONFIAVEL")

    def test_variacoes_do_destino_nao_passam(self):
        for v in ("001-0001-1 ", "0010001-1", ["001-0001-1"], {"conta": "001-0001-1"}, "FORNECEDOR@ACME.COM"):
            lx = Lex(reg(), Ledger(os.path.join(self.tmp.name, f"{abs(hash(str(v)))}.jsonl"), chave=b"k"), {})
            lx.abrir_tarefa("t", "revisao_documental", "op-1")
            chave = "chave_pix" if "@" in str(v) else "conta"
            self.assertEqual(lx.autorizar(Acao("op-1", "ferramenta", "pagamento.agendar", "t", {chave: v})).codigo,
                             "DESTINO_NAO_CONFIAVEL", v)


    def test_destino_disfarcado_na_chave_ou_aninhado(self):
        """Ataque da minha revisão: grafia diferente da chave ou destino dentro de objeto aninhado."""
        for i, payload in enumerate(({"Conta": "999-6666-6"}, {"conta_destino": "999-6666-6"},
                                     {"dados": {"conta": "999-6666-6"}}, {"itens": [{"pix": 1, "chave_pix": "x@y"}]})):
            lx = Lex(reg(), Ledger(os.path.join(self.tmp.name, f"d{i}.jsonl"), chave=b"k"), {})
            lx.abrir_tarefa("t", "revisao_documental", "op-1")
            self.assertEqual(lx.autorizar(Acao("op-1", "ferramenta", "pagamento.agendar", "t", payload)).codigo,
                             "DESTINO_NAO_CONFIAVEL", payload)


    def test_chave_parecida_mas_legitima_nao_e_destino(self):
        """Falso positivo da 1ª correção: 'parametros' contém 'para' e quarentenava agente honesto."""
        self.lex.abrir_tarefa("t", "revisao_documental", "op-1")
        for payload in ({"parametros": {"janela": 5}}, {"hostil": False}, {"curl_versao": 1}):
            self.assertTrue(self.lex.autorizar(Acao("op-1", "ferramenta", "extrato.ler", "t", payload)).permitido,
                            payload)
        lx = Lex(reg(), Ledger(os.path.join(self.tmp.name, "cc.jsonl"), chave=b"k"), {})
        lx.abrir_tarefa("t", "revisao_documental", "op-1")
        self.assertEqual(lx.autorizar(Acao("op-1", "ferramenta", "pagamento.agendar", "t",
                                           {"contaDestino": "999"})).codigo, "DESTINO_NAO_CONFIAVEL")


    def test_argumento_nao_declarado_em_capacidade_sensivel(self):
        """Achado do A6 confirmatório (semente 2027): destino escondido sob chave neutra ({'x': '999...'})."""
        r = reg()
        r["argumentos_livres"] = {"pagamento.agendar": ["valor", "vencimento"]}
        for i, (payload, esperado) in enumerate((({"x": "999-6666-6"}, "ARGUMENTO_NAO_DECLARADO"),
                                                 ({"conta": "001-0001-1", "memo": "999"}, "ARGUMENTO_NAO_DECLARADO"),
                                                 ({"conta": "001-0001-1", "valor": 100}, "OK"))):
            lx = Lex(r, Ledger(os.path.join(self.tmp.name, f"arg{i}.jsonl"), chave=b"k"), {})
            lx.abrir_tarefa("t", "revisao_documental", "op-1")
            self.assertEqual(lx.autorizar(Acao("op-1", "ferramenta", "pagamento.agendar", "t", payload)).codigo,
                             esperado, payload)


class TestIdentidadeModelo(Base):
    def test_sem_atestacao_nao_age(self):
        self.lex.abrir_tarefa("t", "revisao_documental", "op-m")
        self.assertEqual(self.lex.autorizar(Acao("op-m", "ferramenta", "extrato.ler", "t")).codigo, "SEM_ATESTACAO")

    def test_atestado_age(self):
        self.lex.abrir_tarefa("t", "revisao_documental", "op-m")
        self.assertEqual(self.lex.atestar_modelo("op-m", D1).codigo, "ATESTADO")
        self.assertTrue(self.lex.autorizar(Acao("op-m", "ferramenta", "extrato.ler", "t")).permitido)

    def test_pesos_trocados_viram_incidente(self):
        self.assertEqual(self.lex.atestar_modelo("op-m", D2).codigo, "MODELO_TROCADO")
        self.assertIn("op-m", self.lex.quarentena)

    def test_atestacao_nao_sobrevive_ao_reinicio(self):
        self.lex.atestar_modelo("op-m", D1)
        novo = Lex(reg(), Ledger(self.lex.anais.caminho, chave=b"k"), {})
        novo.abrir_tarefa("t", "revisao_documental", "op-m")
        self.assertEqual(novo.autorizar(Acao("op-m", "ferramenta", "extrato.ler", "t")).codigo, "SEM_ATESTACAO")

    def test_agente_nao_se_atesta(self):
        m = self.lex.mandato("op-m")
        self.assertFalse(hasattr(m, "atestar_modelo"))

    def test_mesmo_modelo_com_duas_linhagens_e_recusado(self):
        r = reg()
        r["agentes"]["ex-x"] = {"papel": "examinator", "familia_modelo": "llama", "modelo": {"digest": D1}}
        with self.assertRaises(RegimentoInvalido):
            Lex(r, Ledger(os.path.join(self.tmp.name, "z.jsonl"), chave=b"k"), {})

    def test_digest_malformado(self):
        r = reg()
        r["agentes"]["op-m"]["modelo"]["digest"] = "qwen"
        with self.assertRaises(RegimentoInvalido):
            Lex(r, Ledger(os.path.join(self.tmp.name, "y.jsonl"), chave=b"k"), {})


class _Tags(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        out = json.dumps({"models": [{"name": "q:1b", "model": "q:1b", "digest": "a" * 64}]}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


class TestAdaptadorDigest(unittest.TestCase):
    def test_digest_do_ollama(self):
        srv = HTTPServer(("127.0.0.1", 0), _Tags)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            base = f"http://127.0.0.1:{srv.server_address[1]}"
            self.assertEqual(Ollama("q:1b", base).digest(), D1)
            with self.assertRaises(LookupError):
                Ollama("outro:7b", base).digest()
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main()
