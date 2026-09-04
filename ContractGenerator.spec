# -*- mode: python ; coding: utf-8 -*-
"""Конфигурация сборки одно-файлового EXE.

Каталоги ``templates``, ``data`` и ``output`` НЕ упаковываются: они
записываемые, а временный каталог PyInstaller (``sys._MEIPASS``) удаляется
при выходе из программы. Настройки и реестр договоров хранятся в
``%LOCALAPPDATA%\\ContractGenerator``, каталог результата выбирает пользователь.
"""

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'openpyxl',
        'docx',
        'lxml.etree',
        'lxml._elementpath',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pytest',
        'numpy',
        'pandas',
        'matplotlib',
        'PIL',
        'PyQt5',
        'PySide6',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ContractGenerator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='version.txt',
)
