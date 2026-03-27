@echo off
REM NSP Plugin - Script de Instalacao Automatizada (Windows)
REM Versao: 2.0

setlocal enabledelayedexpansion

echo.
echo ================================================================
echo.
echo            NSP PLUGIN - INSTALADOR AUTOMATIZADO
echo                        Versao 2.0
echo.
echo ================================================================
echo.

REM Detectar diretorio do script
set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..

echo Diretorio do projeto: %PROJECT_ROOT%
echo.

cd /d "%PROJECT_ROOT%"

REM 1. VERIFICAR PRE-REQUISITOS
echo ================================================================
echo   PASSO 1/6: Verificar Pre-requisitos
echo ================================================================
echo.

REM Python
echo Verificando Python 3.8+...
python --version >nul 2>&1
if errorlevel 1 (
    echo [X] Python 3 nao encontrado!
    echo Instale Python 3.8+ de: https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo [OK] Python %PYTHON_VERSION%

REM Git (opcional)
echo Verificando Git...
git --version >nul 2>&1
if errorlevel 1 (
    echo [!] Git nao encontrado ^(opcional^)
) else (
    for /f "tokens=3" %%i in ('git --version') do set GIT_VERSION=%%i
    echo [OK] Git !GIT_VERSION!
)

REM 2. CRIAR AMBIENTE VIRTUAL
echo.
echo ================================================================
echo   PASSO 2/6: Criar Ambiente Virtual
echo ================================================================
echo.

if exist venv (
    echo [!] Ambiente virtual ja existe.
    set /p REMOVE="Remover? (s/N): "
    if /i "!REMOVE!"=="s" (
        echo Removendo venv antigo...
        rmdir /s /q venv
    ) else (
        echo Mantendo venv existente.
    )
)

if not exist venv (
    echo Criando ambiente virtual...
    python -m venv venv
    echo [OK] Ambiente virtual criado
) else (
    echo [OK] Usando ambiente virtual existente
)

REM Ativar venv
call venv\Scripts\activate.bat

REM 3. INSTALAR DEPENDENCIAS
echo.
echo ================================================================
echo   PASSO 3/6: Instalar Dependencias
echo ================================================================
echo.

echo Atualizando pip...
python -m pip install --upgrade pip setuptools wheel

echo.
echo Instalando dependencias do projeto...
if exist requirements.txt (
    pip install -r requirements.txt
    echo [OK] Dependencias instaladas
) else (
    echo [X] requirements.txt nao encontrado!
    pause
    exit /b 1
)

REM 4. CRIAR ESTRUTURA DE DIRETORIOS
echo.
echo ================================================================
echo   PASSO 4/6: Criar Estrutura de Diretorios
echo ================================================================
echo.

if not exist data mkdir data
if not exist data\sessions mkdir data\sessions
if not exist data\feedback mkdir data\feedback
if not exist models mkdir models
if not exist models\backup_v1 mkdir models\backup_v1
if not exist logs mkdir logs
if not exist presets mkdir presets
if not exist datasets mkdir datasets

echo [OK] Estrutura de diretorios criada

REM 5. VERIFICAR MODELOS
echo.
echo ================================================================
echo   PASSO 5/6: Verificar Modelos ML
echo ================================================================
echo.

set MISSING_COUNT=0

if exist "models\best_preset_classifier_v2.pth" (
    echo [OK] models\best_preset_classifier_v2.pth
) else (
    echo [X] models\best_preset_classifier_v2.pth - FALTANDO
    set /a MISSING_COUNT+=1
)

if exist "models\best_refinement_model_v2.pth" (
    echo [OK] models\best_refinement_model_v2.pth
) else (
    echo [X] models\best_refinement_model_v2.pth - FALTANDO
    set /a MISSING_COUNT+=1
)

if !MISSING_COUNT! gtr 0 (
    echo.
    echo [!] Modelos em falta. Precisa de treinar primeiro:
    echo    python train/train_models_v2.py
)

REM 6. INSTALAR PLUGIN NO LIGHTROOM
echo.
echo ================================================================
echo   PASSO 6/6: Instalar Plugin no Lightroom
echo ================================================================
echo.

set PLUGIN_DIR=%PROJECT_ROOT%\NSP-Plugin.lrplugin

if not exist "%PLUGIN_DIR%" (
    echo [X] Diretorio do plugin nao encontrado: %PLUGIN_DIR%
    pause
    exit /b 1
)

echo Plugin localizado: %PLUGIN_DIR%
echo.
echo Para instalar no Lightroom Classic:
echo 1. Abrir Lightroom Classic
echo 2. File ^> Plug-in Manager...
echo 3. Clicar 'Add'
echo 4. Navegar para: %PLUGIN_DIR%
echo 5. Selecionar a pasta 'NSP-Plugin.lrplugin'
echo.
echo Ou copiar manualmente para:
echo    %APPDATA%\Adobe\Lightroom\Modules
echo.

REM RESUMO FINAL
echo.
echo ================================================================
echo.
echo               INSTALACAO CONCLUIDA COM SUCESSO!
echo.
echo ================================================================
echo.

echo Proximos Passos:
echo.
echo 1. Iniciar o servidor:
echo    start_server.bat
echo.
echo 2. ^(Opcional^) Treinar modelos se ainda nao tiver:
echo    venv\Scripts\activate
echo    python train/train_models_v2.py
echo.
echo 3. Instalar plugin no Lightroom ^(ver instrucoes acima^)
echo.
echo 4. ^(Opcional^) Ativar autenticacao API:
echo    Editar config.json e definir:
echo    "api_auth_enabled": true
echo.
echo 5. ^(Opcional^) Gerar API key:
echo    python manage_api_keys.py generate "Nome" --level standard
echo.
echo Documentacao:
echo    - RESUMO_OTIMIZACOES.md
echo    - MELHORIAS_COMPLETAS_FINAL.md
echo    - GUIA_TESTES_RAPIDO.md
echo.
echo Pronto para usar!
echo.

pause
