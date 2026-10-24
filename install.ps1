#Requires -Version 5.1
<#
.SYNOPSIS
    Herdr x Hermes CLI AgenticOS - Windows One-Click Installer (install.ps1)
.DESCRIPTION
    1. Checks/installs Herdr CLI & uv package manager
    2. Creates .env from .env.example if missing
    3. Configures Alt+V & Prefix+I clipboard paste in %APPDATA%\herdr\config.toml using dynamic repo path
    4. Runs `uv sync` and `uv run herdr-os setup` (fallback: `python herdr_os.py setup`) to initialize workspaces, memory, and agent integrations
#>

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$RepoRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$LocalBin = Join-Path $env:USERPROFILE ".local\bin"
$CargoBin = Join-Path $env:USERPROFILE ".cargo\bin"
foreach ($binDir in @($LocalBin, $CargoBin)) {
    if ($env:Path -notlike "*$binDir*") {
        $env:Path = "$binDir;$env:Path"
    }
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Herdr x Hermes CLI AgenticOS - Windows One-Click Setup" -ForegroundColor Cyan
Write-Host "  Repo Root: $RepoRoot" -ForegroundColor Gray
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Check / Install Herdr
if (-not (Get-Command herdr -ErrorAction SilentlyContinue)) {
    Write-Host "[1/4] Herdr CLI가 감지되지 않았습니다. 공식 설치 스크립트를 실행합니다..." -ForegroundColor Yellow
    Invoke-RestMethod https://herdr.dev/install.ps1 | Invoke-Expression
    if ($env:Path -notlike "*$LocalBin*") {
        $env:Path = "$LocalBin;$env:Path"
    }
} else {
    $ver = (& herdr --version 2>&1) -join " "
    Write-Host "[1/4] Herdr CLI 확인 완료: $ver" -ForegroundColor Green
}

# 2. Setup .env from .env.example if missing
$EnvFile = Join-Path $RepoRoot ".env"
$EnvExample = Join-Path $RepoRoot ".env.example"
if (-not (Test-Path $EnvFile)) {
    if (Test-Path $EnvExample) {
        Copy-Item -Path $EnvExample -Destination $EnvFile -Force
        Write-Host "[2/4] .env 파일이 생성되었습니다 (.env.example 복사 완료)." -ForegroundColor Green
        Write-Host "      -> 메신저 연동을 원하시면 .env 파일에 봇 토큰(Telegram/Slack/Discord)을 입력하세요." -ForegroundColor Gray
    } else {
        New-Item -ItemType File -Path $EnvFile -Force | Out-Null
        Write-Host "[2/4] 빈 .env 파일이 생성되었습니다." -ForegroundColor Yellow
    }
} else {
    Write-Host "[2/4] 기존 .env 설정 파일을 유지합니다." -ForegroundColor Green
}

# 3. Configure %APPDATA%\herdr\config.toml with dynamic path for Alt+V clipboard paste
$HerdrConfigDir = Join-Path $env:APPDATA "herdr"
if (-not (Test-Path $HerdrConfigDir)) {
    New-Item -ItemType Directory -Force -Path $HerdrConfigDir | Out-Null
}
$HerdrConfigPath = Join-Path $HerdrConfigDir "config.toml"
$PasteScriptPath = Join-Path $RepoRoot "scripts\paste_clipboard_image.ps1"
$EscapedPasteScript = $PasteScriptPath.Replace("\", "\\")

$ConfigContent = @"
onboarding = false

[[keys.command]]
key = "alt+v"
type = "shell"
command = "powershell -STA -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File \"$EscapedPasteScript\""

[[keys.command]]
key = "prefix+i"
type = "shell"
command = "powershell -STA -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File \"$EscapedPasteScript\""

[experimental]
switch_ascii_input_source_in_prefix = true
"@

[System.IO.File]::WriteAllText($HerdrConfigPath, $ConfigContent, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "[3/4] Herdr 단축키 설정 완료 ($HerdrConfigPath)" -ForegroundColor Green
Write-Host "      -> Alt+V (클립보드 이미지/텍스트 즉시 붙여넣기) 및 한/영 자동 전환 활성화" -ForegroundColor Gray

# 4. Sync uv environment (.venv + uv.lock) and run herdr_os.py setup
$HerdrOsPy = Join-Path $RepoRoot "herdr_os.py"
$HasUv = [bool](Get-Command uv -ErrorAction SilentlyContinue)
if (-not $HasUv) {
    Write-Host "[4/4] uv가 감지되지 않아 공식 설치 스크립트로 uv 설치를 시도합니다..." -ForegroundColor Yellow
    try {
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
        foreach ($binDir in @($LocalBin, $CargoBin)) {
            if ($env:Path -notlike "*$binDir*") {
                $env:Path = "$binDir;$env:Path"
            }
        }
        $HasUv = [bool](Get-Command uv -ErrorAction SilentlyContinue)
    } catch {
        Write-Host "      -> uv 자동 설치를 건너뛰고 기본 Python 런타임을 사용합니다." -ForegroundColor Yellow
    }
}

if (Test-Path $HerdrOsPy) {
    if ($HasUv) {
        Push-Location $RepoRoot
        try {
            Write-Host "[4/4] uv sync 및 uv run herdr-os setup 실행 중..." -ForegroundColor Cyan
            & uv sync
            & uv run herdr-os setup
        } finally {
            Pop-Location
        }
    } else {
        Write-Host "[4/4] python herdr_os.py setup 실행 중..." -ForegroundColor Cyan
        & python $HerdrOsPy setup
    }
} else {
    Write-Host "[4/4] 기본 디렉터리 및 Herdr 에이전트 훅을 초기화합니다..." -ForegroundColor Cyan
    foreach ($dir in @("memory", "skills", "teams", "captures", "gateways", "templates\roles")) {
        $target = Join-Path $RepoRoot $dir
        if (-not (Test-Path $target)) {
            New-Item -ItemType Directory -Force -Path $target | Out-Null
        }
    }
    if (Get-Command herdr -ErrorAction SilentlyContinue) {
        try { & herdr integration install claude 2>$null | Out-Null } catch {}
        try { & herdr integration install codex 2>$null | Out-Null } catch {}
        try { & herdr integration install antigravity-cli 2>$null | Out-Null } catch {}
    }
}

Write-Host ""
Write-Host "✅ 설치 및 초기화가 완료되었습니다!" -ForegroundColor Green
Write-Host "  • Herdr 실행: 터미널에서 'herdr' 입력" -ForegroundColor White
Write-Host "  • 메신저 브릿지 실행: 'start_all.bat' 더블클릭 또는 'uv run herdr-os gateway start'" -ForegroundColor White
Write-Host "  • 새 팀 생성: 'uv run herdr-os team create --name 마케팅팀' (또는 '.\herdr-os.bat team create --name 마케팅팀')" -ForegroundColor White
