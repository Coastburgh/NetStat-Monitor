"""
paginas/relatorio.py

Página do painel dedicada ao relatório consolidado (req. 20).

A página não gera nada por conta própria: exibe o relatório que foi
gerado na página principal (Monitor) e guardado em st.session_state.
Enquanto não houver relatório gerado, mostra uma orientação em vez de
conteúdo vazio.
"""

import os

import streamlit as st

from analise.relatorio import PASTA_RELATORIOS

st.header("Relatório Consolidado")

# O relatório é gravado em st.session_state pela página principal quando o
# usuário clica em "Gerar relatório consolidado". A chave guarda tanto o
# conteúdo (para preview e download) quanto o caminho do arquivo salvo.
relatorio = st.session_state.get("relatorio_gerado")

if relatorio is None:
    st.info(
        "Nenhum relatório gerado ainda. Volte à página **Monitor** e clique em "
        "**Gerar relatório consolidado** (com a coleta parada)."
    )
else:
    st.caption(
        f"Gerado em {relatorio['data_geracao']} — salvo em `{relatorio['caminho']}`."
    )

    st.download_button(
        "Baixar relatório (.md)",
        data=relatorio["conteudo"],
        file_name=os.path.basename(relatorio["caminho"]),
        mime="text/markdown",
        type="primary",
    )

    st.divider()
    st.subheader("Preview")
    st.markdown(relatorio["conteudo"])
