import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
import uuid


@unittest.skipUnless(os.name == "nt", "A ferramenta de instalacao atende apenas Windows.")
class InstaladorWindowsTest(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporario.cleanup)
        self.pasta = Path(self.temporario.name)
        (self.pasta / "NetStat-Monitor.exe").touch()
        (self.pasta / "_internal").mkdir()
        (self.pasta / "_internal" / "app.py").touch()

    def executar(self, *argumentos):
        script = Path(__file__).resolve().parents[1] / "scripts" / "gerar_instalador.ps1"
        return subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script), *argumentos],
            capture_output=True, text=True, errors="replace", timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    def test_rejeita_versao_invalida(self):
        for versao in ("../teste", "1.0", "1.0.0;exit"):
            with self.subTest(versao=versao):
                resultado = self.executar("-Versao", versao)
                self.assertNotEqual(resultado.returncode, 0)

    def test_rejeita_pacote_ausente_ou_incompleto(self):
        for pasta in (self.pasta / "ausente", self.pasta / "_internal"):
            with self.subTest(pasta=pasta):
                resultado = self.executar("-Versao", "0.1.0-dev", "-PastaPacote", str(pasta))
                self.assertNotEqual(resultado.returncode, 0)
                self.assertIn("Pacote incompleto", resultado.stderr)

    def test_rejeita_compilador_ausente(self):
        resultado = self.executar("-Versao", "0.1.0-dev", "-PastaPacote", str(self.pasta), "-Compilador", str(self.pasta / "ausente.exe"))
        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn("Inno Setup 6 nao encontrado", resultado.stderr)

    def test_rejeita_auxiliar_sem_assinatura_microsoft(self):
        auxiliar = self.pasta / "auxiliar.exe"
        auxiliar.touch()
        compilador = Path(os.environ["SystemRoot"]) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        resultado = self.executar("-Versao", "0.1.0-dev", "-PastaPacote", str(self.pasta), "-Compilador", str(compilador), "-WebView2Setup", str(auxiliar))
        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn("assinatura valida da Microsoft", resultado.stderr)

    @unittest.skipUnless(os.environ.get("NETSTAT_TESTAR_INSTALADOR") == "1", "Requer compilador Inno Setup e teste de instalacao explicito.")
    def test_desinstalacao_preserva_ou_exclui_somente_os_dados_selecionados(self):
        raiz = Path(__file__).resolve().parents[1]
        compilador = raiz / "dist/.tools/inno/ISCC.exe"
        auxiliar = raiz / "dist/.tools/MicrosoftEdgeWebview2Setup.exe"
        if not compilador.is_file() or not auxiliar.is_file():
            self.skipTest("Ferramentas locais de empacotamento indisponiveis.")
        identidade = "NetStat-Teste-" + uuid.uuid4().hex
        dados = self.pasta / "NetStat"
        desenvolvimento = self.pasta / "NetStat-Dev"
        desenvolvimento.mkdir()
        (desenvolvimento / "preservar.txt").write_text("teste", encoding="utf-8")
        pacote = self.pasta / "pacote"
        pacote.mkdir()
        (pacote / "NetStat-Monitor.exe").touch()
        # Isola identidade, atalhos e alvo de exclusao; nunca usa o perfil real.
        receita = (raiz / "NetStat-Monitor.iss").read_text(encoding="utf-8")
        receita = receita.replace("AppId=NetStat-Monitor", "AppId=" + identidade)
        receita = receita.replace("NetStat Monitor", identidade)
        receita = receita.replace("{localappdata}\\NetStat", str(dados.resolve()))
        receita = receita.replace("LicenseFile=LICENSE", "LicenseFile=" + str(raiz / "LICENSE"))
        receita = receita.replace("SetupIconFile=assets\\NS_logo_square.ico", "SetupIconFile=" + str(raiz / "assets/NS_logo_square.ico"))
        script = self.pasta / "teste.iss"
        script.write_text(receita, encoding="utf-8")

        def executar(comando):
            resultado = subprocess.run(comando, capture_output=True, text=True, errors="replace", timeout=60, creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)

        executar([str(compilador), "/Q", "/DAppVersion=0.0.0-test", "/DAppFileVersion=0.0.0.0", f"/DBundleDir={pacote}", f"/DWebView2Setup={auxiliar}", f"/O{self.pasta}", "/Fteste", str(script)])
        for excluir, existente in ((False, True), (True, True), (True, False)):
            with self.subTest(excluir=excluir, existente=existente):
                destino = self.pasta / ("instalado-excluir" if excluir else "instalado-preservar")
                sentinela = dados / "preservar.csv"
                if existente:
                    dados.mkdir(exist_ok=True)
                    sentinela.write_text("teste", encoding="utf-8")
                executar([str(self.pasta / "teste.exe"), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-", f"/DIR={destino}"])
                log = self.pasta / "desinstalacao.log"
                argumentos = [str(destino / "unins000.exe"), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", f"/LOG={log}"]
                if excluir:
                    argumentos.append("/EXCLUIRDADOS=1")
                executar(argumentos)
                prazo = time.monotonic() + 10
                while (destino.exists() or (excluir and dados.exists())) and time.monotonic() < prazo:
                    time.sleep(0.1)
                self.assertFalse(destino.exists(), "O processo de desinstalacao ainda nao concluiu a limpeza.")
                self.assertEqual(dados.exists(), existente and not excluir, log.read_text(encoding="utf-8-sig", errors="replace"))
                if not excluir:
                    self.assertEqual(sentinela.read_text(encoding="utf-8"), "teste")
                self.assertTrue((desenvolvimento / "preservar.txt").is_file())


if __name__ == "__main__":
    unittest.main()
