#!/bin/bash
# MetGuardian — Linux build script
# Produces a self-contained AppImage: MetGuardian-x86_64.AppImage
#
# Prerequisites:
#   Python 3.10+, pip, a clean virtual environment (recommended)
#   appimagetool in PATH (see https://github.com/AppImage/AppImageKit/releases)
#     wget https://github.com/AppImage/AppImageKit/releases/latest/download/appimagetool-x86_64.AppImage
#     chmod +x appimagetool-x86_64.AppImage
#     sudo mv appimagetool-x86_64.AppImage /usr/local/bin/appimagetool
#
# Usage:
#   chmod +x build-linux.sh
#   ./build-linux.sh

set -e

echo "[1/4] Installing dependencies..."
pip install --no-cache-dir -r requirements.txt

echo "[2/4] Installing PyInstaller..."
pip install --no-cache-dir pyinstaller

echo "[3/4] Building MetGuardian (onedir)..."
pyinstaller metguardian-linux.spec --clean --noconfirm

echo "[4/4] Creating AppImage..."

if ! command -v appimagetool &>/dev/null; then
    echo ""
    echo "WARNING: appimagetool not found in PATH."
    echo "The onedir build is ready in dist/MetGuardian/ but the AppImage was not created."
    echo ""
    echo "To install appimagetool:"
    echo "  wget https://github.com/AppImage/AppImageKit/releases/latest/download/appimagetool-x86_64.AppImage"
    echo "  chmod +x appimagetool-x86_64.AppImage"
    echo "  sudo mv appimagetool-x86_64.AppImage /usr/local/bin/appimagetool"
    echo "Then re-run: ./build-linux.sh"
    exit 0
fi

APPDIR="dist/MetGuardian.AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR"

# Copy the whole PyInstaller onedir output into the AppDir root.
cp -r dist/MetGuardian/. "$APPDIR/"

# AppRun: entry point executed by the AppImage runtime.
cat > "$APPDIR/AppRun" << 'APPRUN'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
exec "${HERE}/MetGuardian" "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

# .desktop file (required by appimagetool).
cat > "$APPDIR/MetGuardian.desktop" << 'DESKTOP'
[Desktop Entry]
Name=MetGuardian
Comment=Smart backups for eMule part.met files
Exec=MetGuardian
Icon=MetGuardian
Type=Application
Categories=Utility;Network;
DESKTOP

# Icon at the AppDir root (required by the AppImage spec).
cp "$APPDIR/_internal/ui/assets/icon.png" "$APPDIR/MetGuardian.png"

# Build the AppImage.
appimagetool "$APPDIR" "MetGuardian-x86_64.AppImage"

echo ""
echo "Build complete: MetGuardian-x86_64.AppImage"
