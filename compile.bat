@echo off
chcp 65001 >nul 2>nul
title wifi-cut Compiler
echo ============================================
echo   wifi-cut Windows Compiler
echo ============================================
echo.

:: Check Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in PATH.
    echo         Please install Python 3.10+ from https://www.python.org
    echo         Make sure to check "Add Python to PATH" during install.
    goto :fail
)

:: Show Python version
echo [INFO] Python version:
python --version
echo.

:: Create virtual environment
if not exist "venv" (
    echo [1/5] Creating virtual environment...
    python -m venv venv
    if %errorlevel% neq 0 goto :fail
) else (
    echo [1/5] Virtual environment already exists, skipping...
)

:: Activate venv
echo [2/5] Activating virtual environment...
call venv\Scripts\activate.bat

:: Install dependencies
echo [3/5] Installing dependencies...
pip install -e ".[windows,dev]" --quiet
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    goto :fail
)
echo       Done.
echo.

:: Build exe
echo [4/5] Building wifi-cut.exe with PyInstaller...
pyinstaller wifi-cut.spec --clean -y --log-level WARN
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller build failed.
    goto :fail
)
echo.

:: Verify output
if not exist "dist\wifi-cut.exe" (
    echo [ERROR] Build completed but wifi-cut.exe not found in dist\
    goto :fail
)

:: Show file size
echo [5/5] Build complete!
echo.
echo ============================================
echo   Output: dist\wifi-cut.exe
for %%A in (dist\wifi-cut.exe) do echo   Size:   %%~zA bytes
echo ============================================
echo.
echo Usage:
echo   1. Right-click dist\wifi-cut.exe
echo   2. "Run as administrator"
echo   3. The tool will auto-detect and install Npcap if needed
echo.
echo Commands:
echo   wifi-cut.exe interactive     Interactive TUI mode
echo   wifi-cut.exe scan            Scan network devices
echo   wifi-cut.exe cut 192.168.1.5 Block a device
echo   wifi-cut.exe throttle 192.168.1.5 --bw 100Kbit/s
echo.
goto :done

:fail
echo.
echo [FAILED] Build did not complete successfully.
echo.
pause
exit /b 1

:done
pause
