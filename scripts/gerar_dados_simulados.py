"""
scripts/gerar_dados_simulados.py

UTILITÁRIO DE DESENVOLVIMENTO — NÃO faz parte do sistema NetStat Monitor em si.

Gera arquivos CSV com dados sintéticos, no mesmo formato que o ArmazenamentoCSV
produziria, para permitir desenvolver e testar o módulo de análise estatística
sem precisar esperar dias de coleta real.

IMPORTANTE: os dados gerados aqui são artificiais e servem apenas para
desenvolvimento/teste do código. O relatório final do projeto deve ser
baseado nos dados reais coletados pelo main.py.
"""

import csv
import os
import random
from datetime import datetime, timedelta

CAMPOS = ["timestamp", "host", "latencia_ms", "jitter_ms", "perda_pacotes_pct"]


def gerar_medicoes_simuladas(
    host: str,
    quantidade: int,
    latencia_base_ms: float,
    variacao_ms: float,
    intervalo_entre_medicoes_segundos: int = 5,
    probabilidade_falha: float = 0.02,
    probabilidade_outlier: float = 0.03,
    data_inicio: datetime = None,
):
    """
    Gera uma lista de medições sintéticas com padrões plausíveis:
    - Latência com variação aleatória em torno de uma base.
    - Latência um pouco maior em horários de "pico" simulados (18h-22h).
    - Uma pequena chance de falha (perda de pacote) por medição.
    - Uma pequena chance de outlier (pico de latência bem acima do normal).
    """
    if data_inicio is None:
        data_inicio = datetime.now() - timedelta(days=3)

    medicoes = []
    total_falhas = 0
    ultima_latencia_valida = None
    timestamp_atual = data_inicio

    for i in range(quantidade):
        houve_falha = random.random() < probabilidade_falha

        if houve_falha:
            total_falhas += 1
            latencia_ms = None
            jitter_ms = None
        else:
            # Simula latência mais alta em horário de pico (18h-22h)
            fator_pico = 1.6 if 18 <= timestamp_atual.hour <= 22 else 1.0
            latencia_ms = round(
                max(1.0, random.gauss(latencia_base_ms * fator_pico, variacao_ms)), 2
            )

            # Simula outliers ocasionais (pico anômalo de latência)
            if random.random() < probabilidade_outlier:
                latencia_ms = round(latencia_ms * random.uniform(4, 8), 2)

            jitter_ms = (
                round(abs(latencia_ms - ultima_latencia_valida), 2)
                if ultima_latencia_valida is not None
                else None
            )
            ultima_latencia_valida = latencia_ms

        perda_pacotes_pct = round((total_falhas / (i + 1)) * 100, 2)

        medicoes.append({
            "timestamp": timestamp_atual.isoformat(timespec="seconds"),
            "host": host,
            "latencia_ms": latencia_ms,
            "jitter_ms": jitter_ms,
            "perda_pacotes_pct": perda_pacotes_pct,
        })

        timestamp_atual += timedelta(seconds=intervalo_entre_medicoes_segundos)

    return medicoes


def salvar_csv(medicoes: list, caminho_arquivo: str):
    pasta = os.path.dirname(caminho_arquivo)
    if pasta and not os.path.exists(pasta):
        os.makedirs(pasta)

    with open(caminho_arquivo, mode="w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=CAMPOS)
        escritor.writeheader()
        escritor.writerows(medicoes)


if __name__ == "__main__":
    random.seed(42)  # reprodutibilidade: os mesmos dados "aleatórios" toda vez que rodar

    # Simula 3 dias de coleta a cada 5 segundos = ~51.840 medições por arquivo
    # (reduza QUANTIDADE se quiser gerar mais rápido para testes rápidos)
    QUANTIDADE = 2000  # ajuste conforme necessário

    cenarios = [
        # (host, arquivo, latência base, variação, tipo de conexão)
        ("8.8.8.8", "dados/medicoes_8_8_8_8_wifi.csv", 15.0, 4.0),
        ("8.8.8.8", "dados/medicoes_8_8_8_8_cabo.csv", 9.0, 2.0),  # cabo: mais estável e rápido
        ("1.1.1.1", "dados/medicoes_1_1_1_1_wifi.csv", 12.0, 3.5),
        ("172.20.10.1", "dados/medicoes_172_20_10_1_wifi.csv", 3.0, 1.0),
    ]

    for host, caminho, base, variacao in cenarios:
        medicoes = gerar_medicoes_simuladas(
            host=host,
            quantidade=QUANTIDADE,
            latencia_base_ms=base,
            variacao_ms=variacao,
        )
        salvar_csv(medicoes, caminho)
        print(f"Gerado: {caminho} ({QUANTIDADE} medições simuladas)")

    print("\nATENÇÃO: estes são dados sintéticos, apenas para desenvolvimento e teste.")
    print("Substitua pelos dados reais coletados antes de gerar o relatório final.")
