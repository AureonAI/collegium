"""T043: o cliente confere o recibo sozinho. Cada teste é um golpe do OPERADOR contra o cliente."""
import copy
import json
import os
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from collegium import Ledger, Lex  # noqa: E402
from collegium import ed25519 as ed  # noqa: E402
from collegium import recibo as rc  # noqa: E402
from pacotes.conciliacao import dados, operarios, oraculo  # noqa: E402

with open(os.path.join(RAIZ, "regimento.exemplo.json"), encoding="utf-8") as _f:
    REG = json.load(_f)
SK = bytes([7]) * 32
PUB = ed.publica(SK).hex()


class TestRecibo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cam = os.path.join(self.tmp.name, "a.jsonl")
        self.lex = Lex(REG, Ledger(self.cam, chave=b"segredo-do-operador"), {"conciliacao_bancaria": oraculo.oraculo_lex})
        self.ent = {}
        for tid, op in (("boa", operarios.honesto_v4), ("ruim", operarios.fabricador), ("outra", operarios.honesto_v4)):
            ds = dados.gerar({"boa": 2, "ruim": 3, "outra": 4}[tid])
            self.ent[tid] = {"extrato": ds["extrato"], "razao": ds["razao"]}
            p = op(ds["extrato"], ds["razao"])
            prod = "op-1" if tid != "ruim" else "op-2"
            self.lex.abrir_tarefa(tid, "conciliacao_bancaria", prod, entrada=self.ent[tid])
            self.lex.submeter(tid, prod, p)
            self.lex.verificar(tid, "ex-det", p)
        self.cab = rc.cabeca(self.cam, SK, "Escritório Exemplo", "2026-10-10T06:00:00-03:00")

    def tearDown(self):
        self.tmp.cleanup()

    def test_cliente_confere_sozinho(self):
        rec = json.loads(json.dumps(rc.emitir_recibo(self.cam, "boa", self.cab)))  # viaja como arquivo
        ok, motivos, resumo = rc.conferir_recibo(rec, PUB, entrada=self.ent["boa"])
        self.assertTrue(ok, motivos)
        self.assertTrue(resumo["aceito"] and resumo["por_oraculo"])
        self.assertEqual(resumo["verificador"], "ex-det")

    def test_chave_que_o_cliente_nao_conhece(self):
        outra = rc.cabeca(self.cam, bytes([8]) * 32, "Escritório Exemplo", "x")
        self.assertEqual(rc.conferir_recibo(rc.emitir_recibo(self.cam, "boa", outra), PUB)[1],
                         ["CABECA_NAO_ASSINADA_PELA_CHAVE_CONFIAVEL"])

    def test_virar_rejeicao_em_aceite(self):
        rec = rc.emitir_recibo(self.cam, "ruim", self.cab)
        self.assertIn("RECIBO_DE_REJEICAO", rc.conferir_recibo(rec, PUB)[1])
        for it in rec["itens"]:
            it["linha"] = it["linha"].replace('"aceito": false', '"aceito": true')
        ok, motivos, _ = rc.conferir_recibo(rec, PUB)
        self.assertFalse(ok)
        self.assertTrue(any(m.startswith("INCLUSAO_FALHOU") for m in motivos))

    def test_recibo_sobre_os_dados_de_outro_cliente(self):
        rec = rc.emitir_recibo(self.cam, "outra", self.cab)
        rec["tarefa"] = "boa"
        self.assertIn("OUTRA_TAREFA", " ".join(rc.conferir_recibo(rec, PUB)[1]))
        rec2 = rc.emitir_recibo(self.cam, "outra", self.cab)
        self.assertIn("NAO_E_A_SUA_ENTRADA", rc.conferir_recibo(rec2, PUB, entrada=self.ent["boa"])[1])

    def test_indice_trocado(self):
        rec = rc.emitir_recibo(self.cam, "boa", self.cab)
        rec["itens"][0]["indice"] += 1
        self.assertFalse(rc.conferir_recibo(rec, PUB)[0])

    def test_reescrita_do_historico_depois_da_cabeca(self):
        antiga = self.cab
        with open(self.cam, encoding="utf-8") as f:
            linhas = f.readlines()
        alvo = next(i for i, ln in enumerate(linhas) if '"permitido": true' in ln)
        linhas[alvo] = linhas[alvo].replace('"permitido": true', '"permitido": false')
        self.assertLess(alvo, antiga["tamanho"])  # a reescrita é DENTRO do trecho que o cliente já viu
        with open(self.cam, "w", encoding="utf-8") as f:
            f.writelines(linhas)
        nova = rc.cabeca(self.cam, SK, "Escritório Exemplo", "depois")
        prova = rc.prova_consistencia(self.cam, antiga["tamanho"], nova["tamanho"])
        self.assertFalse(rc.conferir_consistencia(antiga, nova, prova, PUB))

    def test_crescimento_honesto_e_consistente(self):
        antiga = self.cab
        ds = dados.gerar(9)
        self.lex.abrir_tarefa("mais", "conciliacao_bancaria", "op-1", entrada={"extrato": ds["extrato"], "razao": ds["razao"]})
        nova = rc.cabeca(self.cam, SK, "Escritório Exemplo", "depois")
        self.assertGreater(nova["tamanho"], antiga["tamanho"])
        self.assertTrue(rc.conferir_consistencia(antiga, nova, rc.prova_consistencia(
            self.cam, antiga["tamanho"], nova["tamanho"]), PUB))

    def test_malformado_falha_fechado(self):
        for ruim in (None, {}, {"formato": rc.FORMATO_RECIBO}, {"formato": rc.FORMATO_RECIBO, "tarefa": "x",
                                                             "cabeca": self.cab, "itens": [{"indice": "a"}]}):
            ok, motivos, _ = rc.conferir_recibo(ruim, PUB)
            self.assertFalse(ok)

    def test_cabeca_adulterada(self):
        c = copy.deepcopy(self.cab)
        c["tamanho"] += 1
        self.assertFalse(rc.conferir_cabeca(c, PUB))


if __name__ == "__main__":
    unittest.main()


class TestCLIRecibo(unittest.TestCase):
    def test_ponta_a_ponta_pela_linha_de_comando(self):
        import contextlib
        import io
        from collegium.__main__ import main
        with tempfile.TemporaryDirectory() as d:
            cam = os.path.join(d, "a.jsonl")
            lex = Lex(REG, Ledger(cam, chave=b"k"), {"conciliacao_bancaria": oraculo.oraculo_lex})
            ds = dados.gerar(2)
            ent = {"extrato": ds["extrato"], "razao": ds["razao"]}
            p = operarios.honesto_v4(ds["extrato"], ds["razao"])
            lex.abrir_tarefa("t1", "conciliacao_bancaria", "op-1", entrada=ent)
            lex.submeter("t1", "op-1", p)
            lex.verificar("t1", "ex-det", p)

            def rodar(args, arquivo=None):
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    cod = main(args)
                if arquivo:
                    with open(os.path.join(d, arquivo), "w", encoding="utf-8") as f:
                        f.write(out.getvalue())
                return cod, out.getvalue()
            with open(os.path.join(d, "sk"), "w") as f:
                f.write(SK.hex())
            with open(os.path.join(d, "ent.json"), "w", encoding="utf-8") as f:
                json.dump(ent, f)
            rodar(["cabeca", cam, os.path.join(d, "sk"), "Ente"], "cab.json")
            rodar(["recibo", cam, "t1", os.path.join(d, "cab.json")], "rec.json")
            cod, out = rodar(["conferir-recibo", os.path.join(d, "rec.json"), PUB, os.path.join(d, "ent.json")])
            self.assertEqual(cod, 0, out)
            cod, _ = rodar(["conferir-recibo", os.path.join(d, "rec.json"), ed.publica(bytes(32)).hex()])
            self.assertEqual(cod, 1)
