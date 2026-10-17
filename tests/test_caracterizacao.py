import hashlib
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from analise.estatisticas import (
    calcular_estatisticas_descritivas,
    carregar_medicoes,
    detectar_outliers_iqr,
)
from analise.gerar_relatorio import gerar_relatorio_consolidado
from coletor.ping_collector import PingCollector
from visualizacao.graficos import (
    calcular_perda_pacotes_total,
    calcular_taxa_perda_por_janela,
    gerar_grafico_serie_temporal,
)


CSV = (
    "timestamp,host,latencia_ms,jitter_ms,perda_pacotes_pct\n"
    "2026-10-01T10:00:00,8.8.8.8,10,,0\n"
    "2026-10-01T11:00:00,8.8.8.8,12,2,0\n"
    "2026-10-01T12:00:00,8.8.8.8,,,33.33\n"
    "2026-10-01T13:00:00,8.8.8.8,11,1,25\n"
    "2026-10-01T14:00:00,8.8.8.8,10,1,20\n"
    "2026-10-01T15:00:00,8.8.8.8,100,90,16.67\n"
)


class CaracterizacaoTest(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.caminho = Path(self.pasta.name) / "wan_8.8.8.8_wifi.csv"
        self.caminho.write_text(CSV, encoding="utf-8")

    def test_relatorio_integral_permanece_identico(self):
        with patch("analise.gerar_relatorio.datetime") as relogio:
            relogio.now.return_value = datetime(2026, 10, 17, 12)
            relatorio = gerar_relatorio_consolidado(self.pasta.name)
        # Assinatura do Markdown produzido antes da reescrita, com relógio fixo.
        self.assertEqual(
            hashlib.sha256(relatorio.encode()).hexdigest(),
            "72115dc49704c7e86cc5bf9484f1e5e03e733a151c3bd8d548c8902af4a17d01",
        )

    def test_estatisticas_e_outliers_usam_dados_brutos(self):
        df = carregar_medicoes(self.caminho)
        estatisticas = calcular_estatisticas_descritivas(df)
        self.assertEqual(estatisticas["quantidade_amostras"], 5)
        self.assertEqual(estatisticas["media_ms"], 28.6)
        self.assertEqual(estatisticas["desvio_padrao_ms"], 39.92)
        self.assertEqual(detectar_outliers_iqr(df)["latencia_ms"].tolist(), [100])
        self.assertEqual(calcular_perda_pacotes_total(df), 16.67)
        figura = gerar_grafico_serie_temporal(
            df, agregacao="1D", destacar_outliers=True, salvar_arquivo=False,
        )
        self.assertEqual(list(figura.data[0].y), [28.6])
        self.assertEqual(list(figura.data[1].y), [100])
        self.assertEqual(len(figura.layout.shapes), 2)

    def test_perda_por_janela_independe_do_contador_cumulativo(self):
        df = pd.DataFrame({
            "timestamp": pd.to_datetime([
                "2026-10-01 10:00:00", "2026-10-01 10:00:05", "2026-10-01 10:01:00",
            ]),
            "latencia_ms": [10, None, 11],
            "perda_pacotes_pct": [0, 50, 0],
        })
        self.assertEqual(
            calcular_taxa_perda_por_janela(df, "1min")["perda_pct_na_janela"].tolist(),
            [50.0, 0.0],
        )

    def test_jitter_preserva_ultima_resposta_valida_apos_falha(self):
        coletor = PingCollector("8.8.8.8")
        saidas = ["time=10ms", "Request timed out.", "tempo=14ms"]
        with patch("coletor.ping_collector.subprocess.run") as executar:
            executar.side_effect = [SimpleNamespace(stdout=s) for s in saidas]
            medicoes = [coletor.coletar_uma_medicao() for _ in saidas]
        self.assertIsNone(medicoes[0]["jitter_ms"])
        self.assertIsNone(medicoes[1]["jitter_ms"])
        self.assertEqual(medicoes[2]["jitter_ms"], 4)
        self.assertEqual(medicoes[2]["perda_pacotes_pct"], 33.33)

    def test_formatos_de_ping(self):
        coletor = PingCollector("8.8.8.8")
        for saida, esperado in [
            ("Resposta de 8.8.8.8: bytes=32 tempo=12ms TTL=114", 12),
            ("Reply from 8.8.8.8: bytes=32 time<1ms TTL=114", 1),
            ("64 bytes from 8.8.8.8: icmp_seq=1 ttl=57 time=12.34 ms", 12.34),
            ("64 bytes from 8.8.8.8: icmp_seq=0 ttl=57 time=5.123 ms", 5.12),
            ("", None),
            ("Request timeout for icmp_seq 0", None),
        ]:
            with self.subTest(saida=saida):
                self.assertEqual(coletor._extrair_latencia_ms(saida), esperado)


if __name__ == "__main__":
    unittest.main()
