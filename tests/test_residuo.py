"""T039/T040: pacote do humano e oráculo da nota do LLM (decisão A, 10/10/2026)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collegium_oficios.conciliacao import dados, operarios, residuo  # noqa: E402


def _caso(seed=1):
    ds = dados.gerar_v2(seed, n=60)
    prop = operarios.honesto_v5(ds["extrato"], ds["razao"])
    return ds, prop, residuo.pacote_humano(ds["extrato"], ds["razao"], prop)


def _nota_boa(pac):
    return {"itens": [{"id": i["id"], "sugestao": residuo.sugestao_base(i), "texto": "ok"} for i in pac]}


class TestResiduo(unittest.TestCase):
    def test_pacote_conserva_todas_as_pendencias(self):
        """Art. 1: toda pendência do operário aparece no pacote do humano, exatamente uma vez."""
        for s in range(1, 6):
            _, prop, pac = _caso(s)
            ids = [i["id"] for i in pac]
            self.assertEqual(sorted(ids), sorted(prop["pendentes_banco"] + prop["pendentes_razao"]))
            self.assertEqual(len(ids), len(set(ids)))
            self.assertTrue(all(i["motivo"] in residuo.MOTIVOS for i in pac))

    def test_pacote_deterministico(self):
        self.assertEqual(_caso(3)[2], _caso(3)[2])

    def test_nota_boa_aceita(self):
        _, _, pac = _caso()
        self.assertEqual(residuo.verificar_nota(pac, _nota_boa(pac)), (True, []))

    def test_nota_com_id_inventado(self):
        _, _, pac = _caso()
        n = _nota_boa(pac)
        n["itens"].append({"id": "B9999", "sugestao": None, "texto": "ajuste"})
        ok, f = residuo.verificar_nota(pac, n)
        self.assertFalse(ok)
        self.assertIn("REFERENCIA_INEXISTENTE:B9999", f)

    def test_sugestao_fora_da_lista(self):
        """O LLM não pode sugerir par que o código não ofereceu (nem id real de fora da lista)."""
        _, _, pac = _caso()
        n = _nota_boa(pac)
        alvo = next(i for i in pac if i["lado"] == "banco")
        fora = next(j["id"] for j in pac if j["lado"] == "razao" and j["id"] not in alvo["candidatos"])
        next(x for x in n["itens"] if x["id"] == alvo["id"])["sugestao"] = fora
        ok, f = residuo.verificar_nota(pac, n)
        self.assertFalse(ok)
        self.assertTrue(any(x.startswith("SUGESTAO_FORA_DOS_CANDIDATOS") for x in f))

    def test_omitir_item_e_conservacao(self):
        _, _, pac = _caso()
        n = _nota_boa(pac)
        n["itens"].pop()
        self.assertTrue(any(x.startswith("CONSERVACAO") for x in residuo.verificar_nota(pac, n)[1]))

    def test_repetir_item_texto_longo_e_formato(self):
        _, _, pac = _caso()
        n = _nota_boa(pac)
        n["itens"].append(dict(n["itens"][0]))
        n["itens"][1]["texto"] = "x" * 301
        f = residuo.verificar_nota(pac, n)[1]
        self.assertTrue(any(x.startswith("REUSO") for x in f))
        self.assertTrue(any(x.startswith("TEXTO_INVALIDO") for x in f))
        self.assertEqual(residuo.verificar_nota(pac, ["lixo"]), (False, ["FORMATO_INVALIDO"]))
        self.assertEqual(residuo.verificar_nota(pac, {"itens": [7]})[1][0], "FORMATO_INVALIDO:item")


if __name__ == "__main__":
    unittest.main()
