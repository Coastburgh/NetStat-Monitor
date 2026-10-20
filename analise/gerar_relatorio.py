"""
analise/gerar_relatorio.py

Módulo responsável pela geração automatizada do relatório consolidado
das medições coletadas (req. 20).

O relatório é gerado em Markdown a partir de todos os arquivos CSV da
pasta de dados, reutilizando as análises já implementadas (estatísticas
descritivas, outliers por IQR, correlação horário x latência e perda de
pacotes), sem duplicar nenhuma lógica de cálculo.
"""

import os
import re
from base64 import b64encode
from datetime import datetime
from functools import partial
from html import escape
from io import BytesIO
from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, portrait
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import CondPageBreak, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib.utils import ImageReader

from analise.estatisticas import (
    carregar_medicoes,
    resumir_medicoes,
)
from armazenamento.armazenamento import (
    PASTA_DADOS,
    PASTA_RELATORIOS,
    extrair_metadados_nome_arquivo,
    listar_arquivos,
)


def _formatar_texto_inline(texto: str, para_html: bool = False) -> str:
    """Compartilha a marcação suportada pelos formatos sem aceitar HTML arbitrário."""
    texto = escape(texto)
    def converter(correspondencia):
        codigo, negrito, italico, rotulo, endereco = correspondencia.groups()
        if codigo is not None:
            if para_html:
                return f"<code>{codigo}</code>"
            return f'<font name="Courier">{codigo}</font>'
        if negrito is not None:
            return f"<b>{negrito}</b>"
        if italico is not None:
            return f"<i>{italico}</i>"
        if para_html:
            return f'<a href="{endereco}">{rotulo}</a>'
        return f'<link href="{endereco}" color="#007D91">{rotulo}</link>'

    return re.sub(r"`([^`]+)`|\*\*([^*]+)\*\*|(?<!\w)_([^_]+)_(?!\w)|\[([^\]]+)\]\((https://[^\s)]+)\)", converter, texto)


def _formatar_texto_pdf(texto: str) -> str:
    """Converte a marcação inline usada nos relatórios para o formato do ReportLab."""
    return _formatar_texto_inline(texto)


def _grafico_horario_html(tabela: list[list[str]], numero: int) -> str:
    """Usa o retrato salvo no relatório, sem depender dos CSVs após a coleta."""
    colunas = ("Hora", "Mediana (ms)", "P90 (ms)", "Sem resposta (%)")
    if not tabela or not set(colunas).issubset(tabela[0]):
        return ""
    indices = [tabela[0].index(coluna) for coluna in colunas]
    valores = {}
    for linha in tabela[1:]:
        if len(linha) <= max(indices):
            return ""
        hora = re.fullmatch(r"(\d{2})h[–-](\d{2})h", linha[indices[0]])
        if hora is None or not 0 <= int(hora[1]) < 24 or int(hora[2]) != int(hora[1]) + 1:
            return ""
        try:
            valores[int(hora[1])] = [
                None if linha[indice] in ("—", "", "None") else float(linha[indice].replace(",", "."))
                for indice in indices[1:]
            ]
        except ValueError:
            return ""
    if not valores:
        return ""
    horas = [f"{hora:02d}h" for hora in range(24)]
    figura = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.12)
    for indice, nome, cor in ((0, "Mediana", "#00ABC2"), (1, "P90", "#526171")):
        figura.add_trace(go.Scatter(
            x=horas, y=[valores.get(hora, [None] * 3)[indice] for hora in range(24)],
            name=nome, mode="lines+markers", line_color=cor, connectgaps=False,
            hovertemplate="%{x}: %{y:.2f} ms<extra>%{fullData.name}</extra>",
        ), row=1, col=1)
    figura.add_trace(go.Bar(
        x=horas, y=[valores.get(hora, [None] * 3)[2] for hora in range(24)],
        name="Sem resposta", marker_color="#00ABC2",
        hovertemplate="%{x}: %{y:.2f}%<extra>Sem resposta</extra>",
    ), row=2, col=1)
    figura.update_yaxes(title_text="Latência (ms)", rangemode="tozero", row=1, col=1)
    figura.update_yaxes(title_text="Sem resposta (%)", rangemode="tozero", row=2, col=1)
    figura.update_layout(template="plotly_white", height=460, margin=dict(l=65, r=20, t=35, b=35),
                         legend=dict(orientation="h", y=1.12), font=dict(family="Arial", color="#121922"))
    return figura.to_html(full_html=False, include_plotlyjs=numero == 1,
                          div_id=f"perfil-horario-{numero}", config={"responsive": True, "displaylogo": False})


def exportar_relatorio_html(conteudo: str | None) -> str:
    """Exporta um documento offline com a mesma análise, marca e gráficos horários."""
    conteudo = conteudo or ""
    geracao = re.search(r"^Gerado automaticamente em (\d{2}/\d{2}/\d{4} \d{2}:\d{2})", conteudo, re.MULTILINE)
    logo = Path(__file__).resolve().parents[1] / "assets" / "NS_logo_long.png"
    try:
        marca = '<img alt="NetStat Monitor" src="data:image/png;base64,' + b64encode(logo.read_bytes()).decode("ascii") + '">'
    except OSError:
        marca = '<span class="marca">NETSTAT MONITOR</span>'
    corpo, navegacao = [], []
    linhas = conteudo.splitlines()
    indice, graficos = 0, 0
    analise_detalhada = detalhes_abertos = False
    while indice < len(linhas):
        linha = linhas[indice].strip()
        if not linha or linha == "# Relatório consolidado — NetStat Monitor" or (geracao and linha.startswith(geracao.group(0))):
            indice += 1
            continue
        if linha.startswith("|"):
            tabela = []
            while indice < len(linhas) and linhas[indice].strip().startswith("|"):
                celulas = [celula.strip() for celula in linhas[indice].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", celula) for celula in celulas):
                    tabela.append(celulas)
                indice += 1
            if tabela:
                grafico = _grafico_horario_html(tabela, graficos + 1)
                if grafico:
                    graficos += 1
                    corpo.extend(['<div class="grafico">', grafico, '</div>',
                                  '<p class="legenda">Perfil por hora, conforme a tabela abaixo. '
                                  'Passe o cursor para consultar valores; horas sem coleta permanecem sem valores.</p>'])
                corpo.append('<div class="tabela"><table><thead>')
                for numero, celulas in enumerate(tabela):
                    if numero == 1:
                        corpo.append('</thead><tbody>')
                    tag = "th" if numero == 0 else "td"
                    corpo.append("<tr>" + "".join(f"<{tag}>{_formatar_texto_inline(celula, True)}</{tag}>" for celula in celulas) + "</tr>")
                corpo.append('</thead></table></div>' if len(tabela) == 1 else '</tbody></table></div>')
            continue
        titulo = re.match(r"^(#{1,4}) (.+)$", linha)
        if titulo:
            nivel, texto = len(titulo[1]), titulo[2]
            if detalhes_abertos and nivel <= 3:
                corpo.append('</details>')
                detalhes_abertos = False
            if nivel == 2:
                analise_detalhada = texto.startswith("3. ")
                identificador = f"secao-{len(navegacao) + 1}"
                navegacao.append(f'<a href="#{identificador}">{_formatar_texto_inline(texto, True)}</a>')
                corpo.append(f'<h2 id="{identificador}">{_formatar_texto_inline(texto, True)}</h2>')
            elif nivel == 3 and analise_detalhada:
                corpo.append(f'<details open><summary>{_formatar_texto_inline(texto, True)}</summary>')
                detalhes_abertos = True
            else:
                corpo.append(f'<h{nivel}>{_formatar_texto_inline(texto, True)}</h{nivel}>')
        elif linha.startswith("> "):
            corpo.append(f'<blockquote>{_formatar_texto_inline(linha[2:], True)}</blockquote>')
        else:
            corpo.append(f'<p>{_formatar_texto_inline(linha, True)}</p>')
        indice += 1
    if detalhes_abertos:
        corpo.append('</details>')
    data = f'<p>Gerado automaticamente em {escape(geracao[1])}</p>' if geracao else ""
    menu = '<nav aria-label="Seções do relatório">' + "".join(navegacao) + '</nav>' if navegacao else ""
    return """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Relatório Consolidado — NetStat Monitor</title>
<style>
* { box-sizing: border-box; }
body { margin: 0; background: #f2f5f8; color: #121922; font: 16px/1.6 Arial, sans-serif; }
header { background: #121922; color: #e6edf3; border-bottom: 4px solid #00ABC2; }
.cabecalho { max-width: 1200px; margin: auto; padding: 28px 32px; display: flex;
align-items: center; justify-content: space-between; gap: 24px; }
header img { width: 280px; max-width: 42%; height: auto; }
header h1 { margin: 0; font-size: 26px; }
header p { margin: 4px 0 0; font-size: 13px; }
.titulo { text-align: right; }
.marca { color: #00ABC2; font-weight: bold; }
main { max-width: 1200px; margin: 24px auto; padding: 24px 32px; background: white; border-radius: 6px; }
nav { display: flex; flex-wrap: wrap; gap: 12px 24px; padding-bottom: 16px; border-bottom: 1px solid #d3f1f5; }
a, h2, h3, summary { color: #007d91; }
h2 { margin-top: 32px; scroll-margin-top: 20px; }
h3 { margin-top: 24px; }
h4 { font-size: 16px; }
blockquote { margin: 16px 0; padding: 12px 16px; background: #eaf8fa; border-left: 4px solid #00ABC2; }
code { background: #f2f5f8; padding: 2px 4px; overflow-wrap: anywhere; }
.tabela { overflow-x: auto; margin: 20px 0; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { padding: 10px 12px; text-align: left; vertical-align: top; overflow-wrap: anywhere; }
th { background: #d3f1f5; border-bottom: 2px solid #00ABC2; }
tbody tr:nth-child(even) { background: #f2f5f8; }
details { margin: 20px 0; padding: 16px; border: 1px solid #d3f1f5; border-radius: 6px; }
summary { cursor: pointer; font-size: 18px; font-weight: bold; }
.grafico { min-width: 0; }
.legenda, footer { font-size: 13px; color: #526171; }
footer { padding: 16px; text-align: center; }
@media (max-width: 640px) {
.cabecalho { padding: 20px; flex-direction: column; align-items: flex-start; }
header img { max-width: 100%; width: 240px; } .titulo { text-align: left; }
main { margin: 12px; padding: 16px; } details { padding: 10px; } th, td { padding: 8px; }
}
@media print { body { background: white; } main { margin: 0; padding: 0; } nav { display: none; } }
</style></head><body>
<header><div class="cabecalho">""" + marca + '<div class="titulo"><h1>Relatório Consolidado</h1>' + data + """</div></div></header>
<main>""" + menu + "\n".join(corpo) + """</main>
<footer>NetStat Monitor | Análise de conectividade ICMP</footer>
</body></html>"""


def _decorar_pagina_pdf(canvas, documento, data_geracao: str | None = None):
    """Mantém a marca e a navegação em todas as páginas, sem depender do cwd."""
    largura, altura = A4
    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#121922"))
    canvas.rect(0, altura - 25 * mm, largura, 25 * mm, fill=1, stroke=0)
    logo = Path(__file__).resolve().parents[1] / "assets" / "NS_logo_long.png"
    if logo.is_file():
        canvas.drawImage(ImageReader(str(logo)), 15 * mm, altura - 17 * mm,
                         width=65 * mm, height=11 * mm, preserveAspectRatio=True, mask="auto")
    else:
        canvas.setFillColor(colors.white)
        canvas.drawString(15 * mm, altura - 15 * mm, "NETSTAT MONITOR")
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 16)
    canvas.drawRightString(largura - 15 * mm, altura - 13 * mm, "Relatório Consolidado")
    if data_geracao is not None:
        canvas.setFont("Helvetica", 7)
        canvas.drawRightString(largura - 15 * mm, altura - 17 * mm, f"Gerado automaticamente em {data_geracao}")
    canvas.setFillColor(colors.HexColor("#00ABC2"))
    canvas.rect(0, altura - 26 * mm, largura, 1 * mm, fill=1, stroke=0)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#526171"))
    canvas.drawString(15 * mm, 10 * mm, "NetStat Monitor | Análise de conectividade ICMP")
    canvas.drawRightString(largura - 15 * mm, 10 * mm, f"Página {documento.page}")
    canvas.restoreState()


def exportar_relatorio_pdf(conteudo: str | None) -> bytes:
    """Gera em memória um PDF legível a partir do Markdown do relatório."""
    conteudo = conteudo or ""
    geracao = re.search(r"^Gerado automaticamente em (\d{2}/\d{2}/\d{4} \d{2}:\d{2})", conteudo, re.MULTILINE)
    decorar_pagina = partial(_decorar_pagina_pdf, data_geracao=geracao.group(1) if geracao else None)
    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=portrait(A4),
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=33 * mm,
        bottomMargin=19 * mm,
        title="Relatório consolidado — NetStat Monitor",
    )
    estilos = getSampleStyleSheet()
    for nome in ("Title", "Heading2", "Heading3"):
        estilos[nome].textColor = colors.HexColor("#007D91")
    estilos["Title"].alignment = 0
    estilos["BodyText"].fontSize = 9
    estilos["BodyText"].leading = 13
    estilos.add(ParagraphStyle("Celula", parent=estilos["BodyText"], fontSize=8, leading=11))
    estilos.add(ParagraphStyle("Nota", parent=estilos["BodyText"], backColor=colors.HexColor("#EAF8FA"),
                               borderPadding=7, spaceBefore=6, spaceAfter=9))
    elementos = []
    linhas = conteudo.splitlines()
    indice = 0
    analise_detalhada = False

    while indice < len(linhas):
        linha = linhas[indice].strip()
        if linha == "# Relatório consolidado — NetStat Monitor" or (geracao and linha.startswith(geracao.group(0))):
            indice += 1
            continue

        if linha.startswith("|"):
            tabela = []
            while indice < len(linhas) and linhas[indice].strip().startswith("|"):
                celulas = [
                    celula.strip()
                    for celula in linhas[indice].strip().strip("|").split("|")
                ]
                if not all(re.fullmatch(r":?-+:?", celula) for celula in celulas):
                    tabela.append([
                        Paragraph(_formatar_texto_pdf(celula), estilos["Celula"])
                        for celula in celulas
                    ])
                indice += 1
            if tabela:
                largura_coluna = documento.width / len(tabela[0])
                elemento_tabela = Table(
                    tabela,
                    colWidths=[largura_coluna] * len(tabela[0]),
                    repeatRows=1,
                )
                elemento_tabela.setStyle(
                    TableStyle([
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D3F1F5")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F5F8")]),
                        ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#00ABC2")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ])
                )
                if len(tabela[0]) == 2 and len(tabela) <= 15:
                    elementos.append(KeepTogether([elemento_tabela, Spacer(1, 4 * mm)]))
                else:
                    elementos.extend([elemento_tabela, Spacer(1, 4 * mm)])
            continue

        if linha.startswith("# "):
            elementos.append(Paragraph(_formatar_texto_pdf(linha[2:]), estilos["Title"]))
        elif linha.startswith("## "):
            analise_detalhada = linha.startswith("## 3. ")
            elementos.append(Paragraph(_formatar_texto_pdf(linha[3:]), estilos["Heading2"]))
        elif linha.startswith("### "):
            if analise_detalhada:
                elementos.append(CondPageBreak(100 * mm))
            elementos.append(Paragraph(_formatar_texto_pdf(linha[4:]), estilos["Heading3"]))
        elif linha.startswith("#### "):
            elementos.append(Paragraph(_formatar_texto_pdf(linha[5:]), estilos["Heading4"]))
        elif linha.startswith("> "):
            elementos.append(Paragraph(_formatar_texto_pdf(linha[2:]), estilos["Nota"]))
        elif linha:
            elementos.append(Paragraph(_formatar_texto_pdf(linha), estilos["BodyText"]))
        elif elementos:
            elementos.append(Spacer(1, 2 * mm))
        indice += 1

    documento.build(elementos, onFirstPage=decorar_pagina, onLaterPages=decorar_pagina)
    return buffer.getvalue()


def _numero(valor, unidade: str = "") -> str:
    """Distingue ausência de valor de zero e usa a notação decimal local."""
    return "—" if valor is None else f"{valor:.2f}".replace(".", ",") + unidade


def _texto_seguro(texto: str) -> str:
    """Impede que nomes de arquivos e hosts alterem as tabelas do relatório."""
    return escape(str(texto)).replace("|", "&#124;").replace("`", "&#96;").replace("\n", " ").replace("\r", " ")


def _identificacao(resultado: dict) -> str:
    dados = resultado["metadados"]
    return f"{dados['camada']} — {dados['host']} ({dados['sessao']})"


def _destaque_horarios(resultado: dict) -> str:
    perfil = resultado["perfil_horario"]
    comparaveis = [h for h in perfil if h["dias_com_cobertura"] > 0]
    latencias = [h for h in comparaveis if h["mediana_coberta_ms"] is not None]
    textos = []
    if len(latencias) >= 2:
        maior = max(h["mediana_coberta_ms"] for h in latencias)
        menor = min(h["mediana_coberta_ms"] for h in latencias)
        if maior > menor:
            horas = ", ".join(f"{h['hora']:02d}h" for h in latencias if h["mediana_coberta_ms"] == maior)
            textos.append(f"Maior latência típica observada: {horas} ({_numero(maior, ' ms')}); "
                          f"menor mediana horária: {_numero(menor, ' ms')}.")
            destaques = [h for h in latencias if h["mediana_coberta_ms"] == maior]
            if len(destaques) == 1 and destaques[0]["dias_comparaveis"]:
                hora = destaques[0]
                textos.append(f"Às {hora['hora']:02d}h, a mediana foi a maior do dia em "
                              f"{hora['dias_pior_latencia']} de {hora['dias_comparaveis']} dia(s) com comparação.")
        else:
            textos.append("As medianas dos horários com cobertura foram iguais.")
    else:
        textos.append("Cobertura insuficiente para comparar a latência entre horários.")
    if len(comparaveis) >= 2:
        maior_perda = max(h["perda_coberta_pct"] for h in comparaveis)
        if maior_perda > 0:
            horas = ", ".join(f"{h['hora']:02d}h" for h in comparaveis if h["perda_coberta_pct"] == maior_perda)
            textos.append(f"Maior proporção de falhas observada: {horas} ({_numero(maior_perda, '%')}).")
    if sum(h["dias_com_cobertura"] >= 2 for h in perfil) < 2:
        textos.append("Ainda não há dois horários com cobertura repetida em dias diferentes; "
                      "não é possível avaliar um padrão diário recorrente.")
    else:
        textos.append("Há horários observados em dias diferentes; os destaques são exploratórios "
                      "e não confirmam que o mesmo comportamento se repete diariamente.")
    return " ".join(textos)


def _secao_resumo(resultados: list[dict]) -> str:
    linhas = ["## 1. Resumo da conexão", "",
              "> Leia primeiro: os resultados descrevem respostas de ping aos destinos monitorados. "
              "Eles ajudam a localizar onde investigar, mas não comprovam a causa de uma lentidão.", ""]
    for resultado in resultados:
        linhas += [f"### {_identificacao(resultado)}", ""]
        total = resultado["quantidade_medicoes"]
        validas = resultado["estatisticas"]["quantidade_amostras"]
        if not total:
            linhas += ["Arquivo sem medições registradas.", ""]
            continue
        falhas = total - validas
        periodo = resultado["periodo"]
        linhas += [f"**Observação:** {periodo['inicio']:%d/%m/%Y %H:%M} a {periodo['fim']:%d/%m/%Y %H:%M}; "
                   f"{periodo['dias']} dia(s) com coleta e {periodo['horas']} de 24 horários representados.", ""]
        linhas.append(f"**Respostas:** {validas} de {total} tentativas; {falhas} sem resposta "
                      f"({_numero(resultado['perda_total'], '%')}).")
        if validas:
            estatisticas = resultado["estatisticas"]
            linhas += ["", f"**Tempo de resposta típico:** {_numero(estatisticas['mediana_ms'], ' ms')} "
                       f"(mediana). Em aproximadamente 90% das respostas, o tempo foi de até "
                       f"{_numero(estatisticas['percentis_ms']['p90'], ' ms')}."]
        else:
            linhas += ["", "Todas as tentativas ficaram sem resposta; todas as leituras falharam. "
                       "Verifique também se o destino aceita ICMP e se houve falha local no comando ping."]
        linhas += ["", f"**Horários que merecem atenção:** {_destaque_horarios(resultado)}", ""]
    return "\n".join(linhas)


def _secao_comparativa(resultados: list[dict]) -> str:
    linhas = ["## 2. Visão por camada e destino", "",
              "| Camada / destino | Conexão | Respostas / tentativas | Mediana (ms) | P90 (ms) | Sem resposta (%) |",
              "|---|---|---|---|---|---|"]
    for resultado in resultados:
        dados = resultado["metadados"]
        estatisticas = resultado["estatisticas"]
        total = resultado["quantidade_medicoes"]
        linhas.append(f"| {dados['camada']} / {dados['host']} | {dados['sessao']} "
                      f"| {estatisticas['quantidade_amostras']} / {total} "
                      f"| {_numero(estatisticas['mediana_ms'])} "
                      f"| {_numero(estatisticas['percentis_ms'].get('p90'))} "
                      f"| {_numero(resultado['perda_total'] if total else None)} |")
    linhas += ["", "Compare preferencialmente o mesmo destino, no mesmo ambiente e em períodos equivalentes. "
               "Os tempos são de ida e volta até cada destino, não o atraso isolado de cada camada. "
               "MAN é uma aproximação do provedor; um roteador pode responder lentamente ao ICMP "
               "e ainda encaminhar tráfego normalmente.", ""]
    return "\n".join(linhas)


def _secao_horarios(resultado: dict) -> list[str]:
    linhas = ["#### Comportamento por hora do dia", "",
              "| Hora | Dias / com cobertura | Respostas / tentativas | Mediana (ms) | P90 (ms) | Sem resposta (%) | Maior mediana (dias) |",
              "|---|---|---|---|---|---|---|"]
    for hora in resultado["perfil_horario"]:
        repeticao = f"{hora['dias_pior_latencia']} / {hora['dias_comparaveis']}" if hora["dias_comparaveis"] else "—"
        linhas.append(f"| {hora['hora']:02d}h–{hora['hora'] + 1:02d}h "
                      f"| {hora['dias']} / {hora['dias_com_cobertura']} "
                      f"| {hora['validas']} / {hora['tentativas']} "
                      f"| {_numero(hora['mediana_ms'])} | {_numero(hora['p90_ms'])} "
                      f"| {_numero(hora['perda_pct'])} | {repeticao} |")
    linhas += [""]
    return linhas


def _secao_arquivo(resultado: dict) -> str:
    linhas = [f"### {_identificacao(resultado)}", "",
              f"Fonte: `{resultado['arquivo']}`", ""]
    if not resultado["quantidade_medicoes"]:
        return "\n".join(linhas + ["Arquivo sem medições registradas.", ""])
    periodo = resultado["periodo"]
    estatisticas = resultado["estatisticas"]
    validas = estatisticas["quantidade_amostras"]
    linhas += [f"**Período:** {periodo['inicio']:%d/%m/%Y %H:%M:%S} a {periodo['fim']:%d/%m/%Y %H:%M:%S} "
               f"(horário local registrado, sem fuso no CSV).", "",
               f"**Cobertura:** {periodo['dias']} dia(s) com coleta; {periodo['horas']} de 24 horas do dia representadas. "
               f"Intervalo mediano observado entre registros: {_numero(periodo['intervalo_mediano_s'], ' s')}. "
               "A diferença entre início e fim não comprova coleta contínua.", "",
               "| Métrica | Valor |", "|---|---|",
               f"| Tentativas / respostas / falhas | {resultado['quantidade_medicoes']} / {validas} / {resultado['quantidade_medicoes'] - validas} |",
               f"| Sem resposta (perda observada) | {_numero(resultado['perda_total'], '%')} |"]
    if validas:
        p = estatisticas["percentis_ms"]
        jitter = resultado["jitter"]
        linhas += [f"| Latência média / mediana | {_numero(estatisticas['media_ms'])} / {_numero(estatisticas['mediana_ms'], ' ms')} |",
                   f"| Desvio padrão amostral | {_numero(estatisticas['desvio_padrao_ms'], ' ms')} |",
                   f"| P90 / P99 da latência | {_numero(p['p90'])} / {_numero(p['p99'], ' ms')} |",
                   f"| Jitter mediano / P90 | {_numero(jitter['mediana_ms'])} / {_numero(jitter['percentis_ms'].get('p90'), ' ms')} |",
                   f"| Pares de respostas com jitter registrado | {jitter['quantidade_amostras']} |",
                   f"| Picos superiores (IQR) | {resultado['picos_superiores']} ({_numero(resultado['picos_superiores'] / validas * 100, '%')}) |"]
        if validas < 100:
            linhas += ["", "> Amostra pequena: P99 é uma estimativa descritiva instável e não representa "
                       "uma garantia para medições futuras."]
        limites = resultado["iqr"]
        linhas += ["", f"**Picos:** Q1 = {_numero(limites['q1'], ' ms')}; Q3 = {_numero(limites['q3'], ' ms')}; "
                   f"limite superior = {_numero(limites['limite_superior'], ' ms')} (Q3 + 1,5 × IQR). "
                   f"Há também {resultado['outliers_inferiores']} valor(es) abaixo do limite inferior; "
                   "respostas rápidas não são contabilizadas como picos. Outliers são candidatos a investigação, "
                   "não falhas comprovadas.", ""]
        if limites["iqr"] == 0:
            linhas += ["> IQR igual a zero: os 50% centrais das respostas têm o mesmo valor. "
                       "Qualquer valor superior é destacado; arredondamento do ping pode aumentar essa sensibilidade.", ""]
    linhas += _secao_horarios(resultado)
    correlacao = resultado["correlacao"]
    linhas += ["#### Pearson: informação complementar", ""]
    if correlacao["coeficiente_r"] is None:
        linhas.append("Não calculável: dados insuficientes ou ausência de variação de horário ou latência.")
    else:
        r = correlacao["coeficiente_r"]
        p = correlacao["p_valor"]
        p_texto = "< 0,0001" if p < 0.0001 else "= " + f"{p:.4f}".replace(".", ",")
        linhas.append(f"r = {str(r).replace('.', ',')}; p-valor nominal {p_texto}; "
                      f"n = {correlacao['quantidade_amostras']} respostas.")
    linhas += [""]
    return "\n".join(linhas)


def _secao_metodologia() -> str:
    return "\n".join([
        "## 4. Como interpretar e aprofundar", "",
        "**Latência:** tempo de ida e volta (RTT) de um ping, não velocidade de download. "
        "Mediana descreve a resposta típica; P90 e P99 ajudam a observar a cauda de respostas lentas. "
        "O desvio padrão é amostral (n − 1); com uma única resposta ele não é calculável.", "",
        "**Jitter:** diferença absoluta entre a resposta atual e a última resposta válida da sessão. "
        "Pode atravessar uma falha de ping; não equivale ao jitter RTP ou à variação de atraso unidirecional da RFC 3393.", "",
        "**Sem resposta:** tentativas com latência ausente divididas por todas as tentativas. "
        "Inclui timeout, bloqueio ou limitação de ICMP e falhas locais ao executar ou interpretar o ping. "
        "O CSV não distingue essas causas. Períodos sem coleta não entram nessa taxa.", "",
        "**Perfil por hora:** as tabelas usam todas as tentativas e ponderam os resultados pela quantidade "
        "de medições; dias mais amostrados têm maior peso. Horas ausentes não foram monitoradas. "
        "Latências consideram só respostas; falhas usam todas as tentativas.", "",
        "**Maior mediana (dias):** conta em quantos dias aquela hora teve a maior latência típica "
        "entre dias com pelo menos duas horas com respostas em 30 minutos distintos. Empates no máximo contam "
        "somente se outro horário teve mediana menor. As horas comparadas podem variar entre dias; "
        "a contagem descreve a amostra, não confirma recorrência.", "",
        "**Pearson:** mede associação linear entre a hora inteira (0–23) e a latência. "
        "Pode não revelar picos localizados ou padrões cíclicos; r próximo de zero não descarta horários ruins. "
        "O p-valor pressupõe condições que não foram verificadas, especialmente independência entre medições. "
        "Pings sucessivos podem ser dependentes: o p-valor é apenas nominal, não confirma um padrão diário "
        "nem mede sua importância prática. Use o perfil horário e sua repetição em vários dias como referência.", "",
        "**Investigação por camada:** compare os mesmos horários da LAN, MAN e WAN. "
        "Piora simultânea já na LAN sugere investigar a rede local; LAN estável e piora nos destinos "
        "externos orientam a investigação para além do gateway. São indícios, não localização comprovada da falha.", "",
        "**Para avaliar um padrão diário:** mantenha coletas em horários equivalentes durante vários dias, "
        "incluindo dias úteis e fins de semana. Compare o mesmo destino e ambiente. "
        "O número de datas tocadas não equivale a dias completos monitorados; nenhuma conclusão causal "
        "sobre Wi-Fi, Ethernet ou provedor é produzida automaticamente.", "",
        "**Limitações da coleta:** o intervalo efetivo inclui o tempo do comando ping e pode aumentar com falhas. "
        "Windows pode informar tempo inferior a 1 ms, armazenado pelo coletor como 1 ms; Linux e macOS "
        "podem fornecer valores fracionários. Essa resolução afeta sobretudo LAN, jitter e IQR. "
        "Reinícios podem compartilhar o mesmo CSV; não há identificação de sessão, fuso ou ambiente nas linhas.", "",
        "**Escopo:** análise descritiva, sem IA, testes de comparação entre grupos ou modelo M/M/1. "
        "Não são aplicados limites universais de conexão boa ou ruim, pois a adequação depende da aplicação.", "",
        "**Referências:** [Pearson — SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.pearsonr.html); "
        "[IQR — NIST](https://www.itl.nist.gov/div898/handbook/eda/section3/boxplot.htm); "
        "[Variação de atraso — RFC 3393](https://www.rfc-editor.org/rfc/rfc3393.html).", "",
    ])


def gerar_relatorio_consolidado(pasta_dados: str | None = None) -> str:
    """
    Gera o relatório consolidado em Markdown a partir de todos os CSVs da
    pasta de dados, ordenados por nome de arquivo.

    Arquivos vazios, sem medições válidas ou fora do padrão de nomeação
    não interrompem a geração: entram no relatório com uma nota apropriada.
    """
    pasta_dados = PASTA_DADOS if pasta_dados is None else pasta_dados
    arquivos_csv = listar_arquivos(pasta_dados, ".csv")

    data_geracao = datetime.now().strftime("%d/%m/%Y %H:%M")
    linhas = [
        "# Relatório consolidado — NetStat Monitor",
        "",
        f"Gerado automaticamente em {data_geracao}.",
        "",
    ]

    if not arquivos_csv:
        linhas.append("_Nenhum arquivo de dados encontrado na pasta de medições._")
        return "\n".join(linhas)

    resultados = []
    erros = []
    for nome_arquivo in arquivos_csv:
        try:
            df = carregar_medicoes(os.path.join(pasta_dados, nome_arquivo))
            resultado = resumir_medicoes(df, detalhado=True)
        except (OSError, ValueError) as erro:
            erros.append(f"**{_texto_seguro(nome_arquivo)}:** Não foi possível carregar o arquivo: {_texto_seguro(erro)}")
            continue

        resultado["metadados"] = {
            chave: _texto_seguro(valor)
            for chave, valor in extrair_metadados_nome_arquivo(nome_arquivo).items()
        }
        resultado["arquivo"] = _texto_seguro(nome_arquivo)
        resultados.append(resultado)

    if resultados:
        linhas.append(_secao_resumo(resultados))
        linhas.append(_secao_comparativa(resultados))
        linhas.extend(["## 3. Análise detalhada", "",
                       "> Nas tabelas horárias, dias com cobertura têm tentativas em pelo menos 30 minutos "
                       "distintos naquela hora. Os destaques do resumo usam somente esses dias-hora. "
                       "Para destacar latência, também são necessárias respostas em 30 minutos distintos. "
                       "É um critério operacional para evitar rajadas pouco representativas, não uma garantia estatística.", ""])
        linhas.extend(_secao_arquivo(resultado) for resultado in resultados)
        linhas.append(_secao_metodologia())
    if erros:
        linhas.extend(["## Arquivos não analisados", "",
                       "> Os arquivos abaixo foram excluídos das análises; os resultados não representam toda a pasta.", ""])
        linhas.extend(erro + "\n" for erro in erros)

    return "\n".join(linhas)


def salvar_relatorio(conteudo: str, pasta_relatorios: str | None = None) -> str:
    """
    Salva o relatório em Markdown dentro da pasta de relatórios, com nome
    contendo o momento da geração, e retorna o caminho completo do arquivo.
    """
    pasta_relatorios = PASTA_RELATORIOS if pasta_relatorios is None else pasta_relatorios
    os.makedirs(pasta_relatorios, exist_ok=True)
    nome_arquivo = f"relatorio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    caminho = os.path.join(pasta_relatorios, nome_arquivo)
    with open(caminho, mode="w", encoding="utf-8") as f:
        f.write(conteudo)
    return caminho


if __name__ == "__main__":
    # Execução manual para teste rápido: python -m analise.gerar_relatorio
    relatorio = gerar_relatorio_consolidado()
    print(relatorio)
    print(f"\n[Salvando cópia em {PASTA_RELATORIOS}]")
    caminho_salvo = salvar_relatorio(relatorio)
    print(f"Relatório salvo em: {caminho_salvo}")
