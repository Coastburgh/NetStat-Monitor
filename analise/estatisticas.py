"""
analise/estatisticas.py

Módulo responsável pela análise estatística das medições coletadas.

Cobre, até aqui, o requisito funcional:
11. Calcular estatísticas descritivas (média, mediana, desvio padrão e
    percentis) da latência coletada.
"""

import pandas as pd


def carregar_medicoes(caminho_csv: str) -> pd.DataFrame:
    """
    Carrega um arquivo CSV de medições e retorna um DataFrame do pandas.
    A coluna 'timestamp' já é convertida para datetime, e linhas onde a
    latência é vazia (falhas de ping) são mantidas — a decisão de descartá-las
    ou não fica a cargo de cada análise específica, não do carregamento em si.
    """
    df = pd.read_csv(caminho_csv, parse_dates=["timestamp"])
    return df


def calcular_estatisticas_descritivas(df: pd.DataFrame) -> dict:
    """
    Calcula estatísticas descritivas da latência: média, mediana, desvio
    padrão e os percentis 25, 50, 75, 90 e 99.

    Medições sem resposta (latencia_ms vazia) são ignoradas aqui, já que
    não fazem sentido em cálculos de tendência central — elas já são
    contabilizadas separadamente na coluna perda_pacotes_pct.
    """
    latencias_validas = df["latencia_ms"].dropna()

    if latencias_validas.empty:
        return {
            "quantidade_amostras": 0,
            "media_ms": None,
            "mediana_ms": None,
            "desvio_padrao_ms": None,
            "percentis_ms": {},
        }

    percentis = latencias_validas.quantile([0.25, 0.50, 0.75, 0.90, 0.99])

    return {
        "quantidade_amostras": int(latencias_validas.count()),
        "media_ms": float(round(latencias_validas.mean(), 2)),
        "mediana_ms": float(round(latencias_validas.median(), 2)),
        "desvio_padrao_ms": float(round(latencias_validas.std(), 2)),
        "percentis_ms": {
            "p25": float(round(percentis[0.25], 2)),
            "p50": float(round(percentis[0.50], 2)),
            "p75": float(round(percentis[0.75], 2)),
            "p90": float(round(percentis[0.90], 2)),
            "p99": float(round(percentis[0.99], 2)),
        },
    }


if __name__ == "__main__":
    # Execução manual para teste rápido: python -m analise.estatisticas
    # Ajuste o caminho abaixo para um arquivo real gerado pela coleta.
    df = carregar_medicoes("dados/medicoes_8_8_8_8_wifi.csv")
    estatisticas = calcular_estatisticas_descritivas(df)

    print(f"Amostras válidas: {estatisticas['quantidade_amostras']}")
    print(f"Média: {estatisticas['media_ms']} ms")
    print(f"Mediana: {estatisticas['mediana_ms']} ms")
    print(f"Desvio padrão: {estatisticas['desvio_padrao_ms']} ms")
    print(f"Percentis: {estatisticas['percentis_ms']}")