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
from datetime import datetime
from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, portrait
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

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


def _formatar_texto_pdf(texto: str) -> str:
    """Converte a marcação inline usada nos relatórios para o formato do ReportLab."""
    texto = escape(texto)
    texto = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', texto)
    return re.sub(r"_([^_]+)_", r"<i>\1</i>", texto)


def exportar_relatorio_pdf(conteudo: str | None) -> bytes:
    """Gera em memória um PDF legível a partir do Markdown do relatório."""
    conteudo = conteudo or ""
    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=portrait(A4),
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title="Relatório consolidado — NetStat Monitor",
    )
    estilos = getSampleStyleSheet()
    elementos = []
    linhas = conteudo.splitlines()
    indice = 0

    while indice < len(linhas):
        linha = linhas[indice].strip()

        if linha.startswith("|"):
            tabela = []
            while indice < len(linhas) and linhas[indice].strip().startswith("|"):
                celulas = [
                    celula.strip()
                    for celula in linhas[indice].strip().strip("|").split("|")
                ]
                if not all(re.fullmatch(r":?-+:?", celula) for celula in celulas):
                    tabela.append([
                        Paragraph(_formatar_texto_pdf(celula), estilos["BodyText"])
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
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF5")),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ])
                )
                elementos.extend([elemento_tabela, Spacer(1, 4 * mm)])
            continue

        if linha.startswith("# "):
            elementos.append(Paragraph(_formatar_texto_pdf(linha[2:]), estilos["Title"]))
        elif linha.startswith("## "):
            elementos.append(Paragraph(_formatar_texto_pdf(linha[3:]), estilos["Heading2"]))
        elif linha:
            elementos.append(Paragraph(_formatar_texto_pdf(linha), estilos["BodyText"]))
        else:
            elementos.append(Spacer(1, 2 * mm))
        indice += 1

    documento.build(elementos)
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


def gerar_relatorio_consolidado(pasta_dados: str = PASTA_DADOS) -> str:
    """
    Gera o relatório consolidado em Markdown a partir de todos os CSVs da
    pasta de dados, ordenados por nome de arquivo.

    Arquivos vazios, sem medições válidas ou fora do padrão de nomeação
    não interrompem a geração: entram no relatório com uma nota apropriada.
    """
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


def salvar_relatorio(conteudo: str, pasta_relatorios: str = PASTA_RELATORIOS) -> str:
    """
    Salva o relatório em Markdown dentro da pasta de relatórios, com nome
    contendo o momento da geração, e retorna o caminho completo do arquivo.
    """
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
