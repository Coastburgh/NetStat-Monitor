import contextlib
import io
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from coletor import deteccao_rede as rede


class DeteccaoRedeTest(unittest.TestCase):
    def test_gateway_windows_sem_dependencia_de_idioma(self):
        for saida, esperado in [("192.168.1.1\r\n", "192.168.1.1"), ("", None), ("0.0.0.0", None), ("inválido", None)]:
            with self.subTest(saida=saida), patch.object(rede.platform, "system", return_value="Windows"), patch.object(rede.subprocess, "run", return_value=SimpleNamespace(stdout=saida)) as executar:
                self.assertEqual(rede.detectar_gateway(), esperado)
                self.assertIn("Get-NetRoute", executar.call_args.args[0][-1])
                self.assertIn("InterfaceMetric", executar.call_args.args[0][-1])

    def test_gateway_linux_e_fallback_macos(self):
        with patch.object(rede.platform, "system", return_value="Linux"), patch.object(rede.subprocess, "run", return_value=SimpleNamespace(stdout="default via 192.168.1.1 dev wlan0 proto dhcp metric 600\n")) as executar:
            self.assertEqual(rede.detectar_gateway(), "192.168.1.1")
            self.assertEqual(executar.call_args.args[0], ["ip", "route", "show", "default"])
            self.assertEqual(executar.call_args.kwargs["env"]["LC_ALL"], "C")
        # Não se adiciona detecção de gateway/interface nativa ao macOS nesta reescrita.
        with patch.object(rede.platform, "system", return_value="Darwin"), patch.object(rede.subprocess, "run", side_effect=FileNotFoundError), contextlib.redirect_stdout(io.StringIO()):
            self.assertIsNone(rede.detectar_gateway())
            self.assertIsNone(rede.detectar_tipo_conexao())

    def test_tipos_de_interface_windows(self):
        for saida, esperado in [("Native 802.11\r\n", "wifi"), ("802.3", "ethernet"), ("Tunnel", None), ("", None)]:
            with self.subTest(saida=saida), patch.object(rede.platform, "system", return_value="Windows"), patch.object(rede.subprocess, "run", return_value=SimpleNamespace(stdout=saida)):
                self.assertEqual(rede.detectar_tipo_conexao(), esperado)

    def test_tipos_de_interface_linux(self):
        for dispositivo, wifi, esperado in [("wlan0", True, "wifi"), ("enp3s0", False, "ethernet"), ("tun0", False, None), ("wg0", False, None), ("usb0", False, None)]:
            with self.subTest(dispositivo=dispositivo), patch.object(rede.platform, "system", return_value="Linux"), patch.object(rede.subprocess, "run", return_value=SimpleNamespace(stdout=f"default via 192.168.1.1 dev {dispositivo}\n")), patch.object(rede.os.path, "exists", return_value=wifi):
                self.assertEqual(rede.detectar_tipo_conexao(), esperado)

    def test_traceroute_formatos_windows_linux_macos(self):
        for sistema, ferramenta, saida in [
            ("Windows", "tracert", "Rastreando a rota para 8.8.8.8\n  1 <1 ms <1 ms <1 ms 192.168.1.1\n  2 * * * Esgotado o tempo limite\n  3 1 ms 2 ms 2 ms 100.64.0.1\n  4 3 ms 4 ms 4 ms 177.107.178.45\n  5 8 ms 8 ms 8 ms 8.8.8.8\n"),
            ("Windows", "tracert", "Tracing route to 8.8.8.8\n  1 * * * Request timed out.\n  2 3 ms 4 ms 4 ms 177.107.178.45\nTrace complete.\n"),
            ("Linux", "tracepath", " 1?: [LOCALHOST] pmtu 1500\n 1: 192.168.1.1 0.5ms\n 2: no reply\n 3: 100.64.0.1 1.2ms\n 4: 177-107-178-45.brcentral.net.br 3.4ms\n"),
            ("Darwin", "traceroute", "traceroute to 8.8.8.8 (8.8.8.8), 6 hops max\n 1 192.168.1.1 1.1 ms 1.2 ms 1.1 ms\n 2 * * *\n 3 provedor (177.107.178.45) 4.3 ms 4.2 ms 4.4 ms\n"),
        ]:
            with self.subTest(sistema=sistema, saida=saida), patch.object(rede.platform, "system", return_value=sistema), patch.object(rede.subprocess, "run", return_value=SimpleNamespace(stdout=saida)) as executar:
                resultado = rede.detectar_primeiro_host_externo()
                self.assertEqual(resultado, "177.107.178.45")
                self.assertEqual(executar.call_args.args[0][0], ferramenta)
                self.assertEqual(executar.call_args.kwargs["timeout"], 30)

    def test_falhas_de_comandos_nao_impedem_configuracao_manual(self):
        for sistema in ["Windows", "Linux", "Darwin"]:
            for erro in [FileNotFoundError(), subprocess.TimeoutExpired("comando", 30)]:
                with self.subTest(sistema=sistema, erro=erro), patch.object(rede.platform, "system", return_value=sistema), patch.object(rede.subprocess, "run", side_effect=erro), contextlib.redirect_stdout(io.StringIO()):
                    self.assertIsNone(rede.detectar_gateway())
                    self.assertIsNone(rede.detectar_tipo_conexao())
                    self.assertIsNone(rede.detectar_primeiro_host_externo())
        with patch.object(rede, "detectar_gateway", return_value=None), patch.object(rede, "detectar_primeiro_host_externo") as rastrear:
            self.assertEqual(rede.detectar_hosts_camadas(), {"lan_gateway": None, "man_provedor": None, "wan_destino": "8.8.8.8"})
            rastrear.assert_not_called()

    def test_sem_saltos_publicos_e_destino_excluido(self):
        for sistema in ["Windows", "Linux", "Darwin"]:
            for saida in ["", " 1 * * *\n", " 1 192.168.1.1\n 2 100.64.0.1\n", " 1 8.8.8.8\n"]:
                with self.subTest(sistema=sistema, saida=saida), patch.object(rede.platform, "system", return_value=sistema), patch.object(rede.subprocess, "run", return_value=SimpleNamespace(stdout=saida)):
                    self.assertIsNone(rede.detectar_primeiro_host_externo())
        self.assertIsNone(rede._primeiro_salto_publico_tracert(" 1 8.8.8.8\n", "8.8.8.8"))
        for ip in ["100.64.0.1", "192.168.1.1", "999.999.1.1", "", None]:
            with self.subTest(ip=ip):
                self.assertFalse(rede._eh_ip_publico(ip))


if __name__ == "__main__":
    unittest.main()
