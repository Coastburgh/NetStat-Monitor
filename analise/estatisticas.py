"""
analise/estatisticas.py

Módulo responsável pela análise estatística das medições coletadas.

Cobre os requisitos funcionais:
11. Calcular estatísticas descritivas (média, mediana, desvio padrão e
    percentis) da latência coletada.
12. Identificar outliers (picos anômalos de latência) utilizando o
    método de z-score.
13. Identificar outliers de forma alternativa utilizando o método do
    intervalo interquartil (IQR).
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


def detectar_outliers_zscore(df: pd.DataFrame, limiar: float = 3.0) -> pd.DataFrame:
    """
    Identifica outliers de latência pelo método de z-score.

    Um valor é considerado outlier quando o módulo do seu z-score
    (distância da média, em desvios padrão) ultrapassa o limiar definido
    (padrão: 3, um valor convencional na literatura estatística).

    Retorna um DataFrame apenas com as linhas identificadas como outliers,
    incluindo uma coluna extra 'zscore' com o valor calculado.
    """
    df_validos = df.dropna(subset=["latencia_ms"]).copy()

    media = df_validos["latencia_ms"].mean()
    desvio_padrao = df_validos["latencia_ms"].std()

    if desvio_padrao == 0 or pd.isna(desvio_padrao):
        # Sem variação nos dados (ou amostra insuficiente): não há outliers a calcular.
        df_validos["zscore"] = 0.0
        return df_validos.iloc[0:0]  # DataFrame vazio, mas com as colunas certas

    df_validos["zscore"] = (df_validos["latencia_ms"] - media) / desvio_padrao

    outliers = df_validos[df_validos["zscore"].abs() > limiar].copy()
    outliers["zscore"] = outliers["zscore"].round(2)
    return outliers


def detectar_outliers_iqr(df: pd.DataFrame, multiplicador: float = 1.5) -> pd.DataFrame:
    """
    Identifica outliers de latência pelo método do intervalo interquartil (IQR).

    Um valor é considerado outlier quando está abaixo de Q1 - multiplicador*IQR
    ou acima de Q3 + multiplicador*IQR. O multiplicador padrão (1.5) é o valor
    convencional, o mesmo usado, por exemplo, nos "bigodes" de um boxplot.

    Retorna um DataFrame apenas com as linhas identificadas como outliers,
    incluindo as colunas 'limite_inferior' e 'limite_superior' usadas no cálculo,
    para facilitar a conferência/depuração dos resultados.
    """
    df_validos = df.dropna(subset=["latencia_ms"]).copy()

    q1 = df_validos["latencia_ms"].quantile(0.25)
    q3 = df_validos["latencia_ms"].quantile(0.75)
    iqr = q3 - q1

    limite_inferior = q1 - multiplicador * iqr
    limite_superior = q3 + multiplicador * iqr

    outliers = df_validos[
        (df_validos["latencia_ms"] < limite_inferior)
        | (df_validos["latencia_ms"] > limite_superior)
    ].copy()
    outliers["limite_inferior"] = round(limite_inferior, 2)
    outliers["limite_superior"] = round(limite_superior, 2)
    return outliers


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

    outliers_z = detectar_outliers_zscore(df)
    print(f"\nOutliers (z-score > 3): {len(outliers_z)} de {len(df)} medições")

    outliers_iqr = detectar_outliers_iqr(df)
    print(f"Outliers (IQR): {len(outliers_iqr)} de {len(df)} medições")