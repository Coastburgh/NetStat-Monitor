import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]


class PontosEntradaTest(unittest.TestCase):
    def test_dados_contem_apenas_csvs(self):
        codigo = """
from pathlib import Path
from armazenamento.armazenamento import PASTA_APLICATIVO, PASTA_DADOS, PASTA_RELATORIOS, PASTA_GRAFICOS, ArmazenamentoCSV
from paginas.recursos import obter_controlador
from analise.gerar_relatorio import salvar_relatorio
from desktop import instancia_unica, registrar_logs

raiz = Path(PASTA_APLICATIVO)
assert Path(PASTA_DADOS) == raiz / 'dados'
assert Path(PASTA_RELATORIOS) == raiz / 'relatorios'
assert Path(PASTA_GRAFICOS) == raiz / 'graficos'
ArmazenamentoCSV()
obter_controlador().atualizar_configuracao({'wan': '1.1.1.1'})
salvar_relatorio('teste')
with instancia_unica(raiz) as adquirida, registrar_logs(raiz) as log:
    assert adquirida
    assert log == raiz / 'logs' / 'netstat.log'
assert (raiz / 'configuracao.json').is_file()
assert (raiz / '.desktop.lock').is_file()
assert all(p.is_file() and p.suffix == '.csv' for p in Path(PASTA_DADOS).iterdir())
"""
        with tempfile.TemporaryDirectory() as pasta:
            resultado = self.executar(pasta, "-c", codigo)
            self.assertEqual(resultado.returncode, 0, resultado.stderr)

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
            self.assertEqual(len(list((Path(pasta) / "relatorios").glob("*.md"))), 1)
            self.assertEqual(len(list((Path(pasta) / "graficos").glob("*.html"))), 3)

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

    def test_configuracao_persiste_entre_processos_independentes(self):
        with tempfile.TemporaryDirectory() as pasta:
            salvar = self.executar(
                pasta, "-c", "from paginas.recursos import obter_controlador; "
                "obter_controlador().atualizar_configuracao({'wan': '1.1.1.1', 'intervalo': 12.0})",
            )
            self.assertEqual(salvar.returncode, 0, salvar.stderr)
            self.assertTrue((Path(pasta) / "configuracao.json").is_file())
            restaurar = self.executar(
                pasta, "-c", "from paginas.recursos import obter_controlador; "
                "controle = obter_controlador(); "
                "assert controle.ler_configuracao()['wan'] == '1.1.1.1'; "
                "assert controle.ler_configuracao()['intervalo'] == 12.0; "
                "assert controle.camadas_ativas() == []",
            )
            self.assertEqual(restaurar.returncode, 0, restaurar.stderr)

    def test_saida_normal_do_python_aguarda_parada_da_coleta(self):
        codigo = """
import atexit
import threading
from coletor.ping_collector import PingCollector
from paginas.recursos import obter_controlador

def verificar():
    if controle.camadas_ativas():
        raise RuntimeError('A coleta permaneceu ativa.')
    print('coleta_encerrada')

atexit.register(verificar)
controle = obter_controlador()
mediu = threading.Event()

def medir(coletor):
    mediu.set()
    return dict(host=coletor.host, latencia_ms=10, jitter_ms=None, perda_pacotes_pct=0)

PingCollector.coletar_uma_medicao = medir
controle.iniciar({'wan': '8.8.8.8'}, 'wifi', 30)
assert mediu.wait(2)
"""
        with tempfile.TemporaryDirectory() as pasta:
            resultado = self.executar(pasta, "-c", codigo)
            self.assertEqual(resultado.returncode, 0, resultado.stderr)
            self.assertIn("coleta_encerrada", resultado.stdout)
            self.assertNotIn("Exception ignored in atexit", resultado.stderr)

    def test_sinal_de_encerramento_pode_ser_tratado_na_thread_principal(self):
        codigo = """
import signal
import threading

recebidos = []
signal.signal(signal.SIGINT, lambda sinal, frame: recebidos.append(sinal))
thread = threading.Thread(target=lambda: signal.raise_signal(signal.SIGINT))
thread.start()
thread.join(2)
assert not thread.is_alive()
assert recebidos == [signal.SIGINT]
"""
        with tempfile.TemporaryDirectory() as pasta:
            resultado = self.executar(pasta, "-c", codigo)
            self.assertEqual(resultado.returncode, 0, resultado.stderr)

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
