# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Lap Coach Logger.

Build with:  pyinstaller lap_coach_logger.spec
Or use:      build.bat
"""

import sys
from pathlib import Path

block_cipher = None
ROOT = Path(SPECPATH)
sys.path.insert(0, str(ROOT / "src"))

from lap_coach_logger.assets import ABOUT_ART_CANDIDATES, APP_ICON_CANDIDATES, MONOGRAM_CANDIDATES, TRAY_ICON_CANDIDATES  # noqa: E402


def _first_existing(root: Path, candidates: tuple[str, ...]) -> Path | None:
    for candidate in candidates:
        path = root / Path(candidate)
        if path.exists():
            return path
    return None


ICON_PATH = _first_existing(ROOT, APP_ICON_CANDIDATES)
VERSION_FILE = ROOT / "build" / "windows" / "version_info.txt"


def _asset_data(path: Path) -> tuple[str, str]:
    relative = path.relative_to(ROOT)
    target_dir = "." if len(relative.parts) == 1 else "/".join(relative.parts[:-1])
    return (str(path), target_dir)


datas = [
    (str(ROOT / "config.sample.json"), "."),
    (str(ROOT / "src" / "lap_coach_logger" / "qml"), "lap_coach_logger/qml"),
]
for candidates in (APP_ICON_CANDIDATES, TRAY_ICON_CANDIDATES, ABOUT_ART_CANDIDATES, MONOGRAM_CANDIDATES):
    asset_path = _first_existing(ROOT, candidates)
    if asset_path is not None:
        entry = _asset_data(asset_path)
        if entry not in datas:
            datas.append(entry)
branding_readme = ROOT / "assets" / "branding" / "README.md"
if branding_readme.exists():
    datas.append(_asset_data(branding_readme))

a = Analysis(
    [str(ROOT / "src" / "lap_coach_logger" / "__main__.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtSvg",
        "PySide6.QtSvgWidgets",
        "PySide6.QtQuick",
        "PySide6.QtQml",
        "pyarrow",
        "pyarrow.parquet",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "numpy.testing",
        "scipy",
        "IPython",
        "notebook",
    ],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LapCoachLogger",
    icon=str(ICON_PATH) if ICON_PATH is not None else None,
    version=str(VERSION_FILE) if VERSION_FILE.exists() else None,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX disabled for reproducibility — some UPX versions produce
    # non-deterministic output and occasionally confuse AV heuristics.
    # Binary size trade-off is acceptable for a ~150MB PySide6 bundle.
    upx=False,
    console=False,          # windowed — no terminal window
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="LapCoachLogger",
)
