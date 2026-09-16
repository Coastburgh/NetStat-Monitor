"""
app.py

Painel Streamlit do NetStat Monitor — requisito 19.

Permite escolher hosts, iniciar/parar a coleta e visualizar os gráficos
em tempo quase real, tudo pelo navegador, sem precisar do terminal
(além do comando único para abrir o painel: streamlit run app.py).
"""

import os
import threading

import streamlit as st

from coletor.ping_collector import PingCollector
from armazenamento.armazenamento import ArmazenamentoCSV
from analise.estatisticas import carregar_medicoes, calcular_estatisticas_descritivas
from visualizacao.graficos import (
    gerar_grafico_serie_temporal,
    gerar_grafico_taxa_perda_pacotes,
    calcular_perda_pacotes_total,
)

PASTA_DADOS = "dados"
HOSTS_PADRAO = ["192.168.11.254", "200.255.254.193","8.8.8.8"]

st.set_page_config(page_title="NetStat Monitor", layout="wide")
st.title("NetStat Monitor")

# --- Estado da sessão: sobrevive entre reruns do Streamlit, enquanto a aba do navegador estiver aberta ---
if "coleta_ativa" not in st.session_state:
    st.session_state.coleta_ativa = False
    st.session_state.threads = {}
    st.session_state.stop_events = {}

# --- Barra lateral: configuração e controle da coleta ---
st.sidebar.header("Configuração da coleta")

hosts_selecionados = st.sidebar.multiselect(
    "Hosts a monitorar", options=HOSTS_PADRAO, default=HOSTS_PADRAO
)
host_customizado = st.sidebar.text_input("Adicionar host customizado (opcional)")
if host_customizado:
    hosts_selecionados.append(host_customizado)

tipo_conexao = st.sidebar.selectbox("Tipo de conexão", ["wifi", "cabo"])
intervalo = st.sidebar.number_input(
    "Intervalo entre coletas (segundos)", min_value=1.0, value=5.0, step=1.0
)

col_iniciar, col_parar = st.sidebar.columns(2)
iniciar = col_iniciar.button("Iniciar", disabled=st.session_state.coleta_ativa)
parar = col_parar.button("Parar", disabled=not st.session_state.coleta_ativa)

if iniciar and hosts_selecionados:
    for host in hosts_selecionados:
        stop_event = threading.Event()
        coletor = PingCollector(host=host, intervalo_segundos=intervalo)

        nome_arquivo = f"{PASTA_DADOS}/medicoes_{host.replace('.', '_')}_{tipo_conexao}.csv"
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
        st.session_state.threads[host] = thread
        st.session_state.stop_events[host] = stop_event

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

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Amostras válidas", estatisticas["quantidade_amostras"])
        c2.metric("Latência média", f"{estatisticas['media_ms']} ms")
        c3.metric("Desvio padrão", f"{estatisticas['desvio_padrao_ms']} ms")
        c4.metric("Perda total", f"{perda_total}%")

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

        fig_perda = gerar_grafico_taxa_perda_pacotes(df, janela="5min", salvar_arquivo=False)
        st.plotly_chart(fig_perda, use_container_width=True)

    mostrar_dados()