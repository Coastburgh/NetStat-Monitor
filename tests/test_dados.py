import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from analise.estatisticas import (
    calcular_correlacao_horario_latencia,
    calcular_estatisticas_descritivas,
    carregar_medicoes,
    medicoes_vazias,
    resumir_medicoes,
)
from analise.gerar_relatorio import gerar_relatorio_consolidado, salvar_relatorio
from armazenamento.armazenamento import (
    ArmazenamentoCSV,
    CAMPOS,
    caminho_coleta,
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

    def test_simulador_usa_o_mesmo_esquema(self):
        medicoes = gerar_medicoes_simuladas("8.8.8.8", 4, 10, 0, probabilidade_falha=1)
        salvar_csv(medicoes, str(self.csv))
        self.assertEqual(carregar_medicoes(self.csv).columns.tolist(), CAMPOS)
        self.assertEqual(resumir_medicoes(carregar_medicoes(self.csv))["perda_total"], 100)
        self.assertEqual(gerar_medicoes_simuladas("8.8.8.8", 0, 10, 0), [])

    def test_exportacao_markdown_e_html(self):
        texto = "# Relatório\n\nTeste de exportação.\n"
        caminho = salvar_relatorio(texto, str(self.pasta / "relatorios"))
        self.assertEqual(Path(caminho).read_text(encoding="utf-8"), texto)
        for funcao, nome in [
            (gerar_grafico_serie_temporal, "serie.html"),
            (gerar_grafico_taxa_perda_pacotes, "perda.html"),
        ]:
            saida = self.pasta / "graficos" / nome
            funcao(medicoes_vazias(), caminho_saida=str(saida))
            self.assertIn("plotly", saida.read_text(encoding="utf-8"))

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


if __name__ == "__main__":
    unittest.main()
