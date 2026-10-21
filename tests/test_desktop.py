import asyncio
import contextlib
import io
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
            ambiente = {**os.environ, "NETSTAT_PASTA_DADOS": pasta}
            resultado = subprocess.run(
                [sys.executable, "-c", codigo], cwd=desktop.RAIZ, env=ambiente,
                capture_output=True, text=True, timeout=30,
            )
        self.assertEqual(resultado.returncode, 0, resultado.stderr)


if __name__ == "__main__":
    unittest.main()
