@echo off
title Building TradingCardManager.exe
echo Building standalone executable...

call venv\Scripts\activate.bat

python -m PyInstaller --onefile ^
    --name "TradingCardManager" ^
    --windowed ^
    --icon=app_icon.ico ^
    --add-data "requirements.txt;." ^
    --hidden-import=PyQt6.QtCore ^
    --hidden-import=PyQt6.QtGui ^
    --hidden-import=PyQt6.QtWidgets ^
    --hidden-import=cv2 ^
    --hidden-import=pytesseract ^
    --hidden-import=reportlab ^
    main.py

echo.
echo Build finished! Check the "dist" folder for TradingCardManager.exe
pauseecho.
echo [done] Executable is in dist\TradingCardManager.exe
pause
endlocal
