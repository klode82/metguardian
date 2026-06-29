@echo off
REM MetGuardian — Windows single-file build script
REM Produces a single MetGuardian.exe in dist\
REM
REM Trade-offs vs build.bat (onedir):
REM   + One file to copy/share.
REM   - First launch extracts ~80-150 MB to %%TEMP%%: ~3-5 s extra startup.
REM   - Some antivirus scanners may flag self-extracting executables.
REM
REM Usage:
REM   build-onefile.bat

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

echo [3/3] Building MetGuardian (single file)...
pyinstaller metguardian-win-onefile.spec --clean --noconfirm
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    exit /b 1
)

echo.
echo Build complete.
echo Output: dist\MetGuardian.exe
endlocal
