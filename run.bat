@echo off
REM Trading Card Manager - launcher
REM Creates a virtual environment on first run, installs dependencies, then launches the app.

setlocal enabledelayedexpansion
cd /d "%~dp0"

if not exist "venv\" (
    echo [setup] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [error] Could not create venv. Make sure Python 3.10+ is installed and on PATH.
        pause
        exit /b 1
    )
)

call venv\Scripts\activate.bat

if not exist "venv\.deps_installed" (
    echo [setup] Installing dependencies...
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [error] Dependency installation failed.
        pause
        exit /b 1
    )
    echo. > venv\.deps_installed
)

echo [run] Launching Trading Card Manager...
python main.py
if errorlevel 1 (
    echo.
    echo [error] App exited with an error.
    pause
)

endlocal
