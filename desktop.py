"""Inicializador Windows: mantém a janela e o servidor local no mesmo processo."""

import asyncio
import os
import socket
import sys
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path


RAIZ = Path(__file__).resolve().parent
# O Python embutido pode omitir a raiz do projeto do caminho de importacao.
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))


class ServidorLocal:
    """Reserva a porta antes de iniciar o servidor, evitando disputa pela porta livre."""

    def __init__(self):
        self._socket = None
        self._servidor = None
        self._thread = None
        self._controlador = None
        self._finalizado = threading.Event()
        self._falha = None

    @asynccontextmanager
    async def _ciclo_vida(self, app):
        # O runtime já existe quando os recursos em cache são inicializados.
        from paginas.recursos import obter_controlador, registrar_encerramento_servidor

        self._controlador = obter_controlador()
        registrar_encerramento_servidor(self.solicitar_parada)
        try:
            yield
        finally:
            try:
                await asyncio.to_thread(self.encerrar_coleta)
            finally:
                registrar_encerramento_servidor(None)

    def iniciar(self, timeout: float = 30.0) -> str:
        import streamlit as st
        import uvicorn

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.bind(("127.0.0.1", 0))
        porta = self._socket.getsockname()[1]
        app = st.App(RAIZ / "app.py", lifespan=self._ciclo_vida)
        configuracao = uvicorn.Config(
            app, host="127.0.0.1", port=porta, access_log=False,
            timeout_graceful_shutdown=5,
            ws_max_size=st.get_option("server.maxMessageSize") * 1024 * 1024,
        )
        self._servidor = uvicorn.Server(configuracao)
        self._thread = threading.Thread(target=self._executar, daemon=True)
        self._thread.start()
        prazo = time.monotonic() + timeout
        while not self._servidor.started:
            if self._finalizado.wait(0.05):
                raise RuntimeError("O servidor local não pôde ser iniciado.") from self._falha
            if time.monotonic() >= prazo:
                raise TimeoutError("O servidor local não iniciou no prazo esperado.")
        return f"http://127.0.0.1:{porta}"

    def _executar(self):
        try:
            self._servidor.run(sockets=[self._socket])
        except BaseException as erro:
            # Uvicorn pode encerrar com SystemExit em falhas de inicialização.
            self._falha = erro
        finally:
            self._finalizado.set()

    def encerrar_coleta(self) -> bool:
        return self._controlador is None or self._controlador.encerrar()

    def solicitar_parada(self):
        if self._servidor is not None:
            self._servidor.should_exit = True

    def aguardar_parada(self):
        self._finalizado.wait()

    def parar(self):
        self.encerrar_coleta()
        self.solicitar_parada()
        if self._thread is not None:
            self._thread.join(15)
        if self._socket is not None:
            self._socket.close()
        if self._thread is not None and self._thread.is_alive():
            raise RuntimeError("O servidor local não encerrou no prazo esperado.")
        if self._falha is not None:
            raise RuntimeError("O servidor local foi interrompido por uma falha.") from self._falha


def executar(webview):
    """Mantém a GUI na thread principal e encerra o servidor ao sair da janela."""
    servidor = ServidorLocal()
    diretorio_anterior = Path.cwd()
    try:
        # A configuração de tema do Streamlit é lida da raiz do projeto.
        os.chdir(RAIZ)
        url = servidor.iniciar()
        webview.settings["ALLOW_DOWNLOADS"] = True
        janela = webview.create_window("NetStat Monitor", url, width=1280, height=800)
        fechada = threading.Event()

        def fechar():
            if not servidor.encerrar_coleta():
                return False
            servidor.solicitar_parada()
            return True

        def acompanhar_servidor():
            servidor.aguardar_parada()
            if not fechada.wait(0.1):
                janela.destroy()

        janela.events.closing += fechar
        janela.events.closed += fechada.set
        webview.start(acompanhar_servidor, gui="edgechromium")
    finally:
        try:
            servidor.parar()
        finally:
            os.chdir(diretorio_anterior)


def main() -> int:
    if sys.platform != "win32":
        print("O inicializador desktop atende Windows. Neste sistema, use python -m streamlit run app.py.", file=sys.stderr)
        return 1
    try:
        import webview
    except ImportError:
        print("Instale a interface Windows: python -m pip install -r requirements-desktop.txt", file=sys.stderr)
        return 1
    try:
        executar(webview)
    except KeyboardInterrupt:
        return 0
    except Exception as erro:
        print(f"Não foi possível executar o aplicativo desktop: {erro}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
