"""
armazenamento/armazenamento.py

Módulo responsável por persistir as medições coletadas pelo PingCollector.
"""

import csv
import os
from datetime import datetime


CAMPOS = ["timestamp", "host", "latencia_ms", "jitter_ms", "perda_pacotes_pct"]


class ArmazenamentoCSV:
    """Salva cada medição como uma nova linha em um arquivo CSV."""

    def __init__(self, caminho_arquivo: str = "dados/medicoes.csv"):
        self.caminho_arquivo = caminho_arquivo
        self._garantir_diretorio()
        self._garantir_cabecalho()

    def _garantir_diretorio(self):
        pasta = os.path.dirname(self.caminho_arquivo)
        if pasta and not os.path.exists(pasta):
            os.makedirs(pasta)

    def _garantir_cabecalho(self):
        """Cria o arquivo com o cabeçalho, caso ainda não exista."""
        arquivo_ja_existe = os.path.exists(self.caminho_arquivo)
        if not arquivo_ja_existe:
            with open(self.caminho_arquivo, mode="w", newline="", encoding="utf-8") as f:
                escritor = csv.DictWriter(f, fieldnames=CAMPOS)
                escritor.writeheader()

    def salvar_medicao(self, medicao: dict):
        """Adiciona uma linha ao CSV com a medição e o timestamp atual."""
        linha = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "host": medicao["host"],
            "latencia_ms": medicao["latencia_ms"],
            "jitter_ms": medicao["jitter_ms"],
            "perda_pacotes_pct": medicao["perda_pacotes_pct"],
        }
        with open(self.caminho_arquivo, mode="a", newline="", encoding="utf-8") as f:
            escritor = csv.DictWriter(f, fieldnames=CAMPOS)
            escritor.writerow(linha)
