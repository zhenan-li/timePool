@echo off
setlocal EnableExtensions
chcp 65001 >nul

set "ENV_NAME=timepool"
set "PROJECT_DIR=%~dp0"
set "PYTHONNOUSERSITE=1"
set "PYTHONUTF8=1"

pushd "%PROJECT_DIR%" || exit /b 1

call :find_conda
if errorlevel 1 goto :fail

call "%CONDA_BAT%" run --no-capture-output -n "%ENV_NAME%" python "%PROJECT_DIR%main.py" %*
if errorlevel 1 goto :fail

popd
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
echo App launch failed. See the error above.
echo To set up or repair the environment, run prepare_anaconda_env.bat.
popd
pause
exit /b 1
