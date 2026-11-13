@echo off
setlocal EnableExtensions
chcp 65001 >nul
set PYTHONUTF8=1

REM Ubicarse siempre en la carpeta del proyecto (compatible con Task Scheduler)
cd /d "%~dp0"

if not exist "logs" mkdir "logs"

REM Fecha YYYYMMDD independiente de configuracion regional
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set TODAY=%%i
set LOG_FILE=logs\extractor_%TODAY%.log

REM Detectar entorno virtual local (.venv) o usar Python global
if exist ".venv\Scripts\python.exe" (
    set PYTHON_EXE=.venv\Scripts\python.exe
) else (
    set PYTHON_EXE=python
)

echo ====================================================================== >> "%LOG_FILE%"
echo [%DATE% %TIME%] Sincronizando rama local con origin/main antes de extraer... >> "%LOG_FILE%"
if exist ".git" (
    git checkout -- output/ >> "%LOG_FILE%" 2>&1
    git pull --rebase origin main >> "%LOG_FILE%" 2>&1
)

echo [%DATE% %TIME%] Iniciando extraccion nacional INFOMAR - IMARPE >> "%LOG_FILE%"
"%PYTHON_EXE%" main.py --days 7 %* >> "%LOG_FILE%" 2>&1
set EXIT_CODE=%ERRORLEVEL%

REM Publicar output/ en GitHub automaticamente tras sincronizar sin conflictos
if "%EXIT_CODE%"=="0" (
    if exist ".git" (
        echo [%DATE% %TIME%] Publicando output/ hacia GitHub achayna/Generador-precios... >> "%LOG_FILE%"
        git add output/ >> "%LOG_FILE%" 2>&1
        git diff --staged --quiet
        if errorlevel 1 (
            git commit -m "chore(data): auto-sync precios playa IMARPE desde IP Peru [skip ci]" >> "%LOG_FILE%" 2>&1
            git pull --rebase -X theirs origin main >> "%LOG_FILE%" 2>&1
            git push origin main >> "%LOG_FILE%" 2>&1
        ) else (
            echo [%DATE% %TIME%] Sin cambios en output/ para subir a GitHub. >> "%LOG_FILE%"
        )
    )
)

echo [%DATE% %TIME%] Finalizado con codigo: %EXIT_CODE% >> "%LOG_FILE%"
exit /b %EXIT_CODE%
