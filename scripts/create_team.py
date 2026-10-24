#!/usr/bin/env python3
"""
Herdr 새 팀(w2, w3...) 및 직원별 역할 자동 생성기
`herdr_os.py`의 핵심 팀 생성 로직을 공유하며 하드코딩 경로 없이 동작합니다.
"""

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from herdr_os import create_team, interactive_pick_roles, prompt_input, prompt_yes_no  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Herdr 새 팀(w2, w3...) 및 직원별 역할 자동 생성기 (herdr_os 연동)"
    )
    parser.add_argument(
        "--team",
        "--name",
        dest="team",
        default="",
        help="생성할 팀(부서) 이름 (예: 마케팅팀, 주식분석팀, 생략 시 대화형 프롬프트 실행)",
    )
    parser.add_argument(
        "--roles",
        default="",
        help="직책:AI종류:설명 형식 (쉼표 구분, 생략 시 기본 3인 팀장/리서처/개발자 구성 또는 대화형 선택)",
    )
    parser.add_argument(
        "--launch",
        action="store_true",
        help="창 생성과 동시에 AI(claude/agy/codex/opencode/gemini) 자동 실행",
    )
    args = parser.parse_args()

    team_name = args.team
    roles_spec = args.roles
    launch = args.launch
    role_items_override = None

    if not team_name:
        team_name = prompt_input("생성할 팀(부서) 이름을 입력하세요", "기획개발팀")
        if not roles_spec:
            role_items_override = interactive_pick_roles(team_name)
        if not launch:
            launch = prompt_yes_no("창 분할 후 AI 에이전트를 즉시 실행할까요?", False)

    create_team(
        team_name=team_name,
        roles_spec=roles_spec,
        launch_agents=launch,
        role_items_override=role_items_override,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
