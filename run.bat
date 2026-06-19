@echo off
title Lorebox - Launcher
echo.
echo ================================================
echo    Lorebox v1.1.0
echo    Privacy-First TCG Collection App
echo ================================================
echo.

:: Set working directory to script location
cd /d "%~dp0"

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
mkdir "%APPDATA%\Lorebox\scans" 2>nul
mkdir "%APPDATA%\Lorebox\reports" 2>nul

echo.
echo ================================================
echo    Starting Lorebox...
echo    Press Ctrl+C in this window to stop
echo ================================================
echo.

:: Launch the app
python main.py

:: Deactivate when closed
deactivate

echo.
echo Application closed.
pause
