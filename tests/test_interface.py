import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from armazenamento.armazenamento import CAMPOS
from paginas.recursos import _carregar_dados_monitor, obter_controlador


APP = Path(__file__).resolve().parents[1] / "app.py"


class InterfaceTest(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporario.cleanup)
        self.anterior = Path.cwd()
        os.chdir(self.temporario.name)
        self.addCleanup(os.chdir, self.anterior)
        pasta_dados = str(Path(self.temporario.name) / "dados")
        for modulo in ("armazenamento.armazenamento", "analise.gerar_relatorio"):
            for campo, valor in (("PASTA_DADOS", pasta_dados), ("PASTA_RELATORIOS", str(Path(pasta_dados) / "relatorios"))):
                substituicao = patch(f"{modulo}.{campo}", valor)
                substituicao.start()
                self.addCleanup(substituicao.stop)
        self.logo = patch("streamlit.logo")
        self.logo.start()
        self.addCleanup(self.logo.stop)
        obter_controlador.clear()
        self.addCleanup(obter_controlador.clear)
        self.addCleanup(_carregar_dados_monitor.clear)
        self.addCleanup(lambda: obter_controlador().parar())

    def app(self):
        return AppTest.from_file(str(APP), default_timeout=15)

    def csv(self, linhas=None):
        caminho = Path("dados/wan_8.8.8.8_wifi.csv")
        caminho.parent.mkdir(exist_ok=True)
        caminho.write_text(
            ",".join(CAMPOS) + "\n" + (
                "2026-10-01T12:00:00,8.8.8.8,30,20,0\n"
                "2026-10-01T10:00:00,8.8.8.8,10,,0\n"
                if linhas is None else linhas
            ), encoding="utf-8",
        )
        return caminho

    def test_logos_usam_recursos_do_projeto_fora_da_pasta_de_execucao(self):
        with patch("streamlit.logo") as logo:
            at = self.app().run()
        self.assertFalse(at.exception)
        principal = Path(logo.call_args.args[0])
        icone = Path(logo.call_args.kwargs["icon_image"])
        for caminho in (principal, icone):
            self.assertTrue(caminho.is_absolute())
            self.assertEqual(caminho.parent, APP.parent / "assets")
            self.assertTrue(caminho.is_file())

    def test_nova_sessao_pode_abrir_relatorio_diretamente(self):
        at = self.app().switch_page("paginas/relatorio.py").run()
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state.coleta_ativa, False)
        self.assertTrue(at.button(key="gerar").disabled)
        self.assertTrue(at.button(key="encerrar"))

    def test_configuracao_persiste_na_navegacao_e_nova_aba(self):
        at = self.app().run()
        self.assertFalse(at.exception)
        at.text_input(key="wan_destino_input").set_value("8.8.8.8").run()
        at.number_input(key="intervalo_input").set_value(9).run()
        at.switch_page("paginas/relatorio.py").run()
        at.switch_page("paginas/monitor.py").run()
        self.assertFalse(at.exception)
        self.assertEqual(at.text_input(key="wan_destino_input").value, "8.8.8.8")
        novo = self.app().run()
        self.assertFalse(novo.exception)
        self.assertEqual(novo.number_input(key="intervalo_input").value, 9)
        self.assertEqual(novo.text_input(key="wan_destino_input").value, "8.8.8.8")

    def test_recriacao_dos_widgets_reenvia_valores_ao_navegador(self):
        obter_controlador().atualizar_configuracao({
            "lan": "192.168.1.1", "man": "1.1.1.1", "wan": "8.8.8.8",
            "tipo_conexao": "Ethernet", "intervalo": 9.0,
        })
        at = self.app().run()
        for etapa in ["nova_execucao", "retorno_do_relatorio"]:
            if etapa == "retorno_do_relatorio":
                at.switch_page("paginas/relatorio.py").run()
                at.run()
                at.switch_page("paginas/monitor.py").run()
            else:
                at.run()
            with self.subTest(etapa=etapa):
                self.assertFalse(at.exception)
                for chave, valor in [
                    ("lan_gateway_input", "192.168.1.1"),
                    ("man_provedor_input", "1.1.1.1"),
                    ("wan_destino_input", "8.8.8.8"),
                ]:
                    campo = at.text_input(key=chave)
                    # Um componente remontado usa o default se o servidor não
                    # transmitir explicitamente o valor restaurado.
                    self.assertEqual(campo.proto.value if campo.proto.set_value else campo.proto.default, valor)

    def test_edicoes_manuais_atualizam_apenas_o_campo_editado(self):
        esperado = {
            "lan": "192.168.1.1", "man": "1.1.1.1", "wan": "8.8.8.8",
            "tipo_conexao": "Ethernet", "intervalo": 9.0, "automatica": False,
        }
        obter_controlador().atualizar_configuracao(esperado)
        at = self.app().run()
        for tipo, chave, campo, valor in [
            ("text_input", "lan_gateway_input", "lan", ""),
            ("text_input", "man_provedor_input", "man", "9.9.9.9"),
            ("text_input", "wan_destino_input", "wan", "example.org"),
            ("selectbox", "tipo_conexao_input", "tipo_conexao", "WiFi"),
            ("number_input", "intervalo_input", "intervalo", 12.0),
        ]:
            with self.subTest(campo=campo):
                getattr(at, tipo)(key=chave).set_value(valor).run()
                esperado[campo] = valor
                self.assertFalse(at.exception)
                self.assertEqual(obter_controlador().ler_configuracao(), esperado)
                self.assertEqual(getattr(at, tipo)(key=chave).value, valor)

    def test_estado_vazio_dos_widgets_nao_apaga_configuracao_salva(self):
        esperado = {
            "lan": "192.168.1.1", "man": "1.1.1.1", "wan": "8.8.8.8",
            "tipo_conexao": "Ethernet", "intervalo": 9.0, "automatica": True,
        }
        obter_controlador().atualizar_configuracao(esperado)
        at = self.app()
        for chave in ["lan_gateway_input", "man_provedor_input", "wan_destino_input"]:
            at.session_state[chave] = ""
        at.session_state["tipo_conexao_input"] = "WiFi"
        at.session_state["intervalo_input"] = 5.0
        at.run()
        self.assertFalse(at.exception)
        self.assertEqual(obter_controlador().ler_configuracao(), esperado)
        self.assertEqual(at.text_input(key="wan_destino_input").value, esperado["wan"])

    def test_configuracao_automatica_e_limpeza_sem_chaves_duplicadas(self):
        with patch("coletor.deteccao_rede.detectar_hosts_camadas", return_value={"lan_gateway": "192.168.1.1", "man_provedor": None, "wan_destino": "8.8.8.8"}), patch("coletor.deteccao_rede.detectar_tipo_conexao", return_value="ethernet"):
            at = self.app().run()
            at.button(key="bold").click().run()
        self.assertFalse(at.exception)
        self.assertEqual(at.text_input(key="lan_gateway_input").value, "192.168.1.1")
        self.assertEqual(at.selectbox(key="tipo_conexao_input").value, "Ethernet")
        at.button(key="bold2").click().run()
        self.assertFalse(at.exception)
        self.assertEqual(at.text_input(key="wan_destino_input").value, "")
        self.assertEqual(at.number_input(key="intervalo_input").value, 5)

    def test_deteccao_sem_resultado_preserva_tipo_selecionado(self):
        at = self.app().run()
        at.selectbox(key="tipo_conexao_input").set_value("Ethernet").run()
        with patch("coletor.deteccao_rede.detectar_hosts_camadas", return_value={}), patch("coletor.deteccao_rede.detectar_tipo_conexao", return_value=None):
            at.button(key="bold").click().run()
        self.assertFalse(at.exception)
        self.assertEqual(at.selectbox(key="tipo_conexao_input").value, "Ethernet")
        self.assertEqual(at.text_input(key="wan_destino_input").value, "8.8.8.8")

    def test_host_vazio_e_invalido_exibem_erro(self):
        at = self.app().run()
        for host in ["", "../arquivo"]:
            with self.subTest(host=host):
                at.text_input(key="wan_destino_input").set_value(host).run()
                at.button(key="bold1").click().run()
                self.assertFalse(at.exception)
                self.assertTrue(at.error)
                self.assertFalse(obter_controlador().camadas_ativas())

    def test_iniciar_parar_reencontrar_coleta_e_preservar_controles(self):
        with patch("coletor.ping_collector.subprocess.run", return_value=SimpleNamespace(stdout="time=10ms")):
            at = self.app().run()
            at.text_input(key="wan_destino_input").set_value("8.8.8.8").run()
            at.button(key="bold1").click().run()
            self.assertFalse(at.exception)
            self.assertTrue(at.session_state.coleta_ativa)
            self.assertEqual(at.button(key="bold1").label, "Parar Coleta")
            self.assertTrue(at.text_input(key="wan_destino_input").disabled)
            novo = self.app().run()
            self.assertFalse(novo.exception)
            self.assertTrue(novo.session_state.coleta_ativa)
            novo.button(key="bold1").click().run()
            self.assertFalse(novo.exception)
            self.assertFalse(novo.session_state.coleta_ativa)
            self.assertFalse(obter_controlador().camadas_ativas())

    def test_configuracao_automatica_persiste_apos_parada_e_navegacoes(self):
        esperado = {
            "lan": "192.168.1.1", "man": "1.1.1.1", "wan": "8.8.8.8",
            "tipo_conexao": "Ethernet", "intervalo": 9.0, "automatica": True,
        }
        with patch("coletor.deteccao_rede.detectar_hosts_camadas", return_value={
            "lan_gateway": esperado["lan"], "man_provedor": esperado["man"],
            "wan_destino": esperado["wan"],
        }), patch("coletor.deteccao_rede.detectar_tipo_conexao", return_value="ethernet"), patch("coletor.ping_collector.subprocess.run", return_value=SimpleNamespace(stdout="time=10ms")):
            at = self.app().run()
            at.button(key="bold").click().run()
            at.number_input(key="intervalo_input").set_value(9.0).run()
            for ciclo in range(2):
                at.button(key="bold1").click().run()
                at.run()
                at.button(key="bold1").click().run()
                at.run()
                for repeticao in range(2):
                    at.switch_page("paginas/relatorio.py").run()
                    at.run()
                    at.switch_page("paginas/monitor.py").run()
                    with self.subTest(ciclo=ciclo, repeticao=repeticao):
                        self.assertFalse(at.exception)
                        self.assertEqual(at.text_input(key="lan_gateway_input").value, esperado["lan"])
                        self.assertEqual(at.text_input(key="man_provedor_input").value, esperado["man"])
                        self.assertEqual(at.text_input(key="wan_destino_input").value, esperado["wan"])
                        self.assertEqual(at.selectbox(key="tipo_conexao_input").value, esperado["tipo_conexao"])
                        self.assertEqual(at.number_input(key="intervalo_input").value, esperado["intervalo"])
                        self.assertEqual(obter_controlador().ler_configuracao(), esperado)

    def test_metricas_e_janela_nao_restringem_estatisticas(self):
        self.csv()
        at = self.app().run()
        self.assertFalse(at.exception)
        self.assertEqual(at.metric[0].value, "30.00 ms")
        self.assertEqual(at.metric[1].value, "20.0 ms")
        self.assertEqual(at.metric[4].value, "2")
        self.assertEqual(len(at.get("plotly_chart")), 3)
        at.toggle[0].set_value(True).run()
        self.assertFalse(at.exception)
        self.assertEqual(len(at.get("plotly_chart")), 3)

    def test_csv_vazio_todas_falhas_e_invalido_nao_derrubam_pagina(self):
        for linhas in ["", "2026-10-01T10:00:00,8.8.8.8,,,100\n", "data-invalida,8.8.8.8,10,,0\n"]:
            with self.subTest(linhas=linhas):
                self.csv(linhas)
                at = self.app().run()
                self.assertFalse(at.exception)
                if linhas.startswith("data-invalida"):
                    self.assertTrue(at.warning)
                else:
                    self.assertEqual(at.metric[0].value, "—")
                    self.assertEqual(at.metric[4].value, "0")

    def test_exclusao_de_csv_exige_confirmacao_e_atualiza_estado_vazio(self):
        caminho = self.csv()
        at = self.app().run()
        at.button(key="excluir_csv").click().run()
        self.assertTrue(caminho.exists())
        self.assertEqual(at.warning[-1].value, "Tem certeza? Isso não pode ser desfeito.")
        at.button(key="cancelar_exclusao_csv").click().run()
        self.assertTrue(caminho.exists())
        at.button(key="excluir_csv").click().run()
        at.button(key="confirmar_exclusao_csv").click().run()
        self.assertFalse(at.exception)
        self.assertFalse(caminho.exists())
        self.assertEqual(at.toast[-1].value, f"Arquivo `{caminho.name}` excluído.")
        self.assertEqual(at.toast[-1].duration, 5)
        self.assertIn("Nenhum arquivo de dados", at.info[-1].value)
        self.assertTrue(at.button(key="gerar").disabled)

    def test_exclusao_de_csv_fica_desabilitada_durante_coleta(self):
        self.csv()
        with patch("coletor.ping_collector.subprocess.run", return_value=SimpleNamespace(stdout="time=10ms")):
            at = self.app().run()
            at.text_input(key="wan_destino_input").set_value("8.8.8.8").run()
            at.button(key="bold1").click().run()
            self.assertTrue(at.button(key="excluir_csv").disabled)

    def test_falha_ao_excluir_csv_exibe_erro_e_preserva_arquivo(self):
        caminho = self.csv()
        at = self.app().run()
        at.button(key="excluir_csv").click().run()
        with patch("armazenamento.armazenamento.os.remove", side_effect=PermissionError("sem acesso")):
            at.button(key="confirmar_exclusao_csv").click().run()
        self.assertFalse(at.exception)
        self.assertTrue(caminho.exists())
        self.assertIn("Não foi possível excluir o arquivo", at.toast[-1].value)
        self.assertEqual(at.toast[-1].duration, 5)

    def test_gerar_visualizar_e_exportar_relatorio(self):
        self.csv()
        at = self.app().run()
        at.button(key="gerar").click().run()
        self.assertFalse(at.exception)
        self.assertEqual(at.header[0].value, "Preview Relatório Consolidado")
        self.assertEqual(len(at.get("download_button")), 3)
        self.assertEqual(
            [botao.label for botao in at.get("download_button")],
            ["Markdown (.md)", "PDF (.pdf)", "HTML (.html)"],
        )
        self.assertIn("Relatório consolidado", at.markdown[-1].value)
        self.assertEqual(len(list(Path("dados/relatorios").glob("*.md"))), 1)

    def test_falha_na_exportacao_pdf_mantem_markdown_disponivel(self):
        pasta = Path("dados/relatorios")
        pasta.mkdir(parents=True)
        (pasta / "relatorio_20261017_120001.md").write_text("# Relatório", encoding="utf-8")
        with patch(
            "analise.gerar_relatorio.exportar_relatorio_pdf",
            side_effect=ValueError("inválido"),
        ):
            at = self.app().switch_page("paginas/relatorio.py").run()
        self.assertFalse(at.exception)
        self.assertTrue(at.warning)
        self.assertEqual(
            [botao.label for botao in at.get("download_button")],
            ["Markdown (.md)", "HTML (.html)"],
        )

    def test_falha_na_exportacao_html_mantem_outros_formatos_disponiveis(self):
        pasta = Path("dados/relatorios")
        pasta.mkdir(parents=True)
        (pasta / "relatorio_20261017_120001.md").write_text("# Relatório", encoding="utf-8")
        with patch("analise.gerar_relatorio.exportar_relatorio_html", side_effect=ValueError("inválido")):
            at = self.app().switch_page("paginas/relatorio.py").run()
        self.assertFalse(at.exception)
        self.assertIn("Não foi possível gerar o HTML", at.warning[-1].value)
        self.assertEqual(
            [botao.label for botao in at.get("download_button")],
            ["Markdown (.md)", "PDF (.pdf)"],
        )

    def test_relatorios_no_mesmo_minuto_permanecem_acessiveis(self):
        pasta = Path("dados/relatorios")
        pasta.mkdir(parents=True)
        nomes = ["relatorio_20261017_120001.md", "relatorio_20261017_120059.md"]
        for nome in nomes:
            (pasta / nome).write_text(nome, encoding="utf-8")
        at = self.app().switch_page("paginas/relatorio.py").run()
        self.assertFalse(at.exception)
        self.assertEqual(len(at.selectbox[0].options), 2)
        self.assertEqual(at.markdown[-1].value, nomes[1])
        at.selectbox[0].set_value(nomes[0]).run()
        self.assertFalse(at.exception)
        self.assertEqual(at.markdown[-1].value, nomes[0])

    def test_exclusao_de_relatorio_remove_selecionado_e_mantem_restante(self):
        pasta = Path("dados/relatorios")
        pasta.mkdir(parents=True)
        nomes = ["relatorio_20261017_120001.md", "relatorio_20261017_120059.md"]
        for nome in nomes:
            (pasta / nome).write_text(nome, encoding="utf-8")
        at = self.app().switch_page("paginas/relatorio.py").run()
        at.button(key="excluir_relatorio").click().run()
        self.assertTrue((pasta / nomes[1]).exists())
        self.assertEqual(at.warning[-1].value, "Tem certeza? Isso não pode ser desfeito.")
        at.button(key="confirmar_exclusao_relatorio").click().run()
        self.assertFalse(at.exception)
        self.assertFalse((pasta / nomes[1]).exists())
        self.assertTrue((pasta / nomes[0]).exists())
        self.assertEqual(at.toast[-1].value, f"Relatório `{nomes[1]}` excluído.")
        self.assertEqual(at.toast[-1].duration, 5)
        self.assertEqual(at.markdown[-1].value, nomes[0])

    def test_exclusao_do_ultimo_relatorio_atualiza_estado_vazio(self):
        pasta = Path("dados/relatorios")
        pasta.mkdir(parents=True)
        relatorio = pasta / "relatorio_20261017_120001.md"
        relatorio.write_text("# Relatório", encoding="utf-8")
        at = self.app().switch_page("paginas/relatorio.py").run()
        at.button(key="excluir_relatorio").click().run()
        at.button(key="confirmar_exclusao_relatorio").click().run()
        self.assertFalse(at.exception)
        self.assertFalse(relatorio.exists())
        self.assertTrue(any("Nenhum relatório disponível" in aviso.value for aviso in at.info))

    def test_falha_ao_excluir_relatorio_exibe_erro_e_preserva_arquivo(self):
        pasta = Path("dados/relatorios")
        pasta.mkdir(parents=True)
        relatorio = pasta / "relatorio_20261017_120001.md"
        relatorio.write_text("# Relatório", encoding="utf-8")
        at = self.app().switch_page("paginas/relatorio.py").run()
        at.button(key="excluir_relatorio").click().run()
        with patch("armazenamento.armazenamento.os.remove", side_effect=PermissionError("sem acesso")):
            at.button(key="confirmar_exclusao_relatorio").click().run()
        self.assertFalse(at.exception)
        self.assertTrue(relatorio.exists())
        self.assertIn("Não foi possível excluir o relatório", at.toast[-1].value)
        self.assertEqual(at.toast[-1].duration, 5)

    def test_falha_de_leitura_e_escrita_de_relatorio_exibe_mensagem(self):
        pasta = Path("dados/relatorios")
        pasta.mkdir(parents=True)
        (pasta / "invalido.md").write_bytes(b"\xff\xfe")
        at = self.app().switch_page("paginas/relatorio.py").run()
        self.assertFalse(at.exception)
        self.assertTrue(at.warning)
        self.csv()
        at.switch_page("paginas/monitor.py").run()
        with patch("analise.gerar_relatorio.salvar_relatorio", side_effect=PermissionError("sem acesso")):
            at.button(key="gerar").click().run()
        self.assertFalse(at.exception)
        self.assertTrue(at.error)

    def test_encerrar_sinaliza_controlador_antes_de_solicitar_parada_do_servidor(self):
        import signal

        at = self.app().run()
        chamadas = []
        with patch("signal.raise_signal", side_effect=lambda sinal: chamadas.append(sinal)) as encerrar, patch.object(obter_controlador(), "encerrar", side_effect=lambda: chamadas.append("coleta") or True) as parar:
            at.button(key="encerrar").click().run()
        self.assertFalse(at.exception)
        parar.assert_called_once()
        encerrar.assert_called_once_with(signal.SIGINT)
        self.assertEqual(chamadas, ["coleta", signal.SIGINT])

    def test_parada_incompleta_nao_envia_sinal_e_permite_tentar_novamente(self):
        at = self.app().run()
        with patch("signal.raise_signal") as sinal, patch.object(obter_controlador(), "encerrar", return_value=False):
            at.button(key="encerrar").click().run()
        self.assertFalse(at.exception)
        sinal.assert_not_called()
        self.assertTrue(any("ainda está encerrando" in aviso.value for aviso in at.warning))
        with patch("signal.raise_signal") as sinal:
            at.button(key="encerrar").click().run()
        self.assertFalse(at.exception)
        sinal.assert_called_once()

    def test_reinicio_do_controlador_restaura_widgets(self):
        at = self.app().run()
        at.text_input(key="wan_destino_input").set_value("1.1.1.1").run()
        at.number_input(key="intervalo_input").set_value(12.0).run()
        obter_controlador.clear()
        novo = self.app().run()
        self.assertFalse(novo.exception)
        self.assertEqual(novo.text_input(key="wan_destino_input").value, "1.1.1.1")
        self.assertEqual(novo.number_input(key="intervalo_input").value, 12.0)
        self.assertFalse(novo.session_state.coleta_ativa)

    def test_falha_de_persistencia_avisa_e_preserva_widget(self):
        at = self.app().run()
        with patch("coletor.controle.salvar_configuracao", side_effect=PermissionError("sem acesso")):
            at.text_input(key="wan_destino_input").set_value("1.1.1.1").run()
        self.assertFalse(at.exception)
        self.assertEqual(at.text_input(key="wan_destino_input").value, "1.1.1.1")
        self.assertTrue(any("não pôde ser salva" in aviso.value for aviso in at.warning))


if __name__ == "__main__":
    unittest.main()
