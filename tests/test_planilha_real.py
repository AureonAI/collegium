"""T065 · rodada 6: planilhas reais de banco e ERP. Cada teste R6-n venceu contra a v0.2.0
(provado em 10/10/2026 antes da correção) e agora é regressão."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collegium_oficios.conciliacao import dados  # noqa: E402
from collegium_oficios.conciliacao import importadores as imp  # noqa: E402


class TestRodada6Importacao(unittest.TestCase):
    def test_r6_2_bom_do_excel(self):
        self.assertEqual(imp.ler_planilha("\ufeffData;Valor\n03/09/2026;10,00\n", "R")["itens"][0]["valor"], 1000)
        # o leitor antigo também passou a aceitar
        self.assertEqual(imp.ler_csv("\ufeffData;Valor\n03/09/2026;10,00\n", {"data": "Data", "valor": "Valor"},
                                     "R")[0]["valor"], 1000)

    def test_cp1252_do_excel_brasileiro(self):
        r = imp.ler_planilha("Data;Histórico;Valor\n03/09/2026;Pagamento à vista;10,00\n".encode("cp1252"), "R")
        self.assertEqual((r["encoding"], r["itens"][0]["desc"]), ("cp1252", "Pagamento à vista"))

    def test_r6_3_titulo_antes_da_tabela(self):
        txt = "Razao Analitico - EMPRESA X LTDA\nPeriodo: 01/09/2026 a 30/09/2026\n\nData;Valor\n03/09/2026;10,00\n"
        r = imp.ler_planilha(txt, "R")
        self.assertEqual((len(r["itens"]), r["linha_cabecalho"]), (1, 4))

    def test_r6_4_sufixo_d_c(self):
        self.assertEqual([imp.centavos(x) for x in ("1.234,56D", "1.234,56 C", "10,00d")], [-123456, 123456, -1000])
        with self.assertRaises(ValueError):
            imp.centavos("D")

    def test_r6_5_total_e_saldo_nao_quebram_e_aparecem(self):
        r = imp.ler_planilha("Data;Valor\nSaldo anterior;100,00\n03/09/2026;10,00\nTOTAL;10,00\n"
                             "Saldo final;110,00\n", "R")
        self.assertEqual(len(r["itens"]), 1)
        self.assertEqual((r["saldo_inicial"], r["saldo_final"]), (10000, 11000))
        self.assertEqual([x["linha"] for x in r["ignoradas"]], [2, 4, 5])  # nada some em silêncio

    def test_linha_desconhecida_falha_com_numero_da_linha(self):
        with self.assertRaises(imp.ImportacaoInvalida) as c:
            imp.ler_planilha("Data;Valor\n03/09/2026;10,00\nxpto;abc\n", "R")
        self.assertIn("linha 3", str(c.exception))

    def test_debito_e_credito_na_mesma_linha_falha(self):
        with self.assertRaises(imp.ImportacaoInvalida):
            imp.ler_planilha("Data;Debito;Credito\n03/09/2026;10,00;5,00\n", "R")

    def test_separadores_e_coluna_lancamento_e_numero(self):
        r = imp.ler_planilha('Lançamento,Data,Histórico,Valor\n77,03/09/2026,PIX,"1.234,56"\n', "R")
        self.assertEqual(r["itens"][0], {"id": "R-77", "data": "2026-09-03", "valor": 123456, "desc": "PIX"})
        r = imp.ler_planilha("Data\tValor\n03/09/2026\t5,00\n", "B")
        self.assertEqual(r["separador"], "\t")

    def test_sem_cabecalho_falha(self):
        with self.assertRaises(imp.ImportacaoInvalida):
            imp.ler_planilha("a;b\n1;2\n", "R")


class TestRodada6Convencao(unittest.TestCase):
    """R6-1: razão contábil (entrada = débito) entrava com todo sinal invertido, em silêncio."""

    def test_r6_1_debito_contabil_detectado(self):
        ds = dados.gerar_v2(3, n=60)
        self.assertEqual(imp.detectar_convencao(ds["extrato"], ds["razao"])["convencao"], "bancaria")
        self.assertEqual(imp.detectar_convencao(ds["extrato"], imp.inverter(ds["razao"]))["convencao"], "contabil")

    def test_conta_errada_e_indeterminado(self):
        ds = dados.gerar_v2(3, n=60)
        outro = dados.gerar_v2(99, n=60)["razao"]
        self.assertEqual(imp.detectar_convencao(ds["extrato"], outro)["convencao"], "indeterminado")

    def test_poucos_dados_e_indeterminado(self):
        ex = [{"id": "B1", "data": "2026-09-01", "valor": 100}]
        rz = [{"id": "R1", "data": "2026-09-01", "valor": 100}]
        self.assertEqual(imp.detectar_convencao(ex, rz)["convencao"], "indeterminado")  # mínimo de 3


if __name__ == "__main__":
    unittest.main()
