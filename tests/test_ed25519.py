"""T042: Ed25519 contra os vetores OFICIAIS da RFC 8032 §7.1 (âncora externa) + ataques de maleabilidade."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collegium import ed25519 as ed  # noqa: E402

RFC8032 = [  # (privada, pública, mensagem, assinatura) — copiados de rfc-editor.org/rfc/rfc8032.txt
    ("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
     "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a", "",
     "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"),
    ("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
     "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c", "72",
     "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"),
    ("c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
     "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025", "af82",
     "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a"),
    ("833fe62409237b9d62ec77587520911e9a759cec1d19755b7da901b96dca3d42",
     "ec172b93ad5e563bf4932c70e1245034c35467ef2efd4d64ebf819683467e2bf",
     "ddaf35a193617abacc417349ae20413112e6fa4e89a97ea20a9eeee64b55d39a2192992a274fc1a836ba3c23a3feebbd454d4423643ce80e2a9ac94fa54ca49f",
     "dc2a4459e7369633a52b1bf277839a00201009a3efbf3ecb69bea2186c26b58909351fc9ac90b3ecfdfbc7c66431e0303dca179c138ac17ad9bef1177331a704"),
]


class TestEd25519(unittest.TestCase):
    def test_vetores_rfc8032(self):
        for sk, pk, m, sig in RFC8032:
            sk, pk, m, sig = (bytes.fromhex(x) for x in (sk, pk, m, sig))
            self.assertEqual(ed.publica(sk), pk)
            self.assertEqual(ed.assinar(sk, m), sig)
            self.assertTrue(ed.verificar(pk, m, sig))

    def test_adulteracoes_recusadas(self):
        sk, pk, m, sig = (bytes.fromhex(x) for x in RFC8032[1])
        self.assertFalse(ed.verificar(pk, m + b"x", sig))                      # mensagem
        self.assertFalse(ed.verificar(pk, m, sig[:-1] + bytes([sig[-1] ^ 1])))  # assinatura
        outro = ed.publica(bytes.fromhex(RFC8032[0][0]))
        self.assertFalse(ed.verificar(outro, m, sig))                          # chave errada
        self.assertFalse(ed.verificar(pk[:31], m, sig))                        # tamanho
        self.assertFalse(ed.verificar(pk, m, "texto"))                         # tipo errado não derruba

    def test_maleabilidade_s_mais_L(self):
        """S' = S + L também satisfaz a equação; uma verificação frouxa aceitaria (assinatura maleável)."""
        sk, pk, m, sig = (bytes.fromhex(x) for x in RFC8032[1])
        S = int.from_bytes(sig[32:], "little") + ed.L
        self.assertLess(S, 2 ** 256)
        self.assertFalse(ed.verificar(pk, m, sig[:32] + S.to_bytes(32, "little")))

    def test_chave_de_ordem_pequena_recusada(self):
        """A = identidade (ordem 1): qualquer R=[S]B 'verificaria' sem a checagem de ordem pequena."""
        ident = (1).to_bytes(32, "little")  # y=1, x=0
        r = 12345
        R = ed._comprimir(ed._mult(r, ed._G))
        forjada = R + r.to_bytes(32, "little")
        self.assertFalse(ed.verificar(ident, b"aprovar tudo", forjada))

    def test_ponto_nao_canonico_recusado(self):
        y = ed.p + 1  # codifica o mesmo y=1 de forma não canônica
        self.assertIsNone(ed._descomprimir(y.to_bytes(32, "little")))

    def test_ida_e_volta(self):
        sk = ed.gerar_privada()
        self.assertTrue(ed.verificar(ed.publica(sk), b"ola", ed.assinar(sk, b"ola")))


if __name__ == "__main__":
    unittest.main()
