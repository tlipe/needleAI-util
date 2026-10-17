@echo off
setlocal
title NeedleAI

set "PROJECT=%~dp0"
set "PYTHON=%PROJECT%.venv\Scripts\python.exe"
set "SCRIPT=%PROJECT%Needle.py"
set "REQUIREMENTS=%PROJECT%requirements.txt"

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python nao encontrado. Instale de https://python.org
    pause
    exit /b 1
)

if not exist "%PYTHON%" (
    echo Criando ambiente virtual...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo Falha ao criar .venv
        pause
        exit /b 1
    )
    
    echo Instalando dependencias...
    call "%PROJECT%.venv\Scripts\activate.bat"
    pip install -r "%REQUIREMENTS%"
    if %errorlevel% neq 0 (
        echo Falha ao instalar dependencias
        pause
        exit /b 1
    )
)

if not exist "%SCRIPT%" (
    echo Needle.py nao encontrado
    pause
    exit /b 1
)

cd /d "%PROJECT%"
echo NeedleAI - /exit para encerrar
echo.

"%PYTHON%" -u "%SCRIPT%"

if %errorlevel% neq 0 (
    echo.
    echo Erro %errorlevel%
)

pause
