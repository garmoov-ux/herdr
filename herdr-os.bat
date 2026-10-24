@echo off
chcp 65001 >nul
setlocal
set "SCRIPT_DIR=%~dp0"
set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"

where uv >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    pushd "%SCRIPT_DIR%"
    uv run herdr-os %*
    set "EXIT_CODE=%ERRORLEVEL%"
    popd
    endlocal & exit /b %EXIT_CODE%
)

if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
    "%SCRIPT_DIR%.venv\Scripts\python.exe" "%SCRIPT_DIR%herdr_os.py" %*
    set "EXIT_CODE=%ERRORLEVEL%"
    endlocal & exit /b %EXIT_CODE%
)

python "%SCRIPT_DIR%herdr_os.py" %*
endlocal
