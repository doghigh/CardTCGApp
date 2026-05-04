@echo off
REM Trading Card Manager - build standalone .exe with PyInstaller

setlocal
cd /d "%~dp0"

if not exist "venv\" (
    echo [setup] Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo [setup] Installing dependencies + PyInstaller...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

echo [build] Building TradingCardManager.exe...
pyinstaller --noconfirm ^
    --onefile ^
    --windowed ^
    --name TradingCardManager ^
    --collect-all=PyQt6 ^
    --hidden-import=PyQt6.QtWidgets ^
    --hidden-import=PyQt6.QtCore ^
    --hidden-import=PyQt6.QtGui ^
    --hidden-import=PyQt6.sip ^
    --hidden-import=cv2 ^
    --collect-all=cv2 ^
    --hidden-import=pytwain ^
    --hidden-import=pytesseract ^
    --hidden-import=reportlab ^
    main.py

if errorlevel 1 (
    echo [error] Build failed.
    pause
    exit /b 1
)

echo.
echo [done] Executable is in dist\TradingCardManager.exe
pause
endlocal
