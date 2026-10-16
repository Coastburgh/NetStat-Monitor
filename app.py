"""
app.py

Ponto de entrada do painel Streamlit do NetStat Monitor.

Não contém lógica de interface: apenas configura a página e registra a
navegação entre as páginas do painel (Monitor e Relatório).
"""

import streamlit as st
import os
import signal
from analise.gerar_relatorio import gerar_relatorio_consolidado, salvar_relatorio

st.set_page_config(page_title="NetStat Monitor", layout="wide")

st.logo("assets/NS_logo_long.png", size="large", icon_image="assets/NS_logo_square.png")

# Navegação entre páginas: Monitor e Relatório
pagina_monitor = st.Page("paginas/monitor.py", title="Monitor", icon=":material/monitoring:", default=True)
pagina_relatorio = st.Page("paginas/relatorio.py", title="Relatório", icon=":material/description:")
st.navigation([pagina_monitor, pagina_relatorio]).run()

# Botões para encerramento do app e geração de relatório
arquivos_disponiveis = (
    sorted(f for f in os.listdir("dados") if f.endswith(".csv"))
    if os.path.isdir("dados")
    else []
)

# Sobrescreve o padrão do Streamlit para mudar a cor do botão ENCERRAR
st.markdown("""
<style>
.st-key-encerrar button {
    background-color: #C0392B;
    border-color: #C0392B;
    color: #e6edf3;
}
</style>
""", unsafe_allow_html=True)

# Adiciona à sidebar os botões de Gerar Relatório e ENCERRAR lado à lado
with st.sidebar:
    col_gerar, col_encerrar = st.columns(2)
    if not st.session_state.coleta_ativa:
        if col_encerrar.button("ENCERRAR",key="encerrar", width='stretch'):
            for evento in st.session_state.get("eventos", {}).values():
                evento.set()
            os.kill(os.getpid(), signal.SIGTERM)
        if col_gerar.button("Gerar Relatório", disabled=not arquivos_disponiveis, type="primary", width='stretch'):
            with st.spinner("Consolidando medições e gerando relatório..."):
                conteudo = gerar_relatorio_consolidado()
                salvar_relatorio(conteudo)
            st.switch_page("paginas/relatorio.py")
