import os
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from reportlab.platypus import Paragraph, Spacer

from analise.estatisticas import (
    analisar_perfil_horario,
    calcular_correlacao_horario_latencia,
    calcular_estatisticas_descritivas,
    carregar_medicoes,
    medicoes_vazias,
    resumir_medicoes,
)
from analise.gerar_relatorio import (
    _decorar_pagina_pdf,
    _formatar_texto_pdf,
    _grafico_horario_html,
    exportar_relatorio_html,
    exportar_relatorio_pdf,
    gerar_relatorio_consolidado,
    salvar_relatorio,
)
from armazenamento.armazenamento import (
    ArmazenamentoCSV,
    CAMPOS,
    caminho_coleta,
    excluir_arquivo_dados,
    extrair_metadados_nome_arquivo,
    listar_arquivos,
    validar_host,
)
from paginas.recursos import _carregar_dados_monitor, carregar_dados_monitor
from scripts.gerar_dados_simulados import gerar_medicoes_simuladas, salvar_csv
from visualizacao.graficos import (
    agregar_por_intervalo,
    calcular_taxa_perda_por_janela,
    gerar_grafico_serie_temporal,
    gerar_grafico_taxa_perda_pacotes,
)


class DadosTest(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporario.cleanup)
        self.pasta = Path(self.temporario.name)
        self.csv = self.pasta / "wan_8.8.8.8_wifi.csv"

    def gravar(self, linhas):
        self.csv.write_text(
            ",".join(CAMPOS) + "\n" + linhas, encoding="utf-8",
        )

    def test_armazenamento_adiciona_sem_duplicar_cabecalho(self):
        self.csv.touch()
        armazenamento = ArmazenamentoCSV(str(self.csv))
        armazenamento.salvar_medicao({
            "host": "8.8.8.8", "latencia_ms": None,
            "jitter_ms": None, "perda_pacotes_pct": 100,
        })
        ArmazenamentoCSV(str(self.csv))
        self.assertEqual(self.csv.read_text().count("timestamp,"), 1)
        df = carregar_medicoes(self.csv)
        self.assertEqual(len(df), 1)
        self.assertEqual(resumir_medicoes(df)["perda_total"], 100)

    def test_csv_vazio_e_somente_cabecalho(self):
        for conteudo in ["", ",".join(CAMPOS) + "\n"]:
            with self.subTest(conteudo=conteudo):
                self.csv.write_text(conteudo, encoding="utf-8")
                df = carregar_medicoes(self.csv)
                self.assertTrue(df.empty)
                self.assertTrue(agregar_por_intervalo(df).empty)
                self.assertTrue(calcular_taxa_perda_por_janela(df).empty)
                self.assertIn("sem medições registradas", gerar_relatorio_consolidado(self.pasta))

    def test_dados_ausentes_nao_geram_excecoes_nas_analises(self):
        for df in [None, pd.DataFrame(), medicoes_vazias()]:
            with self.subTest(df=type(df)):
                resumo = resumir_medicoes(df, detalhado=True)
                self.assertEqual(resumo["estatisticas"]["quantidade_amostras"], 0)
                self.assertEqual(resumo["quantidade_outliers"], 0)
                self.assertIsNone(resumo["correlacao"]["coeficiente_r"])
                self.assertEqual(resumo["perda_total"], 0)
                self.assertEqual(len(gerar_grafico_serie_temporal(df, salvar_arquivo=False).data[0].y), 0)
                self.assertEqual(len(gerar_grafico_taxa_perda_pacotes(df, salvar_arquivo=False).data[0].y), 0)

    def test_arquivo_ausente_e_dados_invalidos_sao_reportados(self):
        with self.assertRaises(OSError):
            carregar_medicoes(self.csv)
        for conteudo in [
            "timestamp,host\n2026-10-01,8.8.8.8\n",
            ",".join(CAMPOS) + "\ninvalid,8.8.8.8,10,1,0\n",
            ",".join(CAMPOS) + "\n,8.8.8.8,10,1,0\n",
            ",".join(CAMPOS) + "\n2026-10-01,8.8.8.8,abc,1,0\n",
            ",".join(CAMPOS) + '\n"linha incompleta',
        ]:
            with self.subTest(conteudo=conteudo):
                self.csv.write_text(conteudo, encoding="utf-8")
                with self.assertRaises(ValueError):
                    carregar_medicoes(self.csv)
                self.assertIn("Não foi possível carregar", gerar_relatorio_consolidado(self.pasta))

    def test_medicoes_fora_de_ordem_sao_ordenadas_sem_perder_falhas(self):
        self.gravar(
            "2026-10-01T12:00:00,8.8.8.8,30,10,0\n"
            "2026-10-01T10:00:00,8.8.8.8,10,,0\n"
            "2026-10-01T11:00:00,8.8.8.8,,,33.33\n"
        )
        df = carregar_medicoes(self.csv)
        self.assertEqual(df["timestamp"].dt.hour.tolist(), [10, 11, 12])
        self.assertEqual(len(df), 3)
        self.assertEqual(resumir_medicoes(df)["perda_total"], 33.33)

    def test_uma_amostra_e_latencia_constante(self):
        self.gravar("2026-10-01T10:00:00,8.8.8.8,10,,0\n")
        self.assertIsNone(calcular_estatisticas_descritivas(carregar_medicoes(self.csv))["desvio_padrao_ms"])
        self.gravar(
            "2026-10-01T10:00:00,8.8.8.8,10,,0\n"
            "2026-10-01T11:00:00,8.8.8.8,10,0,0\n"
        )
        with patch("analise.estatisticas.stats.pearsonr") as pearson:
            self.assertIsNone(calcular_correlacao_horario_latencia(carregar_medicoes(self.csv))["coeficiente_r"])
            pearson.assert_not_called()

    def test_relatorio_consolida_todas_falhas_e_arquivos_renomeados(self):
        self.gravar("2026-10-01T10:00:00,8.8.8.8,,,100\n")
        self.assertIn("todas as leituras falharam", gerar_relatorio_consolidado(self.pasta))
        self.csv.rename(self.pasta / "renomeado.csv")
        self.assertIn("Camada não identificada", gerar_relatorio_consolidado(self.pasta))
        self.assertIn("Nenhum arquivo", gerar_relatorio_consolidado(self.pasta / "ausente"))

    def test_relatorio_calcula_resumo_uma_vez_por_arquivo(self):
        self.gravar("2026-10-01T10:00:00,8.8.8.8,10,,0\n")
        with patch("analise.gerar_relatorio.resumir_medicoes", wraps=resumir_medicoes) as resumir:
            gerar_relatorio_consolidado(self.pasta)
        resumir.assert_called_once()

    def test_perfil_horario_aceita_ausencias_e_hora_sem_respostas(self):
        for dados in (None, pd.DataFrame(), medicoes_vazias()):
            with self.subTest(dados=type(dados)):
                self.assertEqual(analisar_perfil_horario(dados), [])
        df = pd.DataFrame({
            "timestamp": pd.to_datetime(["2026-10-01 23:59", "2026-10-02 00:00", "2026-10-02 00:01"]),
            "latencia_ms": [10, None, None],
        })
        perfil = analisar_perfil_horario(df)
        self.assertEqual([h["hora"] for h in perfil], [0, 23])
        self.assertEqual(perfil[0]["perda_pct"], 100)
        self.assertIsNone(perfil[0]["mediana_ms"])
        self.assertEqual(perfil[1]["mediana_ms"], 10)

    def test_perfil_identifica_pico_diario_e_exclui_rajada_sem_cobertura(self):
        linhas = []
        for dia in range(1, 4):
            for hora, latencia in [(0, 10), (6, 10), (12, 80), (18, 10)]:
                for minuto in range(30):
                    linhas.append({"timestamp": pd.Timestamp(2026, 10, dia, hora, minuto), "latencia_ms": latencia})
        # Muitas amostras no mesmo minuto não equivalem a uma hora acompanhada.
        linhas.extend({"timestamp": pd.Timestamp(2026, 10, 1, 9), "latencia_ms": 1000} for _ in range(60))
        perfil = {h["hora"]: h for h in analisar_perfil_horario(pd.DataFrame(linhas))}
        self.assertEqual(perfil[12]["mediana_coberta_ms"], 80)
        self.assertEqual(perfil[12]["dias_pior_latencia"], 3)
        self.assertEqual(perfil[12]["dias_comparaveis"], 3)
        self.assertEqual(perfil[9]["dias_com_cobertura"], 0)
        self.assertIsNone(perfil[9]["mediana_coberta_ms"])
        self.assertEqual(perfil[0]["dias_pior_latencia"], 0)
        df = pd.DataFrame(linhas)
        df["host"], df["jitter_ms"], df["perda_pacotes_pct"] = "8.8.8.8", None, 0
        df.to_csv(self.csv, index=False)
        relatorio = gerar_relatorio_consolidado(self.pasta)
        self.assertIn("Maior latência típica observada: 12h (80,00 ms)", relatorio)
        self.assertIn("3 de 3 dia(s)", relatorio)
        self.assertNotIn("Maior latência típica observada: 09h", relatorio)

    def test_cobertura_limite_empates_e_dias_parciais(self):
        linhas = []
        for hora, minutos, valor in [(8, 29, 90), (9, 30, 10), (10, 30, 10)]:
            linhas.extend({"timestamp": pd.Timestamp(2026, 10, 1, hora, minuto), "latencia_ms": valor}
                          for minuto in range(minutos))
        # Uma segunda data não pode contaminar o destaque dos dias-hora cobertos.
        linhas.append({"timestamp": pd.Timestamp(2026, 10, 2, 9), "latencia_ms": 9999})
        perfil = {h["hora"]: h for h in analisar_perfil_horario(pd.DataFrame(linhas))}
        self.assertEqual(perfil[8]["dias_com_cobertura"], 0)
        self.assertEqual(perfil[9]["dias"], 2)
        self.assertEqual(perfil[9]["dias_com_cobertura"], 1)
        self.assertEqual(perfil[9]["mediana_coberta_ms"], 10)
        self.assertEqual(perfil[9]["dias_pior_latencia"], 0)
        self.assertEqual(perfil[10]["dias_comparaveis"], 1)

    def test_perda_horaria_inclui_falhas_e_horas_totalmente_inacessiveis(self):
        df = pd.DataFrame({
            "timestamp": pd.to_datetime(["2026-10-01 09:00", "2026-10-01 09:01", "2026-10-01 10:00"]),
            "latencia_ms": [10, None, None],
        })
        perfil = analisar_perfil_horario(df)
        self.assertEqual(perfil[0]["tentativas"], 2)
        self.assertEqual(perfil[0]["validas"], 1)
        self.assertEqual(perfil[0]["perda_pct"], 50)
        self.assertEqual(perfil[1]["perda_pct"], 100)

    def test_uma_resposta_entre_muitas_falhas_nao_sustenta_comparacao_de_latencia(self):
        df = pd.DataFrame({
            "timestamp": pd.date_range("2026-10-01 09:00", periods=30, freq="min"),
            "latencia_ms": [10] + [None] * 29,
        })
        hora = analisar_perfil_horario(df)[0]
        self.assertEqual(hora["dias_com_cobertura"], 1)
        self.assertEqual(hora["mediana_ms"], 10)
        self.assertIsNone(hora["mediana_coberta_ms"])
        self.assertEqual(hora["dias_comparaveis"], 0)
        self.assertEqual(hora["perda_coberta_pct"], 96.67)

    def test_iqr_distingue_caudas_sem_erro_de_arredondamento(self):
        df = pd.DataFrame({"latencia_ms": [1, 10, 10, 10, 10, 10, 10, 20]})
        resumo = resumir_medicoes(df, detalhado=True)
        self.assertEqual(resumo["iqr"]["iqr"], 0)
        self.assertEqual(resumo["picos_superiores"], 1)
        self.assertEqual(resumo["outliers_inferiores"], 1)
        df = pd.DataFrame({"latencia_ms": [0.001] + [0.004] * 6 + [0.020]})
        resumo = resumir_medicoes(df, detalhado=True)
        self.assertEqual(resumo["picos_superiores"], 1)
        self.assertEqual(resumo["outliers_inferiores"], 1)

    def test_pearson_preserva_p_valor_pequeno_e_relatorio_evita_zero(self):
        self.gravar("".join(f"2026-10-01T{hora:02d}:00:00,8.8.8.8,{hora * 10},1,0\n" for hora in range(10)))
        with patch("analise.estatisticas.stats.pearsonr", return_value=(0.03, 0.0000193)):
            correlacao = calcular_correlacao_horario_latencia(carregar_medicoes(self.csv))
            self.assertEqual(correlacao["p_valor"], 0.0000193)
            relatorio = gerar_relatorio_consolidado(self.pasta)
        self.assertIn("p-valor nominal < 0,0001", relatorio)
        self.assertNotIn("significativa", relatorio)
        self.assertIn("r próximo de zero não descarta horários ruins", relatorio)

    def test_relatorio_mostra_perda_total_sem_latencia_e_uma_resposta_sem_desvio(self):
        self.gravar("2026-10-01T10:00:00,8.8.8.8,,,100\n")
        relatorio = gerar_relatorio_consolidado(self.pasta)
        self.assertIn("100,00%", relatorio)
        self.assertIn("0 de 1 tentativas", relatorio)
        self.assertNotIn("None", relatorio)
        self.gravar("2026-10-01T10:00:00,8.8.8.8,10,,0\n")
        relatorio = gerar_relatorio_consolidado(self.pasta)
        self.assertIn("Desvio padrão amostral | —", relatorio)
        self.assertIn("Jitter mediano / P90 | — / —", relatorio)
        self.assertIn("Amostra pequena", relatorio)
        self.assertNotIn("None", relatorio)

    def test_relatorio_avisa_exclusao_de_csv_invalido_sem_perder_resumo(self):
        self.gravar("2026-10-01T10:00:00,8.8.8.8,10,,0\n")
        (self.pasta / "invalido.csv").write_text("timestamp,host\n", encoding="utf-8")
        relatorio = gerar_relatorio_consolidado(self.pasta)
        self.assertIn("## 1. Resumo", relatorio)
        self.assertIn("## Arquivos não analisados", relatorio)
        self.assertIn("não representam toda a pasta", relatorio)

    def test_relatorio_sem_arquivos_e_pdf_com_marcacao_e_logo_ausente(self):
        self.assertIn("Nenhum arquivo", gerar_relatorio_consolidado(self.pasta))
        texto = "# Relatório\n\n## Resumo\n\n### Destino\n\n#### Detalhes\n\n> **Atenção:** sem dados.\n"
        for logo_presente in (True, False):
            with self.subTest(logo_presente=logo_presente), patch("analise.gerar_relatorio.Path.is_file", return_value=logo_presente):
                self.assertTrue(exportar_relatorio_pdf(texto).startswith(b"%PDF-"))

    def test_pdf_preserva_nome_da_fonte_e_formata_texto_sem_html_arbitrario(self):
        texto = _formatar_texto_pdf("`lan_host_wifi.csv` **Resumo** _nota_ <script>")
        self.assertIn('<font name="Courier">lan_host_wifi.csv</font>', texto)
        self.assertIn("<b>Resumo</b>", texto)
        self.assertIn("<i>nota</i>", texto)
        self.assertIn("&lt;script&gt;", texto)
        self.assertNotIn("<script>", texto)

    def test_pdf_move_titulo_e_data_original_para_cabecalho(self):
        for sufixo in (".", " a partir de 2 arquivo(s) de medições."):
            conteudo = (
                "# Relatório consolidado — NetStat Monitor\n\n"
                f"Gerado automaticamente em 17/10/2026 12:34{sufixo}\n\n"
                "## 1. Resumo da conexão\n\nDados da coleta.\n"
            )
            with self.subTest(sufixo=sufixo), patch(
                "analise.gerar_relatorio._decorar_pagina_pdf", wraps=_decorar_pagina_pdf
            ) as decorar, patch("analise.gerar_relatorio.Paragraph", wraps=Paragraph) as paragrafo:
                self.assertTrue(exportar_relatorio_pdf(conteudo).startswith(b"%PDF-"))
                self.assertEqual(decorar.call_args.kwargs["data_geracao"], "17/10/2026 12:34")
                textos = [chamada.args[0] for chamada in paragrafo.call_args_list]
                self.assertIn("Dados da coleta.", textos)
                self.assertFalse(any("Gerado automaticamente" in texto or "NetStat Monitor" in texto for texto in textos))
        self.gravar("2026-10-01T10:00:00,8.8.8.8,10,,0\n")
        self.assertNotIn("a partir de", gerar_relatorio_consolidado(self.pasta))

    def test_pdf_remove_apenas_linhas_vazias_anteriores_ao_primeiro_conteudo(self):
        cabecalho = "# Relatório consolidado — NetStat Monitor\n\nGerado automaticamente em 17/10/2026 12:34.\n\n"
        for quebra in ("\n", "\r\n"):
            for prefixo in ("\n \n", cabecalho):
                conteudo = (prefixo + "## Resumo\n\nDados da coleta.").replace("\n", quebra)
                with self.subTest(quebra=repr(quebra), prefixo=prefixo), patch(
                    "analise.gerar_relatorio.SimpleDocTemplate.build"
                ) as construir:
                    exportar_relatorio_pdf(conteudo)
                    elementos = construir.call_args.args[0]
                    self.assertEqual(len(elementos), 3)
                    self.assertIsInstance(elementos[0], Paragraph)
                    self.assertIsInstance(elementos[1], Spacer)
                    self.assertIsInstance(elementos[2], Paragraph)
        for conteudo in (None, "", "\n \n"):
            with self.subTest(conteudo=conteudo), patch("analise.gerar_relatorio.SimpleDocTemplate.build") as construir:
                exportar_relatorio_pdf(conteudo)
                self.assertEqual(construir.call_args.args[0], [])

    def test_html_exporta_conteudo_salvo_com_navegacao_marca_e_data_original(self):
        texto = (
            "# Relatório consolidado — NetStat Monitor\n\n"
            "Gerado automaticamente em 17/10/2026 12:34 a partir de 2 arquivo(s) de medições.\n\n"
            "## 1. Resumo da conexão\n\n**Respostas:** 10 de 12 tentativas.\n\n"
            "## 3. Análise detalhada\n\n### WAN — 8.8.8.8\n\n"
            "| Métrica | Valor |\n|---|---|\n| Latência | `31,00 ms` |\n\n"
            "> Dados limitados.\n\n## 4. Como interpretar\n\n"
            "[SciPy](https://docs.scipy.org/)\n"
        )
        with patch("analise.gerar_relatorio.carregar_medicoes", side_effect=AssertionError("Não reler CSV")):
            html = exportar_relatorio_html(texto)
        self.assertIn('<html lang="pt-BR">', html)
        self.assertIn('src="data:image/png;base64,', html)
        self.assertEqual(html.count("Gerado automaticamente em 17/10/2026 12:34"), 1)
        self.assertNotIn("a partir de", html)
        self.assertIn('<a href="#secao-1">1. Resumo da conexão</a>', html)
        self.assertIn('<h2 id="secao-1">1. Resumo da conexão</h2>', html)
        self.assertIn('<details open><summary>WAN — 8.8.8.8</summary>', html)
        self.assertEqual(html.count("<details"), html.count("</details>"))
        self.assertIn("<b>Respostas:</b> 10 de 12 tentativas.", html)
        self.assertIn("<code>31,00 ms</code>", html)
        self.assertIn("<blockquote>Dados limitados.</blockquote>", html)
        self.assertIn('<a href="https://docs.scipy.org/">SciPy</a>', html)
        self.assertIn("<thead><tr><th>Métrica</th><th>Valor</th></tr></thead><tbody>", html.replace("\n", ""))

    def test_html_aceita_ausencias_logo_indisponivel_e_quebras_de_linha(self):
        for texto in (None, "", "\n \n"):
            with self.subTest(texto=texto), patch("analise.gerar_relatorio.Path.read_bytes", side_effect=OSError("ausente")):
                html = exportar_relatorio_html(texto)
                self.assertIn('<span class="marca">NETSTAT MONITOR</span>', html)
                self.assertIn("</body></html>", html)
                self.assertNotIn("Gerado automaticamente", html)
        texto = "## Resumo\n\nLatência: 31,25 ms.\n"
        referencia = exportar_relatorio_html(texto)
        for quebra in ("\n", "\r\n", "\r"):
            with self.subTest(quebra=repr(quebra)):
                self.assertEqual(exportar_relatorio_html(texto.replace("\n", quebra)), referencia)

    def test_html_nao_executa_marcacao_arbitraria_do_relatorio(self):
        texto = (
            '## <img src=x onerror="alert(1)">\n\n<script>alert(1)</script>\n\n'
            '| Campo | Valor |\n|---|---|\n| Código | `<svg onload="alert(1)">` |\n\n'
            '[Perigoso](javascript:alert(1))\n'
        )
        html = exportar_relatorio_html(texto)
        self.assertNotIn("<script>", html)
        self.assertNotIn("<svg", html)
        self.assertNotIn('<img src=x', html)
        self.assertNotIn('href="javascript:', html)
        self.assertIn("&lt;script&gt;", html)

    def test_grafico_html_preserva_lacunas_falhas_e_valores_da_tabela(self):
        tabela = [
            ["Hora", "Mediana (ms)", "P90 (ms)", "Sem resposta (%)"],
            ["09h–10h", "31,25", "40,50", "0,25"],
            ["11h–12h", "—", "—", "100,00"],
        ]
        for numero in (1, 2):
            with self.subTest(numero=numero), patch("plotly.graph_objects.Figure.to_html", autospec=True, return_value="<grafico>") as converter:
                self.assertEqual(_grafico_horario_html(tabela, numero), "<grafico>")
                figura = converter.call_args.args[0]
                self.assertEqual(figura.data[0].y[9], 31.25)
                self.assertEqual(figura.data[1].y[9], 40.5)
                self.assertEqual(figura.data[2].y[9], 0.25)
                self.assertIsNone(figura.data[0].y[10])
                self.assertIsNone(figura.data[2].y[10])
                self.assertIsNone(figura.data[0].y[11])
                self.assertEqual(figura.data[2].y[11], 100)
                self.assertFalse(figura.data[0].connectgaps)
                self.assertEqual(converter.call_args.kwargs["include_plotlyjs"], numero == 1)

    def test_grafico_html_ignora_tabelas_ausentes_ou_incompativeis(self):
        cabecalho = ["Hora", "Mediana (ms)", "P90 (ms)", "Sem resposta (%)"]
        for tabela in ([], [["Métrica", "Valor"]], [cabecalho],
                       [cabecalho, ["09h–10h"]], [cabecalho, ["25h–26h", "1", "2", "0"]],
                       [cabecalho, ["09h–11h", "1", "2", "0"]],
                       [cabecalho, ["09h–10h", "inválido", "2", "0"]]):
            with self.subTest(tabela=tabela):
                self.assertEqual(_grafico_horario_html(tabela, 1), "")

    def test_html_incorpora_plotly_uma_vez_sem_recursos_externos(self):
        tabela = "| Hora | Mediana (ms) | P90 (ms) | Sem resposta (%) |\n|---|---|---|---|\n| 09h–10h | 10,00 | 20,00 | 0,00 |\n"
        texto = "## 3. Análise detalhada\n\n### LAN\n\n" + tabela + "\n### WAN\n\n" + tabela
        html = exportar_relatorio_html(texto)
        self.assertEqual(html.count("plotly.js v"), 1)
        self.assertIn('id="perfil-horario-1"', html)
        self.assertIn('id="perfil-horario-2"', html)

        class Recursos(HTMLParser):
            def __init__(self):
                super().__init__()
                self.externos = []

            def handle_starttag(self, tag, attrs):
                atributos = dict(attrs)
                endereco = atributos.get("src") or (atributos.get("href") if tag == "link" else None)
                if endereco and not endereco.startswith("data:"):
                    self.externos.append(endereco)

        recursos = Recursos()
        recursos.feed(html)
        self.assertEqual(recursos.externos, [])

    def test_cache_invalida_com_medicoes_e_substituicao_mesmo_tamanho(self):
        _carregar_dados_monitor.clear()
        self.addCleanup(_carregar_dados_monitor.clear)
        self.gravar("2026-10-01T10:00:00,8.8.8.8,10,,0\n")
        with patch("paginas.recursos.carregar_medicoes", wraps=carregar_medicoes) as carregar:
            df, _ = carregar_dados_monitor(str(self.csv))
            df.loc[0, "latencia_ms"] = 999
            self.assertEqual(carregar_dados_monitor(str(self.csv))[0].iloc[0]["latencia_ms"], 10)
            self.assertEqual(carregar.call_count, 1)
            with self.csv.open("a", encoding="utf-8") as arquivo:
                arquivo.write("2026-10-01T11:00:00,8.8.8.8,20,10,0\n")
            self.assertEqual(len(carregar_dados_monitor(str(self.csv))[0]), 2)
            anterior = self.csv.stat()
            self.csv.write_text(self.csv.read_text().replace(",20,10,0", ",30,10,0"), encoding="utf-8")
            os.utime(self.csv, ns=(anterior.st_atime_ns, anterior.st_mtime_ns + 1000000000))
            self.assertEqual(carregar_dados_monitor(str(self.csv))[1]["estatisticas"]["media_ms"], 20)
            self.assertEqual(carregar.call_count, 3)
        self.csv.unlink()
        with self.assertRaises(OSError):
            carregar_dados_monitor(str(self.csv))

    def test_nomes_preservam_formato_e_codificam_ipv6(self):
        for host, tipo in [("8.8.8.8", "WiFi"), ("example-host.org", "Wi-Fi"), ("2001:4860:4860::8888", "Ethernet")]:
            with self.subTest(host=host):
                nome = Path(caminho_coleta("wan", host, tipo, str(self.pasta))).name
                self.assertNotIn(":", nome)
                metadados = extrair_metadados_nome_arquivo(nome)
                self.assertEqual(metadados["host"], host)
        self.assertEqual(Path(caminho_coleta("wan", "8.8.8.8", "WiFi")).name, "wan_8.8.8.8_wifi.csv")

    def test_host_e_rotulos_invalidos_nao_formam_caminhos(self):
        for host in [None, "", " ", "../arquivo", "a/b", "a\\b", "-n", "a b", "a:80", "a\ncomando"]:
            with self.subTest(host=host), self.assertRaises(ValueError):
                validar_host(host)
        for camada, tipo in [("invalida", "wifi"), ("wan", None), ("wan", "desconhecida")]:
            with self.subTest(camada=camada, tipo=tipo), self.assertRaises(ValueError):
                caminho_coleta(camada, "8.8.8.8", tipo)

    def test_listagem_ignora_diretorios_com_extensao(self):
        self.csv.touch()
        (self.pasta / "outro.csv").mkdir()
        self.assertEqual(listar_arquivos(self.pasta, ".csv"), [self.csv.name])
        self.assertEqual(listar_arquivos(self.pasta / "ausente", ".csv"), [])
        with patch("armazenamento.armazenamento.os.scandir", side_effect=PermissionError):
            self.assertEqual(listar_arquivos(self.pasta, ".csv"), [])

    def test_exclusao_remove_apenas_csv_e_relatorio_das_pastas_previstas(self):
        pasta_relatorios = self.pasta / "relatorios"
        pasta_relatorios.mkdir()
        self.csv.touch()
        relatorio = pasta_relatorios / "relatorio_20261019_120000.md"
        relatorio.touch()
        with patch("armazenamento.armazenamento.PASTA_DADOS", str(self.pasta)), patch(
            "armazenamento.armazenamento.PASTA_RELATORIOS", str(pasta_relatorios)
        ):
            excluir_arquivo_dados(self.csv.name, ".csv")
            excluir_arquivo_dados(relatorio.name, ".md")
        self.assertFalse(self.csv.exists())
        self.assertFalse(relatorio.exists())

    def test_exclusao_rejeita_nome_extensao_e_caminho_invalidos(self):
        pasta_relatorios = self.pasta / "relatorios"
        pasta_relatorios.mkdir()
        (self.pasta / "diretorio.csv").mkdir()
        with patch("armazenamento.armazenamento.PASTA_DADOS", str(self.pasta)), patch(
            "armazenamento.armazenamento.PASTA_RELATORIOS", str(pasta_relatorios)
        ):
            for nome, extensao in [
                (None, ".csv"), ("", ".csv"), ("../arquivo.csv", ".csv"),
                ("subpasta/arquivo.csv", ".csv"), (r"subpasta\arquivo.csv", ".csv"),
                ("arquivo.txt", ".csv"), ("arquivo.csv", ".txt"),
                ("diretorio.csv", ".csv"),
            ]:
                with self.subTest(nome=nome, extensao=extensao), self.assertRaises(ValueError):
                    excluir_arquivo_dados(nome, extensao)
            with self.assertRaises(FileNotFoundError):
                excluir_arquivo_dados("ausente.csv", ".csv")

    def test_falha_de_exclusao_preserva_arquivo(self):
        self.csv.touch()
        with patch("armazenamento.armazenamento.PASTA_DADOS", str(self.pasta)), patch(
            "armazenamento.armazenamento.os.remove", side_effect=PermissionError("sem acesso")
        ), self.assertRaises(PermissionError):
            excluir_arquivo_dados(self.csv.name, ".csv")
        self.assertTrue(self.csv.exists())

    def test_simulador_usa_o_mesmo_esquema(self):
        medicoes = gerar_medicoes_simuladas("8.8.8.8", 4, 10, 0, probabilidade_falha=1)
        salvar_csv(medicoes, str(self.csv))
        self.assertEqual(carregar_medicoes(self.csv).columns.tolist(), CAMPOS)
        self.assertEqual(resumir_medicoes(carregar_medicoes(self.csv))["perda_total"], 100)
        self.assertEqual(gerar_medicoes_simuladas("8.8.8.8", 0, 10, 0), [])

    def test_exportacao_markdown_pdf_e_html(self):
        texto = "# Relatório\n\nTeste de exportação.\n"
        caminho = salvar_relatorio(texto, str(self.pasta / "relatorios"))
        self.assertEqual(Path(caminho).read_text(encoding="utf-8"), texto)
        self.assertTrue(exportar_relatorio_pdf(texto).startswith(b"%PDF-"))
        for funcao, nome in [
            (gerar_grafico_serie_temporal, "serie.html"),
            (gerar_grafico_taxa_perda_pacotes, "perda.html"),
        ]:
            saida = self.pasta / "graficos" / nome
            funcao(medicoes_vazias(), caminho_saida=str(saida))
            self.assertIn("plotly", saida.read_text(encoding="utf-8"))

    def test_exportacao_pdf_aceita_tabela_acentos_e_conteudo_ausente(self):
        texto = (
            "# Relatório consolidado — NetStat Monitor\n\n"
            "| Métrica | Valor |\n|---|---|\n| Latência média | `10 ms` |\n"
        )
        for conteudo in (texto, "", None):
            with self.subTest(conteudo=conteudo):
                self.assertTrue(exportar_relatorio_pdf(conteudo).startswith(b"%PDF-"))

    def test_agregacao_de_jitter_e_janelas_sem_tentativas(self):
        df = pd.DataFrame({
            "timestamp": pd.to_datetime(["2026-10-01 10:00:00", "2026-10-01 10:02:00"]),
            "latencia_ms": [10, None], "jitter_ms": [2, 4],
        })
        self.assertEqual(agregar_por_intervalo(df, "5min", "jitter_ms")["jitter_ms"].tolist(), [3])
        taxas = calcular_taxa_perda_por_janela(df, "1min")["perda_pct_na_janela"]
        self.assertEqual(taxas.iloc[0], 0)
        self.assertTrue(pd.isna(taxas.iloc[1]))
        self.assertEqual(taxas.iloc[2], 100)


class CaminhosTest(unittest.TestCase):
    def resolver(self, plataforma, ambiente=None, **variaveis):
        from armazenamento.armazenamento import obter_pasta_dados

        env = dict(variaveis)
        if ambiente is not None:
            env["NETSTAT_AMBIENTE"] = ambiente
        with patch.dict(os.environ, env, clear=True), patch("sys.platform", plataforma), patch("pathlib.Path.home", return_value=self.home):
            return Path(obter_pasta_dados())

    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporario.cleanup)
        self.home = Path(self.temporario.name)

    def test_perfis_windows_linux_macos(self):
        for plataforma, base, dev, prod in (
            ("win32", self.home / "AppData" / "Local", "NetStat-Dev", "NetStat"),
            ("linux", self.home / ".local" / "share", "netstat-dev", "netstat"),
            ("darwin", self.home / "Library" / "Application Support", "NetStat-Dev", "NetStat"),
        ):
            for ambiente, nome in ((None, dev), ("", dev), ("desenvolvimento", dev), ("producao", prod)):
                with self.subTest(plataforma=plataforma, ambiente=ambiente):
                    destino = self.resolver(plataforma, ambiente)
                    self.assertEqual(destino, base / nome / "dados")
                    self.assertFalse(destino.exists())

    def test_variaveis_da_plataforma_e_fallbacks(self):
        for plataforma, variavel, nome in (("win32", "LOCALAPPDATA", "NetStat-Dev"), ("linux", "XDG_DATA_HOME", "netstat-dev")):
            with self.subTest(plataforma=plataforma):
                self.assertEqual(self.resolver(plataforma, **{variavel: str(self.home)}), self.home / nome / "dados")
                for valor in ("", "relativo"):
                    self.assertEqual(self.resolver(plataforma, **{variavel: valor}), self.resolver(plataforma))

    def test_destino_personalizado_absoluto_tem_precedencia(self):
        for plataforma in ("win32", "linux", "darwin"):
            with self.subTest(plataforma=plataforma):
                self.assertEqual(self.resolver(plataforma, "invalido", NETSTAT_PASTA_DADOS=str(self.home)), self.home)
                self.assertEqual(self.resolver(plataforma, NETSTAT_PASTA_DADOS=""), self.resolver(plataforma))
                with self.assertRaises(ValueError):
                    self.resolver(plataforma, NETSTAT_PASTA_DADOS="dados")
                with self.assertRaises(ValueError):
                    self.resolver(plataforma, "invalido")

    def test_defaults_gravam_no_destino_configurado(self):
        pasta = self.home / "destino"
        relatorios = pasta / "relatorios"
        with patch("armazenamento.armazenamento.PASTA_DADOS", str(pasta)), patch("analise.gerar_relatorio.PASTA_DADOS", str(pasta)), patch("analise.gerar_relatorio.PASTA_RELATORIOS", str(relatorios)):
            self.assertIn("Nenhum arquivo", gerar_relatorio_consolidado(None))
            csv = ArmazenamentoCSV()
            self.assertEqual(Path(csv.caminho_arquivo), pasta / "medicoes.csv")
            self.assertEqual(Path(caminho_coleta("wan", "8.8.8.8", "WiFi", None)).parent, pasta)
            self.assertEqual(Path(salvar_relatorio("teste", None)).parent, relatorios)
            self.assertIn("medicoes.csv", gerar_relatorio_consolidado(None))


if __name__ == "__main__":
    unittest.main()
