"""
app.py

Ponto de entrada do painel Streamlit do NetStat Monitor.

Configura a página, inicializa o estado compartilhado e registra a
navegação e as ações comuns do painel (Monitor e Relatório).
"""

import streamlit as st
import os
import signal
from analise.gerar_relatorio import gerar_relatorio_consolidado, salvar_relatorio
from armazenamento.armazenamento import PASTA_DADOS, listar_arquivos
from paginas.recursos import inicializar_estado, obter_controlador

st.set_page_config(page_title="NetStat Monitor", layout="wide")

st.logo("assets/NS_logo_long.png", size="large", icon_image="assets/NS_logo_square.png")

# Sobrescreve o padrão do Streamlit para mudar a cor do botão ENCERRAR e peso da fonte
# Sobrescreve o padrão do Streamlit para mudar o peso da fonte do botão Gerar Relatório
# Sobrescreve o padrão do Streamlit para mudar o peso da fonte dos botões
# (de novo por chatice do Streamlit)
# (PQP...)
st.html("""
<style>
.st-key-bold button p,
.st-key-bold1 button p,
.st-key-bold2 button p,
.st-key-gerar button p {
    font-weight: 800;
}

.st-key-encerrar button,
.st-key-encerrar button p {
    background-color: #fff;
    border-color: #00ABC2;
    color: #00ABC2;
    font-weight: 1000;
}
</style>
""")

# Navegação entre páginas: Monitor e Relatório
inicializar_estado()
pagina_monitor = st.Page("paginas/monitor.py", title="Monitor", icon=":material/monitoring:", default=True)
pagina_relatorio = st.Page("paginas/relatorio.py", title="Relatório", icon=":material/description:")
st.navigation([pagina_monitor, pagina_relatorio]).run()

# Botões para encerramento do app e geração de relatório
arquivos_disponiveis = listar_arquivos(PASTA_DADOS, ".csv")

# Adiciona à sidebar os botões de Gerar Relatório e ENCERRAR lado à lado
with st.sidebar:
    col_gerar, col_encerrar = st.columns(2)
    if not st.session_state.coleta_ativa:
        if col_encerrar.button("ENCERRAR", key="encerrar", type="primary", width='stretch'):
            obter_controlador().parar()
            os.kill(os.getpid(), signal.SIGTERM)
        if col_gerar.button("Gerar Relatório", key="gerar", disabled=not arquivos_disponiveis, type="primary", width='stretch'):
            try:
                with st.spinner("Consolidando medições e gerando relatório..."):
                    conteudo = gerar_relatorio_consolidado()
                    salvar_relatorio(conteudo)
            except OSError as erro:
                st.sidebar.error(f"Não foi possível salvar o relatório: {erro}")
            else:
                st.switch_page("paginas/relatorio.py")
