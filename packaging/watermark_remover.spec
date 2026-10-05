import platform
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


ROOT = Path(SPECPATH).parent
STAGE = ROOT / "packaging" / "build"
FRONTEND = STAGE / "frontend-dist"
BUILD_INFO = STAGE / "build-info.json"

if not (FRONTEND / "index.html").is_file():
    raise SystemExit("Missing staged frontend build. Run packaging/build_desktop.py.")

hidden_imports = collect_submodules("uvicorn") + collect_submodules("sqlalchemy.dialects.sqlite")

analysis = Analysis(
    [str(ROOT / "packaging" / "desktop_entry.py")],
    pathex=[str(ROOT / "backend" / "src")],
    binaries=[],
    datas=[
        (str(FRONTEND), "wmrm/static"),
        (str(BUILD_INFO), "."),
        (str(ROOT / "LICENSE"), "."),
        (str(ROOT / "NOTICE"), "."),
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "ruff"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="Watermark Remover",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

bundle = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="Watermark Remover",
)

if platform.system() == "Darwin":
    app = BUNDLE(
        bundle,
        name="Watermark Remover.app",
        icon=None,
        bundle_identifier="org.watermarkremover.desktop",
        version="0.1.0.dev0",
        info_plist={
            "CFBundleDisplayName": "Watermark Remover",
            "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.utilities",
        },
    )
