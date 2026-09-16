"""
visualizacao/graficos.py

Módulo responsável por gerar os gráficos de análise das medições coletadas.
Usa Plotly em vez de matplotlib, pela integração nativa e mais simples com
o painel Streamlit previsto no requisito 19 (st.plotly_chart), além de já
oferecer interatividade (zoom, hover com valores exatos) sem esforço extra.

Cobre, até aqui, o requisito funcional:
16. Gerar gráficos de série temporal exibindo a evolução da latência ao
    longo do período de coleta.
"""

import os
import pandas as pd
import plotly.graph_objects as go


def agregar_por_intervalo(df: pd.DataFrame, intervalo: str = "15min") -> pd.DataFrame:
    """
    Agrega as medições por intervalo de tempo (padrão: 1 minuto), calculando
    a média da latência dentro de cada intervalo. Usado apenas para deixar
    o gráfico de série temporal mais legível quando há muitos pontos
    (ex.: uma leitura a cada poucos segundos gera milhares de pontos).

    IMPORTANTE: esta agregação NÃO deve ser usada para detecção de outliers
    ou outras análises estatísticas — calcular a média "esconde" picos
    isolados (um outlier de 100ms dentro de um minuto com outras 11 leituras
    de 15ms viraria uma média de ~22ms, mascarando o outlier). Esta função
    serve apenas para suavizar a exibição visual.
    """
    df_indexado = df.set_index("timestamp")
    df_agregado = df_indexado["latencia_ms"].resample(intervalo).mean().reset_index()
    return df_agregado


def gerar_grafico_serie_temporal(
    df: pd.DataFrame,
    coluna: str = "latencia_ms",
    caminho_saida: str = "dados/graficos/grafico_serie_temporal.html",
    titulo: str = "Latência ao longo do tempo",
    rotulo_eixo_y: str = "Latência (ms)",
    agregacao: str = "15min",
    cor_grafico: str = "#0073ff",
    salvar_arquivo: bool = True
):
    """
    Gera um gráfico de linha interativo mostrando a evolução de uma métrica
    (latência ou jitter) ao longo do tempo. Salva o resultado como um
    arquivo HTML autocontido (abre em qualquer navegador, sem precisar de
    servidor).

    coluna: qual coluna do DataFrame plotar ('latencia_ms' ou 'jitter_ms').
    Não use esta função para 'perda_pacotes_pct' — veja
    gerar_grafico_taxa_perda_pacotes, que trata essa métrica de forma
    diferente (ela é cumulativa por sessão, não um valor pontual comparável).

    agregacao: opcional (ex.: '1min', '5min'). Quando definido, os valores
    são agregados por média nesse intervalo antes de plotar, suavizando a
    linha em conjuntos de dados muito densos. Quando None (padrão), plota
    os dados brutos, ponto a ponto.

    Retorna a figura do Plotly (além de salvar o arquivo), para permitir
    reaproveitá-la diretamente no dashboard Streamlit mais adiante.
    """
    if salvar_arquivo:
        pasta = os.path.dirname(caminho_saida)
        if pasta and not os.path.exists(pasta):
            os.makedirs(pasta)

    if agregacao:
        df_indexado = df.set_index("timestamp")
        df_plot = df_indexado[coluna].resample(agregacao).mean().reset_index()
    else:
        df_plot = df[["timestamp", coluna]]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_plot["timestamp"],
        y=df_plot[coluna],
        mode="lines+markers",
        line=dict(color=cor_grafico, width=1, shape="spline", smoothing=0.8),
        marker=dict(size=4),
        name=rotulo_eixo_y,
        hovertemplate="%{x|%d/%m %H:%M}<br>%{y:.2f}<extra></extra>",
    ))

    subtitulo = f" (média por {agregacao})" if agregacao else " (dados brutos)"
    fig.update_layout(
        title=dict(text=titulo + subtitulo, font=dict(size=18)),
        xaxis_title="Data e hora",
        yaxis_title=rotulo_eixo_y,
        template="plotly_dark",
        hovermode="x unified",
    )

    if salvar_arquivo:
        fig.write_html(caminho_saida)

    return fig


def calcular_taxa_perda_por_janela(df: pd.DataFrame, janela: str = "5min") -> pd.DataFrame:
    """
    Calcula a taxa de perda de pacotes DENTRO de cada janela de tempo
    (ex.: a cada 5 minutos), em vez de usar a coluna 'perda_pacotes_pct'
    do CSV (que é cumulativa desde o início da sessão de coleta, e por
    isso tende a se estabilizar/diluir com o tempo, escondendo picos
    pontuais de instabilidade).

    Retorna um DataFrame com uma linha por janela de tempo, contendo o
    percentual de falhas ocorridas apenas naquela janela específica.
    """
    df_indexado = df.set_index("timestamp")

    total_por_janela = df_indexado["latencia_ms"].resample(janela).count()
    # count() do pandas ignora NaN automaticamente, então isso já dá o
    # número de medições COM resposta em cada janela.
    total_tentativas_por_janela = df_indexado["latencia_ms"].resample(janela).size()
    falhas_por_janela = total_tentativas_por_janela - total_por_janela

    taxa_perda = (falhas_por_janela / total_tentativas_por_janela * 100).round(2)

    return pd.DataFrame({
        "timestamp": taxa_perda.index,
        "perda_pct_na_janela": taxa_perda.values,
    })


def gerar_grafico_taxa_perda_pacotes(
    df: pd.DataFrame,
    janela: str = "5min",
    caminho_saida: str = "dados/graficos/grafico_perda_pacotes.html",
    titulo: str = "Taxa de perda de pacotes ao longo do tempo",
    cor_grafico: str = "#ff1c02",
    salvar_arquivo: bool = True
):
    """
    Gera um gráfico de barras mostrando a taxa de perda de pacotes DENTRO
    de cada janela de tempo (não cumulativa), permitindo identificar picos
    pontuais de instabilidade que ficariam escondidos em uma métrica
    cumulativa desde o início da coleta.
    """
    if salvar_arquivo:
        pasta = os.path.dirname(caminho_saida)
        if pasta and not os.path.exists(pasta):
            os.makedirs(pasta)

    df_taxa = calcular_taxa_perda_por_janela(df, janela)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_taxa["timestamp"],
        y=df_taxa["perda_pct_na_janela"],
        marker=dict(color=cor_grafico),
        name="Perda de pacotes",
        hovertemplate="%{x|%d/%m %H:%M}<br>%{y:.2f}%%<extra></extra>",
    ))

    fig.update_layout(
        title=dict(text=f"{titulo} (janelas de {janela})", font=dict(size=18)),
        xaxis_title="Data e hora",
        yaxis_title="Perda de pacotes (%) na janela",
        template="plotly_dark",
        hovermode="x unified",
    )

    if salvar_arquivo:
        fig.write_html(caminho_saida)

    return fig


def calcular_perda_pacotes_total(df: pd.DataFrame) -> float:
    """
    Calcula a taxa de perda de pacotes total do arquivo, recalculada
    diretamente a partir dos dados brutos (contagem de falhas / total de
    linhas), em vez de usar a coluna 'perda_pacotes_pct' já calculada.

    Isso é mais robusto que simplesmente pegar o valor da última linha:
    se a coleta foi interrompida e retomada em múltiplas sessões, o
    contador interno do coletor reinicia a cada execução, fazendo a
    coluna 'perda_pacotes_pct' refletir apenas a última sessão, não o
    arquivo inteiro. Este cálculo independe de quantas sessões geraram
    o arquivo.
    """
    total_linhas = len(df)
    total_falhas = df["latencia_ms"].isna().sum()

    if total_linhas == 0:
        return 0.0

    return float(round((total_falhas / total_linhas) * 100, 2))


if __name__ == "__main__":
    # Execução manual para teste rápido: python -m visualizacao.graficos
    from analise.estatisticas import carregar_medicoes
 
    df = carregar_medicoes("dados/medicoes_8_8_8_8_cabo.csv")
 
    gerar_grafico_serie_temporal(
        df,
        coluna="latencia_ms",
        caminho_saida="dados/graficos/grafico_latencia_cabo.html",
        titulo="Latência ao longo do tempo — 8.8.8.8 (Ethernet)",
        rotulo_eixo_y="Latência (ms)",
        agregacao="15min",
        cor_grafico="#0073ff"
    )
    print("Gráfico de latência salvo em: dados/graficos/grafico_latencia_cabo.html")
 
    gerar_grafico_serie_temporal(
        df,
        coluna="jitter_ms",
        caminho_saida="dados/graficos/grafico_jitter_cabo.html",
        titulo="Jitter ao longo do tempo — 8.8.8.8 (Ethernet)",
        rotulo_eixo_y="Jitter (ms)",
        agregacao="15min",
        cor_grafico="#ffd900"
    )
    print("Gráfico de jitter salvo em: dados/graficos/grafico_jitter_cabo.html")
 
    gerar_grafico_taxa_perda_pacotes(
        df,
        janela="5min",
        caminho_saida="dados/graficos/grafico_perda_pacotes_cabo.html",
        titulo="Taxa de perda de pacotes — 8.8.8.8 (Ethernet)",
    )
    print("Gráfico de perda de pacotes salvo em: dados/graficos/grafico_perda_pacotes_cabo.html")
 
    perda_total = calcular_perda_pacotes_total(df)
    print(f"\nResumo — perda de pacotes total da sessão: {perda_total}%")
 