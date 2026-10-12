"""
app.py

Ponto de entrada do painel Streamlit do NetStat Monitor.

Não contém lógica de interface: apenas configura a página e registra a
navegação entre as páginas do painel (Monitor e Relatório).
"""

import streamlit as st

st.set_page_config(page_title="NetStat Monitor", layout="wide")

# --- Navegação entre páginas: Monitor e Relatório ---
# A página de relatório não gera nada por conta própria: exibe apenas o
# relatório que o usuário gerar no Monitor, guardado em st.session_state.
pagina_monitor = st.Page("paginas/monitor.py", title="Monitor", icon=":material/monitoring:", default=True)
pagina_relatorio = st.Page("paginas/relatorio.py", title="Relatório", icon=":material/description:")
st.navigation([pagina_monitor, pagina_relatorio])
