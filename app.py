"""
app.py

Painel Streamlit do NetStat Monitor.

Permite configurar hosts das camadas LAN, MAN e WAN, iniciar e interromper
coletas em tempo real e visualizar métricas de latência, jitter e perda de
pacotes em uma interface web. Os valores podem ser informados manualmente ou
preenchidos automaticamente por detecção do gateway e do primeiro host externo.
"""

import os
import threading

import streamlit as st

from coletor.ping_collector import PingCollector
from coletor.deteccao_rede import detectar_hosts_camadas
from armazenamento.armazenamento import ArmazenamentoCSV
from analise.estatisticas import carregar_medicoes, calcular_estatisticas_descritivas
from visualizacao.graficos import (
    gerar_grafico_serie_temporal,
    gerar_grafico_taxa_perda_pacotes,
    calcular_perda_pacotes_total,
)

PASTA_DADOS = "dados"

st.set_page_config(page_title="NetStat Monitor", layout="wide")
st.title("NetStat Monitor")

# --- Estado da sessão: sobrevive entre reruns do Streamlit, enquanto a aba do navegador estiver aberta ---
if "coleta_ativa" not in st.session_state:
    st.session_state.coleta_ativa = False
    st.session_state.threads = {}
    st.session_state.stop_events = {}

# --- Barra lateral: configuração e controle da coleta ---
st.sidebar.header("Configuração da coleta")

# Campos de host por camada de rede (LAN/MAN/WAN), com atalho de detecção automática.
if "lan_gateway_input" not in st.session_state:
    st.session_state.lan_gateway_input = ""
    st.session_state.man_provedor_input = ""
    st.session_state.wan_google_input = "8.8.8.8"

if st.sidebar.button("Detectar automaticamente", disabled=st.session_state.coleta_ativa):
    with st.spinner("Detectando hosts (gateway + traceroute, pode levar alguns segundos)..."):
        detectados = detectar_hosts_camadas()
    st.session_state.lan_gateway_input = detectados["lan_gateway"] or ""
    st.session_state.man_provedor_input = detectados["man_provedor"] or ""
    st.session_state.wan_google_input = detectados["wan_google"] or "8.8.8.8"
    st.rerun()

lan_gateway = st.sidebar.text_input(
    "LAN — gateway", key="lan_gateway_input", disabled=st.session_state.coleta_ativa
)
man_provedor = st.sidebar.text_input(
    "MAN — provedor (aproximado)", key="man_provedor_input", disabled=st.session_state.coleta_ativa
)
wan_google = st.sidebar.text_input(
    "WAN — destino externo", key="wan_google_input", disabled=st.session_state.coleta_ativa
)

hosts_rotulados = {
    rotulo: valor.strip()
    for rotulo, valor in [
        ("lan_gateway", lan_gateway),
        ("man_provedor", man_provedor),
        ("wan_google", wan_google),
    ]
    if valor.strip()
}

tipo_conexao = st.sidebar.selectbox("Tipo de conexão", ["wifi", "cabo"])
intervalo = st.sidebar.number_input(
    "Intervalo entre coletas (segundos)", min_value=1.0, value=5.0, step=1.0
)

col_iniciar, col_parar = st.sidebar.columns(2)
iniciar = col_iniciar.button("Iniciar", disabled=st.session_state.coleta_ativa)
parar = col_parar.button("Parar", disabled=not st.session_state.coleta_ativa)

if iniciar and hosts_rotulados:
    for rotulo, host in hosts_rotulados.items():
        stop_event = threading.Event()
        coletor = PingCollector(host=host, intervalo_segundos=intervalo)

        nome_arquivo = f"{PASTA_DADOS}/medicoes_{rotulo}_{tipo_conexao}.csv"
        armazenamento = ArmazenamentoCSV(caminho_arquivo=nome_arquivo)

        # O parâmetro default=armazenamento evita um erro clássico de closure em
        # loops (sem ele, todas as threads acabariam usando o último armazenamento
        # criado no loop, não o seu próprio).
        def callback(medicao, armazenamento=armazenamento):
            armazenamento.salvar_medicao(medicao)

        thread = threading.Thread(
            target=coletor.iniciar_coleta_continua,
            args=(callback, stop_event),
            daemon=True,
        )
        thread.start()
        st.session_state.threads[rotulo] = thread
        st.session_state.stop_events[rotulo] = stop_event

    st.session_state.coleta_ativa = True
    st.rerun()

if parar:
    for stop_event in st.session_state.stop_events.values():
        stop_event.set()
    st.session_state.threads = {}
    st.session_state.stop_events = {}
    st.session_state.coleta_ativa = False
    st.rerun()

if st.session_state.coleta_ativa:
    st.sidebar.success(f"Coletando: {', '.join(st.session_state.stop_events.keys())}")
else:
    st.sidebar.info("Coleta parada.")

# --- Área principal: visualização dos dados já coletados ---
st.header("Visualização")

arquivos_disponiveis = (
    sorted(f for f in os.listdir(PASTA_DADOS) if f.endswith(".csv"))
    if os.path.isdir(PASTA_DADOS)
    else []
)

if not arquivos_disponiveis:
    st.warning("Nenhum arquivo de dados encontrado ainda. Inicie uma coleta ao lado.")
else:
    arquivo_selecionado = st.selectbox("Arquivo para visualizar", arquivos_disponiveis)

    # st.fragment permite que só esta parte da tela seja recarregada
    # periodicamente, sem re-executar o script inteiro (o que reiniciaria
    # os widgets da barra lateral). run_every só fica ativo enquanto a
    # coleta estiver rodando; parado, o gráfico fica estático até você
    # trocar de arquivo selecionado.
    @st.fragment(run_every=5 if st.session_state.coleta_ativa else None)
    def mostrar_dados():
        caminho = os.path.join(PASTA_DADOS, arquivo_selecionado)
        df = carregar_medicoes(caminho)

        estatisticas = calcular_estatisticas_descritivas(df)
        perda_total = calcular_perda_pacotes_total(df)

        # Última leitura válida (instantânea), para diferenciar de latencia média
        latencias_validas = df["latencia_ms"].dropna()
        if not latencias_validas.empty:
            latencia_atual = latencias_validas.iloc[-1]
            delta_vs_media = (
                latencia_atual - latencias_validas.iloc[-2]
                if latencias_validas.iloc[-2] is not None else None
            )
        else:
            latencia_atual = None
            delta_vs_media = None

        c0, c1, c2, c3, c4 = st.columns(5)
        if latencia_atual is not None:
            c0.metric(
                "Latência instantânea",
                f"{latencia_atual:.2f} ms",
                delta=f"{delta_vs_media:+.2f} ms" if delta_vs_media is not None else None,
                delta_color="inverse",  # menor que a média = verde (bom); maior = vermelho
            )
        else:
            c0.metric("Latência instantânea", "—")
        c1.metric("Latência média", f"{estatisticas['media_ms']} ms")
        c2.metric("Desvio padrão", f"{estatisticas['desvio_padrao_ms']} ms")
        c3.metric("Perda total", f"{perda_total}%")
        c4.metric("Amostras válidas", estatisticas["quantidade_amostras"])

        col_a, col_b = st.columns(2)
        with col_a:
            fig_latencia = gerar_grafico_serie_temporal(
                df, coluna="latencia_ms", titulo="Latência",
                rotulo_eixo_y="Latência (ms)", agregacao="1min",
                salvar_arquivo=False,
            )
            st.plotly_chart(fig_latencia, use_container_width=True)
        with col_b:
            fig_jitter = gerar_grafico_serie_temporal(
                df, coluna="jitter_ms", titulo="Jitter",
                rotulo_eixo_y="Jitter (ms)", agregacao="1min",
                salvar_arquivo=False,
            )
            st.plotly_chart(fig_jitter, use_container_width=True)

        fig_perda = gerar_grafico_taxa_perda_pacotes(df, janela="1min", salvar_arquivo=False)
        st.plotly_chart(fig_perda, use_container_width=True)

    mostrar_dados()