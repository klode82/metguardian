@echo off
REM MetGuardian — Windows build script
REM Run this from the project root on a Windows machine.
REM
REM Prerequisites:
REM   Python 3.10+ in PATH
REM   A clean virtual environment (recommended)
REM
REM Usage:
REM   build.bat

setlocal

echo [1/3] Installing dependencies...
pip install --no-cache-dir -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed.
    exit /b 1
)

echo [2/3] Installing PyInstaller...
pip install --no-cache-dir pyinstaller
if errorlevel 1 (
    echo ERROR: PyInstaller install failed.
    exit /b 1
)

echo [3/3] Building MetGuardian...
pyinstaller metguardian-win.spec --clean --noconfirm
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    exit /b 1
)

echo.
echo Build complete.
echo Output: dist\MetGuardian\MetGuardian.exe
echo.
echo To distribute: zip the dist\MetGuardian\ folder.
endlocal
