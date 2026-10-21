import asyncio
import contextlib
import errno
import io
import logging
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import desktop


class Evento(list):
    def __iadd__(self, callback):
        self.append(callback)
        return self


class DesktopTest(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporario.cleanup)
        destino = patch("armazenamento.armazenamento.PASTA_APLICATIVO", self.temporario.name)
        destino.start()
        self.addCleanup(destino.stop)
        self.janela = SimpleNamespace(
            events=SimpleNamespace(closing=Evento(), closed=Evento()), destroy=Mock(),
        )
        self.webview = SimpleNamespace(
            settings={}, create_window=Mock(return_value=self.janela), start=Mock(),
        )
        self.servidor = Mock()
        self.servidor.iniciar.return_value = "http://127.0.0.1:12345"
        self.servidor.encerrar_coleta.return_value = True
        substituicao = patch("desktop.ServidorLocal", return_value=self.servidor)
        substituicao.start()
        self.addCleanup(substituicao.stop)

    def test_janela_usa_servidor_local_downloads_e_webview2(self):
        desktop.executar(self.webview)
        self.webview.create_window.assert_called_once_with(
            "NetStat Monitor", "http://127.0.0.1:12345", width=1280, height=800,
        )
        self.assertTrue(self.webview.settings["ALLOW_DOWNLOADS"])
        self.assertEqual(self.webview.start.call_args.kwargs["gui"], "edgechromium")
        self.servidor.parar.assert_called_once()

    def test_fechar_aguarda_coleta_antes_de_parar_servidor(self):
        desktop.executar(self.webview)
        self.assertTrue(self.janela.events.closing[0]())
        self.servidor.encerrar_coleta.assert_called_once()
        self.servidor.solicitar_parada.assert_called_once()

    def test_coleta_lenta_impede_fechamento_da_janela(self):
        self.servidor.encerrar_coleta.return_value = False
        desktop.executar(self.webview)
        self.assertFalse(self.janela.events.closing[0]())
        self.servidor.solicitar_parada.assert_not_called()

    def test_parada_pelo_painel_fecha_a_janela(self):
        desktop.executar(self.webview)
        acompanhar = self.webview.start.call_args.args[0]
        acompanhar()
        self.servidor.aguardar_parada.assert_called_once()
        self.janela.destroy.assert_called_once()

    def test_janela_ja_fechada_nao_e_destruida_novamente(self):
        desktop.executar(self.webview)
        self.janela.events.closed[0]()
        self.webview.start.call_args.args[0]()
        self.janela.destroy.assert_not_called()

    def test_falhas_de_servidor_ou_gui_liberam_recursos_e_restauram_diretorio(self):
        anterior = Path.cwd()
        for origem in (self.servidor.iniciar, self.webview.start):
            with self.subTest(origem=origem):
                origem.side_effect = RuntimeError("falha simulada")
                with tempfile.TemporaryDirectory() as pasta:
                    os.chdir(pasta)
                    try:
                        with self.assertRaises(RuntimeError):
                            desktop.executar(self.webview)
                        self.assertEqual(Path.cwd(), Path(pasta))
                    finally:
                        os.chdir(anterior)
                origem.side_effect = None
        self.assertEqual(self.servidor.parar.call_count, 2)

    def test_main_linux_e_macos_nao_exigem_pywebview(self):
        for plataforma in ("linux", "darwin"):
            with self.subTest(plataforma=plataforma), patch("sys.platform", plataforma), patch.dict(sys.modules, {"webview": None}), contextlib.redirect_stderr(io.StringIO()) as saida:
                self.assertEqual(desktop.main(), 1)
                self.assertIn("python -m streamlit run app.py", saida.getvalue())

    def test_main_windows_sem_dependencia_orienta_instalacao(self):
        with patch("sys.platform", "win32"), patch.dict(sys.modules, {"webview": None}), contextlib.redirect_stderr(io.StringIO()) as saida:
            self.assertEqual(desktop.main(), 1)
        self.assertIn("requirements-desktop.txt", saida.getvalue())

    def test_main_reporta_falha_da_interface_sem_traceback(self):
        with patch("sys.platform", "win32"), patch.dict(sys.modules, {"webview": self.webview}), patch("desktop.executar", side_effect=RuntimeError("WebView2 indisponível")), contextlib.redirect_stderr(io.StringIO()) as saida:
            self.assertEqual(desktop.main(), 1)
        self.assertIn("WebView2 indisponível", saida.getvalue())
        log = Path(self.temporario.name) / "logs" / "netstat.log"
        self.assertIn("WebView2 indisponível", log.read_text(encoding="utf-8"))

    def test_segunda_instancia_nao_inicia_interface_nem_abre_log(self):
        pasta = Path(self.temporario.name)
        with desktop.instancia_unica(pasta), patch("sys.platform", "win32"), patch("desktop._executar_interface") as executar, contextlib.redirect_stderr(io.StringIO()) as saida:
            self.assertEqual(desktop.main(), 0)
        executar.assert_not_called()
        self.assertIn("já está em execução", saida.getvalue())
        self.assertFalse((pasta / "logs").exists())

    def test_falha_ao_abrir_log_e_informada_e_libera_trava(self):
        with patch("sys.platform", "win32"), patch("desktop.RotatingFileHandler", side_effect=PermissionError("sem acesso")), contextlib.redirect_stderr(io.StringIO()) as saida:
            self.assertEqual(desktop.main(), 1)
        self.assertIn("sem acesso", saida.getvalue())
        with desktop.instancia_unica(Path(self.temporario.name)) as adquirida:
            self.assertTrue(adquirida)

    def test_diretorio_invalido_nao_produz_excecao_na_inicializacao(self):
        arquivo = Path(self.temporario.name) / "arquivo"
        arquivo.touch()
        with patch("sys.platform", "win32"), patch("armazenamento.armazenamento.PASTA_APLICATIVO", str(arquivo)), contextlib.redirect_stderr(io.StringIO()) as saida:
            self.assertEqual(desktop.main(), 1)
        self.assertIn("Não foi possível preparar", saida.getvalue())


class InstanciaELogsTest(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporario.cleanup)
        self.pasta = Path(self.temporario.name)

    def executar_processo(self, codigo):
        return subprocess.run(
            [sys.executable, "-c", codigo, str(self.pasta)], cwd=desktop.RAIZ,
            capture_output=True, text=True, timeout=15,
        )

    def test_trava_bloqueia_outro_processo_e_libera_apos_saida(self):
        codigo = """
import sys
from pathlib import Path
from desktop import instancia_unica
with instancia_unica(Path(sys.argv[1])) as adquirida:
    print(adquirida)
"""
        with desktop.instancia_unica(self.pasta) as adquirida:
            self.assertTrue(adquirida)
            segundo = self.executar_processo(codigo)
            self.assertEqual(segundo.returncode, 0, segundo.stderr)
            self.assertEqual(segundo.stdout.strip(), "False")
        terceiro = self.executar_processo(codigo)
        self.assertEqual(terceiro.returncode, 0, terceiro.stderr)
        self.assertEqual(terceiro.stdout.strip(), "True")

    def test_queda_do_processo_nao_deixa_trava_obsoleta(self):
        codigo = """
import os
import sys
from pathlib import Path
from desktop import instancia_unica
with instancia_unica(Path(sys.argv[1])) as adquirida:
    assert adquirida
    os._exit(0)
"""
        resultado = self.executar_processo(codigo)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertTrue((self.pasta / ".desktop.lock").exists())
        with desktop.instancia_unica(self.pasta) as adquirida:
            self.assertTrue(adquirida)

    def test_perfis_independentes_e_liberacao_apos_excecao(self):
        with self.assertRaises(ValueError):
            with desktop.instancia_unica(self.pasta) as primeira, desktop.instancia_unica(self.pasta / "outro") as segunda:
                self.assertTrue(primeira and segunda)
                raise ValueError("falha simulada")
        with desktop.instancia_unica(self.pasta) as adquirida:
            self.assertTrue(adquirida)

    def test_erro_de_disco_nao_e_confundido_com_instancia_existente(self):
        with patch("desktop._travar_arquivo", side_effect=OSError(errno.ENOSPC, "disco cheio")):
            with self.assertRaises(OSError):
                with desktop.instancia_unica(self.pasta):
                    self.fail("A trava não deveria ter sido adquirida.")

    def test_operacoes_de_trava_por_plataforma(self):
        arquivo = Mock()
        windows = SimpleNamespace(locking=Mock(), LK_NBLCK=1, LK_UNLCK=2)
        with patch("os.name", "nt"), patch.dict(sys.modules, {"msvcrt": windows}):
            desktop._travar_arquivo(arquivo)
            desktop._travar_arquivo(arquivo, liberar=True)
        self.assertEqual(windows.locking.call_args_list[0].args, (arquivo.fileno(), 1, 1))
        self.assertEqual(windows.locking.call_args_list[1].args, (arquivo.fileno(), 2, 1))
        for plataforma in ("linux", "darwin"):
            posix = SimpleNamespace(flock=Mock(), LOCK_EX=1, LOCK_NB=2, LOCK_UN=4)
            with self.subTest(plataforma=plataforma), patch("os.name", "posix"), patch("sys.platform", plataforma), patch.dict(sys.modules, {"fcntl": posix}):
                desktop._travar_arquivo(arquivo)
                desktop._travar_arquivo(arquivo, liberar=True)
            self.assertEqual(posix.flock.call_args_list[0].args, (arquivo.fileno(), 3))
            self.assertEqual(posix.flock.call_args_list[1].args, (arquivo.fileno(), 4))

    def test_logs_utf8_registram_excecao_sem_ocultar_erro_da_interface(self):
        handlers = list(logging.getLogger().handlers)
        with desktop.registrar_logs(self.pasta) as caminho:
            try:
                raise ValueError("falha de conexão")
            except ValueError as erro:
                self.assertIsNone(desktop.registrar_erro_interface(erro))
        texto = caminho.read_text(encoding="utf-8")
        self.assertIn("ValueError: falha de conexão", texto)
        self.assertEqual(texto.count("Falha na interface Streamlit"), 1)
        self.assertEqual(logging.getLogger().handlers, handlers)

    def test_logs_rotacionam_e_handler_e_removido_apos_excecao(self):
        handlers = list(logging.getLogger().handlers)
        with self.assertRaises(RuntimeError):
            with desktop.registrar_logs(self.pasta) as caminho:
                handler = logging.getLogger().handlers[-1]
                handler.maxBytes = 150
                for _ in range(6):
                    desktop.LOGGER.warning("x" * 80)
                raise RuntimeError("falha simulada")
        self.assertTrue(caminho.is_file())
        self.assertEqual(len(list(caminho.parent.glob("netstat.log*"))), 3)
        self.assertEqual(logging.getLogger().handlers, handlers)

    def test_aviso_sem_console_usa_mensagem_nativa(self):
        with patch("sys.platform", "win32"), patch.object(sys, "stderr", None), patch("ctypes.WinDLL", create=True) as biblioteca:
            desktop.informar("teste")
        biblioteca.return_value.MessageBoxW.assert_called_once_with(None, "teste", "NetStat Monitor", 0x40)

    def test_linux_sem_console_nao_tenta_usar_api_windows(self):
        with patch("sys.platform", "linux"), patch.object(sys, "stderr", None), patch.object(desktop.LOGGER, "error") as registrar:
            desktop.informar("teste")
        registrar.assert_called_once_with("teste")


class ServidorLocalTest(unittest.TestCase):
    def test_inicializador_restaura_importacoes_em_python_isolado(self):
        codigo = """
import importlib.util
import runpy
import sys
from pathlib import Path

raiz = Path(sys.argv[1])
sys.path[:] = [p for p in sys.path if p and Path(p).resolve() != raiz]
runpy.run_path(str(raiz / 'desktop.py'), run_name='desktop_isolado')
assert sys.path[0] == str(raiz)
assert importlib.util.find_spec('paginas').origin == str(raiz / 'paginas' / '__init__.py')
"""
        resultado = subprocess.run(
            [sys.executable, "-I", "-c", codigo, str(desktop.RAIZ)],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(resultado.returncode, 0, resultado.stderr)

    def test_coleta_ausente_ou_lenta(self):
        servidor = desktop.ServidorLocal()
        self.assertTrue(servidor.encerrar_coleta())
        servidor._controlador = Mock()
        servidor._controlador.encerrar.return_value = False
        self.assertFalse(servidor.encerrar_coleta())

    def test_falha_na_thread_e_preservada_e_sinalizada(self):
        servidor = desktop.ServidorLocal()
        servidor._servidor = Mock()
        servidor._servidor.run.side_effect = SystemExit(1)
        servidor._executar()
        self.assertTrue(servidor._finalizado.is_set())
        with self.assertRaises(RuntimeError):
            servidor.parar()

    def test_timeout_de_parada_fecha_socket(self):
        servidor = desktop.ServidorLocal()
        servidor._socket = Mock()
        servidor._servidor = Mock()
        servidor._thread = Mock()
        servidor._thread.is_alive.return_value = True
        with self.assertRaisesRegex(RuntimeError, "prazo"):
            servidor.parar()
        servidor._thread.join.assert_called_once_with(15)
        servidor._socket.close.assert_called_once()
        self.assertTrue(servidor._servidor.should_exit)

    def test_ciclo_de_vida_para_coleta_e_remove_callback_apos_erro(self):
        servidor = desktop.ServidorLocal()
        controlador = Mock()

        async def executar():
            async with servidor._ciclo_vida(None):
                raise ValueError("falha no servidor")

        with patch("paginas.recursos.obter_controlador", return_value=controlador), patch("paginas.recursos.registrar_encerramento_servidor") as registrar:
            with self.assertRaises(ValueError):
                asyncio.run(executar())
        controlador.encerrar.assert_called_once()
        self.assertEqual(registrar.call_args_list[0].args, (servidor.solicitar_parada,))
        self.assertEqual(registrar.call_args_list[-1].args, (None,))

    def test_timeout_de_inicio_e_liberacao_do_socket(self):
        servidor = desktop.ServidorLocal()
        backend = Mock(started=False)
        with patch("socket.socket") as criar_socket, patch("streamlit.App"), patch("uvicorn.Server", return_value=backend), patch("threading.Thread") as criar_thread, patch("time.monotonic", side_effect=[0, 31]), patch.object(servidor._finalizado, "wait", return_value=False):
            criar_thread.return_value.is_alive.return_value = False
            with self.assertRaises(TimeoutError):
                servidor.iniciar()
            servidor.parar()
        criar_socket.return_value.bind.assert_called_once_with(("127.0.0.1", 0))
        criar_socket.return_value.close.assert_called_once()

    def test_servidor_real_responde_e_para_pelo_callback(self):
        codigo = """
import urllib.request
from desktop import ServidorLocal

servidor = ServidorLocal()
try:
    url = servidor.iniciar(timeout=15)
    with urllib.request.urlopen(url + '/_stcore/health', timeout=5) as resposta:
        assert resposta.status == 200
    from paginas.recursos import solicitar_parada_servidor
    solicitar_parada_servidor()
finally:
    servidor.parar()
assert not servidor._thread.is_alive()
"""
        with tempfile.TemporaryDirectory() as pasta:
            ambiente = {**os.environ, "NETSTAT_PASTA_DADOS": str(Path(pasta) / "dados")}
            resultado = subprocess.run(
                [sys.executable, "-c", codigo], cwd=desktop.RAIZ, env=ambiente,
                capture_output=True, text=True, timeout=30,
            )
        self.assertEqual(resultado.returncode, 0, resultado.stderr)


if __name__ == "__main__":
    unittest.main()
