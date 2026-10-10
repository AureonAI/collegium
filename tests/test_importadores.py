"""Importadores de dado real: OFX, CSV brasileiro, OCR (motor falso — sem baixar modelo)."""
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from collegium_oficios.conciliacao import importadores as imp  # noqa: E402
from collegium_oficios.conciliacao import oraculo, operarios  # noqa: E402

OFX_SGML = """OFXHEADER:100
DATA:OFXSGML
CHARSET:1252

<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>BRL
<BANKTRANLIST><DTSTART>20260901<DTEND>20260930
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260903120000[-3:BRT]<TRNAMT>1500.00<FITID>A1<MEMO>PIX NF12345
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260905<TRNAMT>-230,45<FITID>A2<NAME>TARIFA
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260910<TRNAMT>99.99<FITID>A3<MEMO>BOLETO BOL123456
</BANKTRANLIST><LEDGERBAL><BALAMT>3369.54<DTASOF>20260930</LEDGERBAL>
</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"""

OFX_XML = """<?xml version="1.0"?><OFX><BANKTRANLIST>
<STMTTRN><TRNTYPE>CREDIT</TRNTYPE><DTPOSTED>20260903</DTPOSTED><TRNAMT>10.10</TRNAMT><FITID>X1</FITID><MEMO>A</MEMO></STMTTRN>
<STMTTRN><TRNTYPE>CREDIT</TRNTYPE><DTPOSTED>20260904</DTPOSTED><TRNAMT>20.20</TRNAMT><FITID>X2</FITID><MEMO>B</MEMO></STMTTRN>
</BANKTRANLIST><LEDGERBAL><BALAMT>30.30</BALAMT></LEDGERBAL></OFX>"""


class TestNumeros(unittest.TestCase):
    def test_centavos_formatos_brasileiros_sem_float(self):
        casos = {"1.234,56": 123456, "-1.234,56": -123456, "(1.234,56)": -123456, "1.234,56-": -123456,
                 "1234.56": 123456, "R$ 0,10": 10, "1.000.000,00": 100000000, "230,45": 23045}
        for t, v in casos.items():
            self.assertEqual(imp.centavos(t), v, t)
        self.assertEqual(imp.centavos("1,10") + imp.centavos("2,20"), imp.centavos("3,30"))
        with self.assertRaises(ValueError):
            imp.centavos("12a,00")


class TestOFX(unittest.TestCase):
    def test_sgml(self):
        r = imp.ler_ofx(OFX_SGML.encode("cp1252"))
        self.assertEqual([x["valor"] for x in r["extrato"]], [150000, -23045, 9999])
        self.assertEqual(r["extrato"][0]["data"], "2026-09-03")
        self.assertIn("NF12345", r["extrato"][0]["desc"])
        self.assertEqual(r["saldo_final"], 336954)
        self.assertTrue(imp.checar_saldo(r["extrato"], 200000, r["saldo_final"])[0])
        self.assertFalse(imp.checar_saldo(r["extrato"], 210000, r["saldo_final"])[0])

    def test_xml(self):
        r = imp.ler_ofx(OFX_XML)
        self.assertEqual([x["id"] for x in r["extrato"]], ["B-X1", "B-X2"])
        self.assertEqual(r["saldo_final"], 3030)

    def test_fitid_repetido_recusado(self):
        with self.assertRaises(ValueError):
            imp.ler_ofx(OFX_SGML.replace("<FITID>A2", "<FITID>A1"))


class TestCSV(unittest.TestCase):
    def test_razao_do_erp(self):
        csv_txt = "Num;Data;Valor;Documento\n10;03/09/2026;1.500,00;NF12345\n11;10/09/2026;99,99;BOL123456\n"
        r = imp.ler_csv(csv_txt, {"id": "Num", "data": "Data", "valor": "Valor", "doc": "Documento"}, "R")
        self.assertEqual(r[0], {"id": "R-10", "data": "2026-09-03", "valor": 150000, "doc": "NF12345"})

    def test_debito_credito_separados(self):
        csv_txt = "Data;Historico;Entrada;Saida\n01/09/2026;PIX;100,00;\n02/09/2026;TARIFA;;5,50\n"
        r = imp.ler_csv(csv_txt, {"data": "Data", "desc": "Historico", "credito": "Entrada",
                                  "debito": "Saida"}, "B")
        self.assertEqual([x["valor"] for x in r], [10000, -550])

    def test_ponta_a_ponta_ofx_mais_csv_concilia(self):
        ext = imp.ler_ofx(OFX_SGML)["extrato"]
        raz = imp.ler_csv("Num;Data;Valor;Documento\n10;02/09/2026;1.500,00;NF12345\n"
                          "11;09/09/2026;99,99;BOL123456\n", {"id": "Num", "data": "Data", "valor": "Valor",
                                                              "doc": "Documento"}, "R")
        P = {"padroes_documento": [r"NF\d+", r"BOL\d+"]}
        p = operarios.honesto_v5(ext, raz, P)
        ok, falhas = oraculo.verificar(ext, raz, p, parametros=P)
        self.assertTrue(ok, falhas)
        self.assertEqual(sorted(map(tuple, p["pares"])), [("B-A1", "R-10"), ("B-A3", "R-11")])
        self.assertEqual(p["pendentes_banco"], ["B-A2"])  # tarifa sem lançamento: fica pendente


def tok(t, s, y, x=0):
    return (t, s, [x, y, x + 50, y + 10])


class TestOCR(unittest.TestCase):
    TOKENS = [tok("SALDO ANTERIOR", .99, 0), tok("1.000,00", .99, 0, 300),
              tok("03/09", .99, 20), tok("PIX NF12345", .97, 20, 60), tok("500,00", .99, 20, 300),
              tok("05/09", .99, 40), tok("TARIFA", .98, 40, 60), tok("12,50D", .99, 40, 300),
              tok("SALDO FINAL", .99, 60), tok("1.487,50", .99, 60, 300)]

    def test_linhas_e_saldo_fecham(self):
        r = imp.extrato_de_ocr(self.TOKENS, 2026)
        self.assertEqual([x["valor"] for x in r["extrato"]], [50000, -1250])
        self.assertEqual((r["saldo_inicial"], r["saldo_final"]), (100000, 148750))
        self.assertTrue(imp.checar_saldo(r["extrato"], r["saldo_inicial"], r["saldo_final"])[0])

    def test_baixa_confianca_vira_revisar_e_oraculo_nao_deixa_casar(self):
        t = list(self.TOKENS)
        t[4] = tok("500,00", .71, 20, 300)
        r = imp.extrato_de_ocr(t, 2026)
        self.assertTrue(r["extrato"][0].get("revisar"))
        raz = [{"id": "R1", "data": "2026-09-03", "valor": 50000, "doc": "NF12345"}]
        ok, falhas = oraculo.verificar(r["extrato"], raz, {"pares": [["B-OCR0000", "R1"]],
                                                           "pendentes_banco": ["B-OCR0001"], "pendentes_razao": []})
        self.assertFalse(ok)
        self.assertTrue(any(f.startswith("ITEM_NAO_CONFIAVEL") for f in falhas))

    def test_ocr_errado_com_confianca_alta_e_pego_pelo_saldo(self):
        t = list(self.TOKENS)
        t[4] = tok("580,00", .99, 20, 300)  # 5 lido como 8, com confiança alta
        r = imp.extrato_de_ocr(t, 2026)
        ok, msg = imp.checar_saldo(r["extrato"], r["saldo_inicial"], r["saldo_final"])
        self.assertFalse(ok)
        self.assertIn("SALDO_NAO_FECHA", msg)

    def test_adaptador_paddle_com_motor_falso(self):
        class Res:
            def __init__(self, toks):
                self.json = {"res": {"rec_texts": [x[0] for x in toks], "rec_scores": [x[1] for x in toks],
                                     "rec_boxes": [x[2] for x in toks]}}

        class Motor:
            def predict(self, caminho):
                return [Res(TestOCR.TOKENS)]
        r = imp.ler_imagem_paddle("extrato.png", 2026, motor=Motor())
        self.assertEqual(len(r["extrato"]), 2)


if __name__ == "__main__":
    unittest.main()
