# -*- mode: python ; coding: utf-8 -*-
"""Receta de PyInstaller para Ilahi.

Genera un único ejecutable portable (dist/Ilahi.exe), sin consola y con
ícono propio. Compilar con:

    pyinstaller Ilahi.spec --clean --noconfirm

o, más simple, con ./build.ps1
"""

block_cipher = None


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    # El ícono viaja dentro del exe para que root.iconbitmap lo encuentre en runtime
    # (vía utils.resources.resource_path -> sys._MEIPASS).
    datas=[('assets/icon.ico', 'assets')],
    # La app usa solo la librería estándar; no debería hacer falta nada aquí.
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Ilahi',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,            # app GUI: sin ventana de consola
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
)
