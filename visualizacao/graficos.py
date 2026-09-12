"""
visualizacao/graficos.py

Módulo responsável por gerar os gráficos de análise das medições coletadas.

Cobre, até aqui, o requisito funcional:
16. Gerar gráficos de série temporal exibindo a evolução da latência ao
    longo do período de coleta.
"""

import matplotlib.pyplot as plt
import pandas as pd
import os


def gerar_grafico_serie_temporal(
    df: pd.DataFrame,
    caminho_saida: str = "dados/grafico_serie_temporal.png",
    titulo: str = "Latência ao longo do tempo",
):
    """
    Gera um gráfico de linha mostrando a evolução da latência (em ms) ao
    longo do tempo, a partir das colunas 'timestamp' e 'latencia_ms' do
    DataFrame. Salva o resultado como uma imagem PNG.

    Medições sem resposta (latencia_ms vazia) aparecem naturalmente como
    lacunas na linha, o que já é informativo — mostra visualmente os
    momentos de perda de pacote, sem precisar de tratamento especial.
    """
    pasta = os.path.dirname(caminho_saida)
    if pasta and not os.path.exists(pasta):
        os.makedirs(pasta)

    fig, ax = plt.subplots(figsize=(12, 5))

    ax.plot(
        df["timestamp"],
        df["latencia_ms"],
        color="#0f3460",
        linewidth=1,
        marker="o",
        markersize=2,
        alpha=0.8,
    )

    ax.set_title(titulo, fontsize=14, fontweight="bold")
    ax.set_xlabel("Data e hora")
    ax.set_ylabel("Latência (ms)")
    ax.grid(True, linestyle="--", alpha=0.4)
    fig.autofmt_xdate()  # rotaciona as datas no eixo X para melhor legibilidade

    fig.tight_layout()
    fig.savefig(caminho_saida, dpi=150)
    plt.close(fig)

    return caminho_saida


if __name__ == "__main__":
    # Execução manual para teste rápido: python -m visualizacao.graficos
    from analise.estatisticas import carregar_medicoes

    df = carregar_medicoes("dados/medicoes_8_8_8_8_cabo.csv")
    caminho = gerar_grafico_serie_temporal(
        df,
        caminho_saida="dados/grafico_serie_temporal_cabo.png",
        titulo="Latência ao longo do tempo — 8.8.8.8 (Cabo)",
    )
    print(f"Gráfico salvo em: {caminho}")