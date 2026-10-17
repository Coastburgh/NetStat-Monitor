"""Controle da coleta compartilhada pelo processo, independente da interface."""

import math
import threading
import time

from armazenamento.armazenamento import ArmazenamentoCSV, PASTA_DADOS, caminho_coleta
from coletor.ping_collector import PingCollector


def configuracao_padrao() -> dict:
    return {
        "lan": "", "man": "", "wan": "", "tipo_conexao": "WiFi",
        "intervalo": 5.0, "automatica": False,
    }


class ControladorColeta:
    """Serializa início/parada e preserva referências até cada thread terminar."""

    def __init__(self):
        self._lock = threading.RLock()
        self._threads = {}
        self._eventos = {}
        self._configuracao = configuracao_padrao()

    def ler_configuracao(self) -> dict:
        with self._lock:
            return self._configuracao.copy()

    def atualizar_configuracao(self, valores: dict):
        with self._lock:
            if not self.camadas_ativas():
                self._configuracao.update(valores)

    def camadas_ativas(self) -> list[str]:
        with self._lock:
            for camada, thread in list(self._threads.items()):
                if not thread.is_alive():
                    del self._threads[camada]
                    del self._eventos[camada]
            return list(self._threads)

    def iniciar(self, hosts: dict, tipo: str, intervalo: float, pasta: str = PASTA_DADOS) -> bool:
        if not hosts:
            raise ValueError("Informe ao menos um host para a coleta.")
        if not isinstance(intervalo, (int, float)) or not math.isfinite(intervalo) or intervalo <= 0:
            raise ValueError("O intervalo de coleta deve ser positivo.")
        caminhos = {
            camada: caminho_coleta(camada, host, tipo, pasta)
            for camada, host in hosts.items()
        }
        with self._lock:
            if self.camadas_ativas():
                return False
            # Prepara todos os arquivos antes de iniciar qualquer thread.
            destinos = {
                camada: ArmazenamentoCSV(caminho) for camada, caminho in caminhos.items()
            }
            try:
                for camada, armazenamento in destinos.items():
                    evento = threading.Event()
                    coletor = PingCollector(host=hosts[camada].strip(), intervalo_segundos=intervalo)
                    thread = threading.Thread(
                        target=coletor.iniciar_coleta_continua,
                        args=(armazenamento.salvar_medicao, evento),
                        daemon=True,
                    )
                    thread.start()
                    self._threads[camada] = thread
                    self._eventos[camada] = evento
            except (OSError, RuntimeError):
                for evento in self._eventos.values():
                    evento.set()
                raise
            return True

    def parar(self, timeout: float = 5.0) -> bool:
        with self._lock:
            for evento in self._eventos.values():
                evento.set()
            threads = list(self._threads.values())
        # Um único prazo limita a espera mesmo quando há vários destinos.
        prazo = time.monotonic() + timeout
        for thread in threads:
            thread.join(max(0.0, prazo - time.monotonic()))
        return not self.camadas_ativas()
