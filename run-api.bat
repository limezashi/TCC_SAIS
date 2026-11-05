@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=%~dp0.venv-api\Scripts\python.exe"
set "MODEL_DIR=%~dp0artifacts\rl_20261014T100407101829_b83773b9"

if not exist "%PYTHON%" (
    echo Ambiente da API nao encontrado: "%PYTHON%"
    echo Crie o ambiente e instale requirements-api.txt conforme docs\API.md.
    exit /b 1
)

if not exist "%MODEL_DIR%\modelo.joblib" (
    echo Artefato do modelo nao encontrado: "%MODEL_DIR%\modelo.joblib"
    exit /b 1
)

set "TCC_MODEL_DIR=%MODEL_DIR%"
"%PYTHON%" -B -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 1
exit /b %ERRORLEVEL%
