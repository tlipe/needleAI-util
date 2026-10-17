@echo off
setlocal
title Needle Chat

set "PROJECT=%~dp0"
set "PYTHON=%PROJECT%.venv\Scripts\python.exe"
set "SCRIPT=%PROJECT%Needle.py"

if not exist "%PYTHON%" (
    echo [ERRO] Python da .venv nao encontrado:
    echo "%PYTHON%"
    echo.
    echo Execute: python -m venv .venv
    echo          .venv\Scripts\activate
    echo          pip install -r requirements.txt
    pause
    exit /b 1
)

if not exist "%SCRIPT%" (
    echo [ERRO] Needle.py nao encontrado:
    echo "%SCRIPT%"
    pause
    exit /b 1
)

cd /d "%PROJECT%"
echo ========================================
echo             NEEDLE CHAT
echo ========================================
echo Digite /exit ou /quit para encerrar.
echo.

"%PYTHON%" -u "%SCRIPT%"

echo.
echo Needle encerrado.
pause