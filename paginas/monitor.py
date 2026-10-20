"""
paginas/monitor.py

Página Monitor do painel Streamlit.

Permite configurar hosts das camadas LAN, MAN e WAN, iniciar e interromper
coletas em tempo real e visualizar métricas de latência, jitter e perda de
pacotes. Os valores podem ser informados manualmente ou preenchidos
automaticamente por detecção do gateway e do primeiro host externo.
"""

import os

import pandas as pd
import streamlit as st

from coletor.controle import configuracao_padrao
from coletor.deteccao_rede import detectar_hosts_camadas, detectar_tipo_conexao
from armazenamento.armazenamento import PASTA_DADOS, excluir_arquivo_dados, listar_arquivos
from paginas.recursos import (
    aplicar_configuracao,
    carregar_dados_monitor,
    obter_controlador,
    salvar_campo_configuracao,
)
from visualizacao.graficos import (
    gerar_grafico_serie_temporal,
    gerar_grafico_taxa_perda_pacotes,
)

controlador = obter_controlador()
configuracao = controlador.ler_configuracao()


def excluir_csv_confirmado(nome_arquivo: str):
    try:
        excluir_arquivo_dados(nome_arquivo, ".csv")
    except (OSError, ValueError) as erro:
        st.session_state.erro_exclusao_csv = f"Não foi possível excluir o arquivo: {erro}"
    else:
        st.session_state.mensagem_exclusao_csv = f"Arquivo `{nome_arquivo}` excluído."


def selecionar_csv_para_exclusao(nome_arquivo: str):
    st.session_state.csv_para_exclusao = nome_arquivo


@st.dialog("Excluir arquivo", icon=":material/delete:")
def confirmar_exclusao_csv(nome_arquivo: str):
    if "mensagem_exclusao_csv" in st.session_state:
        st.rerun()
    st.write(f"Arquivo selecionado: `{nome_arquivo}`")
    st.warning("Tem certeza? Isso não pode ser desfeito.")
    if "erro_exclusao_csv" in st.session_state:
        st.toast(
            st.session_state.pop("erro_exclusao_csv"),
            icon=":material/error:",
            duration=5,
        )
    col_cancelar, col_confirmar = st.columns(2)
    if col_cancelar.button("Cancelar", key="cancelar_exclusao_csv", width="stretch"):
        st.rerun()
    col_confirmar.button(
        "Sim", key="confirmar_exclusao_csv", type="primary", width="stretch",
        on_click=excluir_csv_confirmado, args=(nome_arquivo,),
    )

# --- Barra lateral: configuração e controle da coleta ---
st.sidebar.header("Configuração da coleta")

# Campos de host por camada de rede (LAN/MAN/WAN), com atalho de detecção automática.
if not configuracao["automatica"]:
    if st.sidebar.button("Configuração Automática", type="primary", key="bold", disabled=st.session_state.coleta_ativa, width='stretch'):
        with st.sidebar.spinner("Configurando a coleta..."):
            detectados = detectar_hosts_camadas()
            tipo_detectado = detectar_tipo_conexao()
        configuracao["lan"] = detectados.get("lan_gateway") or ""
        configuracao["man"] = detectados.get("man_provedor") or ""
        configuracao["wan"] = detectados.get("wan_destino") or "8.8.8.8"
        # A atribuição à chave do selectbox acontece antes do st.rerun(), que
        # reinicia o script antes de o widget ser instanciado novamente — sem
        # isso, o Streamlit levantaria erro de widget já instanciado. Se a
        # detecção falhar (None), o selectbox mantém o valor atual.
        if tipo_detectado:
            configuracao["tipo_conexao"] = "WiFi" if tipo_detectado == "wifi" else "Ethernet"
        configuracao["automatica"] = True
        aplicar_configuracao(configuracao)
        st.rerun()
else:
    if st.sidebar.button("Limpar Configuração", type="primary", key="bold2", disabled=st.session_state.coleta_ativa, width='stretch'):
        aplicar_configuracao(configuracao_padrao())
        st.rerun()

lan_gateway = st.sidebar.text_input(
    "LAN — Gateway", key="lan_gateway_input", disabled=st.session_state.coleta_ativa,
    on_change=salvar_campo_configuracao, args=("lan",),
)
man_provedor = st.sidebar.text_input(
    "MAN — Provedor", key="man_provedor_input", disabled=st.session_state.coleta_ativa,
    on_change=salvar_campo_configuracao, args=("man",),
)
wan_destino = st.sidebar.text_input(
    "WAN — Destino", key="wan_destino_input", disabled=st.session_state.coleta_ativa,
    on_change=salvar_campo_configuracao, args=("wan",),
)

hosts_rotulados = {
    rotulo: valor.strip()
    for rotulo, valor in [
        ("lan", lan_gateway),
        ("man", man_provedor),
        ("wan", wan_destino),
    ]
    if valor.strip()
}

tipo_conexao = st.sidebar.selectbox(
    "Tipo de conexão", ["WiFi", "Ethernet"], key="tipo_conexao_input", disabled=st.session_state.coleta_ativa,
    on_change=salvar_campo_configuracao, args=("tipo_conexao",),
)
intervalo = st.sidebar.number_input(
    "Intervalo de coleta (segundos)", key="intervalo_input", min_value=5.0, step=1.0, disabled=st.session_state.coleta_ativa,
    on_change=salvar_campo_configuracao, args=("intervalo",),
)

iniciar = False
parar = False

if not st.session_state.coleta_ativa:
    iniciar = st.sidebar.button("Iniciar Coleta", type="primary", key="bold1", width='stretch')
else:
    parar = st.sidebar.button("Parar Coleta", type="primary", key="bold1", width='stretch')

if iniciar:
    try:
        controlador.iniciar(hosts_rotulados, tipo_conexao, intervalo)
    except (OSError, ValueError, RuntimeError) as erro:
        st.sidebar.error(f"Não foi possível iniciar a coleta: {erro}")
    else:
        st.rerun()

if parar:
    if controlador.parar():
        st.rerun()
    else:
        st.sidebar.warning("Aguardando o término da medição em andamento.")

if st.session_state.coleta_ativa:
    st.sidebar.info(f"Coletando: {', '.join(controlador.camadas_ativas())}")

# --- Área principal: visualização dos dados já coletados ---
st.header("Monitor de Rede")

if "mensagem_exclusao_csv" in st.session_state:
    st.toast(
        st.session_state.pop("mensagem_exclusao_csv"),
        icon=":material/check_circle:",
        duration=5,
    )
if "erro_exclusao_csv" in st.session_state:
    st.toast(
        st.session_state.pop("erro_exclusao_csv"),
        icon=":material/error:",
        duration=5,
    )

arquivos_disponiveis = listar_arquivos(PASTA_DADOS, ".csv")

if not arquivos_disponiveis:
    st.info("Nenhum arquivo de dados encontrado ainda. Inicie uma coleta ao lado.")
else:
    col_arquivo, col_janela = st.columns(2)

    col_selecao, col_excluir = col_arquivo.columns([8, 1], vertical_alignment="bottom")
    arquivo_selecionado = col_selecao.selectbox("Arquivo para visualizar", arquivos_disponiveis)
    if col_excluir.button(
        "🗑️",
        key="excluir_csv",
        help="Excluir arquivo selecionado",
        disabled=st.session_state.coleta_ativa,
        width="stretch",
        on_click=selecionar_csv_para_exclusao,
        args=(arquivo_selecionado,),
    ):
        confirmar_exclusao_csv(st.session_state.csv_para_exclusao)

    # Seletor de janela temporal dos gráficos (independente da barra lateral);
    # as estatísticas continuam sendo calculadas sobre o arquivo completo.
    opcoes_janela = {
        "Últimos 15 min": pd.Timedelta(minutes=15),
        "Última 1 h": pd.Timedelta(hours=1),
        "Últimas 6 h": pd.Timedelta(hours=6),
        "Últimas 24 h": pd.Timedelta(hours=24),
        "Todos os dados": None,
    }
    opcao_janela = col_janela.selectbox(
        "Janela Temporal", list(opcoes_janela), index=1  # padrão: Última 1 h
    )
    janela = opcoes_janela[opcao_janela]

    # Toggle de destaque de outliers (req. 18): exibido apenas com a coleta
    # parada, para não interferir na visualização em tempo real. Desmarcado
    # por padrão — o usuário ativa manualmente quando quiser.
    if not st.session_state.coleta_ativa:
        destacar_outliers = st.toggle("Destacar outliers (IQR)", value=False)
    else:
        destacar_outliers = False

    # st.fragment permite que só esta parte da tela seja recarregada
    # periodicamente, sem re-executar o script inteiro (o que reiniciaria
    # os widgets da barra lateral). run_every só fica ativo enquanto a
    # coleta estiver rodando; parado, o gráfico fica estático até você
    # trocar de arquivo selecionado.
    @st.fragment(run_every=5 if st.session_state.coleta_ativa else None)
    def mostrar_dados():
        if bool(controlador.camadas_ativas()) != st.session_state.coleta_ativa:
            st.rerun()
        caminho = os.path.join(PASTA_DADOS, arquivo_selecionado)
        try:
            df, resumo = carregar_dados_monitor(caminho)
        except (OSError, ValueError) as erro:
            st.warning(f"Não foi possível carregar as medições: {erro}")
            return

        estatisticas = resumo["estatisticas"]
        perda_total = resumo["perda_total"]

        # Recorta o DataFrame para a janela escolhida; usado apenas nos gráficos
        # e na latência instantânea. Estatísticas seguem sobre o arquivo completo.
        if janela is None or df.empty:
            df_janela = df
        else:
            limite = df["timestamp"].max() - janela
            df_janela = df[df["timestamp"] >= limite]

        # Última leitura válida (instantânea), comparada com a leitura
        # imediatamente anterior (não mais com a média da sessão).
        latencias_validas = df_janela["latencia_ms"].dropna()
        if len(latencias_validas) >= 2:
            latencia_atual = latencias_validas.iloc[-1]
            delta_vs_anterior = latencia_atual - latencias_validas.iloc[-2]
        elif len(latencias_validas) == 1:
            latencia_atual = latencias_validas.iloc[-1]
            delta_vs_anterior = None  # não há leitura anterior para comparar ainda
        else:
            latencia_atual = None
            delta_vs_anterior = None

        c0, c1, c2, c3, c4 = st.columns(5)
        if latencia_atual is not None and st.session_state.coleta_ativa is True:
            c0.metric(
                "Latência Instantânea",
                f"{latencia_atual:.2f} ms",
                delta=f"{delta_vs_anterior:+.2f} ms" if delta_vs_anterior is not None else None,
                delta_color="inverse",  # menor que a leitura anterior = verde (bom); maior = vermelho
            )
        else:
            c0.metric("Última Latência", "—" if latencia_atual is None else f"{latencia_atual:.2f} ms")
        c1.metric("Latência Média", f"{estatisticas['media_ms']} ms")
        c2.metric("Desvio Padrão", f"{estatisticas['desvio_padrao_ms']} ms")
        c3.metric("Perda Total de Pacotes", f"{perda_total}%")
        c4.metric("Amostras Válidas", estatisticas["quantidade_amostras"])

        col_a, col_b = st.columns(2)
        with col_a:
            fig_latencia = gerar_grafico_serie_temporal(
                df_janela, coluna="latencia_ms", titulo="Latência",
                rotulo_eixo_y="Latência (ms)", agregacao="1min",
                salvar_arquivo=False, destacar_outliers=destacar_outliers,
            )
            st.plotly_chart(fig_latencia, width='stretch')
        with col_b:
            fig_jitter = gerar_grafico_serie_temporal(
                df_janela, coluna="jitter_ms", titulo="Jitter",
                rotulo_eixo_y="Jitter (ms)", agregacao="1min",
                salvar_arquivo=False, cor_grafico="#00ABC2",
                destacar_outliers=destacar_outliers,
            )
            st.plotly_chart(fig_jitter, width='stretch')

        fig_perda = gerar_grafico_taxa_perda_pacotes(df_janela, janela="1min", salvar_arquivo=False)
        st.plotly_chart(fig_perda, width='stretch')

        st.caption(f"Gráficos mostram: {opcao_janela} — estatísticas usam o arquivo completo.")

    mostrar_dados()
