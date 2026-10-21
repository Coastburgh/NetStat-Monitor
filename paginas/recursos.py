"""Recursos compartilhados e cache de leitura usados pelas páginas do painel."""

import os
import atexit
import signal
from collections.abc import Callable

import streamlit as st

from analise.estatisticas import carregar_medicoes, resumir_medicoes
from coletor.controle import ControladorColeta
from armazenamento import armazenamento


CAMPOS_CONFIGURACAO = {
    "lan": "lan_gateway_input",
    "man": "man_provedor_input",
    "wan": "wan_destino_input",
    "tipo_conexao": "tipo_conexao_input",
    "intervalo": "intervalo_input",
}
_encerrar_servidor: Callable[[], None] | None = None


def registrar_encerramento_servidor(acao: Callable[[], None] | None):
    """Permite ao inicializador desktop coordenar a parada sem sinais do console."""
    global _encerrar_servidor
    _encerrar_servidor = acao


def solicitar_parada_servidor():
    if _encerrar_servidor is not None:
        _encerrar_servidor()
    else:
        signal.raise_signal(signal.SIGINT)


# --- Registro de coleta: vive no processo do servidor (não na sessão da aba) ---
# Recarregar ou fechar a aba cria uma nova sessão do Streamlit, mas as threads
# de coleta continuam rodando. Guardá-las em cache_resource permite que a nova
# sessão as reencontre, mostre o estado correto e consiga pará-las.
@st.cache_resource
def obter_controlador() -> ControladorColeta:
    caminho = os.path.join(armazenamento.PASTA_APLICATIVO, "configuracao.json")
    controlador = ControladorColeta(caminho_configuracao=caminho)
    atexit.register(controlador.encerrar)
    return controlador


def inicializar_estado():
    controlador = obter_controlador()
    if controlador.aviso_configuracao:
        st.sidebar.warning(controlador.aviso_configuracao)
    configuracao = controlador.ler_configuracao()
    for campo, chave in CAMPOS_CONFIGURACAO.items():
        # Reenvia os valores ao navegador quando os widgets são remontados.
        st.session_state[chave] = configuracao[campo]
    # Coleta ativa = existe ao menos uma thread viva no registro.
    st.session_state.coleta_ativa = bool(controlador.camadas_ativas())


def salvar_campo_configuracao(campo: str):
    chave = CAMPOS_CONFIGURACAO[campo]
    obter_controlador().atualizar_configuracao({campo: st.session_state[chave]})


def aplicar_configuracao(configuracao: dict):
    obter_controlador().atualizar_configuracao(configuracao)
    for campo, chave in CAMPOS_CONFIGURACAO.items():
        st.session_state[chave] = configuracao[campo]


def carregar_dados_monitor(caminho: str):
    estado = os.stat(caminho)
    return _carregar_dados_monitor(
        os.path.abspath(caminho), estado.st_mtime_ns, estado.st_ctime_ns, estado.st_size,
    )


@st.cache_data(max_entries=8, show_spinner=False)
def _carregar_dados_monitor(caminho: str, modificacao: int, criacao: int, tamanho: int):
    # A assinatura do arquivo invalida o cache em novas medições ou substituições.
    df = carregar_medicoes(caminho)
    return df, resumir_medicoes(df)
