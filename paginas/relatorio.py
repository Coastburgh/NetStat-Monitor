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

from analise.gerar_relatorio import exportar_relatorio_pdf
from armazenamento.armazenamento import PASTA_RELATORIOS, listar_arquivos

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
arquivos_relatorios = listar_arquivos(PASTA_RELATORIOS, ".md", decrescente=True)

st.sidebar.header("Relatórios salvos")

if not arquivos_relatorios:
    st.sidebar.info("Nenhum relatório salvo ainda.")
    st.info(
        "Nenhum relatório disponível. Clique em **Gerar Relatório** (com a coleta parada)."
    )
else:
    # O nome real identifica a opção mesmo quando dois rótulos têm o mesmo minuto.
    arquivo_selecionado = st.sidebar.selectbox(
        "Relatório gerado em",
        arquivos_relatorios,
        index=0,
        format_func=rotulo_relatorio,
    )
    caminho = os.path.join(PASTA_RELATORIOS, arquivo_selecionado)

    try:
        with open(caminho, mode="r", encoding="utf-8") as f:
            conteudo = f.read()
    except (OSError, UnicodeError) as erro:
        st.warning(f"Não foi possível abrir o relatório: {erro}")
        st.stop()

    try:
        conteudo_pdf = exportar_relatorio_pdf(conteudo)
    except (OSError, ValueError) as erro:
        conteudo_pdf = None
        st.sidebar.warning(f"Não foi possível gerar o PDF: {erro}")

    with st.sidebar.popover("Exportar", type="primary", width="stretch"):
        st.download_button(
            "Markdown (.md)",
            data=conteudo,
            file_name=arquivo_selecionado,
            mime="text/markdown",
            width="stretch",
        )
        if conteudo_pdf is not None:
            st.download_button(
                "PDF (.pdf)",
                data=conteudo_pdf,
                file_name=os.path.splitext(arquivo_selecionado)[0] + ".pdf",
                mime="application/pdf",
                width="stretch",
            )

    st.divider()
    st.markdown(conteudo)
