"""T044/T045: anonimizador BR e cofre com eliminação. Âncoras externas: exemplo oficial de CNPJ
alfanumérico da Receita (12.ABC.345/01DE-35) e CPF/CNPJ numéricos de exemplo público."""
import json
import os
import random
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from collegium.privacidade import Anonimizador, Cofre, cnpj_valido, cpf_valido, exportar  # noqa: E402
from pacotes.conciliacao import dados, operarios, oraculo, residuo  # noqa: E402

PARAM = {"padroes_documento": [r"NF\d+", r"BOL\d+", r"PED\d+"]}
NOMES = ["JOÃO DA SILVA", "MARIA APARECIDA SOUZA", "ACME COMÉRCIO", "José Pereira"]


def _cpf(rnd):
    n = [rnd.randint(0, 9) for _ in range(9)]
    for pesos in (range(10, 1, -1), range(11, 1, -1)):
        r = sum(a * b for a, b in zip(n, pesos)) % 11
        n.append(0 if r < 2 else 11 - r)
    s = "".join(map(str, n))
    return f"{s[:3]}.{s[3:6]}.{s[6:9]}-{s[9:]}"


class TestDV(unittest.TestCase):
    def test_exemplos_publicos(self):
        self.assertTrue(cpf_valido("529.982.247-25"))
        self.assertFalse(cpf_valido("529.982.247-26"))
        self.assertFalse(cpf_valido("111.111.111-11"))
        self.assertTrue(cnpj_valido("11.222.333/0001-81"))
        self.assertTrue(cnpj_valido("12.ABC.345/01DE-35"))   # exemplo oficial do CNPJ alfanumérico
        self.assertFalse(cnpj_valido("12.ABC.345/01DE-36"))
        self.assertFalse(cnpj_valido("00.000.000/0000-00"))


class TestAnonimizador(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cofre = Cofre(os.path.join(self.tmp.name, "cofre.json"), b"chave-mestra-do-escritorio")
        self.an = Anonimizador(self.cofre, PARAM["padroes_documento"])

    def tearDown(self):
        self.tmp.cleanup()

    def test_nada_sensivel_sobra(self):
        texto = ("PIX RECEBIDO JOÃO DA SILVA CPF 529.982.247-25 joao.silva@mail.com (61) 99876-5432 "
                 "CNPJ 12.ABC.345/01DE-35 chave 123e4567-e89b-12d3-a456-426614174000 cc 98765-4 NF12345")
        saida = self.an.texto(texto)
        for vaza in ("JOÃO", "SILVA", "529", "joao", "99876", "12.ABC", "123e4567", "98765"):
            self.assertNotIn(vaza.upper(), saida.upper(), saida)
        self.assertIn("NF12345", saida)            # documento preservado: é a ponte da conciliação
        self.assertIn("PIX RECEBIDO", saida)

    def test_segunda_rodada_de_vazamentos(self):
        """Ataques da revisão: telefone com espaços e conta curta vazavam; data e valor eram destruídos."""
        saida = self.an.texto("TED MARIA tel 61 99876 5432 AG 0001 CC 12345 em 10/09/2026 R$ 1.234,56")
        for vaza in ("99876", "5432", "12345"):
            self.assertNotIn(vaza, saida, saida)
        self.assertIn("10/09/2026", saida)
        self.assertIn("1.234,56", saida)

    def test_mesmo_titular_mesmo_pseudonimo(self):
        a = self.an.texto("PIX RECEBIDO JOÃO DA SILVA")
        b = self.an.texto("TED JOAO DA SILVA")       # sem acento, outro lançamento
        c = self.an.texto("PIX RECEBIDO MARIA APARECIDA")
        self.assertEqual(a.split()[-1], b.split()[-1])
        self.assertNotEqual(a.split()[-1], c.split()[-1])

    def test_nome_colado_ao_documento(self):
        saida = self.an.texto("JOAONF123")
        self.assertNotIn("JOAO", saida)
        self.assertIn("NF123", saida)

    def test_conciliacao_identica_antes_e_depois(self):
        """Anonimizar não pode mudar o resultado: mesmos pares, mesmo veredito, mesmo resíduo."""
        rnd = random.Random(5)
        for seed in range(1, 6):
            ds = dados.gerar_v2(seed, n=60)
            for x in ds["extrato"]:
                x["desc"] = f"{x['desc']} {rnd.choice(NOMES)} CPF {_cpf(rnd)}"
            for x in ds["razao"]:
                x["fornecedor"] = rnd.choice(NOMES)
            ext = self.an.registros(ds["extrato"])
            raz = self.an.registros(ds["razao"])
            p0 = operarios.honesto_v5(ds["extrato"], ds["razao"], PARAM)
            p1 = operarios.honesto_v5(ext, raz, PARAM)
            self.assertEqual(p0, p1)
            self.assertEqual(oraculo.verificar(ds["extrato"], ds["razao"], p0, parametros=PARAM),
                             oraculo.verificar(ext, raz, p1, parametros=PARAM))
            self.assertEqual(residuo.pacote_humano(ds["extrato"], ds["razao"], p0, PARAM),
                             residuo.pacote_humano(ext, raz, p1, PARAM))
            texto = json.dumps(ext + raz, ensure_ascii=False).upper()
            for n in ("SILVA", "APARECIDA", "ACME", "PEREIRA"):
                self.assertNotIn(n, texto)

    def test_pseudonimo_nunca_parece_documento(self):
        """Achado pelo CI (falha intermitente em 4 de 12 máquinas): pseudônimo aleatório em base32 às vezes
        continha 'PED7'/'NF2...', que o oráculo lia como DOCUMENTO CITADO — contradição falsa e, no pior
        caso, evidência falsa. Aqui a colisão é forçada de forma determinística."""
        original = self.cofre.pseudonimo
        colisoes = iter(["NOME_PED2345XY", "NOME_NF77ABCDE"])

        def colide(tipo, valor, variante=0):
            if variante == 0:
                return next(colisoes, original(tipo, valor, variante))
            return original(tipo, valor, variante)
        self.cofre.pseudonimo = colide
        import re as _re
        for texto in ("PIX RECEBIDO FULANO", "TED SICRANO"):
            saida = self.an.texto(texto)
            for rx in PARAM["padroes_documento"]:
                self.assertIsNone(_re.search(rx, saida), saida)

    def test_padrao_so_de_letras_tambem_nao_colide(self):
        """Entidade com padrão de documento SEM dígitos: a troca de alfabeto não basta; vale a checagem."""
        import re as _re
        an = Anonimizador(self.cofre, [r"[A-Z]{2}Q"])
        for i in range(300):
            saida = an.texto(f"PIX RECEBIDO FULANO{chr(65 + i % 26)} DE TAL{i % 7}")
            self.assertIsNone(_re.search(r"[A-Z]{2}Q", saida.replace("PIX RECEBIDO", "")), saida)

    def test_exportar_exige_revisao_humana(self):
        dados_anon = self.an.registros([{"desc": "PIX RECEBIDO FULANO"}])
        rel = self.an.relatorio()
        with self.assertRaises(PermissionError):
            exportar(dados_anon, rel, None)
        with self.assertRaises(PermissionError):
            exportar(dados_anon, rel, "codigo-errado")
        self.assertEqual(exportar(dados_anon, rel, rel["confirmacao"]), dados_anon)
        self.assertIn("RECEBIDO", rel["palavras_mantidas"])


class TestCofre(unittest.TestCase):
    def test_eliminacao_lgpd(self):
        with tempfile.TemporaryDirectory() as d:
            cam = os.path.join(d, "c.json")
            c = Cofre(cam, b"chave-mestra-do-escritorio")
            an = Anonimizador(c)
            antes = an.texto("PIX RECEBIDO JOÃO DA SILVA")
            self.assertTrue(c.eliminar("NOME", "JOÃO DA SILVA"))
            depois = Anonimizador(Cofre(cam, b"chave-mestra-do-escritorio")).texto("PIX RECEBIDO JOÃO DA SILVA")
            self.assertNotEqual(antes, depois)              # o pseudônimo antigo não é mais recalculável
            with open(cam, encoding="utf-8") as f:
                conteudo = f.read()
            self.assertNotIn("SILVA", conteudo.upper())     # o cofre não guarda o original (padrão)
            self.assertFalse(c.eliminar("NOME", "NINGUEM"))

    def test_chave_mestra_fraca_recusada(self):
        with self.assertRaises(ValueError):
            Cofre("x.json", b"curta")


if __name__ == "__main__":
    unittest.main()


class TestCLIPrivacidade(unittest.TestCase):
    def test_fluxo_com_confirmacao(self):
        import contextlib
        import io
        from collegium.__main__ import main
        with tempfile.TemporaryDirectory() as d:
            ent, sai, cof = (os.path.join(d, x) for x in ("e.json", "s.json", "c.json"))
            with open(ent, "w", encoding="utf-8") as f:
                json.dump({"extrato": [{"id": "B1", "desc": "PIX RECEBIDO JOÃO DA SILVA NF1", "valor": 1}]}, f)
            os.environ["COLLEGIUM_CHAVE_COFRE"] = "chave-mestra-de-teste-123"
            try:
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    self.assertEqual(main(["anonimizar", ent, sai, cof]), 3)
                self.assertFalse(os.path.exists(sai))          # sem confirmação, nada sai
                codigo = out.getvalue().strip().split()[-1]
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(main(["anonimizar", ent, sai, cof, "--confirmo", codigo]), 0)
                with open(sai, encoding="utf-8") as f:
                    txt = f.read()
                self.assertNotIn("SILVA", txt)
                self.assertIn("NF1", txt)
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(main(["eliminar-titular", cof, "NOME", "JOÃO DA SILVA"]), 0)
            finally:
                del os.environ["COLLEGIUM_CHAVE_COFRE"]
