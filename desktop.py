"""Inicializador Windows: mantém a janela e o servidor local no mesmo processo."""

import asyncio
import errno
import logging
import os
import socket
import sys
import threading
import time
from contextlib import asynccontextmanager, contextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path


RAIZ = Path(__file__).resolve().parent
# O Python embutido pode omitir a raiz do projeto do caminho de importacao.
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
LOGGER = logging.getLogger("netstat.desktop")


def _travar_arquivo(arquivo, liberar: bool = False):
    if os.name == "nt":
        import msvcrt

        arquivo.seek(0)
        msvcrt.locking(arquivo.fileno(), msvcrt.LK_UNLCK if liberar else msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(arquivo.fileno(), fcntl.LOCK_UN if liberar else fcntl.LOCK_EX | fcntl.LOCK_NB)


@contextmanager
def instancia_unica(pasta: Path):
    """Mantém o arquivo aberto para o sistema liberar a trava mesmo após uma queda.

    O arquivo permanece no disco: excluí-lo permitiria travar arquivos distintos
    com o mesmo nome durante uma disputa entre processos.
    """
    pasta.mkdir(parents=True, exist_ok=True)
    with (pasta / ".desktop.lock").open("a+b") as arquivo:
        if os.fstat(arquivo.fileno()).st_size == 0:
            arquivo.write(b"\0")
            arquivo.flush()
        try:
            _travar_arquivo(arquivo)
        except OSError as erro:
            if erro.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                raise
            yield False
            return
        try:
            yield True
        finally:
            _travar_arquivo(arquivo, liberar=True)


@contextmanager
def registrar_logs(pasta: Path):
    """Limita os logs a um arquivo de 1 MiB e duas cópias anteriores por perfil."""
    caminho = pasta / "logs" / "netstat.log"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(caminho, maxBytes=1024 * 1024, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    raiz = logging.getLogger()
    nivel_anterior = LOGGER.level
    LOGGER.setLevel(logging.INFO)
    raiz.addHandler(handler)
    try:
        yield caminho
    finally:
        raiz.removeHandler(handler)
        handler.close()
        LOGGER.setLevel(nivel_anterior)


def informar(mensagem: str):
    """Usa uma mensagem nativa quando o executável não possui console."""
    if sys.stderr is not None:
        print(mensagem, file=sys.stderr)
    elif sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        caixa = ctypes.WinDLL("user32", use_last_error=True).MessageBoxW
        caixa.argtypes = (wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT)
        caixa.restype = ctypes.c_int
        caixa(None, mensagem, "NetStat Monitor", 0x40)
    else:
        LOGGER.error(mensagem)


def registrar_erro_interface(erro: Exception):
    LOGGER.error("Falha na interface Streamlit", exc_info=(type(erro), erro, erro.__traceback__))


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
        app = st.App(RAIZ / "app.py", lifespan=self._ciclo_vida, on_script_error=registrar_erro_interface)
        configuracao = uvicorn.Config(
            app, host="127.0.0.1", port=porta, access_log=False, log_config=None,
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
        LOGGER.info("Servidor local iniciado na porta %s", porta)
        return f"http://127.0.0.1:{porta}"

    def _executar(self):
        try:
            self._servidor.run(sockets=[self._socket])
        except BaseException as erro:
            # Uvicorn pode encerrar com SystemExit em falhas de inicialização.
            self._falha = erro
            LOGGER.exception("Falha na execução do servidor local")
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
                LOGGER.warning("Fechamento adiado: a coleta ainda está encerrando")
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


def _executar_interface(caminho_log: Path) -> int:
    try:
        import webview
    except ImportError:
        LOGGER.exception("Dependência da interface Windows indisponível")
        informar("Instale a interface Windows: python -m pip install -r requirements-desktop.txt")
        return 1
    try:
        executar(webview)
    except KeyboardInterrupt:
        return 0
    except Exception as erro:
        LOGGER.exception("Falha no aplicativo desktop")
        informar(f"Não foi possível executar o aplicativo desktop: {erro}\nDetalhes em: {caminho_log}")
        return 1
    return 0


def main() -> int:
    if sys.platform != "win32":
        informar("O inicializador desktop atende Windows. Neste sistema, use python -m streamlit run app.py.")
        return 1
    try:
        from armazenamento.armazenamento import PASTA_APLICATIVO

        with instancia_unica(Path(PASTA_APLICATIVO)) as adquirida:
            if not adquirida:
                informar("O NetStat Monitor já está em execução para esta pasta de dados.")
                return 0
            with registrar_logs(Path(PASTA_APLICATIVO)) as caminho_log:
                LOGGER.info("Inicializando aplicativo desktop")
                try:
                    return _executar_interface(caminho_log)
                finally:
                    LOGGER.info("Finalizando aplicativo desktop")
    except (OSError, ValueError) as erro:
        informar(f"Não foi possível preparar os arquivos do aplicativo: {erro}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
