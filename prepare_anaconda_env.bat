@echo off
setlocal EnableExtensions
chcp 65001 >nul

set "ENV_NAME=timepool"
set "PROJECT_DIR=%~dp0"
set "LOG_FILE=%PROJECT_DIR%prepare_anaconda_env.log"
set "PYTHONNOUSERSITE=1"
set "PYTHONUTF8=1"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"

pushd "%PROJECT_DIR%" || exit /b 1

call :find_conda
if errorlevel 1 goto :fail

echo.
echo [1/5] Using Conda: %CONDA_BAT%
echo [1/5] Using Conda: %CONDA_BAT%>"%LOG_FILE%"

echo.
echo [2/5] Checking Conda environment: %ENV_NAME%
echo [2/5] Checking Conda environment: %ENV_NAME%>>"%LOG_FILE%"
call "%CONDA_BAT%" run -n "%ENV_NAME%" python --version >>"%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo Creating environment %ENV_NAME% ...
    echo Creating environment %ENV_NAME% ...>>"%LOG_FILE%"
    call "%CONDA_BAT%" create -n "%ENV_NAME%" python=3.12 pip -y >>"%LOG_FILE%" 2>&1
    if errorlevel 1 goto :fail
) else (
    echo Environment already exists. Missing dependencies will be installed.
)

echo.
echo [3/5] Installing dependencies
echo [3/5] Installing dependencies>>"%LOG_FILE%"

call "%CONDA_BAT%" run --no-capture-output -n "%ENV_NAME%" python -m pip install --retries 5 --timeout 45 --log "%LOG_FILE%" -r "%PROJECT_DIR%requirements.txt"
if errorlevel 1 (
    echo Configured package index failed. Retrying with official PyPI...
    echo Configured package index failed. Retrying with official PyPI...>>"%LOG_FILE%"
    call "%CONDA_BAT%" run --no-capture-output -n "%ENV_NAME%" python -m pip install --index-url https://pypi.org/simple --retries 5 --timeout 45 --log "%LOG_FILE%" -r "%PROJECT_DIR%requirements.txt"
    if errorlevel 1 goto :fail
)

echo.
echo [4/5] Verifying Qt binding
echo [4/5] Verifying Qt binding>>"%LOG_FILE%"
call "%CONDA_BAT%" run -n "%ENV_NAME%" python -c "from timepool.qt_compat import QT_API; print('Qt binding:', QT_API)" >>"%LOG_FILE%" 2>&1
if errorlevel 1 goto :fail

echo.
echo [5/5] Running basic tests
echo [5/5] Running basic tests>>"%LOG_FILE%"
call "%CONDA_BAT%" run -n "%ENV_NAME%" python -m unittest discover -s tests >>"%LOG_FILE%" 2>&1
if errorlevel 1 goto :fail

echo.
echo Environment is ready. You can run run_timepool.bat to start the app.
echo For offline speech, use Download model in the app.
echo Environment is ready.>>"%LOG_FILE%"
popd
pause
exit /b 0

:find_conda
set "CONDA_BAT="
if exist "%USERPROFILE%\anaconda3\condabin\conda.bat" set "CONDA_BAT=%USERPROFILE%\anaconda3\condabin\conda.bat"
if not defined CONDA_BAT if exist "%USERPROFILE%\miniconda3\condabin\conda.bat" set "CONDA_BAT=%USERPROFILE%\miniconda3\condabin\conda.bat"
if not defined CONDA_BAT if exist "%ProgramData%\anaconda3\condabin\conda.bat" set "CONDA_BAT=%ProgramData%\anaconda3\condabin\conda.bat"
if not defined CONDA_BAT if exist "%ProgramData%\miniconda3\condabin\conda.bat" set "CONDA_BAT=%ProgramData%\miniconda3\condabin\conda.bat"
if not defined CONDA_BAT (
    for /f "delims=" %%I in ('where conda.bat 2^>nul') do (
        if not defined CONDA_BAT set "CONDA_BAT=%%I"
    )
)
if not defined CONDA_BAT (
    echo conda.bat was not found. Install Anaconda/Miniconda or add conda to PATH.
    exit /b 1
)
exit /b 0

:fail
echo.
echo Environment setup failed.
echo Environment setup failed. See log: %LOG_FILE%
echo Environment setup failed.>>"%LOG_FILE%"
popd
pause
exit /b 1
