"""T059: CNAB 240 (Segmento E) e Open Finance Brasil. O arquivo CNAB de teste é montado campo a campo
a partir da TABELA do manual (CAIXA, layouts 030/040/089), independente do leitor."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collegium_oficios.conciliacao.importadores import CNABInvalido, ler_cnab240, ler_open_finance  # noqa: E402


def linha(campos: dict) -> str:
    """campos: {(inicio, fim): texto} com posições 1-based do manual."""
    buf = [" "] * 240
    for (a, b), v in campos.items():
        v = str(v)
        assert len(v) == b - a + 1, (a, b, v)
        buf[a - 1:b] = list(v)
    return "".join(buf)


def num(v, n):
    return str(v).zfill(n)


def cnab(lancs, saldo_ini=100_000, saldo_fim=None, sit_ini="C", deb=None, cred=None):
    saldo_fim = saldo_ini + sum(v if dc == "C" else -v for _, v, dc, _ in lancs) if saldo_fim is None else saldo_fim
    deb = sum(v for _, v, dc, _ in lancs if dc == "D") if deb is None else deb
    cred = sum(v for _, v, dc, _ in lancs if dc == "C") if cred is None else cred
    L = [linha({(1, 3): "104", (4, 7): "0000", (8, 8): "0"}),
         linha({(1, 3): "104", (4, 7): "0001", (8, 8): "1", (143, 150): "01092026",
                (151, 168): num(abs(saldo_ini), 18), (169, 169): sit_ini, (170, 170): "F"})]
    for i, (data, v, dc, hist) in enumerate(lancs, 1):
        L.append(linha({(1, 3): "104", (4, 7): "0001", (8, 8): "3", (9, 13): num(i, 5), (14, 14): "E",
                        (143, 150): data, (151, 168): num(v, 18), (169, 169): dc, (170, 172): "101",
                        (173, 176): "0001", (177, 201): hist.ljust(25)[:25], (202, 208): num(i, 7)}))
    L.append(linha({(1, 3): "104", (4, 7): "0001", (8, 8): "5", (143, 150): "30092026",
                    (151, 168): num(abs(saldo_fim), 18), (169, 169): "C" if saldo_fim >= 0 else "D",
                    (170, 170): "F", (177, 194): num(deb, 18), (195, 212): num(cred, 18)}))
    L.append(linha({(1, 3): "104", (4, 7): "9999", (8, 8): "9"}))
    return "\r\n".join(L)


LANCS = [("05092026", 150_000, "C", "PIX RECEBIDO NF12345"), ("10092026", 2_990, "D", "TARIFA PACOTE"),
         ("15092026", 47_500, "D", "BOLETO BOL654321")]


class TestCNAB(unittest.TestCase):
    def test_leitura_e_prova_de_saldo(self):
        r = ler_cnab240(cnab(LANCS))
        self.assertEqual([x["valor"] for x in r["extrato"]], [150_000, -2_990, -47_500])
        self.assertEqual(r["extrato"][0]["data"], "2026-09-05")
        self.assertIn("NF12345", r["extrato"][0]["desc"])
        self.assertEqual(r["conferencia"], {"saldo": "SALDO_FECHA", "somatorios_trailer": "CONFERE"})

    def test_trailer_divergente_e_saldo_que_nao_fecha(self):
        r = ler_cnab240(cnab(LANCS, saldo_fim=1, deb=1))
        self.assertNotEqual(r["conferencia"]["saldo"], "SALDO_FECHA")
        self.assertTrue(r["conferencia"]["somatorios_trailer"].startswith("DIVERGE"))

    def test_saldo_inicial_devedor(self):
        r = ler_cnab240(cnab(LANCS, saldo_ini=-50_000, sit_ini="D"))
        self.assertEqual(r["saldo_inicial"], -50_000)
        self.assertEqual(r["conferencia"]["saldo"], "SALDO_FECHA")

    def test_falha_fechada(self):
        with self.assertRaises(CNABInvalido):
            ler_cnab240(cnab(LANCS) + "\r\n" + "x" * 241)
        ruim = cnab([("31022026", 1, "C", "DATA IMPOSSIVEL")])
        with self.assertRaises((CNABInvalido, ValueError)):
            ler_cnab240(ruim)
        with self.assertRaises(CNABInvalido):
            ler_cnab240(cnab([("05092026", 1, "X", "TIPO ERRADO")]))

    def test_brancos_finais_cortados(self):
        r = ler_cnab240("\n".join(x.rstrip() for x in cnab(LANCS).splitlines()))
        self.assertEqual(len(r["extrato"]), 3)


class TestOpenFinance(unittest.TestCase):
    def test_fuso_valor_e_filtragem(self):
        resp = {"data": [
            {"transactionId": "TX1", "completedAuthorisedPaymentType": "TRANSACAO_EFETIVADA", "creditDebitType": "CREDITO",
             "transactionName": "PIX RECEBIDO", "type": "PIX", "transactionAmount": {"amount": "1500.0000", "currency": "BRL"},
             "transactionDateTime": "2026-09-30T01:30:00.000Z", "partieCnpjCpf": "52998224725"},
            {"transactionId": "TX2", "completedAuthorisedPaymentType": "TRANSACAO_EFETIVADA", "creditDebitType": "DEBITO",
             "transactionName": "TARIFA", "type": "OUTROS", "transactionAmount": {"amount": "29.90", "currency": "BRL"},
             "transactionDateTime": "2026-09-10T15:00:00Z"},
            {"transactionId": "TX3", "completedAuthorisedPaymentType": "LANCAMENTO_FUTURO", "creditDebitType": "DEBITO",
             "transactionName": "AGENDADO", "type": "TED", "transactionAmount": {"amount": "10.00", "currency": "BRL"},
             "transactionDateTime": "2026-10-20T15:00:00Z"},
            {"transactionId": "TX4", "completedAuthorisedPaymentType": "TRANSACAO_EFETIVADA", "creditDebitType": "CREDITO",
             "transactionName": "RENDIMENTO", "type": "OUTROS", "transactionAmount": {"amount": "0.0450", "currency": "BRL"},
             "transactionDateTime": "2026-09-10T15:00:00Z"}]}
        r = ler_open_finance(resp)
        ex = {x["id"]: x for x in r["extrato"]}
        self.assertEqual(ex["BTX1"]["data"], "2026-09-29")        # 01h30 UTC do dia 30 = 22h30 do dia 29 em Brasília
        self.assertEqual(ex["BTX1"]["valor"], 150_000)
        self.assertEqual(ex["BTX2"]["valor"], -2_990)
        self.assertNotIn("BTX3", ex)
        self.assertEqual(r["fora_por_nao_efetivada"], 1)
        self.assertTrue(ex["BTX4"]["revisar"])                    # meio centavo: não se arredonda calado


if __name__ == "__main__":
    unittest.main()
