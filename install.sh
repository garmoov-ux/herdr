#!/usr/bin/env bash
# ============================================================================
# Herdr x Hermes CLI AgenticOS - macOS / Linux One-Click Installer (install.sh)
# ============================================================================
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

echo "============================================================"
echo "  Herdr x Hermes CLI AgenticOS - Unix One-Click Setup"
echo "  Repo Root: $REPO_ROOT"
echo "============================================================"

# 1. Check / Install Herdr CLI
if ! command -v herdr >/dev/null 2>&1; then
    echo "[1/4] Herdr CLI가 감지되지 않았습니다. 공식 설치 스크립트를 실행합니다..."
    curl -fsSL https://herdr.dev/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
else
    echo "[1/4] Herdr CLI 확인 완료: $(herdr --version 2>&1 | head -n 1)"
fi

# 2. Setup .env from .env.example if missing
if [ ! -f "$REPO_ROOT/.env" ]; then
    if [ -f "$REPO_ROOT/.env.example" ]; then
        cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
        echo "[2/4] .env 파일이 생성되었습니다 (.env.example 복사 완료)."
        echo "      -> 메신저 연동을 원하시면 .env 파일에 봇 토큰(Telegram/Slack/Discord)을 입력하세요."
    else
        touch "$REPO_ROOT/.env"
        echo "[2/4] 빈 .env 파일이 생성되었습니다."
    fi
else
    echo "[2/4] 기존 .env 설정 파일을 유지합니다."
fi

# 3. Configure ~/.config/herdr/config.toml if missing
HERDR_CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/herdr"
mkdir -p "$HERDR_CONFIG_DIR"
HERDR_CONFIG_FILE="$HERDR_CONFIG_DIR/config.toml"
if [ ! -f "$HERDR_CONFIG_FILE" ]; then
    cat << 'EOF' > "$HERDR_CONFIG_FILE"
onboarding = false

[experimental]
switch_ascii_input_source_in_prefix = true
EOF
    echo "[3/4] Herdr 기본 설정 생성 완료 ($HERDR_CONFIG_FILE)"
else
    echo "[3/4] 기존 Herdr 설정 파일을 유지합니다 ($HERDR_CONFIG_FILE)"
fi

# 4. Sync uv environment (.venv + uv.lock) and run herdr-os setup
if ! command -v uv >/dev/null 2>&1; then
    echo "[4/4] uv가 감지되지 않아 공식 설치 스크립트로 uv 설치를 시도합니다..."
    curl -LsSf https://astral.sh/uv/install.sh | sh || true
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

PYTHON_BIN="python3"
if ! command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python"
fi

if [ -f "$REPO_ROOT/herdr_os.py" ]; then
    if command -v uv >/dev/null 2>&1; then
        echo "[4/4] uv sync 및 uv run herdr-os setup 실행 중..."
        (cd "$REPO_ROOT" && uv sync && uv run herdr-os setup)
    else
        echo "[4/4] $PYTHON_BIN herdr_os.py setup 실행 중..."
        "$PYTHON_BIN" "$REPO_ROOT/herdr_os.py" setup
    fi
else
    echo "[4/4] 기본 디렉터리 및 Herdr 에이전트 훅을 초기화합니다..."
    mkdir -p "$REPO_ROOT/memory" "$REPO_ROOT/skills" "$REPO_ROOT/teams" "$REPO_ROOT/captures" "$REPO_ROOT/gateways" "$REPO_ROOT/templates/roles"
    if command -v herdr >/dev/null 2>&1; then
        herdr integration install claude >/dev/null 2>&1 || true
        herdr integration install codex >/dev/null 2>&1 || true
        herdr integration install antigravity-cli >/dev/null 2>&1 || true
    fi
fi

echo ""
echo "✅ 설치 및 초기화가 완료되었습니다!"
echo "  • Herdr 실행: 터미널에서 'herdr' 입력"
echo "  • 메신저 브릿지 실행: 'uv run herdr-os gateway start' (또는 '$PYTHON_BIN ./gateways/messenger_bridge.py')"
echo "  • 새 팀 생성: 'uv run herdr-os team create --name 마케팅팀' (또는 './herdr-os.sh team create --name 마케팅팀')"
