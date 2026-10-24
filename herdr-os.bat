@echo off
chcp 65001 >nul
setlocal
set "SCRIPT_DIR=%~dp0"
python "%SCRIPT_DIR%herdr_os.py" %*
endlocal
