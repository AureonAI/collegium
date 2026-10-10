"""T066/T071 · o trabalho que se vende, de ponta a ponta: arquivo do banco + arquivo do ERP ->
conciliação sob o LEX -> relatório -> aprovação humana assinada -> recibo conferível fora do sistema."""
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "ferramentas"))
from collegium import Ledger, ed25519, execucao  # noqa: E402
from collegium import recibo as rc  # noqa: E402
from collegium_oficios.conciliacao import dados, oraculo, piloto  # noqa: E402
from collegium_oficios.conciliacao import exemplo as kit  # noqa: E402

EXT = os.path.join(RAIZ, "exemplos", "piloto", "extrato.ofx")
RAZ = os.path.join(RAIZ, "exemplos", "piloto", "razao_contabil.csv")


def _cli(*args, env_extra=None):
    env = dict(os.environ, **(env_extra or {}))
    env.pop("COLLEGIUM_CHAVE", None)
    return subprocess.run([sys.executable, "-m", "collegium", *args], cwd=RAIZ, capture_output=True, text=True, encoding="utf-8",
                          env=env)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def escrever(self, nome, conteudo, enc="utf-8"):
        cam = os.path.join(self.tmp, nome)
        with open(cam, "wb") as f:
            f.write(conteudo if isinstance(conteudo, bytes) else conteudo.encode(enc))
        return cam


class TestKit(unittest.TestCase):
    def test_kit_e_deterministico_e_igual_ao_publicado(self):
        o, c = kit.gerar()
        self.assertEqual(kit.gerar(), (o, c))
        with open(EXT, "rb") as f1, open(RAZ, "rb") as f2:
            self.assertEqual((f1.read(), f2.read()), (o, c), "rode ferramentas/gerar_exemplo_piloto.py")


class TestPiloto(Base):
    def test_kit_concilia_sem_par_errado_e_detecta_convencao_contabil(self):
        r = piloto.conciliar_arquivos(EXT, RAZ, os.path.join(self.tmp, "s"), "Empresa Exemplo Ltda")
        self.assertEqual(r["status"], "CONCILIADO")
        self.assertEqual(r["convencao"]["usada"], "contabil")
        self.assertTrue(any("CONTÁBIL" in a for a in r["avisos"]))
        self.assertTrue(any("S1" in a for a in r["avisos"]))          # OFX sem saldo inicial: dito, não escondido
        self.assertTrue(r["anais_integro"])
        self.assertEqual([x["texto"][:14] for x in r["linhas_ignoradas"]["razao"]],
                         [";;Saldo anteri", ";;Total do per", ";;Saldo final;"])
        # contra o gabarito sintético: nenhum par 1:1 errado
        ds = dados.gerar_v2(42, n=60, taxa_injecao=0.0)
        raz = sorted(ds["razao"], key=lambda x: (x["data"], x["id"]))
        mapa = {f"R-{k}": x["id"] for k, x in enumerate(raz, start=1001)}
        gab = {("B-" + b, rr) for b, rr in ds["gabarito"]}
        with open(os.path.join(self.tmp, "s", "pares.csv"), encoding="utf-8-sig") as f:
            pares = list(csv.reader(f, delimiter=";"))[1:]
        um_a_um = [p for p in pares if not p[6].startswith("(lote)")]
        self.assertGreater(len(um_a_um), 30)
        self.assertEqual([p for p in um_a_um if (p[0], mapa[p[4]]) not in gab], [])

    def test_texto_hostil_nao_executa(self):
        s = os.path.join(self.tmp, "s")
        piloto.conciliar_arquivos(EXT, RAZ, s, "Empresa Exemplo Ltda")
        with open(os.path.join(s, "relatorio.html"), encoding="utf-8") as f:
            h = f.read()
        self.assertNotIn("<script>", h)
        self.assertIn("Content-Security-Policy", h)
        for nome in ("pendencias.csv", "pares.csv"):
            with open(os.path.join(s, nome), encoding="utf-8-sig") as f:
                for linha in csv.reader(f, delimiter=";"):
                    self.assertFalse(any(c[:1] in "=+-@" for c in linha if c), (nome, linha))

    def test_anais_nao_guarda_historico_do_cliente(self):
        s = os.path.join(self.tmp, "s")
        piloto.conciliar_arquivos(EXT, RAZ, s, "Empresa Exemplo Ltda")
        with open(os.path.join(s, "anais.jsonl"), encoding="utf-8") as f:
            self.assertNotIn("PIX RECEBIDO", f.read())

    def test_r6_13_resumo_json_nao_leva_dado_do_cliente(self):
        """R6-13: resumo.json levava caminho absoluto (nome do usuário), nome dos arquivos e o TEXTO das linhas
        ignoradas (título/total do ERP). É o arquivo que pode sair do escritório: só números e códigos."""
        o, c = kit.gerar(42)
        marca = "FULANO DE TAL"
        c = c.decode("cp1252").replace("EMPRESA EXEMPLO LTDA", marca).replace("Total do período", f"Total {marca}")
        d = os.path.join(self.tmp, "pasta_de_FULANO DE TAL")
        os.makedirs(d)
        ext, raz = os.path.join(d, f"extrato_{marca}.ofx"), os.path.join(d, f"razao_{marca}.csv")
        with open(ext, "wb") as f:
            f.write(o)
        with open(raz, "wb") as f:
            f.write(c.encode("cp1252"))
        saida = os.path.join(self.tmp, "s")
        res = piloto.conciliar_arquivos(ext, raz, saida, "Ente")
        self.assertEqual(res["status"], "CONCILIADO")
        with open(os.path.join(saida, "resumo.json"), encoding="utf-8") as f:
            texto = f.read()
        self.assertNotIn("FULANO", texto)
        self.assertNotIn(self.tmp, texto)
        r = json.loads(texto)
        self.assertEqual(len(r["extrato_sha256"]), 64)
        self.assertTrue(all(set(x) == {"linha"} for x in r["linhas_ignoradas"]["razao"]))
        with open(os.path.join(saida, "relatorio.html"), encoding="utf-8") as f:
            self.assertIn("FULANO", f.read())  # o relatório LOCAL continua mostrando o que foi ignorado

    def test_s3_conta_errada_e_bloqueada_com_evidencia(self):
        o, _ = kit.gerar(42)
        _, outra = kit.gerar(7)  # razão de OUTRA empresa
        r = piloto.conciliar_arquivos(self.escrever("e.ofx", o), self.escrever("r.csv", outra),
                                      os.path.join(self.tmp, "s"), "X")
        self.assertEqual(r["status"], "BLOQUEADO")
        self.assertIn("CONVENCAO_INDETERMINADA", r["motivo"])
        with open(os.path.join(self.tmp, "s", "anais.jsonl"), encoding="utf-8") as f:
            self.assertIn("CONVENCAO_INDETERMINADA", f.read())  # a evidência fica selada
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "s", "pares.csv")))  # nada entregue

    def test_s2_periodos_diferentes(self):
        ext = "Data;Historico;Valor\n" + "".join(f"{d:02d}/09/2026;PIX;{d},00\n" for d in range(1, 29))
        raz = "Data;Historico;Valor\n" + "".join(f"{d:02d}/08/2026;PIX;{d},00\n" for d in range(1, 29))
        r = piloto.conciliar_arquivos(self.escrever("e.csv", ext), self.escrever("r.csv", raz),
                                      os.path.join(self.tmp, "s"), "X")
        self.assertEqual(r["status"], "BLOQUEADO")
        self.assertIn("PERIODOS_DIFERENTES", r["motivo"])

    def test_s1_saldo_do_extrato_que_nao_fecha(self):
        ext = "Data;Historico;Valor\nSaldo anterior;;100,00\n03/09/2026;PIX;10,00\nSaldo final;;999,00\n"
        r = piloto.conciliar_arquivos(self.escrever("e.csv", ext), self.escrever("r.csv", "Data;Valor\n03/09/2026;10,00\n"),
                                      os.path.join(self.tmp, "s"), "X")
        self.assertEqual(r["status"], "BLOQUEADO")
        self.assertIn("SALDO_NAO_FECHA", r["motivo"])

    def test_mesma_entrada_duas_vezes_no_mesmo_anais_e_recusada(self):
        s = os.path.join(self.tmp, "s")
        piloto.conciliar_arquivos(EXT, RAZ, s, "Empresa Exemplo Ltda")
        with self.assertRaises(execucao.JaExecutada):
            piloto.conciliar_arquivos(EXT, RAZ, s, "Empresa Exemplo Ltda")

    def test_anais_de_um_ente_nao_aceita_outro(self):
        s = os.path.join(self.tmp, "s")
        piloto.conciliar_arquivos(EXT, RAZ, s, "Empresa A")
        o, c = kit.gerar(43)
        with self.assertRaises(ValueError):
            piloto.conciliar_arquivos(self.escrever("e.ofx", o), self.escrever("r.csv", c), s, "Empresa B")


class TestAprovacaoHumana(Base):
    """T071: sem isto a tarefa ficava em AGUARDA_HUMANO para sempre."""

    def test_laco_completo_e_recibo_mostra_liberada(self):
        sk = ed25519.gerar_privada()
        pub = ed25519.publica(sk).hex()
        s = os.path.join(self.tmp, "s")
        r = piloto.conciliar_arquivos(EXT, RAZ, s, "Empresa Exemplo Ltda", humanos={"renato": pub})
        self.assertEqual(r["humanos"], ["renato"])
        of = piloto.OFICIO
        led = Ledger(os.path.join(s, "anais.jsonl"))
        errada = execucao.aprovar(of, led, r["tarefa"], "renato", ed25519.gerar_privada())
        self.assertEqual(errada["codigo"], "FALSO_HUMANO")
        ok = execucao.aprovar(of, Ledger(os.path.join(s, "anais.jsonl")), r["tarefa"], "renato", sk)
        self.assertEqual((ok["codigo"], ok["estado"]), ("LIBERADA", "LIBERADA"))
        cam = os.path.join(s, "anais.jsonl")
        cab = rc.cabeca(cam, sk, "Empresa Exemplo Ltda", "2026-10-10T00:00:00+00:00")
        conf = rc.conferir_recibo(json.loads(json.dumps(rc.emitir_recibo(cam, r["tarefa"], cab))), pub)
        valido, resumo = (conf["valido"], conf["resumo"]) if isinstance(conf, dict) else (conf[0], conf[2])
        self.assertTrue(valido)
        self.assertEqual(resumo["eventos"][-1], "LIBERADA")

    def test_sem_humano_registrado_relatorio_avisa(self):
        s = os.path.join(self.tmp, "s")
        piloto.conciliar_arquivos(EXT, RAZ, s, "Empresa Exemplo Ltda")
        with open(os.path.join(s, "relatorio.html"), encoding="utf-8") as f:
            self.assertIn("Ninguém pode aprovar", f.read())


class TestCLI(Base):
    def test_codigos_de_saida(self):
        sk_path = os.path.join(self.tmp, "k.priv")
        pub = _cli("gerar-chave", sk_path).stdout.strip()
        s = os.path.join(self.tmp, "s")
        r = _cli("conciliar", "--extrato", EXT, "--razao", RAZ, "--saida", s, "--ente", "E", "--humano", "ana",
                 "--chave-publica", pub, "--chave", sk_path)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.exists(os.path.join(s, "recibo.json")))
        with open(os.path.join(s, "resumo.json"), encoding="utf-8") as f:
            resumo = json.load(f)
        t = resumo["tarefa"]
        self.assertEqual(resumo["humanos"], ["ana"])
        a = _cli("aprovar", "--anais", os.path.join(s, "anais.jsonl"), "--tarefa", t, "--humano", "ana", "--chave", sk_path)
        self.assertEqual(a.returncode, 0, a.stderr + a.stdout)
        self.assertEqual(_cli("aprovar", "--anais", os.path.join(s, "anais.jsonl"), "--tarefa", t, "--humano", "ana",
                              "--chave", sk_path).returncode, 2)  # já liberada
        o, _ = kit.gerar(42)
        _, outra = kit.gerar(7)
        b = _cli("conciliar", "--extrato", self.escrever("e.ofx", o), "--razao", self.escrever("r.csv", outra),
                 "--saida", os.path.join(self.tmp, "b"))
        self.assertEqual(b.returncode, 2)
        x = _cli("conciliar", "--extrato", self.escrever("lixo.csv", "a;b\n1;2\n"), "--razao", RAZ,
                 "--saida", os.path.join(self.tmp, "x"))
        self.assertEqual(x.returncode, 1)
        self.assertIn("cabeçalho", x.stderr)


class TestRodada6Oraculo(unittest.TestCase):
    def test_r6_6_documento_e_palavra_inteira(self):
        P = {"padroes_documento": [r"NF\d+"]}
        ex = [{"id": "B1", "data": "2026-09-03", "valor": 10000, "desc": "TED RECEBIDA 14512"}]
        rz = [{"id": "R1", "data": "2026-09-03", "valor": 10000, "doc": "4512"},
              {"id": "R2", "data": "2026-09-04", "valor": 10000, "doc": "14512"}]
        errado = {"pares": [["B1", "R1"]], "pendentes_banco": [], "pendentes_razao": ["R2"]}
        certo = {"pares": [["B1", "R2"]], "pendentes_banco": [], "pendentes_razao": ["R1"]}
        self.assertFalse(oraculo.verificar(ex, rz, errado, parametros=P)[0])
        self.assertTrue(oraculo.verificar(ex, rz, certo, parametros=P)[0])
        self.assertTrue(oraculo.verificar(ex, rz, errado, versao="0.1.4", parametros=P)[0])  # passado reproduzível

    def test_documentos_canonicos(self):
        casos = {"NF-e 012345": ["NF12345"], "Nota Fiscal nº 12345": ["NF12345"], "NF 000123": ["NF123"],
                 "PIX NF12345 BOLETO 0099": ["NF12345", "BOL99"], "Pedido 77": ["PED77"],
                 "TARIFA PACOTE": [], "NOTA 4567": ["NF4567"]}
        for t, esperado in casos.items():
            self.assertEqual(piloto.docs_canonicos(t), esperado, t)


if __name__ == "__main__":
    unittest.main()
