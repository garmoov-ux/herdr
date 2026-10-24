import argparse
import json
import os
import subprocess
from pathlib import Path

BASE_DIR = Path("F:/herdr")
TEAMS_DIR = BASE_DIR / "teams"

USER_PATH = os.environ.get("PATH", "")
LOCAL_BIN = str(Path.home() / ".local" / "bin")
if LOCAL_BIN not in USER_PATH:
    os.environ["PATH"] = f"{LOCAL_BIN};{USER_PATH}"


def run_herdr(args):
    cmd = ["herdr"] + args
    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return res.returncode, res.stdout.strip(), res.stderr.strip()


def make_role_files(role_dir: Path, team_name: str, role_name: str, role_desc: str, team_memory_path: Path):
    role_dir.mkdir(parents=True, exist_ok=True)
    guide = f"""# 🪪 사원증 및 직무 지침서 ({team_name} - {role_name})

당신은 **{team_name}** 소속의 **{role_name}** AI 직원입니다.

## 🎯 나의 핵심 임무
{role_desc}

## 🧠 기억 및 협업 규칙 (Hermes × Herdr 프로토콜)
1. **출근 시 필독 문서:**
   - 전사 헌법: `F:\\herdr\\AGENTS.md`
   - 사장님 프로필: `F:\\herdr\\memory\\USER_PROFILE.md`
   - 우리 팀 공유 기억장: `{team_memory_path}`
2. **작업 결과 기록:**
   - 내가 조사하거나 작업한 핵심 결과물은 내 머릿속(채팅창)에만 두지 말고, 반드시 `{team_memory_path}` 또는 팀 폴더 안에 마크다운(`.md`) 문서로 저장하세요.
3. **다른 직원/팀과 소통:**
   - `herdr pane list`로 같은 팀 또는 다른 팀(`w1`, `w2`, `w3`)의 창 번호를 확인하고, `herdr pane run <창ID> "<전달할 내용>"`으로 업무를 인계할 수 있습니다.
"""
    (role_dir / "ROLE_GUIDE.md").write_text(guide, encoding="utf-8")
    (role_dir / "AGENTS.md").write_text(guide, encoding="utf-8")
    (role_dir / "CLAUDE.md").write_text(guide, encoding="utf-8")
    (role_dir / "GEMINI.md").write_text(guide, encoding="utf-8")


def create_team(team_name: str, roles_spec: str, launch_agents: bool = False):
    """
    roles_spec 예시: "총괄팀장:agy:팀 전체 기획 및 업무 분배,리서처:claude:자료 조사 및 팩트체크,개발자:codex:코드 작성 및 테스트"
    """
    team_dir = TEAMS_DIR / team_name
    team_dir.mkdir(parents=True, exist_ok=True)
    team_memory = team_dir / "TEAM_MEMORY.md"
    if not team_memory.exists():
        team_memory.write_text(
            f"# 📋 [{team_name}] 부서 전용 공유 기억장 (TEAM_MEMORY.md)\n\n"
            f"- 이 파일은 **{team_name}** 소속 직원들(`p1`, `p2`, `p3`...)이 함께 읽고 쓰는 부서 전용 업무 수첩입니다.\n\n"
            f"## 📝 업무 진행 기록\n",
            encoding="utf-8",
        )

    role_items = []
    for part in roles_spec.split(","):
        part = part.strip()
        if not part:
            continue
        bits = part.split(":")
        r_name = bits[0].strip()
        r_agent = bits[1].strip() if len(bits) > 1 else "claude"
        r_desc = bits[2].strip() if len(bits) > 2 else f"{team_name}의 {r_name} 역할을 수행합니다."
        role_items.append((r_name, r_agent, r_desc))

    if not role_items:
        role_items = [
            ("1_팀장", "agy", "팀 전체 업무 기획, 지시 및 최종 검토를 담당합니다."),
            ("2_리서처", "claude", "인터넷 검색, 자료 조사 및 요약을 담당합니다."),
            ("3_실무작성자", "codex", "실제 문서 작성, 코드 구현 및 결과물 제작을 담당합니다."),
        ]

    # 1. Create per-employee directories and role manuals
    role_dirs = []
    for idx, (r_name, r_agent, r_desc) in enumerate(role_items, start=1):
        sub = team_dir / f"p{idx}_{r_name}"
        make_role_files(sub, team_name, r_name, r_desc, team_memory)
        role_dirs.append((sub, r_name, r_agent))

    # 2. Create Herdr workspace for this team
    first_dir = str(role_dirs[0][0])
    code, out, err = run_herdr(["workspace", "create", "--cwd", first_dir])
    if code != 0:
        print(f"[오류] Herdr 워크스페이스 생성 실패: {err or out}")
        return

    ws_data = json.loads(out).get("result", {}).get("workspace", {})
    ws_id = ws_data.get("workspace_id")
    first_pane = ws_data.get("focused_pane_id")
    run_herdr(["workspace", "rename", ws_id, team_name])
    run_herdr(["pane", "rename", first_pane, f"{role_dirs[0][1]}({role_dirs[0][2]})"])

    created_panes = [(first_pane, role_dirs[0][0], role_dirs[0][1], role_dirs[0][2])]

    # 3. Split additional panes for the remaining employees in the team
    last_pane = first_pane
    for sub_dir, r_name, r_agent in role_dirs[1:]:
        direction = "right" if len(created_panes) == 1 else "down"
        c2, o2, _ = run_herdr(
            ["pane", "split", last_pane, "--direction", direction, "--cwd", str(sub_dir), "--no-focus"]
        )
        if c2 == 0:
            p_id = json.loads(o2)["result"]["pane"]["pane_id"]
            run_herdr(["pane", "rename", p_id, f"{r_name}({r_agent})"])
            created_panes.append((p_id, sub_dir, r_name, r_agent))
            last_pane = p_id

    # 4. Print welcome banner or launch AI in each pane
    for p_id, sub_dir, r_name, r_agent in created_panes:
        run_herdr(
            [
                "pane",
                "run",
                p_id,
                f'echo "=== [{team_name}] {r_name} 책상 ({p_id}) | 지침서: {sub_dir}\\ROLE_GUIDE.md ==="',
            ]
        )
        if launch_agents and r_agent in ("claude", "codex", "agy"):
            run_herdr(["pane", "run", p_id, r_agent])

    print(f"✅ 새 팀 [{team_name}] (워크스페이스 ID: {ws_id}) 생성 및 직원 {len(created_panes)}명 역할 부여 완료!")
    for p_id, sub_dir, r_name, r_agent in created_panes:
        print(f"  - {p_id}: {r_name} (추천 AI: {r_agent}) -> 폴더: {sub_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Herdr 새 팀(w2, w3...) 및 직원별 역할 자동 생성기")
    parser.add_argument("--team", required=True, help="생성할 팀(부서) 이름 (예: 마케팅팀, 주식분석팀)")
    parser.add_argument(
        "--roles",
        default="",
        help="직책:AI종류:설명 형식 (쉼표 구분, 생략 시 기본 3인 팀장/리서처/실무자 자동 구성)",
    )
    parser.add_argument("--launch", action="store_true", help="창 생성과 동시에 AI(claude/agy/codex) 자동 실행")
    args = parser.parse_args()
    create_team(args.team, args.roles, args.launch)
