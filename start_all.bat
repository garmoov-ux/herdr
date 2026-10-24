@echo off
chcp 65001 > nul
title Herdr x Hermes Multi-Messenger Bridge (Telegram / Slack / Discord)
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
cd /d "%~dp0"

echo ============================================================
echo   Herdr x Hermes CLI AgenticOS - Multi-Messenger Bridge
echo   Working Directory: %~dp0
echo ============================================================
echo.

python "%~dp0gateways\messenger_bridge.py"
pause
