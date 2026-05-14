@echo off
echo ================================================
echo    Trading Card Manager - Launcher
echo ================================================

:: Set paths
set PYTHON_EXE=python
set VENV_DIR=venv
set PROJECT_DIR=%\~dp0

:: Check if Python is installed
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in PATH.
    echo Please install Python from https://python.org and check "Add Python to PATH"
    pause
    exit /b 1
)

:: Create virtual environment if it doesn't exist
if not exist %VENV_DIR% (
    echo Creating virtual environment...
    %PYTHON_EXE% -m venv %VENV_DIR%
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: Activate virtual environment
call %VENV_DIR%\Scripts\activate.bat

:: Install/upgrade dependencies
echo Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

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