"""T042: o humano assina com Ed25519; o núcleo só conhece a chave pública.
Ataques cobertos: rebaixamento para HMAC, autoaprovação de REGIMENTO, quórum insuficiente,
revogação desfeita, assinatura de chave revogada."""
import copy
import json
import os
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from collegium import Ledger, Lex, RegimentoInvalido  # noqa: E402
from collegium import ed25519 as ed  # noqa: E402
from collegium.lex import assinar_humano, assinar_humano_ed25519, _h  # noqa: E402
from collegium_oficios.conciliacao import dados, operarios, oraculo  # noqa: E402

with open(os.path.join(RAIZ, "regimento.exemplo.json"), encoding="utf-8") as _f:
    REG = json.load(_f)
ORAC = {"conciliacao_bancaria": oraculo.oraculo_lex}
SK = {n: bytes([i + 1]) * 32 for i, n in enumerate(["ana", "bia", "caio", "davi"])}
PK = {n: ed.publica(k).hex() for n, k in SK.items()}


def reg_com(chaves, quorum, revogadas=(), humano_pk=None, versao="x"):
    r = copy.deepcopy(REG)
    r["versao"] = versao
    r["patronus"] = {"quorum": quorum, "chaves": {n: PK[n] for n in chaves}, "revogadas": list(revogadas)}
    if humano_pk:
        r["agentes"]["renato"]["chave_publica"] = humano_pk
    return r


def assinar_reg(r, nomes):
    return {n: assinar_humano_ed25519(SK[n], "regimento", _h(r)) for n in nomes}


class TestPatronus(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cam = os.path.join(self.tmp.name, "a.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def lex(self, r, chave_patronus=None, assinatura=None):
        return Lex(r, Ledger(self.cam, chave=b"k"), ORAC, chave_patronus=chave_patronus, assinatura_regimento=assinatura)

    def _aguardando(self, lx):
        ds = dados.gerar(2)
        p = operarios.honesto_v4(ds["extrato"], ds["razao"])
        lx.abrir_tarefa("t", "conciliacao_bancaria", "op-1", entrada={"extrato": ds["extrato"], "razao": ds["razao"]})
        lx.submeter("t", "op-1", p)
        lx.verificar("t", "ex-det", p)
        self.assertEqual(lx.liberar("t").codigo, "AGUARDA_HUMANO")
        return lx.tarefas["t"].entrega_hash

    def test_aprovacao_ed25519_sem_o_nucleo_conhecer_a_privada(self):
        lx = self.lex(reg_com(["ana"], 1, humano_pk=PK["davi"]))  # chave_patronus=None: o núcleo não tem segredo
        h = self._aguardando(lx)
        sig = assinar_humano_ed25519(SK["davi"], "aprovar", "t", h, True, "renato")
        self.assertTrue(lx.aprovar_humano("t", "renato", True, sig).permitido)

    def test_rebaixamento_para_hmac_recusado(self):
        """Quem tem o HMAC (o próprio núcleo) não pode mais falar pelo humano que tem chave pública."""
        lx = self.lex(reg_com(["ana"], 1, humano_pk=PK["davi"]), chave_patronus=b"chave-do-patronus")
        h = self._aguardando(lx)
        forjada = assinar_humano(b"chave-do-patronus", "aprovar", "t", h, True, "renato")
        self.assertEqual(lx.aprovar_humano("t", "renato", True, forjada).codigo, "FALSO_HUMANO")

    def test_assinatura_de_outro_humano_ou_outra_decisao(self):
        lx = self.lex(reg_com(["ana"], 1, humano_pk=PK["davi"]))
        h = self._aguardando(lx)
        self.assertEqual(lx.aprovar_humano("t", "renato", True,
                                           assinar_humano_ed25519(SK["ana"], "aprovar", "t", h, True, "renato")).codigo,
                         "FALSO_HUMANO")
        neg = assinar_humano_ed25519(SK["davi"], "aprovar", "t", h, False, "renato")  # assinou NEGAR
        self.assertEqual(lx.aprovar_humano("t", "renato", True, neg).codigo, "FALSO_HUMANO")

    def test_quorum_2_de_3(self):
        r1 = reg_com(["ana", "bia", "caio"], 2)
        self.lex(r1)
        r2 = reg_com(["ana", "bia", "caio"], 2, versao="y")
        with self.assertRaises(RegimentoInvalido):
            self.lex(r2, assinatura=assinar_reg(r2, ["ana"]))           # só 1
        with self.assertRaises(RegimentoInvalido):
            dup = assinar_reg(r2, ["ana"])
            dup["ana2"] = dup["ana"]                                     # mesma chave sob outro nome
            self.lex(r2, assinatura=dup)
        self.lex(r2, assinatura=assinar_reg(r2, ["ana", "caio"]))     # 2 de 3: passa

    def test_regimento_novo_nao_se_autoaprova(self):
        self.lex(reg_com(["ana", "bia"], 2))
        golpe = reg_com(["davi"], 1, versao="golpe")                    # traz a própria chave
        with self.assertRaises(RegimentoInvalido):
            self.lex(golpe, assinatura=assinar_reg(golpe, ["davi"]))
        with self.assertRaises(RegimentoInvalido):                      # HMAC antigo também não serve mais
            sem = copy.deepcopy(golpe)
            del sem["patronus"]
            self.lex(sem, chave_patronus=b"chave-do-patronus",
                     assinatura=assinar_humano(b"chave-do-patronus", "regimento", _h(sem)))

    def test_revogacao_nao_se_desfaz(self):
        self.lex(reg_com(["ana", "bia", "caio"], 2))
        r2 = reg_com(["ana", "bia"], 2, revogadas=[PK["caio"]], versao="y")
        self.lex(r2, assinatura=assinar_reg(r2, ["ana", "bia"]))
        with self.assertRaises(RegimentoInvalido):                      # carregar já recusa reintroduzir
            reg_com(["ana", "bia", "caio"], 2, revogadas=[PK["caio"]], versao="z")
            self.lex(reg_com(["ana", "bia", "caio"], 2, revogadas=[PK["caio"]], versao="z"))
        r3 = reg_com(["ana", "bia"], 2, revogadas=[], versao="w")      # tenta "esquecer" a revogação
        with self.assertRaises(RegimentoInvalido):
            self.lex(r3, assinatura=assinar_reg(r3, ["ana", "bia"]))

    def test_humano_com_chave_revogada(self):
        r = reg_com(["ana"], 1, humano_pk=PK["davi"])
        r["patronus"]["revogadas"] = []
        lx = self.lex(r)
        h = self._aguardando(lx)
        lx.r["patronus"]["revogadas"] = [PK["davi"]]  # simula o estado pós-revogação
        sig = assinar_humano_ed25519(SK["davi"], "aprovar", "t", h, True, "renato")
        self.assertEqual(lx.aprovar_humano("t", "renato", True, sig).codigo, "FALSO_HUMANO")

    def test_mesma_chave_sob_dois_nomes_nao_vale_dois(self):
        """Ataque achado na própria revisão: quórum 2 satisfeito por UMA pessoa listada duas vezes."""
        r = copy.deepcopy(REG)
        r["patronus"] = {"quorum": 2, "chaves": {"ana": PK["ana"], "ana_bis": PK["ana"]}}
        with self.assertRaises(RegimentoInvalido):
            self.lex(r)

    def test_regimento_malformado(self):
        for ruim in ({"quorum": 3, "chaves": {"a": PK["ana"]}}, {"quorum": 1, "chaves": {"a": "zz"}},
                     {"quorum": 1, "chaves": {}}):
            r = copy.deepcopy(REG)
            r["patronus"] = ruim
            with self.assertRaises(RegimentoInvalido):
                self.lex(r)


if __name__ == "__main__":
    unittest.main()


class TestCLIEd(unittest.TestCase):
    def test_gerar_assinar_verificar_pela_linha_de_comando(self):
        import contextlib
        import io
        from collegium.__main__ import main
        with tempfile.TemporaryDirectory() as d:
            arq = os.path.join(d, "renato.chave")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(main(["gerar-chave", arq]), 0)
            pub = out.getvalue().strip()
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(["gerar-chave", arq]), 2)  # não sobrescreve
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                main(["assinar-ed", arq, "aprovar", "t", "abc", "true", "renato"])
            from collegium.lex import _ed_ok
            self.assertTrue(_ed_ok(pub, out.getvalue().strip(), "aprovar", "t", "abc", True, "renato"))
