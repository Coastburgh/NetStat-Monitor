"""
app.py

Ponto de entrada do painel Streamlit do NetStat Monitor.

Não contém lógica de interface: apenas configura a página e registra a
navegação entre as páginas do painel (Monitor e Relatório).
"""

import streamlit as st
import os
import signal

st.set_page_config(page_title="NetStat Monitor", layout="wide")

st.logo("assets/NS_logo_long.png", size="large", icon_image="assets/NS_logo_square.png")

# --- Navegação entre páginas: Monitor e Relatório ---
# A página de relatório não gera nada por conta própria: exibe apenas o
# relatório que o usuário gerar no Monitor, salvo em dados/relatorios/.
pagina_monitor = st.Page("paginas/monitor.py", title="Monitor", icon=":material/monitoring:", default=True)
pagina_relatorio = st.Page("paginas/relatorio.py", title="Relatório", icon=":material/description:")
st.navigation([pagina_monitor, pagina_relatorio]).run()

st.markdown("""
<style>
.st-key-encerrar button {
    background-color: #C0392B;
    border-color: #C0392B;
    color: #e6edf3;
}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    if st.button("Encerrar Aplicação",key="encerrar"):
        for evento in st.session_state.get("eventos", {}).values():
            evento.set()
        os.kill(os.getpid(), signal.SIGTERM)