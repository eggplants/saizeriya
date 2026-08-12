# PyInstaller spec for the standalone, single-file `saizeriya` console binary.
#
# Built by .github/workflows/build-binaries.yml; `uv run --with pyinstaller
# pyinstaller packaging/saizeriya.spec` reproduces the same binary locally.
#
# SPECPATH is injected into this file's namespace by PyInstaller.

from __future__ import annotations

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

SPEC_DIR = Path(SPECPATH)  # noqa: F821
ROOT = SPEC_DIR.parent

# Package data read at runtime through `Path(__file__).parent` (menu.py) and
# Textual's `CSS_PATH` (tui/app.py). Both resolve under sys._MEIPASS once the
# files are bundled at the same relative paths they have in the source tree.
datas = [
    (str(ROOT / "saizeriya" / "data" / "menu.json"), "saizeriya/data"),
    (str(ROOT / "saizeriya" / "tui" / "saizeriya.tcss"), "saizeriya/tui"),
]
binaries = []
# bs4 selects its parser through a registry and lxml.etree resolves this one at
# runtime -- neither import is visible to the static analysis.
hiddenimports = ["bs4.builder._lxml", "lxml._elementpath"]

# textual exposes its widgets through a lazy module __getattr__ and ships .css
# alongside them; textual-serve serves jinja2 templates and static assets out of
# its own package directory.
for package in ("textual", "textual_serve"):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

a = Analysis(  # noqa: F821
    [str(SPEC_DIR / "entrypoint.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["pytest", "tkinter"],
)
pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="saizeriya",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
