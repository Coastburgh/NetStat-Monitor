"""
coletor/ping_collector.py

Módulo responsável pela coleta periódica de latência via ping.
Usa o comando "ping" nativo do sistema operacional via subprocess,
evitando a necessidade de privilégios de administrador no Windows
(diferente do uso de sockets ICMP brutos, como faz a biblioteca ping3).

Cobre os requisitos funcionais:
1. Configurar o host de destino.
2. Definir o intervalo entre as coletas.
3. Coletar periodicamente o tempo de resposta (latência).
4. Registrar a taxa de perda de pacotes observada durante cada sessão de coleta.
5. Calcular e registrar o jitter (variação de latência) entre medições consecutivas.
6. Armazenar cada medição coletada em um arquivo CSV.
7. Oferecer suporte alternativo de armazenamento em banco de dados SQLite.
8. Tratar erros de timeout e host inacessível sem interromper a execução contínua da coleta
   (e também outras falhas inesperadas do processo, como permissão negada ou comando
   não encontrado, registrando um aviso no terminal sem derrubar a coleta).
"""

import time
import subprocess
import platform
import re

from armazenamento.armazenamento import ArmazenamentoCSV


class PingCollector:
    def __init__(self, host: str, intervalo_segundos: float = 5.0, timeout_segundos: int = 2):
        """
        host: endereço IP ou domínio do destino (ex.: '8.8.8.8')
        intervalo_segundos: tempo de espera entre uma coleta e outra
        timeout_segundos: tempo máximo de espera por uma resposta do ping (em segundos)
        """
        self.host = host
        self.intervalo_segundos = intervalo_segundos
        self.timeout_segundos = timeout_segundos
        self.sistema = platform.system()  # 'Windows', 'Linux' ou 'Darwin'

        # Estado interno da sessão, usado para calcular perda de pacotes e jitter
        self._total_tentativas = 0
        self._total_falhas = 0
        self._ultima_latencia_valida = None

    def _montar_comando(self) -> list:
        """Monta o comando de ping correto para o sistema operacional atual."""
        if self.sistema == "Windows":
            # -n 1 = uma única tentativa | -w em milissegundos
            return ["ping", "-n", "1", "-w", str(self.timeout_segundos * 1000), self.host]
        else:
            # Linux/Mac: -c 1 = uma única tentativa | -W em segundos
            return ["ping", "-c", "1", "-W", str(self.timeout_segundos), self.host]

    def _extrair_latencia_ms(self, saida_texto: str):
        """
        Extrai o valor da latência a partir da saída de texto do ping,
        cobrindo tanto a saída em português ('tempo=') quanto em inglês ('time=').
        Retorna None se não encontrar (host não respondeu).
        """
        padrao = r"(?:tempo|time)[=<]\s*(\d+(?:\.\d+)?)\s*ms"
        resultado = re.search(padrao, saida_texto, re.IGNORECASE)
        if resultado:
            return round(float(resultado.group(1)), 2)
        return None

    def _calcular_jitter_ms(self, latencia_atual_ms):
        """
        Calcula o jitter como a diferença absoluta entre a latência atual
        e a última latência válida registrada. Retorna None quando não há
        latência anterior para comparar (primeira medição, ou após uma falha).
        """
        if latencia_atual_ms is None or self._ultima_latencia_valida is None:
            return None
        return round(abs(latencia_atual_ms - self._ultima_latencia_valida), 2)

    def coletar_uma_medicao(self) -> dict:
        """
        Executa um único ping e retorna um dicionário com o resultado,
        já incluindo jitter e perda de pacotes acumulada da sessão.
        latencia_ms e jitter_ms vêm como None quando o host não responde
        (ou quando ainda não há dados suficientes para o cálculo).
        """
        comando = self._montar_comando()
        try:
            resultado = subprocess.run(
                comando,
                capture_output=True,
                text=True,
                timeout=self.timeout_segundos + 2,  # margem de segurança para o processo
            )
            latencia_ms = self._extrair_latencia_ms(resultado.stdout)
        except Exception as erro:
            print(f"Aviso: falha ao executar ping para {self.host} — {type(erro).__name__}: {erro}")
            latencia_ms = None

        # Atualiza contadores da sessão (requisito 4 — perda de pacotes)
        self._total_tentativas += 1
        if latencia_ms is None:
            self._total_falhas += 1

        perda_pacotes_pct = round((self._total_falhas / self._total_tentativas) * 100, 2)

        # Calcula o jitter (requisito 5) antes de atualizar a última latência válida
        jitter_ms = self._calcular_jitter_ms(latencia_ms)
        if latencia_ms is not None:
            self._ultima_latencia_valida = latencia_ms

        return {
            "host": self.host,
            "latencia_ms": latencia_ms,
            "jitter_ms": jitter_ms,
            "perda_pacotes_pct": perda_pacotes_pct,
        }

    def iniciar_coleta_continua(self, callback):
        """
        Roda a coleta em loop, chamando callback(medicao) a cada medição.
        callback é o ponto de extensão onde, nas próximas etapas, entrarão
        o armazenamento em CSV/SQLite e o tratamento de erros mais robusto.
        """
        print(f"Iniciando coleta contínua para {self.host} "
              f"(intervalo: {self.intervalo_segundos}s, sistema: {self.sistema})")
        while True:
            medicao = self.coletar_uma_medicao()
            callback(medicao)
            time.sleep(self.intervalo_segundos)


def _exemplo_callback(medicao: dict):
    """Callback simples para teste manual: apenas imprime a medição no terminal."""
    if medicao["latencia_ms"] is not None:
        jitter_texto = f"{medicao['jitter_ms']} ms" if medicao["jitter_ms"] is not None else "N/A"
        print(f"[{medicao['host']}] latência: {medicao['latencia_ms']} ms | "
              f"jitter: {jitter_texto} | perda acumulada: {medicao['perda_pacotes_pct']}%")
    else:
        print(f"[{medicao['host']}] sem resposta (timeout) | "
              f"perda acumulada: {medicao['perda_pacotes_pct']}%")


def _criar_callback_com_armazenamento(armazenamento):
    """
    Retorna um callback que salva a medição no armazenamento escolhido
    E imprime no terminal, para acompanhar a coleta em tempo real.
    """
    def callback(medicao: dict):
        _exemplo_callback(medicao)          # feedback visual no terminal
        armazenamento.salvar_medicao(medicao)  # persistência em CSV/SQLite
    return callback


if __name__ == "__main__":
    # Execução manual para teste rápido: python -m coletor.ping_collector
    coletor = PingCollector(host="8.8.8.8", intervalo_segundos=2.0)
    armazenamento_csv = ArmazenamentoCSV(caminho_arquivo="dados/medicoes.csv")
    callback_com_armazenamento = _criar_callback_com_armazenamento(armazenamento_csv)

    try:
        coletor.iniciar_coleta_continua(callback=callback_com_armazenamento)
    except KeyboardInterrupt:
        print("\nColeta interrompida pelo usuário.")