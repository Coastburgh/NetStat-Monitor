"""
paginas/relatorio.py

Página do painel dedicada ao relatório consolidado (req. 20).

A página não gera relatórios: lista os arquivos já salvos em
dados/relatorios/ na barra lateral e exibe o selecionado, com preview
e download. Assim, relatórios de sessões anteriores permanecem
acessíveis sem depender de uma nova geração na sessão atual.
"""

import os

import streamlit as st

from analise.relatorio import PASTA_RELATORIOS

st.header("Relatório Consolidado")

# --- Barra lateral: seleção entre os relatórios já salvos em disco ---
arquivos_relatorios = (
    sorted(f for f in os.listdir(PASTA_RELATORIOS) if f.endswith(".md"))
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
    arquivo_selecionado = st.sidebar.selectbox(
        "Arquivo", arquivos_relatorios, index=len(arquivos_relatorios) - 1
    )
    caminho = os.path.join(PASTA_RELATORIOS, arquivo_selecionado)

    with open(caminho, mode="r", encoding="utf-8") as f:
        conteudo = f.read()

    st.caption(f"Arquivo: `{caminho}`")

    st.download_button(
        "Baixar relatório (.md)",
        data=conteudo,
        file_name=arquivo_selecionado,
        mime="text/markdown",
        type="primary",
    )

    st.divider()
    st.subheader("Preview")
    st.markdown(conteudo)
