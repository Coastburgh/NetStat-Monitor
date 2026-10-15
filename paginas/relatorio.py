"""
paginas/relatorio.py

Página do painel dedicada ao relatório consolidado (req. 20).

A página não gera relatórios: lista os arquivos já salvos em
dados/relatorios/ na barra lateral e exibe o selecionado, com preview
e download. Assim, relatórios de sessões anteriores permanecem
acessíveis sem depender de uma nova geração na sessão atual.
"""

import os
from datetime import datetime

import streamlit as st

from analise.gerar_relatorio import PASTA_RELATORIOS

st.header("Preview Relatório Consolidado")


def rotulo_relatorio(nome_arquivo: str) -> str:
    """
    Converte o nome do arquivo de relatório (relatorio_YYYYMMDD_HHMMSS.md)
    em um rótulo legível com a data de geração (ex.: 11/10/2026 23:25).
    Nomes fora do padrão são exibidos sem alteração.
    """
    if not nome_arquivo.startswith("relatorio_"):
        return nome_arquivo
    try:
        momento = datetime.strptime(
            nome_arquivo.removeprefix("relatorio_").removesuffix(".md"),
            "%Y%m%d_%H%M%S",
        )
        return momento.strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return nome_arquivo


# --- Barra lateral: seleção entre os relatórios já salvos em disco ---
# Ordenação decrescente: o mais recente aparece primeiro na selectbox.
arquivos_relatorios = (
    sorted(
        (f for f in os.listdir(PASTA_RELATORIOS) if f.endswith(".md")),
        reverse=True,
    )
    if os.path.isdir(PASTA_RELATORIOS)
    else []
)

st.sidebar.header("Relatórios salvos")

if not arquivos_relatorios:
    st.sidebar.info("Nenhum relatório salvo ainda.")
    st.info(
        "Nenhum relatório disponível. Volte à página **Monitor** e clique em "
        "**Gerar relatório consolidado** (com a coleta parada)."
    )
else:
    # A selectbox exibe os rótulos legíveis; o dicionário devolve o nome
    # real do arquivo correspondente à escolha do usuário.
    rotulo_para_arquivo = {rotulo_relatorio(f): f for f in arquivos_relatorios}
    rotulo_selecionado = st.sidebar.selectbox(
        "Relatório gerado em",
        list(rotulo_para_arquivo),
        index=0,
    )
    arquivo_selecionado = rotulo_para_arquivo[rotulo_selecionado]
    caminho = os.path.join(PASTA_RELATORIOS, arquivo_selecionado)

    with open(caminho, mode="r", encoding="utf-8") as f:
        conteudo = f.read()

    st.download_button(
        "Baixar relatório (.md)",
        data=conteudo,
        file_name=arquivo_selecionado,
        mime="text/markdown",
        type="primary",
    )

    st.divider()
    st.markdown(conteudo)
