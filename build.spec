# -*- mode: python ; coding: utf-8 -*-

import os

block_cipher = None

a = Analysis(
    ['gui_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('icon.png', '.'),
        ('SztuSrunLogin', 'SztuSrunLogin'),
    ],
    hiddenimports=[
        'SztuSrunLogin',
        'SztuSrunLogin.LoginManager',
        'SztuSrunLogin.encryption',
        'SztuSrunLogin.encryption.srun_base64',
        'SztuSrunLogin.encryption.srun_md5',
        'SztuSrunLogin.encryption.srun_sha1',
        'SztuSrunLogin.encryption.srun_xencode',
        'SztuSrunLogin._decorators',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SZTU校园网登录助手',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,       # windowed mode - no console window
    icon='icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SZTU校园网登录助手',
)
