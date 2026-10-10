"""T043: árvore de Merkle RFC 9162. Âncora externa: raízes de referência do Certificate
Transparency (dados de teste públicos da RFC 6962/9162, mesmos hashes de folha e nó)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collegium import merkle as mk  # noqa: E402

ENTRADAS = ["", "00", "10", "2021", "3031", "40414243", "5051525354555657",
            "606162636465666768696a6b6c6d6e6f"]
RAIZES_CT = ["6e340b9cffb37a989ca544e6bb780a2c78901d3fb33738768511a30617afa01d",
             "fac54203e7cc696cf0dfcb42c92a1d9dbaf70ad9e621f4bd8d98662f00e3c125",
             "aeb6bcfe274b70a14fb067a5e5578264db0fa9b51af5e0ba159158f329e06e77",
             "d37ee418976dd95753c1c73862b9398fa2a2cf9b4ff0fdfe8b30cd95209614b7",
             "4e3bbb1f7b478dcfe71fb631631519a3bca12c9aefca1612bfce4c13a86264d4",
             "76e67dadbcdf1e10e1b74ddc608abd2f98dfb16fbce75277b5232a127f2087ef",
             "ddb89be403809e325750d3d263cd78929c2942b7942a34b77e122c9594a74c8c",
             "5dc9da79a70659a9ad559cb701ded9a2ab9d823aad2f4960cfe370eff4604328"]


def arv(n):
    return mk.Arvore([mk.folha(bytes([i % 256]) * (i % 7)) for i in range(n)])


class TestMerkle(unittest.TestCase):
    def test_raizes_de_referencia_ct(self):
        a = mk.Arvore([mk.folha(bytes.fromhex(x)) for x in ENTRADAS])
        for n, esperado in enumerate(RAIZES_CT, 1):
            self.assertEqual(a.raiz(0, n).hex(), esperado, f"n={n}")
        self.assertEqual(mk.Arvore([]).raiz().hex(),
                         "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")

    def test_inclusao_exaustiva_e_adulteracao(self):
        for n in range(1, 41):
            a = arv(n)
            for m in range(n):
                pr = a.prova_inclusao(m)
                self.assertTrue(mk.verificar_inclusao(a.f[m], m, n, pr, a.raiz()), (n, m))
                self.assertFalse(mk.verificar_inclusao(mk.folha(b"falso"), m, n, pr, a.raiz()))
                if pr:
                    ruim = [bytes(32)] + pr[1:]
                    self.assertFalse(mk.verificar_inclusao(a.f[m], m, n, ruim, a.raiz()))
                self.assertFalse(mk.verificar_inclusao(a.f[m], m + n, n, pr, a.raiz()))

    def test_consistencia_exaustiva(self):
        for n in range(1, 41):
            a = arv(n)
            for m in range(1, n + 1):
                pr = a.prova_consistencia(m)
                self.assertTrue(mk.verificar_consistencia(m, a.raiz(0, m), n, a.raiz(), pr), (m, n))

    def test_historico_reescrito_e_detectado(self):
        """O operador mostra ao cliente a raiz de 10 registros; depois reescreve o registro 3."""
        a = arv(25)
        raiz10 = a.raiz(0, 10)
        b = mk.Arvore(list(a.f))
        b.f[3] = mk.folha(b"reescrito")
        for n in (10, 17, 25):
            self.assertFalse(mk.verificar_consistencia(10, raiz10, n, b.raiz(0, n), b.prova_consistencia(10, n)))
        self.assertTrue(mk.verificar_consistencia(10, raiz10, 25, a.raiz(), a.prova_consistencia(10)))

    def test_entradas_invalidas(self):
        self.assertFalse(mk.verificar_consistencia(0, b"", 5, b"", []))
        self.assertFalse(mk.verificar_consistencia(6, b"", 5, b"", []))
        with self.assertRaises(IndexError):
            arv(3).prova_inclusao(3)


if __name__ == "__main__":
    unittest.main()
