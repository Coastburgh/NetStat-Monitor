"""
paginas/monitor.py

Página Monitor do painel Streamlit.

Permite configurar hosts das camadas LAN, MAN e WAN, iniciar e interromper
coletas em tempo real e visualizar métricas de latência, jitter e perda de
pacotes. Os valores podem ser informados manualmente ou preenchidos
automaticamente por detecção do gateway e do primeiro host externo.
"""

import os
import threading

import pandas as pd
import streamlit as st

from coletor.ping_collector import PingCollector
from coletor.deteccao_rede import detectar_hosts_camadas, detectar_tipo_conexao
from armazenamento.armazenamento import ArmazenamentoCSV
from analise.estatisticas import carregar_medicoes, calcular_estatisticas_descritivas
from visualizacao.graficos import (
    gerar_grafico_serie_temporal,
    gerar_grafico_taxa_perda_pacotes,
    calcular_perda_pacotes_total,
)

PASTA_DADOS = "dados"

# Sobrescreve o padrão do Streamlit para mudar o peso da fonte dos botões
st.markdown("""
<style>
.st-key-bold button p {
    font-weight: 800;
}
</style>
""", unsafe_allow_html=True)

# --- Registro de coleta: vive no processo do servidor (não na sessão da aba) ---
# Recarregar ou fechar a aba cria uma nova sessão do Streamlit, mas as threads
# de coleta continuam rodando. Guardá-las em cache_resource permite que a nova
# sessão as reencontre, mostre o estado correto e consiga pará-las.
@st.cache_resource
def obter_registro_coleta() -> dict:
    return {"threads": {}, "stop_events": {}, "config": {}}


registro = obter_registro_coleta()
# Coleta ativa = existe ao menos uma thread viva no registro.
st.session_state.coleta_ativa = any(t.is_alive() for t in registro["threads"].values())

# --- Barra lateral: configuração e controle da coleta ---
st.sidebar.header("Configuração da coleta")

# Campos de host por camada de rede (LAN/MAN/WAN), com atalho de detecção automática.
if "lan_gateway_input" not in st.session_state:
    st.session_state.lan_gateway_input = ""
    st.session_state.man_provedor_input = ""
    st.session_state.wan_destino_input = ""

if st.sidebar.button("Configuração Automática", type="primary", key="bold", disabled=st.session_state.coleta_ativa, width='stretch'):
    with st.sidebar.spinner("Configurando a coleta..."):
        detectados = detectar_hosts_camadas()
        tipo_detectado = detectar_tipo_conexao()
    st.session_state.lan_gateway_input = detectados.get("lan_gateway") or ""
    st.session_state.man_provedor_input = detectados.get("man_provedor") or ""
    st.session_state.wan_destino_input = detectados.get("wan_destino") or "8.8.8.8"
    # A atribuição à chave do selectbox acontece antes do st.rerun(), que
    # reinicia o script antes de o widget ser instanciado novamente — sem
    # isso, o Streamlit levantaria erro de widget já instanciado. Se a
    # detecção falhar (None), o selectbox mantém o valor atual.
    if tipo_detectado:
        st.session_state.tipo_conexao_input = "WiFi" if tipo_detectado == "wifi" else "Ethernet"
    st.rerun()

lan_gateway = st.sidebar.text_input(
    "LAN — Gateway", key="lan_gateway_input", disabled=st.session_state.coleta_ativa
)
man_provedor = st.sidebar.text_input(
    "MAN — Provedor", key="man_provedor_input", disabled=st.session_state.coleta_ativa
)
wan_destino = st.sidebar.text_input(
    "WAN — Destino", key="wan_destino_input", disabled=st.session_state.coleta_ativa
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
    "Tipo de conexão", ["WiFi", "Ethernet"], key="tipo_conexao_input", disabled=st.session_state.coleta_ativa
)
intervalo = st.sidebar.number_input(
    "Intervalo entre coletas (segundos)", min_value=1.0, value=5.0, step=1.0, disabled=st.session_state.coleta_ativa
)

# Sobrescreve o padrão do Streamlit para mudar o peso da fonte dos botões (de novo por chatice do Streamlit)
st.markdown("""
<style>
.st-key-bold1 button p {
    font-weight: 800;
}
</style>
""", unsafe_allow_html=True)

iniciar = False;
parar = False;

if not st.session_state.coleta_ativa:
    iniciar = st.sidebar.button("Iniciar Coleta", type="primary", key="bold1", width='stretch')
else:
    parar = st.sidebar.button("Parar Coleta", type="primary", key="bold1", width='stretch')

if iniciar and hosts_rotulados and not st.session_state.coleta_ativa:
    for rotulo, host in hosts_rotulados.items():
        stop_event = threading.Event()
        coletor = PingCollector(host=host, intervalo_segundos=intervalo)

        endereco = host.strip()
        nome_arquivo = f"{PASTA_DADOS}/{rotulo}_{endereco}_{tipo_conexao.lower()}.csv"
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
        registro["threads"][rotulo] = thread
        registro["stop_events"][rotulo] = stop_event

    st.session_state.coleta_ativa = True
    st.rerun()

if parar:
    for stop_event in registro["stop_events"].values():
        stop_event.set()
    registro["threads"].clear()
    registro["stop_events"].clear()
    st.session_state.coleta_ativa = False
    st.rerun()

if st.session_state.coleta_ativa:
    st.sidebar.success(f"Coletando: {', '.join(registro['stop_events'].keys())}")

# --- Área principal: visualização dos dados já coletados ---
st.header("Monitor de Rede")

arquivos_disponiveis = (
    sorted(f for f in os.listdir(PASTA_DADOS) if f.endswith(".csv"))
    if os.path.isdir(PASTA_DADOS)
    else []
)

if not arquivos_disponiveis:
    st.info("Nenhum arquivo de dados encontrado ainda. Inicie uma coleta ao lado.")
else:
    col_arquivo, col_janela = st.columns(2)

    arquivo_selecionado = col_arquivo.selectbox("Arquivo para visualizar", arquivos_disponiveis)

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
        caminho = os.path.join(PASTA_DADOS, arquivo_selecionado)
        df = carregar_medicoes(caminho)

        estatisticas = calcular_estatisticas_descritivas(df)
        perda_total = calcular_perda_pacotes_total(df)

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
