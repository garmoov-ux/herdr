@echo off
chcp 65001 > nul
title Herdr x Hermes Multi-Messenger Bridge (Telegram / Slack / Discord)
set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"
cd /d "%~dp0"

echo ============================================================
echo   Herdr x Hermes CLI AgenticOS - Multi-Messenger Bridge
echo   Working Directory: %~dp0
echo ============================================================
echo.

where uv >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    uv run python "%~dp0gateways\messenger_bridge.py"
) else if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" "%~dp0gateways\messenger_bridge.py"
) else (
    python "%~dp0gateways\messenger_bridge.py"
)
pause
