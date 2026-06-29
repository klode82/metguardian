# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for MetGuardian — Linux one-folder (onedir) build.

Usage (on a Linux machine):
    pip install --no-cache-dir -r requirements.txt
    pip install --no-cache-dir pyinstaller
    pyinstaller metguardian-linux.spec --clean --noconfirm

The resulting dist/MetGuardian/ folder is then wrapped into an AppImage by
build-linux.sh using appimagetool.

Cross-compilation is NOT supported: run on Linux only.
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
        # pywebview Linux backend (Qt).
        'webview',
        'webview.platforms.qt',
        # Qt / WebEngine (the Linux GUI stack).
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtWebEngineCore',
        'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtWebChannel',
        'PyQt6.QtNetwork',
        'qtpy',
        # pystray Linux backend.
        'pystray',
        'pystray._xorg',
        'pystray._base',
        # Xlib required by pystray._xorg.
        'Xlib',
        'Xlib.display',
        'Xlib.protocol',
        'Xlib.ext',
        # Pillow.
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.PngImagePlugin',
        # Desktop notifications (Linux).
        'plyer',
        'plyer.platforms.linux',
        'plyer.platforms.linux.notification',
        # Standard library.
        'sqlite3',
        'threading',
        'pathlib',
        'logging.handlers',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Windows-only.
        'win11toast',
        'webview.platforms.winforms',
        'webview.platforms.edgechromium',
        'pystray._win32',
        # macOS-only.
        'pyobjc', 'objc', 'Cocoa', 'WebKit',
        # Dev tools.
        'pytest', 'pip', 'setuptools',
    ],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MetGuardian',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=os.path.join(ROOT, 'ui', 'assets', 'icon.png'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='MetGuardian',
)
