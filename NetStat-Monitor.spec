"""Pacote Windows em pasta; recursos e código das páginas acompanham o executável."""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata


if sys.platform != "win32":
    raise RuntimeError("O pacote Windows deve ser construído no Windows.")

raiz = Path(SPECPATH)
dados = [
    (str(raiz / "app.py"), "."),
    (str(raiz / "assets"), "assets"),
    (str(raiz / ".streamlit" / "config.toml"), ".streamlit"),
    (str(raiz / "LICENSE"), "."),
]
dados += [(str(arquivo), "paginas") for arquivo in (raiz / "paginas").glob("*.py")]
dados += collect_data_files("streamlit")
for pacote in ("streamlit", "pandas", "scipy", "plotly", "reportlab", "pywebview", "uvicorn"):
    dados += copy_metadata(pacote)

# As páginas são executadas pelo Streamlit e não aparecem nos imports do inicializador.
imports = []
for pacote in ("paginas", "coletor", "armazenamento", "analise", "visualizacao"):
    imports += collect_submodules(pacote)
imports += ["streamlit.runtime.scriptrunner.magic_funcs", "uvicorn.logging", "uvicorn.loops.asyncio", "uvicorn.protocols.http.h11_impl", "uvicorn.protocols.websockets.websockets_impl", "uvicorn.lifespan.on"]

analise = Analysis(
    [str(raiz / "desktop.py")], pathex=[str(raiz)],
    binaries=[], datas=dados, hiddenimports=imports,
    hookspath=[], runtime_hooks=[], excludes=["pytest", "IPython", "tkinter"],
    noarchive=False,
)
arquivo_python = PYZ(analise.pure)
executavel = EXE(
    arquivo_python, analise.scripts, [], exclude_binaries=True,
    name="NetStat-Monitor", debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=False, icon=str(raiz / "assets" / "NS_logo_square.ico"),
)
COLLECT(
    executavel, analise.binaries, analise.datas,
    strip=False, upx=False, name="NetStat-Monitor",
)
