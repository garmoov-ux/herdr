#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

if command -v uv >/dev/null 2>&1; then
    cd "$SCRIPT_DIR"
    exec uv run herdr-os "$@"
elif [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
    exec "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/herdr_os.py" "$@"
else
    exec python3 "$SCRIPT_DIR/herdr_os.py" "$@"
fi
