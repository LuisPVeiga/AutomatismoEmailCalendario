@echo off
SETLOCAL ENABLEDELAYEDEXPANSION

REM =====================================================
REM  Automação de Contas a Pagar — Windows
REM  Usar com Windows Task Scheduler
REM  Executa diariamente e regista log com timestamp
REM =====================================================

REM -- Ir para o diretório do projeto (um nível acima de config\)
cd /d "%~dp0.."

REM -- Formatar timestamp para o nome do log rotacionado
FOR /F "tokens=1-3 delims=/ " %%a IN ("%DATE%") DO (
    SET DD=%%a
    SET MM=%%b
    SET YYYY=%%c
)
FOR /F "tokens=1-2 delims=:." %%a IN ("%TIME%") DO (
    SET HH=%%a
    SET MIN=%%b
)
SET TIMESTAMP=%YYYY%%MM%%DD%_%HH%%MIN%
SET LOG_FILE=logs\run_%TIMESTAMP%.log

REM -- Criar pasta logs se não existir
IF NOT EXIST logs\ (
    mkdir logs
)

REM -- Activar virtual environment
IF NOT EXIST venv\Scripts\activate.bat (
    echo [ERRO] Ambiente virtual nao encontrado em venv\
    echo        Execute: python -m venv venv ^& pip install -r requirements.txt
    EXIT /B 1
)
CALL venv\Scripts\activate.bat

REM -- Executar automação e guardar saída no log rotacionado + logs.txt geral
echo [%TIMESTAMP%] A iniciar automacao... > "%LOG_FILE%"
python -m src.main >> "%LOG_FILE%" 2>&1

SET EXIT_CODE=%ERRORLEVEL%

REM -- Copiar para logs.txt (ficheiro principal)
TYPE "%LOG_FILE%" >> logs.txt

IF %EXIT_CODE% EQU 0 (
    echo [%TIMESTAMP%] Execucao bem-sucedida. >> logs.txt
    echo Execucao concluida com sucesso. Ver %LOG_FILE%
) ELSE (
    echo [%TIMESTAMP%] ERRO na execucao. Codigo: %EXIT_CODE% >> logs.txt
    echo ERRO na execucao! Codigo: %EXIT_CODE% — Ver %LOG_FILE%
)

REM -- Limpar logs com mais de 30 dias
forfiles /p logs /s /m run_*.log /d -30 /c "cmd /c del @path" 2>nul

ENDLOCAL
EXIT /B %EXIT_CODE%
