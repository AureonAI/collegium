"""T067 · mapa verificável de tarefas. Cada teste é um ataque: R6-7 (recibo honesto escondia a rejeição
humana) venceu contra a v0.2.0; os demais testam o próprio mapa e fecham os limites R-1 e F-L."""
import copy
import json
import os
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from collegium import Ledger, Lex, ed25519, execucao  # noqa: E402
from collegium import fatura as ft  # noqa: E402
from collegium import mapa as mp  # noqa: E402
from collegium import merkle as mk  # noqa: E402
from collegium import recibo as rc  # noqa: E402
from collegium_oficios.conciliacao import dados, operarios, oraculo  # noqa: E402
from collegium_oficios.registro import carregar  # noqa: E402

SK = bytes([9]) * 32
PUB = ed25519.publica(SK).hex()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cam = os.path.join(self.tmp.name, "a.jsonl")
        self.of, _ = carregar("conciliacao_bancaria")
        led = lambda: Ledger(self.cam, chave=b"k")  # noqa: E731
        self.t1 = execucao.executar(self.of, led(), self.of.gerar(5)["entrada"], "E", humanos={"ana": PUB})["tarefa"]
        self.t2 = execucao.executar(self.of, led(), self.of.gerar(6)["entrada"], "E")["tarefa"]
        self.t3 = execucao.executar(self.of, led(), self.of.gerar(7)["entrada"], "E")["tarefa"]
        execucao.aprovar(self.of, led(), self.t1, "ana", SK, aprovado=False)   # o humano RECUSA a t1
        self.linhas = rc._linhas(self.cam)
        self.cab = rc.cabeca(self.cam, SK, "E", "agora")

    def tearDown(self):
        self.tmp.cleanup()

    def cabeca_com(self, fs):
        """Operador DESONESTO assina um mapa à sua escolha (a chave é dele)."""
        a = mk.Arvore([mk.folha(mp._bytes(f)) for f in fs])
        c = {k: v for k, v in self.cab.items() if k != "assinatura"}
        c["mapa"] = {"raiz": a.raiz(0, len(fs)).hex(), "tarefas": len(fs)}
        c["assinatura"] = ed25519.assinar(SK, rc._corpo_cabeca(c)).hex()
        return c, a

    def recibo_com(self, fs, tarefa):
        c, a = self.cabeca_com(fs)
        p = next(i for i, f in enumerate(fs) if f["tarefa"] == tarefa)
        no = lambda q: {"posicao": q, "folha": fs[q], "prova": [h.hex() for h in a.prova_inclusao(q, len(fs))]}  # noqa
        alog, _ = rc.arvore(self.cam)
        n = len(self.linhas)
        return {"formato": rc.FORMATO_RECIBO, "tarefa": tarefa, "cabeca": c,
                "itens": [{"indice": i, "linha": self.linhas[i], "prova": [h.hex() for h in alog.prova_inclusao(i, n)]}
                          for i in fs[p]["indices"]],
                "mapa": {"formato": mp.FORMATO_MAPA, "alvo": no(p), "esquerda": no(p - 1) if p else None,
                         "direita": no(p + 1) if p + 1 < len(fs) else None}}, c


class TestRecibo(Base):
    def test_r6_7_recibo_honesto_mostra_a_rejeicao_humana(self):
        ok, mot, res = rc.conferir_recibo(rc.emitir_recibo(self.cam, self.t1, self.cab), PUB)
        self.assertFalse(ok)
        self.assertIn("ENTREGA_REJEITADA", mot)
        self.assertEqual(res["estado_final"], "REJEITADA")
        self.assertEqual(res["completude"], "PROVADA (mapa assinado)")

    def test_eventos_sem_duplicata_e_estado_datado(self):
        """T068 (usado como estranho): 'ACEITA' aparecia 2x (decisão do LEX + linha de recibo = 1 evento),
        e nada dizia que o estado é o da cabeça, não o de agora."""
        _, _, res = rc.conferir_recibo(rc.emitir_recibo(self.cam, self.t1, self.cab), PUB)
        self.assertEqual(res["eventos"], ["SUBMETIDA", "ACEITA", "AGUARDA_HUMANO", "REJEITADA"])
        self.assertIn(str(self.cab["tamanho"]), res["estado_valido_em"])
        self.assertIn(self.cab["instante"], res["estado_valido_em"])

    def test_tarefa_aguardando_humano_continua_valida(self):
        ok, mot, res = rc.conferir_recibo(rc.emitir_recibo(self.cam, self.t2, self.cab), PUB)
        self.assertTrue(ok, mot)
        self.assertEqual(res["estado_final"], "AGUARDA_HUMANO")

    def test_esconder_linha_e_detectado(self):
        rec = rc.emitir_recibo(self.cam, self.t1, self.cab)
        rec["itens"] = [it for it in rec["itens"] if "REJEITADA" not in it["linha"]]
        self.assertEqual(rc.conferir_recibo(rec, PUB)[1], ["RECIBO_INCOMPLETO_OU_COM_LINHA_A_MAIS"])

    def test_enxertar_linha_de_outra_tarefa_e_detectado(self):
        rec = rc.emitir_recibo(self.cam, self.t2, self.cab)
        outro = rc.emitir_recibo(self.cam, self.t3, self.cab)["itens"][-1]
        rec["itens"].append(outro)
        self.assertFalse(rc.conferir_recibo(rec, PUB)[0])

    def test_folha_duplicada_e_detectada_pelo_cliente(self):
        fs = mp.folhas(self.linhas, len(self.linhas))
        sem_rej = [dict(f, indices=[i for i in f["indices"] if "REJEITADA" not in self.linhas[i]])
                   for f in fs if f["tarefa"] == self.t1][0]
        dup = sorted(fs + [sem_rej], key=lambda f: (f["tarefa"], len(f["indices"])))
        rec, _ = self.recibo_com(dup, self.t1)
        self.assertIn("MAPA_UNICIDADE_NAO_PROVADA", rc.conferir_recibo(rec, PUB)[1])

    def test_mapa_mentiroso_engana_o_cliente_mas_nao_o_auditor(self):
        """Limite declarado: a mentira passa no cliente sozinho, mas fica ASSINADA e o auditor a prova."""
        fs = [dict(f, indices=[i for i in f["indices"] if "REJEITADA" not in self.linhas[i]])
              if f["tarefa"] == self.t1 else f for f in mp.folhas(self.linhas, len(self.linhas))]
        rec, c = self.recibo_com(fs, self.t1)
        self.assertTrue(rc.conferir_recibo(rec, PUB)[0])
        self.assertEqual(mp.auditar(self.linhas, c), (False, ["MAPA_ASSINADO_DIFERE_DO_ANAIS"]))
        self.assertEqual(mp.auditar(self.linhas, self.cab), (True, []))

    def test_auditar_cabeca_completa(self):
        self.assertEqual(rc.auditar_cabeca(self.cam, self.cab, PUB), (True, []))
        c, _ = self.cabeca_com([f for f in mp.folhas(self.linhas, len(self.linhas)) if f["tarefa"] != self.t3])
        self.assertEqual(rc.auditar_cabeca(self.cam, c, PUB), (False, ["MAPA_ASSINADO_DIFERE_DO_ANAIS"]))
        self.assertEqual(rc.auditar_cabeca(self.cam, self.cab, ed25519.publica(bytes([1]) * 32).hex()),
                         (False, ["CABECA_NAO_CONFIAVEL"]))
        with open(self.cam, "a", encoding="utf-8") as f:  # o registro cresce: a cabeça antiga continua auditável
            f.write(self.linhas[-1] + "\n")
        self.assertTrue(rc.auditar_cabeca(self.cam, self.cab, PUB)[0])

    def test_auditar_cabeca_pela_linha_de_comando(self):
        import subprocess
        cp = os.path.join(self.tmp.name, "cab.json")
        with open(cp, "w", encoding="utf-8") as f:
            json.dump(self.cab, f)
        r = subprocess.run([sys.executable, "-m", "collegium", "auditar-cabeca", self.cam, cp, PUB],
                           cwd=RAIZ, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(json.loads(r.stdout)["confere"])

    def test_legado_sem_mapa_so_com_permissao_e_avisa(self):
        rec = rc.emitir_recibo(self.cam, self.t2, self.cab)
        c = {k: v for k, v in self.cab.items() if k not in ("assinatura", "mapa")}
        c["formato"] = rc.LEGADO_CABECA
        c["assinatura"] = ed25519.assinar(SK, rc._corpo_cabeca(c)).hex()
        leg = {"formato": rc.LEGADO_RECIBO, "tarefa": self.t2, "cabeca": c, "itens": rec["itens"]}
        self.assertEqual(rc.conferir_recibo(leg, PUB)[1], ["RECIBO_SEM_PROVA_DE_COMPLETUDE"])
        ok, _, res = rc.conferir_recibo(leg, PUB, permitir_legado=True)
        self.assertTrue(ok)
        self.assertTrue(res["completude"].startswith("NAO_PROVADA"))

    def test_cabeca_v2_sem_mapa_e_recusada(self):
        c = {k: v for k, v in self.cab.items() if k not in ("assinatura", "mapa")}
        c["assinatura"] = ed25519.assinar(SK, rc._corpo_cabeca(c)).hex()
        self.assertFalse(rc.conferir_cabeca(c, PUB))

    def test_tarefa_fora_do_mapa(self):
        with self.assertRaises(KeyError):
            mp.provar(self.linhas, len(self.linhas), "NAO-EXISTE")


class TestFatura(unittest.TestCase):
    """F-L (limite da v0.2.0): o cliente não conseguia provar que um item não era canário."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cam = os.path.join(self.tmp.name, "a.jsonl")
        with open(os.path.join(RAIZ, "regimento.exemplo.json"), encoding="utf-8") as f:
            reg = json.load(f)
        reg["agentes"]["ana"] = {"papel": "patronus", "familia_modelo": "humano", "chave_publica": PUB}
        self.lex = Lex(reg, Ledger(self.cam, chave=b"k"), {"conciliacao_bancaria": oraculo.oraculo_lex})
        for tid, seed in (("a", 2), ("b", 4)):
            ds = dados.gerar(seed)
            e, p = {"extrato": ds["extrato"], "razao": ds["razao"]}, operarios.honesto_v4(ds["extrato"], ds["razao"])
            self.lex.abrir_tarefa(tid, "conciliacao_bancaria", "op-1", entrada=e)
            self.lex.submeter(tid, "op-1", p)
            self.lex.verificar(tid, "ex-det", p)
        ds = dados.gerar(5)
        e, g = {"extrato": ds["extrato"], "razao": ds["razao"]}, operarios.honesto_v4(ds["extrato"], ds["razao"])
        self.lex.abrir_canario("can", "conciliacao_bancaria", "op-1", e, g)
        self.lex.submeter("can", "op-1", g)
        self.lex.verificar("can", "ex-det", g)
        self.lex.liberar("b")  # vai ao humano...
        sig = execucao.assinar_humano_ed25519(SK, "aprovar", "b", self.lex.tarefas["b"].entrega_hash, False, "ana")
        self.lex.aprovar_humano("b", "ana", False, sig)  # ...que RECUSA
        self.cab = rc.cabeca(self.cam, SK, "E", "agora")

    def tearDown(self):
        self.tmp.cleanup()

    def _fatura_desonesta(self, tarefas):
        """Operador inclui o que quiser e assina (a chave é dele)."""
        a, linhas = rc.arvore(self.cam)
        n = len(linhas)
        itens = []
        for i, ln in enumerate(linhas):
            c = json.loads(ln)["corpo"]
            d = c["dados"]
            if c["tipo"] == "recibo" and d.get("tarefa") in tarefas and d.get("aceito"):
                j = next(k for k, x in enumerate(linhas) if json.loads(x)["corpo"]["tipo"] == "tarefa_aberta"
                         and json.loads(x)["corpo"]["dados"]["tarefa"] == d["tarefa"])
                pm = mp.provar(linhas, n, d["tarefa"])
                itens.append({"indice": i, "linha": ln, "prova": [h.hex() for h in a.prova_inclusao(i, n)],
                              "abertura": {"indice": j, "linha": linhas[j], "prova": [h.hex() for h in a.prova_inclusao(j, n)]},
                              "preco_centavos": 1500,
                              "historia": {"mapa": pm, "linhas": [{"indice": k, "linha": linhas[k],
                                                                   "prova": [h.hex() for h in a.prova_inclusao(k, n)]}
                                                                  for k in pm["alvo"]["folha"]["indices"]]}})
        f = {"formato": ft.FORMATO, "ente": "E", "periodo": [0, 10 ** 12], "precos": {"conciliacao_bancaria": 1500},
             "cabeca": self.cab, "itens": itens, "total_centavos": 1500 * len(itens)}
        f["assinatura"] = ed25519.assinar(SK, ft._corpo(f)).hex()
        return f

    def test_honesta_nao_cobra_canario_nem_recusada(self):
        f = ft.emitir_fatura(self.cam, self.cab, 0, 10 ** 12, {"conciliacao_bancaria": 1500}, SK)
        ok, mot, res = ft.conferir_fatura(json.loads(json.dumps(f)), PUB)
        self.assertTrue(ok, mot)
        self.assertEqual([json.loads(i["linha"])["corpo"]["dados"]["tarefa"] for i in f["itens"]], ["a"])
        self.assertEqual(res["total_centavos"], 1500)

    def test_r6_8_cobrar_recusada_pelo_humano_e_detectado(self):
        """R6-8: a 1ª versão do emissor (honesto!) cobrava 'b', recusada depois pelo humano."""
        ok, mot, _ = ft.conferir_fatura(self._fatura_desonesta({"a", "b"}), PUB)
        self.assertFalse(ok)
        self.assertEqual(mot, ["COBRANCA_DE_ENTREGA_REJEITADA:b"])

    def test_cobrar_canario_e_detectado(self):
        ok, mot, _ = ft.conferir_fatura(self._fatura_desonesta({"a", "can"}), PUB)
        self.assertFalse(ok)
        self.assertIn("COBRANCA_DE_CANARIO:can", mot)

    def test_historia_incompleta_e_detectada(self):
        f = self._fatura_desonesta({"a"})
        f["itens"][0]["historia"]["linhas"].pop()
        f["assinatura"] = ed25519.assinar(SK, ft._corpo(f)).hex()
        self.assertIn("HISTORIA_INCOMPLETA:a", ft.conferir_fatura(f, PUB)[1])


if __name__ == "__main__":
    unittest.main()
