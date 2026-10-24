@echo off
chcp 65001 > nul
title AgenticOS Launcher (Herdr + Telegram + Pixel Agents)
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
cd /d "F:\herdr"

echo [1/2] Pixel Agents 가상 오피스 서버 시작 중 (포트 8089)...
start "Pixel Agents Office" cmd /c "set PATH=%USERPROFILE%\.local\bin;%PATH% && cd /d F:\herdr && pixel-agents --port 8089"

echo [2/2] Herdr 텔레그램 브릿지 시작 중...
python "F:\herdr\scripts\herdr_telegram_bridge.py"
pause
