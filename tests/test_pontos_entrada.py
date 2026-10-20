import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]


class PontosEntradaTest(unittest.TestCase):
    def executar(self, pasta, *argumentos):
        ambiente = {**os.environ, "PYTHONPATH": str(RAIZ), "PYTHONIOENCODING": "utf-8", "NETSTAT_PASTA_DADOS": str(Path(pasta) / "dados")}
        return subprocess.run(
            [sys.executable, *argumentos], cwd=pasta, env=ambiente,
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )

    def test_simulador_por_caminho_e_modulos_de_analise_e_exportacao(self):
        with tempfile.TemporaryDirectory() as pasta:
            resultado = self.executar(pasta, str(RAIZ / "scripts" / "gerar_dados_simulados.py"))
            self.assertEqual(resultado.returncode, 0, resultado.stderr)
            self.assertEqual(len(list((Path(pasta) / "dados").glob("*.csv"))), 4)
            for modulo in ["analise.estatisticas", "analise.gerar_relatorio", "visualizacao.graficos"]:
                with self.subTest(modulo=modulo):
                    resultado = self.executar(pasta, "-m", modulo)
                    self.assertEqual(resultado.returncode, 0, resultado.stderr)
                    self.assertTrue(resultado.stdout)
            self.assertEqual(len(list((Path(pasta) / "dados/relatorios").glob("*.md"))), 1)
            self.assertEqual(len(list((Path(pasta) / "dados/graficos").glob("*.html"))), 3)

    def test_destino_nao_muda_com_diretorio_de_execucao(self):
        with tempfile.TemporaryDirectory() as pasta:
            outra = Path(pasta) / "outra"
            outra.mkdir()
            codigo = (
                "import os; from armazenamento.armazenamento import PASTA_DADOS, ArmazenamentoCSV; "
                f"os.chdir({str(outra)!r}); "
                "arquivo = ArmazenamentoCSV(); print(arquivo.caminho_arquivo)"
            )
            resultado = self.executar(pasta, "-c", codigo)
            self.assertEqual(resultado.returncode, 0, resultado.stderr)
            destino = Path(pasta) / "dados" / "medicoes.csv"
            self.assertEqual(Path(resultado.stdout.strip()), destino)
            self.assertTrue(destino.is_file())
            self.assertFalse((outra / "dados").exists())

    def test_modulos_sem_dados_exibem_mensagem_sem_traceback(self):
        with tempfile.TemporaryDirectory() as pasta:
            for modulo in ["analise.estatisticas", "visualizacao.graficos"]:
                with self.subTest(modulo=modulo):
                    resultado = self.executar(pasta, "-m", modulo)
                    self.assertEqual(resultado.returncode, 1)
                    self.assertIn("Não foi possível carregar", resultado.stdout)
                    self.assertNotIn("Traceback", resultado.stderr)
            resultado = self.executar(pasta, "-m", "analise.gerar_relatorio")
            self.assertEqual(resultado.returncode, 0, resultado.stderr)
            self.assertIn("Nenhum arquivo", resultado.stdout)


if __name__ == "__main__":
    unittest.main()
