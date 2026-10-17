"""
analise/gerar_relatorio.py

Módulo responsável pela geração automatizada do relatório consolidado
das medições coletadas (req. 20).

O relatório é gerado em Markdown a partir de todos os arquivos CSV da
pasta de dados, reutilizando as análises já implementadas (estatísticas
descritivas, outliers por IQR, correlação horário x latência e perda de
pacotes), sem duplicar nenhuma lógica de cálculo.
"""

import os
from datetime import datetime

from analise.estatisticas import (
    carregar_medicoes,
    resumir_medicoes,
)
from armazenamento.armazenamento import (
    PASTA_DADOS,
    PASTA_RELATORIOS,
    extrair_metadados_nome_arquivo,
    listar_arquivos,
)


def _secao_arquivo(resultado: dict) -> str:
    """Monta a seção do relatório referente a um único arquivo CSV."""
    metadados = resultado["metadados"]
    linhas = [
        f"## {metadados['camada']} — {metadados['host']} ({metadados['sessao']})",
        "",
        f"Endereço: `{metadados['host']}`",
        "",
    ]

    if resultado["quantidade_medicoes"] == 0:
        linhas.append("_Arquivo sem medições registradas._")
        return "\n".join(linhas) + "\n"

    estatisticas = resultado["estatisticas"]
    perda_total = resultado["perda_total"]
    quantidade_outliers = resultado["quantidade_outliers"]
    correlacao = resultado["correlacao"]

    if estatisticas["quantidade_amostras"] == 0:
        linhas.append("_Arquivo sem medições válidas (todas as leituras falharam)._")
        return "\n".join(linhas) + "\n"

    percentual_outliers = round(quantidade_outliers / estatisticas["quantidade_amostras"] * 100, 2)
    p = estatisticas["percentis_ms"]

    linhas += [
        "| Métrica | Valor |",
        "|---|---|",
        f"| Amostras válidas | {estatisticas['quantidade_amostras']} |",
        f"| Latência média | {estatisticas['media_ms']} ms |",
        f"| Latência mediana | {estatisticas['mediana_ms']} ms |",
        f"| Desvio padrão | {estatisticas['desvio_padrao_ms']} ms |",
        f"| Percentil 90 | {p['p90']} ms |",
        f"| Percentil 99 | {p['p99']} ms |",
        f"| Perda de pacotes total | {perda_total}% |",
        f"| Outliers (IQR) | {quantidade_outliers} ({percentual_outliers}%) |",
        "",
    ]

    if correlacao["coeficiente_r"] is not None:
        significado = "significativa" if correlacao["significativo"] else "não significativa"
        linhas.append(
            f"Correlação horário x latência: r = {correlacao['coeficiente_r']} "
            f"(p-valor = {correlacao['p_valor']}, {significado})."
        )
    else:
        linhas.append(
            "Correlação horário x latência: dados insuficientes "
            "(sem variação suficiente de horário ou latência nas medições)."
        )

    return "\n".join(linhas) + "\n"


def _secao_comparativa(resultados: list[dict]) -> str:
    """
    Monta a tabela comparativa final, resumindo todos os arquivos em uma
    única visão — base para a comparação entre camadas e entre Wi-Fi e
    Ethernet prevista no escopo do projeto.
    """
    linhas = [
        "## Comparação geral",
        "",
        "| Host | Conexão | Camada | Média (ms) | Desvio padrão (ms) | Perda total (%) | Outliers (%) |",
        "|---|---|---|---|---|---|---|",
    ]

    for resultado in resultados:
        if resultado["estatisticas"]["quantidade_amostras"] == 0:
            linhas.append(
                f"| `{resultado['metadados']['host']}` | {resultado['metadados']['sessao']} "
                f"| {resultado['metadados']['camada']} | — | — | — | — |"
            )
            continue

        estatisticas = resultado["estatisticas"]
        percentual_outliers = round(
            resultado["quantidade_outliers"] / estatisticas["quantidade_amostras"] * 100, 2
        )
        linhas.append(
            f"| `{resultado['metadados']['host']}` | {resultado['metadados']['sessao']} "
            f"| {resultado['metadados']['camada']} | {estatisticas['media_ms']} "
            f"| {estatisticas['desvio_padrao_ms']} | {resultado['perda_total']} "
            f"| {percentual_outliers} |"
        )

    return "\n".join(linhas) + "\n"


def gerar_relatorio_consolidado(pasta_dados: str = PASTA_DADOS) -> str:
    """
    Gera o relatório consolidado em Markdown a partir de todos os CSVs da
    pasta de dados, ordenados por nome de arquivo.

    Arquivos vazios, sem medições válidas ou fora do padrão de nomeação
    não interrompem a geração: entram no relatório com uma nota apropriada.
    """
    arquivos_csv = listar_arquivos(pasta_dados, ".csv")

    data_geracao = datetime.now().strftime("%d/%m/%Y %H:%M")
    linhas = [
        "# Relatório consolidado — NetStat Monitor",
        "",
        f"Gerado automaticamente em {data_geracao} a partir de "
        f"{len(arquivos_csv)} arquivo(s) de medições.",
        "",
    ]

    if not arquivos_csv:
        linhas.append("_Nenhum arquivo de dados encontrado na pasta de medições._")
        return "\n".join(linhas)

    resultados = []
    for nome_arquivo in arquivos_csv:
        try:
            df = carregar_medicoes(os.path.join(pasta_dados, nome_arquivo))
            resultado = resumir_medicoes(df, detalhado=True)
        except (OSError, ValueError) as erro:
            linhas.append(f"## `{nome_arquivo}`\n\n")
            linhas.append(f"_Não foi possível carregar o arquivo: {erro}_\n")
            continue

        resultado["metadados"] = extrair_metadados_nome_arquivo(nome_arquivo)
        resultados.append(resultado)

        linhas.append(_secao_arquivo(resultado))
        linhas.append("")

    if resultados:
        linhas.append(_secao_comparativa(resultados))

    return "\n".join(linhas)


def salvar_relatorio(conteudo: str, pasta_relatorios: str = PASTA_RELATORIOS) -> str:
    """
    Salva o relatório em Markdown dentro da pasta de relatórios, com nome
    contendo o momento da geração, e retorna o caminho completo do arquivo.
    """
    os.makedirs(pasta_relatorios, exist_ok=True)
    nome_arquivo = f"relatorio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    caminho = os.path.join(pasta_relatorios, nome_arquivo)
    with open(caminho, mode="w", encoding="utf-8") as f:
        f.write(conteudo)
    return caminho


if __name__ == "__main__":
    # Execução manual para teste rápido: python -m analise.gerar_relatorio
    relatorio = gerar_relatorio_consolidado()
    print(relatorio)
    print(f"\n[Salvando cópia em {PASTA_RELATORIOS}]")
    caminho_salvo = salvar_relatorio(relatorio)
    print(f"Relatório salvo em: {caminho_salvo}")
