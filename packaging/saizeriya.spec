from __future__ import annotations

from importlib.util import find_spec
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

SPEC_DIR = Path(SPECPATH)  # noqa: F821
ROOT = SPEC_DIR.parent

datas = [
    (str(ROOT / "saizeriya" / "data" / "menu.json"), "saizeriya/data"),
    (str(ROOT / "saizeriya" / "tui" / "saizeriya.tcss"), "saizeriya/tui"),
]
binaries = []
hiddenimports = ["bs4.builder._lxml", "lxml._elementpath"]

for package in ("textual", "textual_serve"):
    if find_spec(package) is None:
        print(f"saizeriya.spec: {package} is not installed, not bundling it")  # noqa: T201
        continue
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
