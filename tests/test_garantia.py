"""T050: garantia estatística. Valores de referência analíticos conhecidos."""
import math
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collegium.garantia import (Calibracao, Vigia, binom_cdf, clopper_pearson_sup, kappa_cohen,  # noqa: E402
                                learn_then_test, p_valor_risco)


class TestGarantia(unittest.TestCase):
    def test_cdf_binomial_exata(self):
        self.assertAlmostEqual(binom_cdf(0, 10, 0.1), 0.9 ** 10, places=12)
        self.assertAlmostEqual(binom_cdf(5, 10, 0.5), sum(math.comb(10, i) for i in range(6)) / 1024, places=12)
        self.assertAlmostEqual(binom_cdf(1000, 2000, 0.5), 0.5 + math.comb(2000, 1000) / 2 ** 2001, places=9)

    def test_clopper_pearson_zero_erros(self):
        self.assertAlmostEqual(clopper_pearson_sup(0, 10, 0.95), 1 - 0.05 ** (1 / 10), places=6)
        self.assertEqual(clopper_pearson_sup(5, 5), 1.0)

    def test_kappa(self):
        a = [True, False, True, True]
        self.assertEqual(kappa_cohen(a, a), 1.0)
        self.assertLess(kappa_cohen(a, [not x for x in a]), 0)

    def test_ltt_sem_dados_suficientes_manda_tudo_ao_humano(self):
        cal = Calibracao([[True, True, True]] * 10, [True] * 10)
        self.assertIsNone(learn_then_test(cal, 0.05, 0.1).minimo_votos)  # n < n_min

    def test_ltt_libera_unanimidade_quando_ela_e_boa(self):
        rnd = random.Random(1)
        votos, hum = [], []
        for _ in range(2000):
            bom = rnd.random() < 0.8
            votos.append([(rnd.random() >= 0.05) == bom for _ in range(3)])
            hum.append(bom)
        esc = learn_then_test(Calibracao(votos, hum), 0.05, 0.1)
        self.assertIsNotNone(esc.minimo_votos)
        self.assertLessEqual(p_valor_risco(0, 100, 0.05), 0.0060)

    def test_vigia(self):
        v = Vigia(0.05, 0.10)
        while v.estado == "continuar":
            v.registrar(True)
        self.assertEqual(v.estado, "revogar")
        self.assertLess(v.n, 10)
        v = Vigia(0.05, 0.10)
        while v.estado == "continuar":
            v.registrar(False)
        self.assertEqual(v.estado, "manter")
        with self.assertRaises(ValueError):
            Vigia(0.1, 0.05)


if __name__ == "__main__":
    unittest.main()
