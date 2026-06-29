# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for MetGuardian — Windows single-file build.

Usage (on a Windows machine):
    pip install --no-cache-dir -r requirements.txt
    pip install --no-cache-dir pyinstaller
    pyinstaller metguardian-win-onefile.spec --clean --noconfirm

Output: dist\MetGuardian.exe  (single portable executable)

Trade-offs vs onedir (metguardian-win.spec):
  + One file to copy/share — no folder to zip.
  - First launch extracts ~50-100 MB to %TEMP%: startup takes ~3-5 s extra.
  - Some antivirus scanners flag self-extracting executables as suspicious.

Cross-compilation is NOT supported: run on Windows only.
"""

import os

ROOT = SPECPATH
block_cipher = None

a = Analysis(
    [os.path.join(ROOT, 'app.py')],
    pathex=[ROOT],
    binaries=[],
    datas=[
        (os.path.join(ROOT, 'ui'), 'ui'),
        (os.path.join(ROOT, 'db', 'schema.sql'), 'db'),
    ],
    hiddenimports=[
        'webview',
        'webview.platforms.winforms',
        'webview.platforms.edgechromium',
        'pystray',
        'pystray._win32',
        'pystray._base',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.PngImagePlugin',
        'PIL.IcoImagePlugin',
        'win11toast',
        'sqlite3',
        'threading',
        'pathlib',
        'logging.handlers',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt6', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets',
        'PyQt6.QtWebEngineCore', 'PyQt6.QtWebEngineWidgets',
        'qtpy', 'xlib', 'python_xlib',
        'pyobjc', 'objc', 'Cocoa', 'WebKit',
        'pytest', 'pip', 'setuptools',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Onefile: binaries and datas are packed directly into EXE; no COLLECT step.
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MetGuardian',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,   # use default %TEMP%\...
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(ROOT, 'ui', 'assets', 'icon.ico'),
)
