# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for MetGuardian — Windows one-folder (onedir) build.

Usage (on a Windows machine):
    pip install -r requirements.txt
    pip install pyinstaller
    pyinstaller metguardian.spec

Output: dist\MetGuardian\MetGuardian.exe  (+ sibling files)

Cross-compilation is NOT supported by PyInstaller: this spec must be run on
Windows to produce a Windows executable.
"""

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        # The whole UI folder (HTML, CSS, JS, assets) lands at dist/MetGuardian/ui/
        ('ui', 'ui'),
        # The SQLite schema is loaded at first run; it must be a real file.
        ('db/schema.sql', 'db'),
    ],
    hiddenimports=[
        # pywebview Windows backends (both; one is selected at runtime).
        'webview',
        'webview.platforms.winforms',
        'webview.platforms.edgechromium',
        # pystray Windows backend.
        'pystray',
        'pystray._win32',
        'pystray._base',
        # Pillow sub-modules used by make_tray_image().
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.PngImagePlugin',
        'PIL.IcoImagePlugin',
        # Windows toast notifications.
        'win11toast',
        # Standard library (collected explicitly to be safe).
        'sqlite3',
        'threading',
        'pathlib',
        'logging.handlers',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Linux-only dependencies — never needed on Windows.
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtWebEngineCore',
        'PyQt6.QtWebEngineWidgets',
        'qtpy',
        'xlib',
        'python_xlib',
        # macOS-only dependencies.
        'pyobjc',
        'objc',
        'Cocoa',
        'WebKit',
        # Development-only tools.
        'pytest',
        'pip',
        'setuptools',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
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
    upx=False,             # UPX is optional; set True if it is in PATH
    console=False,         # No black terminal window — GUI-only app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='ui\\assets\\icon.ico',
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
