@echo off
setlocal EnableExtensions
chcp 65001 >nul
set PYTHONUTF8=1

REM Ubicarse siempre en la carpeta del proyecto (compatible con Task Scheduler)
cd /d "%~dp0"

if not exist "logs" mkdir "logs"

REM Fecha YYYYMMDD independiente de configuracion regional usando PowerShell
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set TODAY=%%i
set LOG_FILE=logs\extractor_%TODAY%.log

REM Detectar entorno virtual local (.venv) o usar Python global
if exist ".venv\Scripts\python.exe" (
    set PYTHON_EXE=.venv\Scripts\python.exe
) else (
    set PYTHON_EXE=python
)

echo ====================================================================== >> "%LOG_FILE%"
echo [%DATE% %TIME%] Iniciando extraccion nacional INFOMAR - IMARPE >> "%LOG_FILE%"
"%PYTHON_EXE%" main.py --days 7 %* >> "%LOG_FILE%" 2>&1
set EXIT_CODE=%ERRORLEVEL%
echo [%DATE% %TIME%] Finalizado con codigo: %EXIT_CODE% >> "%LOG_FILE%"

exit /b %EXIT_CODE%
