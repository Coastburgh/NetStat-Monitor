"""
armazenamento/armazenamento.py

Módulo responsável por persistir as medições coletadas pelo PingCollector.
"""

import csv
import os
import ipaddress
import re
import sys
from pathlib import Path
from datetime import datetime
from urllib.parse import quote, unquote


CAMPOS = ["timestamp", "host", "latencia_ms", "jitter_ms", "perda_pacotes_pct"]


def obter_pasta_dados() -> str:
    """Resolve o destino no início do processo, sem depender da pasta de execução.

    NETSTAT_PASTA_DADOS permite isolar testes ou manter dados portáteis.
    NETSTAT_AMBIENTE=producao seleciona o perfil de uso normal; o padrão
    desenvolvimento evita misturar experimentos com medições reais.
    """
    personalizada = os.environ.get("NETSTAT_PASTA_DADOS", "").strip()
    if personalizada:
        caminho = Path(personalizada).expanduser()
        if not caminho.is_absolute():
            raise ValueError("NETSTAT_PASTA_DADOS deve ser um caminho absoluto.")
        return str(caminho)

    ambiente = os.environ.get("NETSTAT_AMBIENTE", "").strip() or "desenvolvimento"
    if ambiente not in ("desenvolvimento", "producao"):
        raise ValueError("NETSTAT_AMBIENTE deve ser desenvolvimento ou producao.")
    desenvolvimento = ambiente == "desenvolvimento"
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        if not base.is_absolute():
            base = Path.home() / "AppData" / "Local"
        nome = "NetStat-Dev" if desenvolvimento else "NetStat"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
        nome = "NetStat-Dev" if desenvolvimento else "NetStat"
    else:
        xdg = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
        base = xdg if xdg.is_absolute() else Path.home() / ".local" / "share"
        nome = "netstat-dev" if desenvolvimento else "netstat"
    return str(base / nome / "dados")


PASTA_DADOS = obter_pasta_dados()
PASTA_RELATORIOS = os.path.join(PASTA_DADOS, "relatorios")
PADRAO_NOME_ARQUIVO = re.compile(
    r"^(?P<camada>lan|man|wan)_(?P<host>.+)_(?P<sessao>wifi|ethernet)\.csv$"
)
ROTULOS_CAMADA = {"lan": "LAN (Gateway)", "man": "MAN (Provedor)", "wan": "WAN (Destino)"}
ROTULOS_SESSAO = {"wifi": "Wi-Fi", "ethernet": "Ethernet"}


def listar_arquivos(pasta: str, extensao: str, decrescente: bool = False) -> list[str]:
    """Lista apenas arquivos, tolerando pastas ainda não criadas ou inacessíveis."""
    try:
        with os.scandir(pasta) as entradas:
            return sorted(
                (e.name for e in entradas if e.is_file() and e.name.endswith(extensao)),
                reverse=decrescente,
            )
    except OSError:
        return []


def excluir_arquivo_dados(nome_arquivo: str, extensao: str) -> None:
    """Exclui somente CSVs de dados ou relatórios Markdown das pastas previstas."""
    pastas_permitidas = {".csv": PASTA_DADOS, ".md": PASTA_RELATORIOS}
    pasta = pastas_permitidas.get(extensao)
    if (
        pasta is None
        or not isinstance(nome_arquivo, str)
        or not nome_arquivo.endswith(extensao)
        or nome_arquivo in ("", ".", "..")
        or "/" in nome_arquivo
        or "\\" in nome_arquivo
        or os.path.isabs(nome_arquivo)
    ):
        raise ValueError("Arquivo inválido para exclusão.")

    caminho = os.path.join(pasta, nome_arquivo)
    if not os.path.isfile(caminho):
        if not os.path.exists(caminho):
            raise FileNotFoundError(caminho)
        raise ValueError("O caminho informado não é um arquivo.")
    os.remove(caminho)


def normalizar_tipo_conexao(tipo: str) -> str:
    sessao = (tipo or "").lower().replace("-", "")
    if sessao not in ROTULOS_SESSAO:
        raise ValueError("Selecione WiFi ou Ethernet como tipo de conexão.")
    return sessao


def validar_host(host: str) -> str:
    """Aceita IPs e nomes de host sem permitir opções de comando ou caminhos."""
    host = (host or "").strip()
    if not host:
        raise ValueError("Informe ao menos um host para a coleta.")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if len(host) > 253 or not all(
            re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9_-]{0,61}[A-Za-z0-9])?", parte)
            for parte in host.rstrip(".").split(".")
        ):
            raise ValueError(f"Host inválido: {host}") from None
    return host


def caminho_coleta(camada: str, host: str, tipo: str, pasta: str | None = None) -> str:
    if camada not in ROTULOS_CAMADA:
        raise ValueError("Camada de rede inválida.")
    # Codificação reversível mantém IPv6 utilizável em nomes de arquivo no Windows.
    endereco = quote(validar_host(host), safe=".-")
    return os.path.join(PASTA_DADOS if pasta is None else pasta, f"{camada}_{endereco}_{normalizar_tipo_conexao(tipo)}.csv")


def extrair_metadados_nome_arquivo(nome_arquivo: str) -> dict:
    """Interpreta o formato da coleta e mantém o fallback para arquivos renomeados."""
    correspondencia = PADRAO_NOME_ARQUIVO.fullmatch(nome_arquivo)
    if correspondencia:
        return {
            "camada": ROTULOS_CAMADA[correspondencia.group("camada")],
            "host": unquote(correspondencia.group("host")),
            "sessao": ROTULOS_SESSAO[correspondencia.group("sessao")],
        }
    return {"camada": "Camada não identificada", "host": nome_arquivo, "sessao": "—"}


class ArmazenamentoCSV:
    """Salva cada medição como uma nova linha em um arquivo CSV."""

    def __init__(self, caminho_arquivo: str | None = None):
        self.caminho_arquivo = os.path.join(PASTA_DADOS, "medicoes.csv") if caminho_arquivo is None else caminho_arquivo
        self._garantir_diretorio()
        self._garantir_cabecalho()

    def _garantir_diretorio(self):
        pasta = os.path.dirname(self.caminho_arquivo)
        if pasta:
            os.makedirs(pasta, exist_ok=True)

    def _garantir_cabecalho(self):
        """Garante o cabeçalho também em arquivos criados vazios, sem apagar medições."""
        with open(self.caminho_arquivo, mode="a+", newline="", encoding="utf-8") as f:
            if f.tell() == 0:
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
