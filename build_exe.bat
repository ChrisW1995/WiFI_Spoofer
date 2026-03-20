@echo off
echo === wifi-cut Windows Build ===
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+.
    pause
    exit /b 1
)

echo [1/3] Installing dependencies...
pip install -e ".[windows,dev]"
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo [2/3] Building exe with PyInstaller...
pyinstaller wifi-cut.spec --clean -y
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo [3/3] Done!
echo.
echo Output: dist\wifi-cut.exe
echo.
echo Usage: Run as Administrator
echo   dist\wifi-cut.exe interactive
echo   dist\wifi-cut.exe scan
echo   dist\wifi-cut.exe cut 192.168.1.5
echo.
pause
