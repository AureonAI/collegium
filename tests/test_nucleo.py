"""Testes do núcleo. Rodar: python -m unittest discover -s tests -v
Cada teste nomeia a fraqueza/ataque que cobre (ver forge/ADVERSARIAL_LOG.md)."""
import copy
import json
import os
import random
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from collegium import Acao, Ledger, Lex, RegimentoInvalido, carregar_regimento, wilson_inferior  # noqa: E402
from collegium.autonomia import Historico, nivel  # noqa: E402
from collegium.lex import assinar_humano  # noqa: E402
from collegium_oficios.conciliacao import dados, oraculo, operarios  # noqa: E402

with open(os.path.join(RAIZ, "regimento.exemplo.json"), encoding="utf-8") as _f:
    REG = json.load(_f)
ORACULOS = {"conciliacao_bancaria": oraculo.oraculo_lex}
CHAVE = b"chave-do-patronus"


def ent(ds):
    return {"extrato": ds["extrato"], "razao": ds["razao"]}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cam = os.path.join(self.tmp.name, "a.jsonl")
        self.lex = self.novo()
        self.ds = dados.gerar(1)

    def novo(self, reg=REG, oraculos=ORACULOS):
        return Lex(reg, Ledger(self.cam, chave=b"k"), oraculos, chave_patronus=CHAVE)

    def tearDown(self):
        self.tmp.cleanup()

    def tarefa_aceita(self, tid="t", produtor="op-1", seed=2):
        ds = dados.gerar(seed)
        p = operarios.honesto_v4(ds["extrato"], ds["razao"])
        self.lex.abrir_tarefa(tid, "conciliacao_bancaria", produtor, entrada=ent(ds))
        self.lex.submeter(tid, produtor, p)
        self.assertEqual(self.lex.verificar(tid, "ex-det", p).codigo, "ACEITA")
        return p


class TestAnais(Base):
    def test_integro_e_reabre(self):
        p = os.path.join(self.tmp.name, "b.jsonl")
        L = Ledger(p, chave=b"k")
        for i in range(10):
            L.anexar("x", {"i": i})
        self.assertEqual(L.verificar(), (True, None))
        L2 = Ledger(p, chave=b"k")
        self.assertEqual((len(L2), L2.cabeca), (10, L.cabeca))

    def test_recusa_abrir_corrompido(self):
        p = os.path.join(self.tmp.name, "c.jsonl")
        L = Ledger(p, chave=b"k")
        L.anexar("x", {"v": 1})
        L.anexar("x", {"v": 2})
        with open(p, encoding="utf-8") as f:
            linhas = f.read().replace('"v": 1', '"v": 9')
        with open(p, "w", encoding="utf-8") as f:
            f.write(linhas)
        with self.assertRaises(ValueError):
            Ledger(p, chave=b"k")

    def test_truncar_cauda_so_com_ancora(self):
        p = os.path.join(self.tmp.name, "d.jsonl")
        L = Ledger(p, chave=b"k")
        for i in range(5):
            L.anexar("x", {"i": i})
        anc = L.ancora()
        with open(p, encoding="utf-8") as f:
            linhas = f.readlines()[:-2]
        with open(p, "w", encoding="utf-8") as f:
            f.writelines(linhas)
        leitor = Ledger.__new__(Ledger)
        leitor.caminho, leitor.chave = p, b"k"
        self.assertTrue(leitor.verificar()[0])          # sem âncora: o ataque vence (declarado)
        self.assertFalse(leitor.verificar(anc)[0])      # com âncora externa: detectado

    def test_C1_dois_escritores_nao_bifurcam_a_cadeia(self):
        """GAP de concorrência: dois processos/objetos escrevendo o mesmo ANAIS."""
        p = os.path.join(self.tmp.name, "e.jsonl")
        A, B = Ledger(p, chave=b"k"), Ledger(p, chave=b"k")
        for i in range(20):
            (A if i % 2 else B).anexar("x", {"i": i})
        self.assertEqual(Ledger(p, chave=b"k").verificar(), (True, None))

    def test_C1b_quatro_processos_simultaneos(self):
        import subprocess
        p = os.path.join(self.tmp.name, "mp.jsonl")
        codigo = ("import sys; sys.path.insert(0, sys.argv[1]); from collegium import Ledger; "
                  "L = Ledger(sys.argv[2], chave=b'k'); [L.anexar('x', {'p': sys.argv[3], 'i': i}) for i in range(40)]")
        procs = [subprocess.Popen([sys.executable, "-c", codigo, RAIZ, p, str(k)]) for k in range(4)]
        self.assertEqual([x.wait() for x in procs], [0, 0, 0, 0])
        L = Ledger(p, chave=b"k")
        self.assertEqual((L.verificar(), len(L)), ((True, None), 160))

    def test_minimizacao_lgpd_sem_dado_bruto(self):
        """O ANAIS guarda hashes das entradas, não valores do extrato."""
        self.tarefa_aceita()
        with open(self.cam, encoding="utf-8") as f:
            texto = f.read()
        ds = dados.gerar(2)
        self.assertFalse(any(f'"{x["desc"]}"' in texto for x in ds["extrato"]))
        self.assertFalse(any(str(x["valor"]) in texto for x in ds["extrato"][:20]))


class TestRegimento(unittest.TestCase):
    def test_exige_familia_e_orcamento(self):
        r = copy.deepcopy(REG)
        r["agentes"]["op-1"]["familia_modelo"] = ""
        with self.assertRaises(RegimentoInvalido):
            carregar_regimento(r)
        r = copy.deepcopy(REG)
        r["classes_tarefa"]["conciliacao_bancaria"]["orcamento_passos"] = 0
        with self.assertRaises(RegimentoInvalido):
            carregar_regimento(r)


class TestLeis(Base):
    def test_L1_negacao_por_padrao_e_quarentena(self):
        self.lex.abrir_tarefa("t", "conciliacao_bancaria", "op-1", entrada=ent(self.ds))
        self.assertEqual(self.lex.autorizar(Acao("op-1", "rede", "paste.rs", "t")).codigo, "EGRESSO_NEGADO")
        self.assertEqual(self.lex.autorizar(Acao("op-1", "ferramenta", "extrato.ler", "t")).codigo, "QUARENTENA")

    def test_L1_mural_oficial_tipado(self):
        self.lex.abrir_tarefa("t", "conciliacao_bancaria", "op-1", entrada=ent(self.ds))
        m = self.lex.mandato("op-1")
        self.assertTrue(m.agir("mensagem", "forum", "t", para="op-2", tipo="pedido",
                               conteudo="preciso do razão").permitido)
        self.assertEqual(m.agir("mensagem", "forum", "t", conteudo="livre").codigo, "MENSAGEM_INVALIDA")
        self.assertEqual(m.agir("mensagem", "forum", "t", para="op-2", tipo="pedido",
                                conteudo="x" * 100_000).codigo, "MENSAGEM_INVALIDA")  # R5
        tipos = [r["corpo"]["tipo"] for r in self.lex.anais.registros()]
        self.assertEqual(tipos.count("mensagem"), 1)

    def test_R1_sem_tarefa_nao_foge_do_orcamento(self):
        d = self.lex.autorizar(Acao("op-1", "ferramenta", "extrato.ler", None))
        self.assertEqual(d.codigo, "SEM_TAREFA")
        self.assertTrue(self.lex.autorizar(Acao("rec-1", "ferramenta", "tarefa.distribuir", None)).permitido)

    def test_L2_orcamento_e_dever_de_declarar(self):
        self.lex.abrir_tarefa("t", "conciliacao_bancaria", "op-1", entrada=ent(self.ds))
        orc = REG["classes_tarefa"]["conciliacao_bancaria"]["orcamento_passos"]
        for _ in range(orc):
            self.assertTrue(self.lex.autorizar(Acao("op-1", "ferramenta", "extrato.ler", "t")).permitido)
        d = self.lex.mandato("op-1").declarar("t", "IMPOSSIVEL", "sem razão de setembro")
        self.assertTrue(d.permitido)

    def test_L2_declarar_sem_evidencia_negado(self):
        self.lex.abrir_tarefa("t", "conciliacao_bancaria", "op-1", entrada=ent(self.ds))
        self.assertEqual(self.lex.autorizar(Acao("op-1", "declaracao", "IMPOSSIVEL", "t")).codigo, "SEM_EVIDENCIA")

    def test_L3_separacao_de_poderes_e_linhagem(self):
        p = operarios.honesto_v4(self.ds["extrato"], self.ds["razao"])
        self.lex.abrir_tarefa("t", "conciliacao_bancaria", "ex-det", entrada=ent(self.ds))
        self.lex.submeter("t", "ex-det", p)
        self.assertEqual(self.lex.verificar("t", "ex-det", p, True).codigo, "AUTOVERIFICACAO")
        # sem oráculo, linhagem compartilhada é recusada — inclusive destilado (op-3 = qwen+deepseek)
        r = copy.deepcopy(REG)
        r["classes_tarefa"]["revisao"] = {"orcamento_passos": 5}
        lex = Lex(r, Ledger(os.path.join(self.tmp.name, "s.jsonl"), chave=b"k"), ORACULOS, CHAVE)
        lex.abrir_tarefa("u", "revisao", "op-3")
        lex.submeter("u", "op-3", {"texto": "x"})
        self.assertEqual(lex.verificar("u", "ex-q", {"texto": "x"}, True).codigo, "MESMA_FAMILIA")

    def test_L3_fabricacao_gera_quarentena(self):
        ds = dados.gerar(3)
        p = operarios.fabricador(ds["extrato"], ds["razao"])
        self.lex.abrir_tarefa("t", "conciliacao_bancaria", "op-1", entrada=ent(ds))
        self.lex.submeter("t", "op-1", p)
        self.lex.verificar("t", "ex-det", p)
        self.assertIn("op-1", self.lex.quarentena)

    def test_L4_liberacao_exige_humano_assinado(self):
        p = self.tarefa_aceita()
        self.assertEqual(self.lex.liberar("t").codigo, "AGUARDA_HUMANO")
        self.assertEqual(self.lex.aprovar_humano("t", "op-1", True).codigo, "FALSO_HUMANO")
        self.assertEqual(self.lex.aprovar_humano("t", "renato", True).codigo, "FALSO_HUMANO")  # R2: sem assinatura
        h = self.lex.tarefas["t"].entrega_hash
        self.assertEqual(self.lex.aprovar_humano("t", "renato", True, "f" * 64).codigo, "FALSO_HUMANO")
        sig = assinar_humano(CHAVE, "aprovar", "t", h, True, "renato")
        self.assertTrue(self.lex.aprovar_humano("t", "renato", True, sig).permitido)
        self.assertEqual(self.lex.anais.verificar(), (True, None))
        self.assertIsNotNone(p)

    def test_mandato_fixa_identidade(self):
        m = self.lex.mandato("op-1")
        self.assertFalse(hasattr(m, "verificar") or hasattr(m, "aprovar_humano") or hasattr(m, "reabilitar"))
        with self.assertRaises(KeyError):
            self.lex.mandato("intruso")


class TestCorrecoes(Base):
    def test_D1_veredito_falso_nao_passa(self):
        ds = dados.gerar(3)
        p = operarios.fabricador(ds["extrato"], ds["razao"])
        self.lex.abrir_tarefa("f", "conciliacao_bancaria", "op-1", entrada=ent(ds))
        self.lex.submeter("f", "op-1", p)
        self.lex.verificar("f", "ex-det", p, True)  # mente
        self.assertEqual(self.lex.tarefas["f"].estado, "REJEITADA")
        self.assertIn("ex-det", self.lex.quarentena)
        self.assertIn("op-1", self.lex.quarentena)

    def test_D1_entrada_obrigatoria_com_oraculo(self):
        with self.assertRaises(ValueError):
            self.lex.abrir_tarefa("x", "conciliacao_bancaria", "op-1")

    def test_D2_estado_completo_sobrevive_ao_reinicio(self):
        for i in range(3):
            self.tarefa_aceita(f"h{i}", "op-2", seed=10 + i)
        self.lex.abrir_tarefa("meio", "conciliacao_bancaria", "op-1", entrada=ent(self.ds))
        for _ in range(4):
            self.lex.autorizar(Acao("op-1", "ferramenta", "extrato.ler", "meio"))
        self.lex.abrir_tarefa("v", "conciliacao_bancaria", "op-3", entrada=ent(self.ds))
        self.lex.autorizar(Acao("op-3", "rede", "paste.rs", "v"))
        novo = self.novo()
        self.assertIn("op-3", novo.quarentena)
        self.assertEqual(novo._hist("op-2", "conciliacao_bancaria").total, 3)
        self.assertEqual(novo.tarefas["meio"].passos, 4)          # tarefa em andamento retomada
        self.assertEqual(novo.tarefas["h0"].estado, "ACEITA")
        self.assertFalse(novo.vincular_entrada("meio", ent(dados.gerar(99))).permitido)
        self.assertTrue(novo.vincular_entrada("meio", ent(self.ds)).permitido)
        sig = assinar_humano(CHAVE, "reabilitar", "op-3", "renato")
        self.assertTrue(novo.reabilitar("op-3", "renato", "revisado", sig).permitido)
        self.assertNotIn("op-3", self.novo().quarentena)

    def test_D2_agente_nao_se_reabilita(self):
        self.lex.abrir_tarefa("v", "conciliacao_bancaria", "op-1", entrada=ent(self.ds))
        self.lex.autorizar(Acao("op-1", "rede", "paste.rs", "v"))
        self.assertEqual(self.lex.reabilitar("op-1", "op-2", "amigo").codigo, "FALSO_HUMANO")
        self.assertEqual(self.lex.reabilitar("op-1", "renato", "sem assinatura").codigo, "FALSO_HUMANO")
        self.assertIn("op-1", self.lex.quarentena)

    def test_D3_versao_numerica(self):
        from collegium_oficios.conciliacao.oraculo import _v
        self.assertGreater(_v("0.1.10"), _v("0.1.2"))

    def test_R3_amostragem_imprevisivel_e_proporcional(self):
        sorteados = sum(self.lex._amostra_l1(f"T{i}") for i in range(5000))
        self.assertTrue(800 < sorteados < 1200, sorteados)  # ~1/5, sem padrão de módulo
        self.assertNotEqual([self.lex._amostra_l1(f"T{i}") for i in range(10)],
                            [(i % 5 == 0) for i in range(10)])

    def test_ids_de_tarefa_nao_se_reutilizam(self):
        self.lex.abrir_tarefa("t", "conciliacao_bancaria", "op-1", entrada=ent(self.ds))
        with self.assertRaises(KeyError):
            self.lex.abrir_tarefa("t", "conciliacao_bancaria", "op-1", entrada=ent(self.ds))

    def test_admissao_exigida(self):
        r = copy.deepcopy(REG)
        r["admissao"]["exigida"] = True
        lex = Lex(r, Ledger(os.path.join(self.tmp.name, "adm.jsonl"), chave=b"k"), ORACULOS, CHAVE)
        with self.assertRaises(PermissionError):
            lex.abrir_tarefa("t", "conciliacao_bancaria", "op-1", entrada=ent(self.ds))
        lex.registrar_admissao("op-1", True, 1.0, "e" * 64, "r" * 64)
        lex.abrir_tarefa("t", "conciliacao_bancaria", "op-1", entrada=ent(self.ds))
        lex2 = Lex(r, Ledger(os.path.join(self.tmp.name, "adm.jsonl"), chave=b"k"), ORACULOS, CHAVE)
        self.assertIn("op-1", lex2.admitidos)


class TestAutonomia(unittest.TestCase):
    CFG = dict(REG["autonomia"], janela_incidente=0)

    def test_wilson(self):
        self.assertAlmostEqual(wilson_inferior(100, 100), 0.963, places=3)
        self.assertEqual(wilson_inferior(0, 0), 0.0)

    def test_niveis_estabilidade_e_rebaixamento(self):
        h = Historico()
        for _ in range(130):
            h.registrar(True)
        self.assertEqual(nivel(h, self.CFG), 1)   # estabilidade ainda não cumprida para L2
        for _ in range(100):  # z=2,326 + estabilidade 50: L2 só a partir de ~224 aceites seguidos
            h.registrar(True)
        self.assertEqual(nivel(h, self.CFG), 2)
        h.incidente()
        self.assertEqual(nivel(h, self.CFG), 0)

    def test_R4_agente_que_piora_perde_nivel(self):
        h, rnd = Historico(), random.Random(1)
        for _ in range(2000):
            h.registrar(True)
        self.assertGreaterEqual(nivel(h, self.CFG), 2)
        for _ in range(100):
            h.registrar(rnd.random() < 0.80)
        self.assertLessEqual(nivel(h, self.CFG), 0)  # janela recente a ~80% < 0,90 de L1


class TestOraculo(unittest.TestCase):
    def test_honesto_v4_aceito_sem_duplicatas(self):
        for s in range(1, 30):
            ds = dados.gerar(s)
            p = operarios.honesto_v4(ds["extrato"], ds["razao"])
            ok, falhas = oraculo.verificar(ds["extrato"], ds["razao"], p)
            self.assertTrue(ok, (s, falhas))
            self.assertEqual(set(map(tuple, p["pares"])), set(map(tuple, ds["gabarito"])))

    def test_maquiador_reprovado_por_conservacao(self):
        ds = dados.gerar(5)
        ok, falhas = oraculo.verificar(ds["extrato"], ds["razao"], operarios.maquiador(ds["extrato"], ds["razao"]))
        self.assertFalse(ok)
        self.assertTrue(any(f.startswith("CONSERVACAO") for f in falhas))


if __name__ == "__main__":
    unittest.main()


class TestGPTRedFinal(Base):
    """Lacunas G1–G5 achadas na varredura final (ADVERSARIAL_LOG)."""

    def test_G1_entrega_malformada_rejeita_sem_derrubar(self):
        self.lex.abrir_tarefa("m", "conciliacao_bancaria", "op-1", entrada=ent(self.ds))
        mal = {"pares": [["B0001"]], "pendentes_banco": [], "pendentes_razao": []}
        self.lex.submeter("m", "op-1", mal)
        self.assertEqual(self.lex.verificar("m", "ex-det", mal).codigo, "REJEITADA")
        self.assertNotIn("op-1", self.lex.quarentena)  # erro de formato não é fraude

    def test_G1b_oraculo_que_explode_falha_fechado(self):
        lex = Lex(REG, Ledger(os.path.join(self.tmp.name, "x.jsonl"), chave=b"k"),
                  {"conciliacao_bancaria": lambda e, s: 1 / 0}, CHAVE)
        lex.abrir_tarefa("t", "conciliacao_bancaria", "op-1", entrada=ent(self.ds))
        lex.submeter("t", "op-1", {"pares": []})
        self.assertEqual(lex.verificar("t", "ex-det", {"pares": []}).codigo, "REJEITADA")

    def test_G2_entrega_nao_serializavel(self):
        self.lex.abrir_tarefa("n", "conciliacao_bancaria", "op-1", entrada=ent(self.ds))
        self.assertEqual(self.lex.submeter("n", "op-1", {"pares": {1, 2}}).codigo, "ENTREGA_INVALIDA")

    def test_G3_evidencia_da_declaracao_selada(self):
        self.lex.abrir_tarefa("d", "conciliacao_bancaria", "op-2", entrada=ent(self.ds))
        self.lex.mandato("op-2").declarar("d", "IMPOSSIVEL", "EVIDENCIA_UNICA_XYZ")
        with open(self.cam, encoding="utf-8") as f:
            self.assertIn("EVIDENCIA_UNICA_XYZ", f.read())

    def test_G4_regimento_alterado_exige_assinatura(self):
        r2 = copy.deepcopy(REG)
        r2["papeis"]["operarius"]["rede"] = ["paste.rs"]
        with self.assertRaises(RegimentoInvalido):
            Lex(r2, Ledger(self.cam, chave=b"k"), ORACULOS, CHAVE)
        from collegium.lex import _h
        sig = assinar_humano(CHAVE, "regimento", _h(r2))
        self.assertIsNotNone(Lex(r2, Ledger(self.cam, chave=b"k"), ORACULOS, CHAVE, assinatura_regimento=sig))

    def test_G5_admissao_caduca_quando_regimento_muda(self):
        r = copy.deepcopy(REG)
        r["admissao"]["exigida"] = True
        cam = os.path.join(self.tmp.name, "g5.jsonl")
        lex = Lex(r, Ledger(cam, chave=b"k"), ORACULOS, CHAVE)
        lex.registrar_admissao("op-1", True, 1.0, "e" * 64, "r" * 64)
        r2 = copy.deepcopy(r)
        r2["classes_tarefa"]["conciliacao_bancaria"]["orcamento_passos"] = 20
        from collegium.lex import _h
        lex2 = Lex(r2, Ledger(cam, chave=b"k"), ORACULOS, CHAVE,
                   assinatura_regimento=assinar_humano(CHAVE, "regimento", _h(r2)))
        self.assertNotIn("op-1", lex2.admitidos)  # precisa refazer o EXAME

    def test_saldo_que_nao_fecha_bloqueia_qualquer_entrega(self):
        e = dict(ent(self.ds), saldo_inicial=0, saldo_final=1)
        p = operarios.honesto_v4(self.ds["extrato"], self.ds["razao"])
        ok, falhas = oraculo.oraculo_lex(e, p)
        self.assertFalse(ok)
        self.assertTrue(falhas[0].startswith("SALDO_NAO_FECHA"))

    def test_equipe_abaixo_do_minimo_gera_alerta(self):
        from collegium.equipe import relatorio
        for ag in ("op-1", "op-2"):
            self.lex.abrir_tarefa(f"q-{ag}", "conciliacao_bancaria", ag, entrada=ent(self.ds))
            self.lex.autorizar(Acao(ag, "rede", "paste.rs", f"q-{ag}"))
        self.assertIn("ABAIXO DO MÍNIMO", relatorio(self.lex)["alerta_equipe"])

    def test_exame_responder_sempre_nao_reprova(self):
        from collegium.dossie import carregar_dossie, corrigir, gerar_exame
        _, gab = gerar_exame(carregar_dossie(os.path.join(RAIZ, "dossie_exemplo")), "op-1")
        self.assertLess(corrigir(gab, {k: "nao" for k in gab})[0], 0.9)
