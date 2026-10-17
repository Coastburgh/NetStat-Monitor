import contextlib
import io
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from analise.estatisticas import carregar_medicoes
from coletor.controle import ControladorColeta, configuracao_padrao
from coletor.ping_collector import PingCollector


class ControleTest(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory()
        self.pasta = self.temporario.name
        self.addCleanup(self.temporario.cleanup)
        self.controle = ControladorColeta()
        self.addCleanup(self.controle.parar)

    def test_configuracao_e_copiada_e_pode_ser_redefinida(self):
        self.controle.atualizar_configuracao({"wan": "8.8.8.8", "intervalo": 9})
        copia = self.controle.ler_configuracao()
        copia["wan"] = "outro"
        self.assertEqual(self.controle.ler_configuracao()["wan"], "8.8.8.8")
        self.controle.atualizar_configuracao(configuracao_padrao())
        self.assertEqual(self.controle.ler_configuracao(), configuracao_padrao())

    def test_inicio_parada_reinicio_e_callbacks_por_destino(self):
        recebidas = {camada: threading.Event() for camada in ["lan", "wan"]}
        from armazenamento.armazenamento import ArmazenamentoCSV
        salvar = ArmazenamentoCSV.salvar_medicao

        def gravar(armazenamento, medicao):
            salvar(armazenamento, medicao)
            recebidas[Path(armazenamento.caminho_arquivo).name.split("_")[0]].set()

        with patch("coletor.ping_collector.subprocess.run", return_value=SimpleNamespace(stdout="time=10ms")), patch.object(ArmazenamentoCSV, "salvar_medicao", gravar):
            self.assertTrue(self.controle.iniciar({"lan": "192.168.1.1", "wan": "8.8.8.8"}, "WiFi", 30, self.pasta))
            self.assertTrue(all(evento.wait(2) for evento in recebidas.values()))
            self.assertEqual(self.controle.camadas_ativas(), ["lan", "wan"])
            self.assertFalse(self.controle.iniciar({"wan": "1.1.1.1"}, "WiFi", 5, self.pasta))
            self.controle.atualizar_configuracao({"wan": "alterado"})
            self.assertEqual(self.controle.ler_configuracao()["wan"], "")
            self.assertTrue(self.controle.parar())
            self.assertEqual(self.controle.camadas_ativas(), [])
            self.assertTrue(self.controle.iniciar({"wan": "8.8.8.8"}, "WiFi", 30, self.pasta))
            self.assertTrue(self.controle.parar())
        for camada, host in [("lan", "192.168.1.1"), ("wan", "8.8.8.8")]:
            df = carregar_medicoes(Path(self.pasta) / f"{camada}_{host}_wifi.csv")
            self.assertTrue((df["host"] == host).all())

    def test_parada_lenta_impede_coleta_sobreposta(self):
        entrou = threading.Event()
        liberar = threading.Event()
        self.addCleanup(liberar.set)

        def medir(coletor):
            entrou.set()
            liberar.wait(3)
            return {"host": coletor.host, "latencia_ms": 10, "jitter_ms": None, "perda_pacotes_pct": 0}

        with patch.object(PingCollector, "coletar_uma_medicao", medir):
            self.controle.iniciar({"wan": "8.8.8.8"}, "wifi", 30, self.pasta)
            self.assertTrue(entrou.wait(2))
            self.assertFalse(self.controle.parar(timeout=0))
            self.assertEqual(self.controle.camadas_ativas(), ["wan"])
            self.assertFalse(self.controle.iniciar({"wan": "8.8.8.8"}, "wifi", 30, self.pasta))
            liberar.set()
            self.assertTrue(self.controle.parar())

    def test_inicios_concorrentes_criam_uma_unica_coleta(self):
        with patch("coletor.ping_collector.subprocess.run", return_value=SimpleNamespace(stdout="time=1ms")):
            resultados = []
            barreira = threading.Barrier(3)

            def iniciar():
                barreira.wait()
                resultados.append(self.controle.iniciar({"wan": "8.8.8.8"}, "wifi", 30, self.pasta))

            threads = [threading.Thread(target=iniciar) for _ in range(2)]
            for thread in threads:
                thread.start()
            barreira.wait()
            for thread in threads:
                thread.join(3)
                self.assertFalse(thread.is_alive())
            self.assertCountEqual(resultados, [True, False])
            self.assertTrue(self.controle.parar())

    def test_validacao_ocorre_antes_de_criar_threads_ou_arquivos(self):
        for hosts, intervalo in [({}, 5), ({"wan": None}, 5), ({"wan": "8.8.8.8"}, None), ({"wan": "8.8.8.8"}, 0), ({"wan": "8.8.8.8"}, float("nan"))]:
            with self.subTest(hosts=hosts, intervalo=intervalo), self.assertRaises(ValueError):
                self.controle.iniciar(hosts, "wifi", intervalo, self.pasta)
        self.assertEqual(list(Path(self.pasta).iterdir()), [])
        self.assertTrue(self.controle.parar())

    def test_falha_de_preparacao_nao_inicia_threads(self):
        with patch("coletor.controle.ArmazenamentoCSV", side_effect=PermissionError), self.assertRaises(OSError):
            self.controle.iniciar({"wan": "8.8.8.8"}, "wifi", 5, self.pasta)
        self.assertEqual(self.controle.camadas_ativas(), [])

    def test_comando_e_locale_por_sistema(self):
        for sistema, comando in [
            ("Windows", ["ping", "-n", "1", "-w", "2000", "8.8.8.8"]),
            ("Linux", ["ping", "-c", "1", "-W", "2", "8.8.8.8"]),
            ("Darwin", ["ping", "-c", "1", "-W", "2000", "8.8.8.8"]),
        ]:
            with self.subTest(sistema=sistema), patch("coletor.ping_collector.platform.system", return_value=sistema), patch("coletor.ping_collector.subprocess.run", return_value=SimpleNamespace(stdout="time=10ms")) as executar:
                coletor = PingCollector("8.8.8.8")
                self.assertEqual(coletor._montar_comando(), comando)
                self.assertEqual(coletor.coletar_uma_medicao()["latencia_ms"], 10)
                ambiente = executar.call_args.kwargs["env"]
                if sistema == "Windows":
                    self.assertIsNone(ambiente)
                else:
                    self.assertEqual(ambiente["LC_ALL"], "C")
                self.assertEqual(executar.call_args.kwargs["timeout"], 4)

    def test_ping_indisponivel_ou_timeout_conta_falha(self):
        for erro in [FileNotFoundError(), subprocess.TimeoutExpired("ping", 4)]:
            with self.subTest(erro=erro), patch("coletor.ping_collector.subprocess.run", side_effect=erro), contextlib.redirect_stdout(io.StringIO()):
                medicao = PingCollector("8.8.8.8").coletar_uma_medicao()
                self.assertIsNone(medicao["latencia_ms"])
                self.assertEqual(medicao["perda_pacotes_pct"], 100)
        self.assertIsNone(PingCollector("8.8.8.8")._extrair_latencia_ms(None))

    def test_evento_sinalizado_nao_coleta(self):
        evento = threading.Event()
        evento.set()
        with patch.object(PingCollector, "coletar_uma_medicao") as medir:
            PingCollector("8.8.8.8").iniciar_coleta_continua(lambda medicao: None, evento)
            medir.assert_not_called()

    def test_falha_de_escrita_encerra_loop_sem_excecao_na_thread(self):
        with patch.object(PingCollector, "coletar_uma_medicao", return_value={}), contextlib.redirect_stdout(io.StringIO()) as saida:
            def falhar(medicao):
                raise OSError("disco indisponível")

            PingCollector("8.8.8.8").iniciar_coleta_continua(falhar)
        self.assertIn("falha ao armazenar", saida.getvalue())


if __name__ == "__main__":
    unittest.main()
