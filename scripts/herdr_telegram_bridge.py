#!/usr/bin/env python3
"""
Backward-compatible wrapper for Herdr Multi-Messenger Bridge.
Delegates execution to `gateways/messenger_bridge.py`.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from gateways.messenger_bridge import main  # noqa: E402

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[Herdr Multi-Messenger Bridge] 종료되었습니다.")
        sys.exit(0)
