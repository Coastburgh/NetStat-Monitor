import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


@unittest.skipUnless(os.name == "nt", "A etapa de versionamento usa PowerShell no Windows.")
class VersaoReleaseTest(unittest.TestCase):
    def executar(self, evento="workflow_dispatch", versao="", tag="", integrado=True):
        raiz = Path(__file__).resolve().parents[1]
        workflow = (raiz / ".github/workflows/windows-release.yml").read_text(encoding="utf-8")
        etapa = workflow.split("      - name: Determinar versao\n", 1)[1].split("\n      - ", 1)[0]
        codigo = textwrap.dedent(etapa.split("        run: |\n", 1)[1])
        # Simula somente o resultado do Git; a validacao executada e a do workflow.
        codigo = "$ErrorActionPreference = 'Stop'\nfunction git { $global:LASTEXITCODE = [int]$env:TESTE_GIT_EXIT }\n" + codigo
        with tempfile.TemporaryDirectory() as pasta:
            script = Path(pasta) / "versao.ps1"
            script.write_text(codigo, encoding="utf-8")
            saida = Path(pasta) / "output.txt"
            ambiente = {
                **os.environ, "GITHUB_EVENT_NAME": evento, "VERSAO_MANUAL": versao,
                "GITHUB_REF_NAME": tag, "GITHUB_OUTPUT": str(saida),
                "TESTE_GIT_EXIT": "0" if integrado else "1",
            }
            resultado = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                env=ambiente, capture_output=True, text=True, errors="replace", timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            bruto = saida.read_bytes() if saida.exists() else b""
            texto = bruto.decode("utf-16" if bruto.startswith(b"\xff\xfe") else "utf-8-sig")
            return resultado, texto

    def test_versoes_manuais_validas(self):
        for versao in ("0.1.0", "1.2.3-rc.1", "65535.0.0"):
            with self.subTest(versao=versao):
                resultado, saida = self.executar(versao=versao)
                self.assertEqual(resultado.returncode, 0, resultado.stderr)
                self.assertEqual(saida.strip(), "versao=" + versao)

    def test_rejeita_versao_ausente_invalida_ou_fora_do_limite(self):
        for versao in ("", "v0.1.0", "1.0", "65536.0.0", "0.1.0\n", "0.1.0;exit", "../teste"):
            with self.subTest(versao=versao):
                resultado, saida = self.executar(versao=versao)
                self.assertNotEqual(resultado.returncode, 0)
                self.assertEqual(saida, "")

    def test_tag_define_versao_e_ignora_entrada_manual(self):
        resultado, saida = self.executar(evento="push", versao="9.9.9", tag="v0.1.0-rc.1")
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertEqual(saida.strip(), "versao=0.1.0-rc.1")

    def test_tag_fora_da_main_nao_gera_versao(self):
        resultado, saida = self.executar(evento="push", tag="v0.1.0", integrado=False)
        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn("integrado a main", resultado.stderr)
        self.assertEqual(saida, "")


if __name__ == "__main__":
    unittest.main()
