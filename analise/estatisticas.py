"""
analise/estatisticas.py

Módulo responsável pela análise estatística das medições coletadas.

Cobre os requisitos funcionais:
11. Calcular estatísticas descritivas (média, mediana, desvio padrão e
    percentis) da latência coletada.
12. REMOVIDO
13. Identificar outliers de (picos anômalos de latência) utilizando o método do
    intervalo interquartil (IQR).
14. Permitir a análise de correlação entre o horário do dia e a
    latência observada.
"""

import pandas as pd
from scipy import stats

from armazenamento.armazenamento import CAMPOS


def medicoes_vazias() -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp": pd.Series(dtype="datetime64[ns]"),
        "host": pd.Series(dtype="str"),
        **{campo: pd.Series(dtype="float64") for campo in CAMPOS[2:]},
    })


def carregar_medicoes(caminho_csv: str) -> pd.DataFrame:
    """
    Carrega um arquivo CSV de medições e retorna um DataFrame do pandas.
    A coluna 'timestamp' já é convertida para datetime, e linhas onde a
    latência é vazia (falhas de ping) são mantidas — a decisão de descartá-las
    ou não fica a cargo de cada análise específica, não do carregamento em si.
    """
    try:
        df = pd.read_csv(caminho_csv)
    except pd.errors.EmptyDataError:
        return medicoes_vazias()
    ausentes = set(CAMPOS) - set(df.columns)
    if ausentes:
        raise ValueError(f"Colunas ausentes no CSV: {', '.join(sorted(ausentes))}")
    df["timestamp"] = pd.to_datetime(df["timestamp"], format="mixed", errors="raise")
    if df["timestamp"].isna().any():
        raise ValueError("O CSV contém medições sem timestamp.")
    for campo in CAMPOS[2:]:
        df[campo] = pd.to_numeric(df[campo], errors="raise")
    # A última leitura e as linhas dos gráficos devem seguir a ordem cronológica.
    if not df["timestamp"].is_monotonic_increasing:
        df = df.sort_values("timestamp", kind="stable").reset_index(drop=True)
    return df


def calcular_estatisticas_descritivas(df: pd.DataFrame) -> dict:
    """
    Calcula estatísticas descritivas da latência: média, mediana, desvio
    padrão e os percentis 25, 50, 75, 90 e 99.

    Medições sem resposta (latencia_ms vazia) são ignoradas aqui, já que
    não fazem sentido em cálculos de tendência central — elas já são
    contabilizadas separadamente na coluna perda_pacotes_pct.
    """
    latencias_validas = (
        df["latencia_ms"].dropna()
        if df is not None and "latencia_ms" in df
        else pd.Series(dtype="float64")
    )

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
        "desvio_padrao_ms": float(round(latencias_validas.std(), 2)) if len(latencias_validas) > 1 else None,
        "percentis_ms": {
            "p25": float(round(percentis[0.25], 2)),
            "p50": float(round(percentis[0.50], 2)),
            "p75": float(round(percentis[0.75], 2)),
            "p90": float(round(percentis[0.90], 2)),
            "p99": float(round(percentis[0.99], 2)),
        },
    }


def detectar_outliers_iqr(df: pd.DataFrame, multiplicador: float = 1.5, coluna: str = "latencia_ms") -> pd.DataFrame:
    """
    Identifica outliers de latência pelo método do intervalo interquartil (IQR).

    Um valor é considerado outlier quando está abaixo de Q1 - multiplicador*IQR
    ou acima de Q3 + multiplicador*IQR. O multiplicador padrão (1.5) é o valor
    convencional, o mesmo usado, por exemplo, nos "bigodes" de um boxplot.

    coluna: qual coluna analisar ('latencia_ms' ou 'jitter_ms'), permitindo
    destacar outliers também no gráfico de jitter, não só no de latência.

    Retorna um DataFrame apenas com as linhas identificadas como outliers,
    incluindo as colunas 'limite_inferior' e 'limite_superior' usadas no cálculo,
    para facilitar a conferência/depuração dos resultados.
    """
    if df is None or coluna not in df:
        df = pd.DataFrame(columns=[coluna])
    df_validos = df.dropna(subset=[coluna])

    q1 = df_validos[coluna].quantile(0.25)
    q3 = df_validos[coluna].quantile(0.75)
    iqr = q3 - q1

    limite_inferior = q1 - multiplicador * iqr
    limite_superior = q3 + multiplicador * iqr

    outliers = df_validos[
        (df_validos[coluna] < limite_inferior)
        | (df_validos[coluna] > limite_superior)
    ].copy()
    outliers["limite_inferior"] = round(limite_inferior, 2)
    outliers["limite_superior"] = round(limite_superior, 2)
    return outliers


def calcular_correlacao_horario_latencia(df: pd.DataFrame) -> dict:
    """
    Calcula a correlação de Pearson entre o horário do dia (hora, de 0 a 23,
    extraída do timestamp) e a latência observada.

    Retorna o coeficiente de correlação (r), que varia de -1 a 1, e o
    p-valor associado, que indica se essa correlação é estatisticamente
    significativa (convencionalmente, p < 0.05) ou se pode ter ocorrido
    ao acaso, dado o tamanho da amostra.

    Observação sobre a limitação desse método: a hora do dia é tratada aqui
    como uma variável numérica linear (0, 1, 2, ..., 23), o que ignora sua
    natureza cíclica (23h e 0h são horários adjacentes na realidade, mas
    numericamente distantes). Para os fins deste projeto, essa simplificação
    é aceitável, mas vale mencioná-la como uma limitação conhecida caso o
    resultado pareça contraintuitivo.
    """
    if df is None or not {"timestamp", "latencia_ms"}.issubset(df.columns):
        df = medicoes_vazias()
    df_validos = df.dropna(subset=["latencia_ms", "timestamp"]).copy()
    df_validos["hora_do_dia"] = df_validos["timestamp"].dt.hour

    if df_validos["hora_do_dia"].nunique() < 2 or df_validos["latencia_ms"].nunique() < 2:
        # Horário ou latência constantes não permitem estimar uma correlação.
        return {
            "coeficiente_r": None,
            "p_valor": None,
            "quantidade_amostras": int(len(df_validos)),
            "significativo": None,
        }

    coeficiente_r, p_valor = stats.pearsonr(
        df_validos["hora_do_dia"], df_validos["latencia_ms"]
    )

    return {
        "coeficiente_r": float(round(coeficiente_r, 4)),
        "p_valor": float(round(p_valor, 4)),
        "quantidade_amostras": int(len(df_validos)),
        "significativo": bool(p_valor < 0.05),
    }


def calcular_perda_pacotes_total(df: pd.DataFrame) -> float:
    """Recalcula falhas sobre os dados brutos, independente dos reinícios da coleta."""
    if df is None or df.empty or "latencia_ms" not in df:
        return 0.0
    return float(round(df["latencia_ms"].isna().sum() / len(df) * 100, 2))


def resumir_medicoes(df: pd.DataFrame, detalhado: bool = False) -> dict:
    """Compartilha o resumo sem calcular IQR e correlação quando o painel não os usa."""
    resultado = {
        "quantidade_medicoes": len(df) if df is not None else 0,
        "estatisticas": calcular_estatisticas_descritivas(df),
        "perda_total": calcular_perda_pacotes_total(df),
    }
    if detalhado:
        resultado["quantidade_outliers"] = len(detectar_outliers_iqr(df))
        resultado["correlacao"] = calcular_correlacao_horario_latencia(df)
    return resultado


if __name__ == "__main__":
    # Execução manual para teste rápido: python -m analise.estatisticas
    # Ajuste o caminho abaixo para um arquivo real gerado pela coleta.
    try:
        df = carregar_medicoes("dados/wan_8.8.8.8_wifi.csv")
    except (OSError, ValueError) as erro:
        print(f"Não foi possível carregar as medições: {erro}")
        raise SystemExit(1)

    estatisticas = calcular_estatisticas_descritivas(df)
    print(f"Amostras válidas: {estatisticas['quantidade_amostras']}")
    print(f"Média: {estatisticas['media_ms']} ms")
    print(f"Mediana: {estatisticas['mediana_ms']} ms")
    print(f"Desvio padrão: {estatisticas['desvio_padrao_ms']} ms")
    print(f"Percentis: {estatisticas['percentis_ms']}")

    outliers_iqr = detectar_outliers_iqr(df)
    print(f"Outliers (IQR): {len(outliers_iqr)} de {len(df)} medições")

    correlacao = calcular_correlacao_horario_latencia(df)
    if correlacao["coeficiente_r"] is not None:
        print(f"\nCorrelação horário x latência: r = {correlacao['coeficiente_r']} "
              f"(p-valor = {correlacao['p_valor']}, "
              f"{'significativa' if correlacao['significativo'] else 'não significativa'})")
    else:
        print("\nCorrelação horário x latência: dados insuficientes (sem variação de horário)")