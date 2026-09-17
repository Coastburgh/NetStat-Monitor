import unittest

from coletor.deteccao_rede import _extrair_ip_v4, _extrair_primeiro_ip_publico


class TestDeteccaoRede(unittest.TestCase):
    def test_extrair_ip_v4_do_ipconfig_windows(self):
        texto = """
        Windows IP Configuration

        Ethernet adapter Ethernet:

           IPv4 Address. . . . . . . . . . . : 192.168.100.15
           Subnet Mask . . . . . . . . . . . : 255.255.255.0
           Default Gateway . . . . . . . . . : 192.168.100.1
           Default Gateway . . . . . . . . . : fe80::1%8
        """
        self.assertEqual(_extrair_ip_v4(texto), "192.168.100.1")

    def test_extrair_primeiro_ip_publico_do_tracert(self):
        texto = """
        Tracing route to dns.google [8.8.8.8]
        over a maximum of 6 hops:

          1    <1 ms    <1 ms    <1 ms  192.168.100.1
          2     3 ms     3 ms     3 ms  187-54-90-1.user3p.v-tal.net.br [187.54.90.1]
          3    15 ms    12 ms    11 ms  100.120.70.19
        """
        self.assertEqual(_extrair_primeiro_ip_publico(texto), "187.54.90.1")


if __name__ == "__main__":
    unittest.main()
