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
from armazenamento.armazenamento import PASTA_RELATORIOS, excluir_arquivo_dados, listar_arquivos

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


def excluir_relatorio_confirmado(nome_arquivo: str):
    try:
        excluir_arquivo_dados(nome_arquivo, ".md")
    except (OSError, ValueError) as erro:
        st.session_state.erro_exclusao_relatorio = f"Não foi possível excluir o relatório: {erro}"
    else:
        st.session_state.mensagem_exclusao_relatorio = f"Relatório `{nome_arquivo}` excluído."


def selecionar_relatorio_para_exclusao(nome_arquivo: str):
    st.session_state.relatorio_para_exclusao = nome_arquivo


@st.dialog("Excluir relatório", icon=":material/delete:")
def confirmar_exclusao_relatorio(nome_arquivo: str):
    if "mensagem_exclusao_relatorio" in st.session_state:
        st.rerun()
    st.write(f"Relatório selecionado: `{nome_arquivo}`")
    st.warning("Tem certeza? Isso não pode ser desfeito.")
    if "erro_exclusao_relatorio" in st.session_state:
        st.toast(
            st.session_state.pop("erro_exclusao_relatorio"),
            icon=":material/error:",
            duration=5,
        )
    col_cancelar, col_confirmar = st.columns(2)
    if col_cancelar.button("Cancelar", key="cancelar_exclusao_relatorio", width="stretch"):
        st.rerun()
    col_confirmar.button(
        "Sim", key="confirmar_exclusao_relatorio", type="primary", width="stretch",
        on_click=excluir_relatorio_confirmado, args=(nome_arquivo,),
    )


# --- Barra lateral: seleção entre os relatórios já salvos em disco ---
# Ordenação decrescente: o mais recente aparece primeiro na selectbox.
arquivos_relatorios = listar_arquivos(PASTA_RELATORIOS, ".md", decrescente=True)

st.sidebar.header("Relatórios salvos")

if "mensagem_exclusao_relatorio" in st.session_state:
    st.toast(
        st.session_state.pop("mensagem_exclusao_relatorio"),
        icon=":material/check_circle:",
        duration=5,
    )
if "erro_exclusao_relatorio" in st.session_state:
    st.toast(
        st.session_state.pop("erro_exclusao_relatorio"),
        icon=":material/error:",
        duration=5,
    )

if not arquivos_relatorios:
    st.sidebar.info("Nenhum relatório salvo ainda.")
    st.info(
        "Nenhum relatório disponível. Clique em **Gerar Relatório** (com a coleta parada)."
    )
else:
    # O nome real identifica a opção mesmo quando dois rótulos têm o mesmo minuto.
    col_selecao, col_excluir = st.sidebar.columns([8, 2], vertical_alignment="bottom")
    arquivo_selecionado = col_selecao.selectbox(
        "Relatório gerado em",
        arquivos_relatorios,
        index=0,
        format_func=rotulo_relatorio,
    )
    if col_excluir.button(
        "🗑️",
        key="excluir_relatorio",
        help="Excluir relatório selecionado",
        width="stretch",
        on_click=selecionar_relatorio_para_exclusao,
        args=(arquivo_selecionado,),
    ):
        confirmar_exclusao_relatorio(st.session_state.relatorio_para_exclusao)
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
