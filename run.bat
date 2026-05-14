@echo off
title Trading Card Manager - Launcher
echo.
echo ================================================
echo    Trading Card Manager v1.1.0
echo    Privacy-First TCG Collection App
echo ================================================
echo.

:: Set working directory to script location
cd /d "%\~dp0"

:: Check Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please download from https://python.org and check "Add Python to PATH"
    pause
    exit /b 1
)

:: Create virtual environment if it doesn't exist
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: Activate venv
call venv\Scripts\activate.bat

:: Install dependencies
echo Installing / updating dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo [WARNING] Some packages failed to install.
    echo Tesseract OCR is recommended for best OCR performance.
    echo.
)

:: Create required folders
mkdir "%APPDATA%\TradingCardManager\scans" 2>nul
mkdir "%APPDATA%\TradingCardManager\reports" 2>nul

echo.
echo ================================================
echo    Starting Trading Card Manager...
echo    Press Ctrl+C in this window to stop
echo ================================================
echo.

:: Launch the app
python main.py

echo.
echo Application closed.
pausepython -m pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo [WARNING] Some dependencies failed to install.
    echo Make sure Tesseract OCR is installed for full functionality.
)

:: Create necessary directories
if not exist "%APPDATA%\TradingCardManager\scans" mkdir "%APPDATA%\TradingCardManager\scans"
if not exist "%APPDATA%\TradingCardManager\reports" mkdir "%APPDATA%\TradingCardManager\reports"

echo.
echo ================================================
echo    Starting Trading Card Manager...
echo ================================================
echo.

:: Run the application
python main.py

:: Deactivate when closed
deactivate

pause
