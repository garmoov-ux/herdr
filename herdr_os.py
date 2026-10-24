#!/usr/bin/env python3
"""
Herdr × Hermes AgenticOS CLI (herdr_os.py)
100% Portable, Zero-Hardcoded-Path Multi-Team & Multi-Employee CLI Framework.
Uses only the Python 3 standard library.
"""

import argparse
import datetime
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Force UTF-8 encoding on Windows consoles to prevent cp949 UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Dynamic paths relative to project root and user home (Zero hardcoded paths)
ROOT_DIR = Path(__file__).resolve().parent
MEMORY_DIR = ROOT_DIR / "memory"
TEAMS_DIR = ROOT_DIR / "teams"
SKILLS_DIR = ROOT_DIR / "skills"
GATEWAYS_DIR = ROOT_DIR / "gateways"
SCRIPTS_DIR = ROOT_DIR / "scripts"
CAPTURES_DIR = ROOT_DIR / "captures"
ENV_FILE = ROOT_DIR / ".env"
ENV_EXAMPLE_FILE = ROOT_DIR / ".env.example"

# Ensure user local bin directories are on PATH so `herdr` and AI CLIs resolve reliably
_extra_bins = [
    Path.home() / ".local" / "bin",
    Path.home() / ".cargo" / "bin",
]
if os.name == "nt":
    appdata = os.environ.get("APPDATA")
    if appdata:
        _extra_bins.append(Path(appdata) / "npm")
    localappdata = os.environ.get("LOCALAPPDATA")
    if localappdata:
        _extra_bins.append(Path(localappdata) / "Programs" / "herdr")

_current_path = os.environ.get("PATH", "")
for _b in _extra_bins:
    _b_str = str(_b)
    if _b.exists() and _b_str not in _current_path:
        _current_path = f"{_b_str}{os.pathsep}{_current_path}"
os.environ["PATH"] = _current_path

# Supported AI CLI engines and their Herdr integration target names
SUPPORTED_AGENTS: Dict[str, Optional[str]] = {
    "agy": "antigravity-cli",
    "claude": "claude",
    "codex": "codex",
    "opencode": "opencode",
    "gemini": None,
}

# Built-in Role Presets for Teams & Employees
ROLE_PRESETS: List[Tuple[str, str, str]] = [
    ("팀장(PM)", "agy", "팀 전체 업무 기획, 하위 직원(창) 업무 분배 및 최종 결과물 검수를 담당합니다."),
    ("리서처", "claude", "심층 자료 조사, 레퍼런스 수집, 팩트체크 및 핵심 요약을 담당합니다."),
    ("개발자", "codex", "코드 설계, 구현, 버그 수정 및 자동화 테스트 작성을 담당합니다."),
    ("작가", "claude", "보고서, 기획서, 기술 문서 및 카피라이팅 초안 작성을 담당합니다."),
    ("검수자(QA)", "codex", "결과물 품질 검증, 코드 리뷰, 엣지 케이스 점검 및 개선안 도출을 담당합니다."),
]


# =====================================================================
# Utility & Helper Functions
# =====================================================================

def sanitize_folder_name(name: str) -> str:
    """Remove filesystem-unsafe characters from folder names."""
    cleaned = re.sub(r'[<>:"/\\|?*]+', "_", name.strip())
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned or "unnamed"


def run_cmd(cmd: List[str], cwd: Optional[Path] = None) -> Tuple[int, str, str]:
    """Run a subprocess command safely and return (returncode, stdout, stderr)."""
    try:
        res = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except FileNotFoundError:
        return 127, "", f"Command not found: {cmd[0]}"
    except Exception as exc:
        return 1, "", str(exc)


def run_herdr(args: List[str]) -> Tuple[int, str, str]:
    """Execute a `herdr` CLI command."""
    return run_cmd(["herdr"] + args)


def parse_herdr_json(stdout: str) -> dict:
    """Parse JSON output from `herdr` CLI commands."""
    if not stdout:
        return {}
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except Exception:
                pass
    try:
        return json.loads(stdout)
    except Exception:
        return {}


def detect_installed_agents() -> Dict[str, Optional[str]]:
    """Return mapping of agent CLI name -> executable path (or None if not installed)."""
    found: Dict[str, Optional[str]] = {}
    for agent in SUPPORTED_AGENTS:
        found[agent] = shutil.which(agent)
    return found


def get_herdr_config_path() -> Path:
    """Resolve the OS-appropriate Herdr `config.toml` path without hardcoding usernames."""
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "herdr" / "config.toml"
        return Path.home() / "AppData" / "Roaming" / "herdr" / "config.toml"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "herdr" / "config.toml"
    return Path.home() / ".config" / "herdr" / "config.toml"


def load_env_file(path: Path = ENV_FILE) -> Dict[str, str]:
    """Parse `.env` file into a dictionary."""
    data: Dict[str, str] = {}
    if not path.exists():
        return data
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip()
    return data


def save_env_file(env_vars: Dict[str, str], path: Path = ENV_FILE) -> None:
    """Write `.env` file cleanly with comments for multi-messenger configuration."""
    lines = [
        "# =====================================================================",
        "# Herdr × Hermes AgenticOS 환경 설정 파일 (.env)",
        "# `python herdr_os.py setup` 명령어로 언제든 다시 설정할 수 있습니다.",
        "# =====================================================================",
        "",
        f"ENABLED_MESSENGERS={env_vars.get('ENABLED_MESSENGERS', '')}",
        "",
        "# --- Telegram 설정 (@BotFather 발급 토큰 및 허용 채팅방 ID) ---",
        f"TELEGRAM_BOT_TOKEN={env_vars.get('TELEGRAM_BOT_TOKEN', '')}",
        f"TELEGRAM_ALLOWED_CHAT_IDS={env_vars.get('TELEGRAM_ALLOWED_CHAT_IDS', '')}",
        "",
        "# --- Slack 설정 (Bot Token, App Token / Webhook, 채널 ID) ---",
        f"SLACK_BOT_TOKEN={env_vars.get('SLACK_BOT_TOKEN', '')}",
        f"SLACK_APP_TOKEN={env_vars.get('SLACK_APP_TOKEN', '')}",
        f"SLACK_CHANNEL_ID={env_vars.get('SLACK_CHANNEL_ID', '')}",
        f"SLACK_WEBHOOK_URL={env_vars.get('SLACK_WEBHOOK_URL', '')}",
        "",
        "# --- Discord 설정 (Bot Token, 채널 ID, Webhook URL) ---",
        f"DISCORD_BOT_TOKEN={env_vars.get('DISCORD_BOT_TOKEN', '')}",
        f"DISCORD_CHANNEL_ID={env_vars.get('DISCORD_CHANNEL_ID', '')}",
        f"DISCORD_WEBHOOK_URL={env_vars.get('DISCORD_WEBHOOK_URL', '')}",
    ]
    # Preserve any custom user keys
    known_keys = {
        "ENABLED_MESSENGERS",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_ALLOWED_CHAT_IDS",
        "SLACK_BOT_TOKEN",
        "SLACK_APP_TOKEN",
        "SLACK_CHANNEL_ID",
        "SLACK_WEBHOOK_URL",
        "DISCORD_BOT_TOKEN",
        "DISCORD_CHANNEL_ID",
        "DISCORD_WEBHOOK_URL",
    }
    extra_keys = [k for k in env_vars if k not in known_keys]
    if extra_keys:
        lines.append("")
        lines.append("# --- 추가 사용자 정의 설정 ---")
        for k in extra_keys:
            lines.append(f"{k}={env_vars[k]}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def prompt_input(question: str, default: str = "") -> str:
    """Interactive CLI prompt with a default fallback."""
    suffix = f" [{default}]" if default else ""
    try:
        ans = input(f"{question}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    return ans if ans else default


def prompt_yes_no(question: str, default: bool = True) -> bool:
    """Interactive Y/N prompt."""
    hint = "Y/n" if default else "y/N"
    try:
        ans = input(f"{question} ({hint}): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    if not ans:
        return default
    return ans in ("y", "yes", "네", "예", "1")


# =====================================================================
# Memory, Constitution & Role File Generators
# =====================================================================

def ensure_root_constitution() -> None:
    """Ensure root AGENTS.md, CLAUDE.md, and GEMINI.md exist with portable paths."""
    agents_md = ROOT_DIR / "AGENTS.md"
    if not agents_md.exists():
        content = f"""# 🧠 AgenticOS 통합 헌법 (Herdr × Hermes Self-Improving Architecture)

이 워크스페이스(`{ROOT_DIR}`)에서 실행되는 모든 AI 에이전트(`agy`, `claude`, `codex`, `opencode`, `gemini`)는 **Herdr의 멀티 에이전트 제어 능력**과 **Hermes Agent의 자기 진화형 기억·스킬 루프(Self-Improving Loop)**를 결합하여 행동합니다.

---

## 1. 출근 시 필수 초기화 (Boot Sequence)
대화를 시작하거나 새 업무를 부여받으면 반드시 다음 순서로 컨텍스트를 확인합니다:
1. **사용자 프로필 확인:** `{MEMORY_DIR / "USER_PROFILE.md"}`를 읽어 사용자의 선호 방식과 작업 원칙을 숙지합니다.
2. **전사/팀 기억 확인:** `{MEMORY_DIR / "COMPANY_MEMORY.md"}` 및 현재 소속 폴더의 `TEAM_MEMORY.md`(존재 시)를 읽어 이전 작업 맥락을 이어받습니다.
3. **내 직책 및 위치 파악:** 환경변수 `HERDR_WORKSPACE_ID` (`w1`, `w2`...), `HERDR_TAB_ID` (`t1`, `t2`...), `HERDR_PANE_ID` (`w1:p1`, `w1:p2`...) 및 현재 폴더의 `ROLE_GUIDE.md`를 통해 내 역할(팀장/리서처/개발자/작가/검수자 등)을 인식합니다.

---

## 2. 헤르메스식 자기 진화 루프 (Hermes Self-Improving Loop)

### ① 2단 영구 기억 자동 갱신 (Memory Consolidation)
- 사용자의 새로운 선호도, 자주 쓰는 경로, 스타일 교정을 발견하면 **즉시 `{MEMORY_DIR / "USER_PROFILE.md"}`에 추가**합니다.
- 중요한 작업이 완료되거나 아키텍처/결정이 내려지면 **사용자가 별도로 시키지 않아도 `{MEMORY_DIR / "COMPANY_MEMORY.md"}` (또는 팀의 `TEAM_MEMORY.md`)에 날짜와 함께 핵심 요약을 기록**합니다.

### ② 스킬 자동 생성 및 개선 (Autonomous Skill Synthesis)
- 복잡한 문제를 해결했거나, 시행착오 끝에 성공한 절차, 또는 사용자로부터 *"앞으로는 이렇게 해"*라는 피드백을 받았을 때:
  1. `python "{ROOT_DIR / "herdr_os.py"}" skill create <스킬이름> "<설명>"` 명령 또는 직접 `{SKILLS_DIR / "<스킬이름>" / "SKILL.md"}` 파일을 생성/업데이트합니다.
  2. 다음번에 유사한 요청이 들어오면 `{SKILLS_DIR}` 목록을 먼저 검색해 기존 노하우를 즉시 재사용합니다.

---

## 3. Herdr 멀티 팀(`w1`, `w2`, `w3`) & 직원(`p1`, `p2`, `p3`) 오케스트레이션

컨텍스트(기억 용량) 오염을 막기 위해, 팀장 에이전트는 무거운 세부 작업을 직접 다 떠안지 않고 **하위 창(Pane)이나 다른 팀(Workspace)의 AI 직원에게 분배**합니다.

### 핵심 제어 명령어
```bash
# 전체 팀(워크스페이스) 및 창(직원) 상태 확인
python "{ROOT_DIR / "herdr_os.py"}" team list

# 새 팀(w2, w3...) + 직책별 직원 책상 자동 생성
python "{ROOT_DIR / "herdr_os.py"}" team create --name "마케팅팀" --roles "팀장(PM):agy:전체 기획,리서처:claude:자료 조사,작가:codex:원고 작성"

# 특정 창(예: w1:p2)에 직책 부여 및 지침서 생성
python "{ROOT_DIR / "herdr_os.py"}" employee assign w1:p2 --role "리서처" --agent claude --mission "트렌드 및 레퍼런스 심층 조사"

# 특정 창(예: w1:p2)의 직원에게 업무 지시 보내기
python "{ROOT_DIR / "herdr_os.py"}" employee prompt w1:p2 "주어진 주제를 조사해서 TEAM_MEMORY.md 에 요약 저장해줘"

# 특정 창의 화면 출력 읽어오기
herdr pane read w1:p2 --source recent-unwrapped --lines 40
```
"""
        agents_md.write_text(content, encoding="utf-8")

    pointer_text = (
        f"# Agent Instructions\n\n"
        f"반드시 `{ROOT_DIR / 'AGENTS.md'}`와 `{MEMORY_DIR / 'USER_PROFILE.md'}`, "
        f"`{MEMORY_DIR / 'COMPANY_MEMORY.md'}`를 먼저 읽고 지침에 따라 행동하세요.\n"
    )
    for fname in ("CLAUDE.md", "GEMINI.md"):
        fpath = ROOT_DIR / fname
        if not fpath.exists():
            fpath.write_text(pointer_text, encoding="utf-8")


def generate_user_profile_and_memory(
    owner_name: str,
    preferred_lang: str,
    work_style: str,
    overwrite_profile: bool = True,
) -> Tuple[Path, Path]:
    """Create or update `memory/USER_PROFILE.md` and `memory/COMPANY_MEMORY.md`."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    user_profile_path = MEMORY_DIR / "USER_PROFILE.md"
    company_memory_path = MEMORY_DIR / "COMPANY_MEMORY.md"
    today = datetime.date.today().isoformat()

    if overwrite_profile or not user_profile_path.exists():
        profile_md = f"""# 👤 사용자(오너) 프로필 및 작업 원칙 (USER_PROFILE.md)

> 이 파일은 헤르메스(Hermes) 아키텍처의 `USER.md` 역할을 하며, 모든 팀(`w1`, `w2`, `w3`...)의 AI 직원이 출근 시 공유합니다.

## 1. 기본 정보 및 선호사항
- **이름 / 호칭:** {owner_name}
- **선호 언어:** {preferred_lang}
- **운영체제:** {platform.system()} ({platform.release()})
- **메인 작업 본부 경로:** `{ROOT_DIR}`
- **업무 및 보고 스타일:** {work_style}

## 2. 공통 작업 수칙
- 중요한 결정 사항이나 조사 결과는 일회성 채팅으로 흘려보내지 않고 `memory/COMPANY_MEMORY.md` 또는 각 부서의 `TEAM_MEMORY.md`에 기록합니다.
- 반복 가능한 문제 해결 절차는 `skills/<스킬명>/SKILL.md`로 문서화하여 전사 직원이 재사용할 수 있게 합니다.
"""
        user_profile_path.write_text(profile_md, encoding="utf-8")

    if not company_memory_path.exists():
        memory_md = f"""# 🏛️ 전사 공유 영구 기억 노트 (COMPANY_MEMORY.md)

> 이 파일은 헤르메스(Hermes) 아키텍처의 장기 기억(Long-term Memory) 저장소입니다.  
> 각 팀(`w1`, `w2`, `w3`...)의 팀장 AI는 주요 작업이 완료되거나 새로운 결정이 내려질 때마다 이 파일 하단에 날짜와 함께 핵심 요약을 기록합니다.

---

## 📅 기록 로그 (History)

### [{today}] Herdr × Hermes AgenticOS 초기화 완료
- **오너 프로필 등록:** `{owner_name}` ({preferred_lang}) 맞춤형 `memory/USER_PROFILE.md` 생성 완료.
- **멀티 팀·직원 오케스트레이션 준비 완료:** `herdr_os.py` CLI를 통한 팀(`w1`, `w2`...) 및 직원(`p1`, `p2`...) 역할 부여 시스템 활성화.
"""
        company_memory_path.write_text(memory_md, encoding="utf-8")

    return user_profile_path, company_memory_path


def make_role_files(
    role_dir: Path,
    team_name: str,
    role_name: str,
    agent_name: str,
    role_desc: str,
    team_memory_path: Path,
    pane_id: Optional[str] = None,
) -> None:
    """Create per-employee role directory and write ROLE_GUIDE.md, AGENTS.md, CLAUDE.md, GEMINI.md, and EMPLOYEE_META.json."""
    role_dir.mkdir(parents=True, exist_ok=True)
    pane_label = pane_id or "미지정"
    guide = f"""# 🪪 사원증 및 직무 지침서 ({team_name} - {role_name})

당신은 **{team_name}** 소속의 **{role_name}** AI 직원입니다.
- **배정된 창(Pane) ID:** `{pane_label}`
- **주력 AI 엔진:** `{agent_name}`
- **직무 폴더:** `{role_dir}`

## 🎯 나의 핵심 임무 (Mission)
{role_desc}

## 🧠 기억 및 협업 규칙 (Hermes × Herdr 프로토콜)
1. **출근 시 필독 문서:**
   - 전사 헌법: `{ROOT_DIR / "AGENTS.md"}`
   - 오너 프로필: `{MEMORY_DIR / "USER_PROFILE.md"}`
   - 전사 공유 기억장: `{MEMORY_DIR / "COMPANY_MEMORY.md"}`
   - 우리 팀 공유 기억장: `{team_memory_path}`
2. **작업 결과 기록:**
   - 조사하거나 작업한 핵심 결과물은 채팅창에만 두지 말고, 반드시 `{team_memory_path}` 또는 현재 직무 폴더(`{role_dir}`) 안에 마크다운(`.md`) 문서로 저장하세요.
3. **다른 직원/팀과 소통:**
   - `herdr pane list` 또는 `python "{ROOT_DIR / "herdr_os.py"}" team list`로 같은 팀 또는 다른 팀(`w1`, `w2`, `w3`)의 창 번호를 확인합니다.
   - `python "{ROOT_DIR / "herdr_os.py"}" employee prompt <창ID> "<전달할 내용>"` 또는 `herdr pane run <창ID> "<전달할 내용>"`으로 업무를 인계할 수 있습니다.
4. **스킬 축적 (Self-Improving):**
   - 재사용 가치가 높은 해결법이나 절차를 발견하면 `python "{ROOT_DIR / "herdr_os.py"}" skill create <스킬이름> "<설명>"`으로 전사 스킬을 등록하세요.
"""
    for filename in ("ROLE_GUIDE.md", "AGENTS.md", "CLAUDE.md", "GEMINI.md"):
        (role_dir / filename).write_text(guide, encoding="utf-8")

    meta = {
        "team_name": team_name,
        "role_name": role_name,
        "agent": agent_name,
        "mission": role_desc,
        "pane_id": pane_id,
        "role_dir": str(role_dir),
        "team_memory": str(team_memory_path),
        "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    (role_dir / "EMPLOYEE_META.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def configure_herdr_toml() -> Path:
    """Update Herdr's config.toml with dynamic clipboard paste shortcut and prefix input switch."""
    cfg_path = get_herdr_config_path()
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    ps_script = SCRIPTS_DIR / "paste_clipboard_image.ps1"
    ps_escaped = str(ps_script).replace("\\", "\\\\")

    new_config = f"""onboarding = false

[[keys.command]]
key = "alt+v"
type = "shell"
command = "powershell -STA -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File \\"{ps_escaped}\\""

[[keys.command]]
key = "prefix+i"
type = "shell"
command = "powershell -STA -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File \\"{ps_escaped}\\""

[experimental]
switch_ascii_input_source_in_prefix = true
"""
    cfg_path.write_text(new_config, encoding="utf-8")
    return cfg_path


# =====================================================================
# Team & Employee Core Operations
# =====================================================================

def parse_roles_spec(roles_spec: str, team_name: str) -> List[Tuple[str, str, str]]:
    """
    Parse roles specification string like:
    "팀장(PM):agy:팀 전체 기획,리서처:claude:자료 조사,개발자:codex:코드 구현"
    """
    role_items: List[Tuple[str, str, str]] = []
    if roles_spec:
        for part in roles_spec.split(","):
            part = part.strip()
            if not part:
                continue
            bits = part.split(":", 2)
            r_name = bits[0].strip()
            r_agent = bits[1].strip() if len(bits) > 1 and bits[1].strip() else "claude"
            r_desc = (
                bits[2].strip()
                if len(bits) > 2 and bits[2].strip()
                else f"{team_name}의 {r_name} 역할을 수행합니다."
            )
            role_items.append((r_name, r_agent, r_desc))

    if not role_items:
        role_items = [
            ("팀장(PM)", "agy", "팀 전체 업무 기획, 지시 및 최종 검토를 담당합니다."),
            ("리서처", "claude", "인터넷 검색, 자료 조사 및 핵심 요약을 담당합니다."),
            ("개발자", "codex", "실제 문서 작성, 코드 구현 및 결과물 제작을 담당합니다."),
        ]
    return role_items


def interactive_pick_roles(team_name: str) -> List[Tuple[str, str, str]]:
    """Interactively ask user to configure employee roles and AI engines for a team."""
    print(f"\n👥 [{team_name}] 부서 직원(Pane) 구성을 시작합니다.")
    print("  [프리셋 목록]")
    for idx, (r_name, r_agent, r_desc) in enumerate(ROLE_PRESETS, start=1):
        print(f"    {idx}. {r_name} (기본 AI: {r_agent}) - {r_desc}")
    print("    6. 직접 입력 (Custom 직책)")

    count_str = prompt_input("배치할 직원(창) 수를 입력하세요 (1~6)", "3")
    try:
        count = max(1, min(6, int(count_str)))
    except ValueError:
        count = 3

    chosen_roles: List[Tuple[str, str, str]] = []
    for i in range(1, count + 1):
        default_preset = str(min(i, len(ROLE_PRESETS)))
        print(f"\n  --- [직원 p{i} 설정] ---")
        choice = prompt_input(f"  p{i} 프리셋 번호 선택 (1~5, 직접 입력은 6)", default_preset)
        try:
            c_idx = int(choice)
        except ValueError:
            c_idx = 0

        if 1 <= c_idx <= len(ROLE_PRESETS):
            base_name, base_agent, base_desc = ROLE_PRESETS[c_idx - 1]
            r_name = base_name
            r_agent = prompt_input(
                f"  p{i} ({r_name}) AI 엔진 선택 [agy/claude/codex/opencode/gemini]",
                base_agent,
            )
            r_desc = prompt_input(f"  p{i} ({r_name}) 상세 임무", base_desc)
        else:
            r_name = prompt_input(f"  p{i} 직책 이름 (예: 데이터분석가)", f"직원{i}")
            r_agent = prompt_input(
                f"  p{i} ({r_name}) AI 엔진 선택 [agy/claude/codex/opencode/gemini]",
                "claude",
            )
            r_desc = prompt_input(
                f"  p{i} ({r_name}) 상세 임무",
                f"{team_name}의 {r_name} 직무를 수행합니다.",
            )
        chosen_roles.append((r_name, r_agent, r_desc))

    return chosen_roles


def create_team(
    team_name: str,
    roles_spec: str = "",
    launch_agents: bool = False,
    role_items_override: Optional[List[Tuple[str, str, str]]] = None,
) -> Optional[str]:
    """
    Create a new team folder structure under `teams/<team_name>/`,
    create a Herdr workspace, split panes for each employee, rename them,
    and optionally launch their AI CLI engines.
    """
    safe_team_dir_name = sanitize_folder_name(team_name)
    team_dir = TEAMS_DIR / safe_team_dir_name
    team_dir.mkdir(parents=True, exist_ok=True)
    team_memory = team_dir / "TEAM_MEMORY.md"
    if not team_memory.exists():
        team_memory.write_text(
            f"# 📋 [{team_name}] 부서 전용 공유 기억장 (TEAM_MEMORY.md)\n\n"
            f"- 이 파일은 **{team_name}** 소속 직원들(`p1`, `p2`, `p3`...)이 함께 읽고 쓰는 부서 전용 업무 수첩입니다.\n\n"
            f"## 📝 업무 진행 기록\n",
            encoding="utf-8",
        )

    role_items = (
        role_items_override
        if role_items_override is not None
        else parse_roles_spec(roles_spec, team_name)
    )

    # 1. Pre-create employee directories & role manuals
    role_dirs: List[Tuple[Path, str, str, str]] = []
    for idx, (r_name, r_agent, r_desc) in enumerate(role_items, start=1):
        safe_role = sanitize_folder_name(r_name)
        sub = team_dir / f"p{idx}_{safe_role}"
        make_role_files(sub, team_name, r_name, r_agent, r_desc, team_memory)
        role_dirs.append((sub, r_name, r_agent, r_desc))

    # 2. Create Herdr workspace for this team
    first_dir = str(role_dirs[0][0])
    code, out, err = run_herdr(["workspace", "create", "--cwd", first_dir])
    if code != 0:
        print(f"⚠️  Herdr 워크스페이스 생성 실패 (오프라인 모드이거나 Herdr 미실행): {err or out}")
        print(f"📁 로컬 팀 폴더 및 지침서는 정상 생성되었습니다: {team_dir}")
        for idx, (sub_dir, r_name, r_agent, _) in enumerate(role_dirs, start=1):
            print(f"  - p{idx}: {r_name} ({r_agent}) -> {sub_dir}")
        return None

    ws_data = parse_herdr_json(out).get("result", {}).get("workspace", {})
    ws_id = ws_data.get("workspace_id", "")
    first_pane = ws_data.get("focused_pane_id", "")

    if ws_id:
        run_herdr(["workspace", "rename", ws_id, team_name])
    if first_pane:
        run_herdr(["pane", "rename", first_pane, f"{role_dirs[0][1]}({role_dirs[0][2]})"])
        make_role_files(
            role_dirs[0][0],
            team_name,
            role_dirs[0][1],
            role_dirs[0][2],
            role_dirs[0][3],
            team_memory,
            pane_id=first_pane,
        )

    created_panes = [(first_pane, role_dirs[0][0], role_dirs[0][1], role_dirs[0][2])]

    # 3. Split additional panes for the remaining employees in the team
    last_pane = first_pane
    for sub_dir, r_name, r_agent, r_desc in role_dirs[1:]:
        direction = "right" if len(created_panes) == 1 else "down"
        c2, o2, _ = run_herdr(
            [
                "pane",
                "split",
                last_pane,
                "--direction",
                direction,
                "--cwd",
                str(sub_dir),
                "--no-focus",
            ]
        )
        if c2 == 0:
            p_id = parse_herdr_json(o2).get("result", {}).get("pane", {}).get("pane_id", "")
            if p_id:
                run_herdr(["pane", "rename", p_id, f"{r_name}({r_agent})"])
                make_role_files(
                    sub_dir, team_name, r_name, r_agent, r_desc, team_memory, pane_id=p_id
                )
                created_panes.append((p_id, sub_dir, r_name, r_agent))
                last_pane = p_id

    # 4. Print welcome banner or launch AI CLI in each pane
    for p_id, sub_dir, r_name, r_agent in created_panes:
        if not p_id:
            continue
        guide_path = sub_dir / "ROLE_GUIDE.md"
        run_herdr(
            [
                "pane",
                "run",
                p_id,
                f'echo "=== [{team_name}] {r_name} 책상 ({p_id}) | 지침서: {guide_path} ==="',
            ]
        )
        if launch_agents and r_agent in SUPPORTED_AGENTS:
            run_herdr(["pane", "run", p_id, r_agent])

    print(
        f"\n✅ 새 팀 [{team_name}] (워크스페이스 ID: {ws_id}) 생성 및 직원 {len(created_panes)}명 역할 부여 완료!"
    )
    for p_id, sub_dir, r_name, r_agent in created_panes:
        print(f"  - {p_id}: {r_name} (AI: {r_agent}) -> 폴더: {sub_dir}")
    return ws_id


def assign_employee_to_pane(
    pane_id: str,
    role_name: str,
    agent_name: str,
    mission: str,
    team_name: Optional[str] = None,
    launch: bool = False,
) -> Path:
    """Assign a role and mission to an existing Herdr pane (e.g., w1:p2)."""
    ws_id = pane_id.split(":")[0] if ":" in pane_id else "w1"
    pane_short = pane_id.split(":")[1] if ":" in pane_id else pane_id

    # Look up workspace label from Herdr if team_name was not explicitly provided
    if not team_name:
        code, out, _ = run_herdr(["workspace", "list"])
        if code == 0:
            ws_list = parse_herdr_json(out).get("result", {}).get("workspaces", [])
            for ws in ws_list:
                if ws.get("workspace_id") == ws_id:
                    label = ws.get("label") or ws_id
                    team_name = label if label != ws_id else f"{ws_id}_본부"
                    break
    if not team_name:
        team_name = f"{ws_id}_본부"

    safe_team = sanitize_folder_name(team_name)
    safe_role = sanitize_folder_name(role_name)
    team_dir = TEAMS_DIR / safe_team
    team_dir.mkdir(parents=True, exist_ok=True)
    team_memory = team_dir / "TEAM_MEMORY.md"
    if not team_memory.exists():
        team_memory.write_text(
            f"# 📋 [{team_name}] 부서 전용 공유 기억장 (TEAM_MEMORY.md)\n\n"
            f"- 이 파일은 **{team_name}** 소속 직원들이 함께 읽고 쓰는 부서 전용 업무 수첩입니다.\n\n"
            f"## 📝 업무 진행 기록\n",
            encoding="utf-8",
        )

    role_dir = team_dir / f"{pane_short}_{safe_role}"
    make_role_files(
        role_dir=role_dir,
        team_name=team_name,
        role_name=role_name,
        agent_name=agent_name,
        role_desc=mission,
        team_memory_path=team_memory,
        pane_id=pane_id,
    )

    # Rename pane in Herdr & announce role
    rc, _, err = run_herdr(["pane", "rename", pane_id, f"{role_name}({agent_name})"])
    if rc == 0:
        guide_path = role_dir / "ROLE_GUIDE.md"
        run_herdr(
            [
                "pane",
                "run",
                pane_id,
                f'echo "=== [{team_name}] {role_name} ({pane_id}) 임무 배정 완료 | 지침서: {guide_path} ==="',
            ]
        )
        if launch and agent_name in SUPPORTED_AGENTS:
            run_herdr(["pane", "run", pane_id, f'cd "{role_dir}"'])
            run_herdr(["pane", "run", pane_id, agent_name])
        print(f"✅ 창 [{pane_id}] 직책 부여 완료: {role_name} (AI: {agent_name})")
    else:
        print(f"⚠️  Herdr 창 이름 변경 실패 ({err}). 로컬 지침서는 정상 생성되었습니다.")

    print(f"   - 직무 지침서: {role_dir / 'ROLE_GUIDE.md'}")
    print(f"   - 팀 기억장:   {team_memory}")
    return role_dir


# =====================================================================
# Subcommand Handlers
# =====================================================================

def cmd_doctor(_args: argparse.Namespace) -> int:
    """Run comprehensive health check of Herdr, AI CLIs, .env, memory, and skills."""
    print("=" * 68)
    print("🩺 Herdr × Hermes AgenticOS 시스템 진단 (doctor)")
    print("=" * 68)
    print(f"📂 프로젝트 루트 경로: {ROOT_DIR}")
    print(f"💻 운영체제 환경:      {platform.system()} {platform.release()} ({sys.version.split()[0]})")

    # 1. Herdr CLI & Server check
    print("\n[1/4] 🖥️  Herdr 터미널 멀티플렉서 상태")
    herdr_bin = shutil.which("herdr")
    if herdr_bin:
        rc, ver_out, _ = run_herdr(["--version"])
        print(f"  ✅ Herdr 실행 파일: {herdr_bin} ({ver_out or '버전 확인됨'})")
        rc_ws, ws_out, ws_err = run_herdr(["workspace", "list"])
        if rc_ws == 0:
            ws_list = parse_herdr_json(ws_out).get("result", {}).get("workspaces", [])
            print(f"  ✅ Herdr 서버 연결: 정상 작동 중 (활성 워크스페이스 {len(ws_list)}개)")
        else:
            print(f"  ⚠️  Herdr 서버 연결: 비활성 또는 세션 외부 ({ws_err or 'Herdr 창에서 실행 필요'})")
    else:
        print("  ❌ Herdr CLI가 설치되어 있지 않거나 PATH에서 찾을 수 없습니다.")

    cfg_path = get_herdr_config_path()
    if cfg_path.exists():
        print(f"  ✅ Herdr 설정 파일: {cfg_path}")
    else:
        print(f"  ℹ️  Herdr 설정 파일 미생성 ({cfg_path}) -> `herdr-os setup`에서 자동 구성 가능")

    # 2. Installed AI CLIs
    print("\n[2/4] 🤖 설치된 AI 에이전트 CLI 상태")
    installed_agents = detect_installed_agents()
    any_agent = False
    for agent, path in installed_agents.items():
        target = SUPPORTED_AGENTS[agent]
        if path:
            any_agent = True
            hook_note = f"Herdr 훅 타겟: {target}" if target else "스탠드얼론 CLI"
            print(f"  ✅ {agent:<10} : 설치됨 ({path}) [{hook_note}]")
        else:
            print(f"  ⚪ {agent:<10} : 미설치")
    if not any_agent:
        print("  ⚠️  감지된 AI CLI가 없습니다. (agy, claude, codex, opencode, gemini 중 최소 1개 권장)")

    # 3. Messenger (.env) Configuration
    print("\n[3/4] 💬 멀티 메신저 연동 설정 (.env)")
    if ENV_FILE.exists():
        env_vars = load_env_file(ENV_FILE)
        enabled = env_vars.get("ENABLED_MESSENGERS", "")
        print(f"  ✅ .env 파일 존재 ({ENV_FILE})")
        if enabled:
            print(f"  📌 활성화된 메신저 목록: {enabled}")

        tg_tok = env_vars.get("TELEGRAM_BOT_TOKEN", "")
        tg_ok = bool(tg_tok and tg_tok != "YOUR_TELEGRAM_BOT_TOKEN_HERE")
        sl_tok = env_vars.get("SLACK_BOT_TOKEN", "") or env_vars.get("SLACK_WEBHOOK_URL", "")
        dc_tok = env_vars.get("DISCORD_BOT_TOKEN", "") or env_vars.get("DISCORD_WEBHOOK_URL", "")

        print(f"  {'✅' if tg_ok else '⚪'} Telegram : {'토큰 설정됨' if tg_ok else '미설정'}")
        print(f"  {'✅' if sl_tok else '⚪'} Slack    : {'토큰/웹훅 설정됨' if sl_tok else '미설정'}")
        print(f"  {'✅' if dc_tok else '⚪'} Discord  : {'토큰/웹훅 설정됨' if dc_tok else '미설정'}")
    else:
        print(f"  ⚪ .env 파일 없음 ({ENV_FILE}) -> `herdr-os setup`으로 메신저 연동 가능")

    # 4. Memory, Teams, Skills, Gateways directories
    print("\n[4/4] 🧠 기억장(Memory) · 부서(Teams) · 스킬(Skills) · 게이트웨이 상태")
    up_file = MEMORY_DIR / "USER_PROFILE.md"
    cm_file = MEMORY_DIR / "COMPANY_MEMORY.md"
    print(f"  {'✅' if up_file.exists() else '⚠️ '} 오너 프로필 (USER_PROFILE.md)     : {up_file}")
    print(f"  {'✅' if cm_file.exists() else '⚠️ '} 전사 기억장 (COMPANY_MEMORY.md)   : {cm_file}")

    skill_files = list(SKILLS_DIR.glob("*/SKILL.md")) if SKILLS_DIR.exists() else []
    print(f"  ✅ 보유 스킬 (skills/*/SKILL.md)    : {len(skill_files)}개")

    team_dirs = (
        [d for d in TEAMS_DIR.iterdir() if d.is_dir()] if TEAMS_DIR.exists() else []
    )
    print(f"  ✅ 구성된 부서 폴더 (teams/*)       : {len(team_dirs)}개")

    gw_script = GATEWAYS_DIR / "messenger_bridge.py"
    legacy_gw = SCRIPTS_DIR / "herdr_telegram_bridge.py"
    if gw_script.exists():
        print(f"  ✅ 멀티 메신저 게이트웨이           : {gw_script}")
    elif legacy_gw.exists():
        print(f"  ℹ️  레거시 텔레그램 브릿지 존재      : {legacy_gw}")
    else:
        print(f"  ⚪ 메신저 브릿지 스크립트 대기 중   : {gw_script}")

    print("=" * 68)
    return 0


def cmd_setup(_args: argparse.Namespace) -> int:
    """Interactive 4-step CLI Onboarding Wizard (`herdr-os setup`)."""
    print("=" * 68)
    print("🚀 Herdr × Hermes AgenticOS 대화형 온보딩 마법사 (Setup Wizard)")
    print("=" * 68)
    print(f"설치 경로: {ROOT_DIR}\n")

    # -----------------------------------------------------------------
    # Step 1: Herdr & AI CLI Detection + Integration Hook Installation
    # -----------------------------------------------------------------
    print("━" * 68)
    print("📌 [Step 1/4] Herdr 및 AI 에이전트 CLI 감지 · 훅(Integration) 자동 연동")
    print("━" * 68)
    herdr_bin = shutil.which("herdr")
    if herdr_bin:
        _, ver_out, _ = run_herdr(["--version"])
        print(f"  ✅ Herdr 감지됨: {ver_out} ({herdr_bin})")
    else:
        print("  ⚠️  Herdr가 감지되지 않았습니다. https://herdr.dev 에서 설치 후 다시 실행해 주세요.")

    installed_agents = detect_installed_agents()
    detected_names = [a for a, p in installed_agents.items() if p]
    print(
        f"  🔍 설치된 AI CLI 감지 결과: {', '.join(detected_names) if detected_names else '없음'}"
    )

    if herdr_bin and detected_names:
        if prompt_yes_no("  감지된 AI 에이전트에 Herdr 상태 표시 훅(integration)을 자동 연결할까요?", True):
            for agent in detected_names:
                target = SUPPORTED_AGENTS.get(agent)
                if not target:
                    continue
                rc, out, err = run_herdr(["integration", "install", target])
                if rc == 0:
                    print(f"    ✅ `herdr integration install {target}` 완료 ({agent})")
                else:
                    print(f"    ⚠️  `{target}` 연동 참고: {err or out}")

    if prompt_yes_no(
        "  Herdr 단축키(Alt+V 클립보드 이미지 붙여넣기 & 한/영 프리픽스 자동 전환)를 설정할까요?",
        True,
    ):
        cfg_file = configure_herdr_toml()
        print(f"    ✅ Herdr 설정 업데이트 완료: {cfg_file}")

    # -----------------------------------------------------------------
    # Step 2: Owner / User Profile & Company Memory Onboarding
    # -----------------------------------------------------------------
    print("\n" + "━" * 68)
    print("📌 [Step 2/4] 오너(사용자) 프로필 및 전사 영구 기억장(Memory) 설정")
    print("━" * 68)
    owner_name = prompt_input("  1) 사용자 이름 또는 직함/호칭을 입력하세요", "사장님")
    preferred_lang = prompt_input("  2) 기본 응답 언어를 입력하세요", "한국어")
    work_style = prompt_input(
        "  3) 선호하는 업무/보고 스타일을 입력하세요",
        "비개발자도 직관적으로 이해할 수 있도록 핵심 요약과 명확한 설명 선호",
    )

    ensure_root_constitution()
    up_path, cm_path = generate_user_profile_and_memory(
        owner_name=owner_name,
        preferred_lang=preferred_lang,
        work_style=work_style,
        overwrite_profile=True,
    )
    print(f"  ✅ 오너 프로필 생성 완료: {up_path}")
    print(f"  ✅ 전사 기억장 준비 완료: {cm_path}")

    # -----------------------------------------------------------------
    # Step 3: Multi-Messenger Setup Wizard (Telegram, Slack, Discord)
    # -----------------------------------------------------------------
    print("\n" + "━" * 68)
    print("📌 [Step 3/4] 멀티 메신저 원격 제어 설정 (Telegram / Slack / Discord)")
    print("━" * 68)
    print("  사용할 메신저 번호를 선택하세요 (복수 선택 시 쉼표 구분, 예: 1,2 / 건너뛰기는 0):")
    print("    1. Telegram (텔레그램 봇 양방향 제어)")
    print("    2. Slack    (슬랙 봇 / 채널 연동)")
    print("    3. Discord  (디스코드 봇 / 웹훅 연동)")
    print("    0. 지금은 건너뛰기 (나중에 설정)")

    env_vars = load_env_file(ENV_FILE)
    ms_choice = prompt_input("  메신저 선택", "0")
    selected_tokens = [c.strip().lower() for c in ms_choice.split(",") if c.strip()]
    enabled_list: List[str] = []

    if "1" in selected_tokens or "telegram" in selected_tokens or "all" in selected_tokens:
        enabled_list.append("telegram")
        print("\n  [Telegram 설정]")
        env_vars["TELEGRAM_BOT_TOKEN"] = prompt_input(
            "    - 텔레그램 봇 토큰 (@BotFather 발급)",
            env_vars.get("TELEGRAM_BOT_TOKEN", ""),
        )
        env_vars["TELEGRAM_ALLOWED_CHAT_IDS"] = prompt_input(
            "    - 허용할 Chat ID (비워두면 첫 메시지 전송자 자동 등록)",
            env_vars.get("TELEGRAM_ALLOWED_CHAT_IDS", ""),
        )

    if "2" in selected_tokens or "slack" in selected_tokens or "all" in selected_tokens:
        enabled_list.append("slack")
        print("\n  [Slack 설정]")
        env_vars["SLACK_BOT_TOKEN"] = prompt_input(
            "    - Slack Bot Token (xoxb-...)",
            env_vars.get("SLACK_BOT_TOKEN", ""),
        )
        env_vars["SLACK_APP_TOKEN"] = prompt_input(
            "    - Slack App-Level Token (xapp-..., 선택사항)",
            env_vars.get("SLACK_APP_TOKEN", ""),
        )
        env_vars["SLACK_CHANNEL_ID"] = prompt_input(
            "    - 기본 Slack 채널 ID (예: C0123456789)",
            env_vars.get("SLACK_CHANNEL_ID", ""),
        )
        env_vars["SLACK_WEBHOOK_URL"] = prompt_input(
            "    - Slack Incoming Webhook URL (선택사항)",
            env_vars.get("SLACK_WEBHOOK_URL", ""),
        )

    if "3" in selected_tokens or "discord" in selected_tokens or "all" in selected_tokens:
        enabled_list.append("discord")
        print("\n  [Discord 설정]")
        env_vars["DISCORD_BOT_TOKEN"] = prompt_input(
            "    - Discord Bot Token",
            env_vars.get("DISCORD_BOT_TOKEN", ""),
        )
        env_vars["DISCORD_CHANNEL_ID"] = prompt_input(
            "    - 기본 Discord 채널 ID",
            env_vars.get("DISCORD_CHANNEL_ID", ""),
        )
        env_vars["DISCORD_WEBHOOK_URL"] = prompt_input(
            "    - Discord Webhook URL (선택사항)",
            env_vars.get("DISCORD_WEBHOOK_URL", ""),
        )

    if enabled_list:
        env_vars["ENABLED_MESSENGERS"] = ",".join(enabled_list)
    save_env_file(env_vars, ENV_FILE)
    print(f"  ✅ 메신저 환경설정 저장 완료: {ENV_FILE}")

    # -----------------------------------------------------------------
    # Step 4: Initial Team (w1, w2...) & Employee (p1, p2, p3...) Setup
    # -----------------------------------------------------------------
    print("\n" + "━" * 68)
    print("📌 [Step 4/4] 초기 부서(Team 워크스페이스) 및 AI 직원(Pane) 배치")
    print("━" * 68)
    if prompt_yes_no("  지금 바로 첫 번째 부서(팀)와 AI 직원 책상(p1, p2, p3...)을 생성할까요?", True):
        t_name = prompt_input("  생성할 부서(팀) 이름을 입력하세요", "메인본부")
        roles_override = interactive_pick_roles(t_name)
        launch_now = prompt_yes_no("  각 창에 배정된 AI CLI를 즉시 실행할까요?", False)
        create_team(
            team_name=t_name,
            launch_agents=launch_now,
            role_items_override=roles_override,
        )
    else:
        print("  ℹ️  나중에 `herdr-os team create` 명령으로 언제든 부서를 생성할 수 있습니다.")

    print("\n" + "=" * 68)
    print("🎉 온보딩 완료! 주요 명령어 안내:")
    print("  - 상태 점검:       herdr-os doctor")
    print("  - 새 부서 생성:    herdr-os team create")
    print("  - 부서/직원 목록:  herdr-os team list")
    print("  - 직원 직책 부여:  herdr-os employee assign w1:p2 --role 리서처 --agent claude --mission \"자료 조사\"")
    print("  - 직원 업무 지시:  herdr-os employee prompt w1:p2 \"주어진 주제를 요약해줘\"")
    print("  - 메신저 브릿지:   herdr-os gateway start")
    print("=" * 68)
    return 0


def cmd_team_create(args: argparse.Namespace) -> int:
    """Handler for `team create [--name <팀명>] [--roles <직책:AI:설명,...>] [--launch]`."""
    team_name = args.name
    roles_spec = args.roles or ""
    launch = bool(args.launch)
    role_items_override = None

    if not team_name:
        print("🏢 [새 부서(Team) 대화형 생성 마법사]")
        team_name = prompt_input("생성할 부서(팀) 이름을 입력하세요 (예: 마케팅팀, 개발팀)", "기획개발팀")
        if not roles_spec:
            role_items_override = interactive_pick_roles(team_name)
        if not args.launch:
            launch = prompt_yes_no("창 분할 후 AI 에이전트를 즉시 실행할까요?", False)

    create_team(
        team_name=team_name,
        roles_spec=roles_spec,
        launch_agents=launch,
        role_items_override=role_items_override,
    )
    return 0


def cmd_team_list(_args: argparse.Namespace) -> int:
    """Handler for `team list`: shows all Herdr workspaces, panes, and assigned employee roles."""
    print("=" * 72)
    print("🏢 Herdr × Hermes 전체 부서(Workspace) 및 직원(Pane) 현황")
    print("=" * 72)

    # Collect employee metadata from `teams/*/*/EMPLOYEE_META.json`
    pane_meta_map: Dict[str, dict] = {}
    team_folders: Dict[str, List[dict]] = {}
    if TEAMS_DIR.exists():
        for t_dir in sorted(TEAMS_DIR.iterdir()):
            if not t_dir.is_dir():
                continue
            team_folders[t_dir.name] = []
            for sub in sorted(t_dir.iterdir()):
                if not sub.is_dir():
                    continue
                meta_file = sub / "EMPLOYEE_META.json"
                if meta_file.exists():
                    try:
                        m = json.loads(meta_file.read_text(encoding="utf-8"))
                        team_folders[t_dir.name].append(m)
                        if m.get("pane_id"):
                            pane_meta_map[m["pane_id"]] = m
                    except Exception:
                        pass
                elif (sub / "ROLE_GUIDE.md").exists():
                    team_folders[t_dir.name].append(
                        {
                            "team_name": t_dir.name,
                            "role_name": sub.name,
                            "agent": "-",
                            "mission": "ROLE_GUIDE.md 참조",
                            "pane_id": None,
                            "role_dir": str(sub),
                        }
                    )

    # Query live Herdr workspaces and panes
    rc_ws, ws_out, _ = run_herdr(["workspace", "list"])
    rc_p, p_out, _ = run_herdr(["pane", "list"])

    if rc_ws == 0 and rc_p == 0:
        workspaces = parse_herdr_json(ws_out).get("result", {}).get("workspaces", [])
        panes = parse_herdr_json(p_out).get("result", {}).get("panes", [])
        print("\n🖥️  [실시간 Herdr 워크스페이스 & 창 상태]")
        if not workspaces:
            print("  (활성 워크스페이스가 없습니다)")
        for ws in workspaces:
            ws_id = ws.get("workspace_id", "?")
            label = ws.get("label", ws_id)
            status = ws.get("agent_status", "idle")
            focus_mark = "⭐" if ws.get("focused") else "  "
            print(f"\n{focus_mark} [{ws_id}] 부서명: {label} (상태: {status}, 창 {ws.get('pane_count', 0)}개)")
            ws_panes = [p for p in panes if p.get("workspace_id") == ws_id]
            for p in ws_panes:
                p_id = p.get("pane_id", "?")
                p_agent = p.get("agent") or "-"
                p_status = p.get("agent_status", "unknown")
                p_cwd = p.get("cwd", "")
                meta = pane_meta_map.get(p_id)
                if meta:
                    role_info = f"{meta.get('role_name')} (추천AI: {meta.get('agent')}) | 임무: {meta.get('mission')}"
                else:
                    role_info = f"실행중AI: {p_agent} | 경로: {p_cwd}"
                p_focus = "👉" if p.get("focused") else "  "
                print(f"   {p_focus} {p_id:<6} [{p_status:<8}] {role_info}")
    else:
        print("\nℹ️  Herdr 서버에 연결되지 않아 로컬 부서 폴더(`teams/`) 기준으로 표시합니다.")

    print("\n📁 [로컬 부서 및 직무 지침서 폴더 (`teams/`)]")
    if not team_folders:
        print("  (생성된 부서 폴더가 없습니다. `herdr-os team create`로 새 부서를 만드세요.)")
    else:
        for t_name, members in team_folders.items():
            print(f"  📂 teams/{t_name}/ (직원 {len(members)}명)")
            for m in members:
                p_tag = m.get("pane_id") or "미배정"
                print(
                    f"     - [{p_tag}] {m.get('role_name')} (AI: {m.get('agent')}) : {m.get('mission')}"
                )
    print("=" * 72)
    return 0


def cmd_employee_assign(args: argparse.Namespace) -> int:
    """Handler for `employee assign <pane_id> --role <직책> --agent <AI> --mission "<임무>" [--team <팀명>] [--launch]`."""
    pane_id = args.pane_id
    role_name = args.role or prompt_input(f"[{pane_id}] 부여할 직책 이름", "리서처")
    agent_name = args.agent or prompt_input(
        f"[{pane_id}] 사용할 AI 엔진 (agy/claude/codex/opencode/gemini)", "claude"
    )
    mission = args.mission or prompt_input(
        f"[{pane_id}] 핵심 임무 설명",
        f"{role_name}로서 배정된 조사 및 실무 과제를 완수하고 TEAM_MEMORY.md에 기록합니다.",
    )
    assign_employee_to_pane(
        pane_id=pane_id,
        role_name=role_name,
        agent_name=agent_name,
        mission=mission,
        team_name=args.team,
        launch=bool(args.launch),
    )
    return 0


def cmd_employee_prompt(args: argparse.Namespace) -> int:
    """Handler for `employee prompt <pane_id> "<업무지시>"`."""
    pane_id = args.pane_id
    instruction = " ".join(args.instruction).strip()
    if not instruction:
        print("❌ 전달할 업무 지시 내용을 입력해 주세요.")
        return 1

    rc, out, err = run_herdr(["pane", "run", pane_id, instruction])
    if rc == 0:
        print(f"📨 [{pane_id}] 창 직원에게 업무 지시 전송 완료!")
        print(f"   💬 지시 내용: {instruction}")
        return 0
    print(f"❌ [{pane_id}] 업무 지시 전송 실패: {err or out}")
    return 1


def parse_skill_frontmatter(skill_md: Path) -> Tuple[str, str]:
    """Extract `name` and `description` from a SKILL.md YAML frontmatter."""
    name = skill_md.parent.name
    desc = ""
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return name, desc

    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    k = k.strip().lower()
                    v = v.strip().strip('"').strip("'")
                    if k == "name" and v:
                        name = v
                    elif k == "description" and v:
                        desc = v
    return name, desc


def cmd_skill_list(_args: argparse.Namespace) -> int:
    """Handler for `skill list`."""
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    skill_files = sorted(SKILLS_DIR.glob("*/SKILL.md"))
    print("=" * 68)
    print(f"📚 보유 중인 헤르메스 스킬 목록 (`{SKILLS_DIR}`) - 총 {len(skill_files)}개")
    print("=" * 68)
    if not skill_files:
        print("  (등록된 스킬이 없습니다. `herdr-os skill create <이름> \"<설명>\"`으로 생성하세요.)")
    else:
        for sf in skill_files:
            s_name, s_desc = parse_skill_frontmatter(sf)
            print(f"  🔹 {s_name:<24} : {s_desc}")
            print(f"     경로: {sf}")
    print("=" * 68)
    return 0


def cmd_skill_create(args: argparse.Namespace) -> int:
    """Handler for `skill create <name> "<description>"`."""
    raw_name = args.name.strip()
    safe_name = sanitize_folder_name(raw_name.lower().replace(" ", "-"))
    desc = " ".join(args.description).strip() or f"{raw_name} 수행 절차 및 노하우 스킬"

    skill_dir = SKILLS_DIR / safe_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    today = datetime.date.today().isoformat()

    content = f"""---
name: {safe_name}
description: "{desc}"
---

# 🛠️ {raw_name} ({safe_name})

> 생성일: {today}  
> 이 스킬은 Herdr × Hermes 자기 진화 루프(Self-Improving Skill Loop)를 통해 생성된 재사용 가능 업무 표준 절차서(SOP)입니다.

## 1. 언제 이 스킬을 사용하는가 (Trigger)
- {desc}

## 2. 표준 수행 절차 (Step-by-Step Procedure)
1. 관련 컨텍스트(`memory/COMPANY_MEMORY.md` 또는 `TEAM_MEMORY.md`)를 먼저 확인합니다.
2. 아래 검증된 명령어 및 절차를 순서대로 실행합니다.
3. 실행 결과를 검증하고 새롭게 발견한 엣지 케이스가 있다면 이 `SKILL.md`를 업데이트합니다.

## 3. 주의사항 및 노하우 (Best Practices)
- 하드코딩된 절대 경로 대신 프로젝트 상대 경로를 사용합니다.
"""
    skill_file.write_text(content, encoding="utf-8")
    print(f"✅ 새 스킬 생성 완료: {skill_file}")
    return 0


def cmd_gateway_start(args: argparse.Namespace) -> int:
    """Handler for `gateway start`: launches `gateways/messenger_bridge.py`."""
    gw_script = GATEWAYS_DIR / "messenger_bridge.py"
    legacy_script = SCRIPTS_DIR / "herdr_telegram_bridge.py"

    target_script = gw_script if gw_script.exists() else legacy_script
    if not target_script.exists():
        print(f"❌ 게이트웨이 스크립트를 찾을 수 없습니다: {gw_script}")
        return 1

    print(f"🌐 멀티 메신저 게이트웨이를 시작합니다: {target_script}")
    extra = getattr(args, "extra", []) or []
    cmd = [sys.executable, str(target_script)] + extra
    try:
        return subprocess.call(cmd, cwd=str(ROOT_DIR))
    except KeyboardInterrupt:
        print("\n🛑 메신저 게이트웨이가 종료되었습니다.")
        return 0


# =====================================================================
# CLI Argument Parser Builder
# =====================================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="herdr-os",
        description="Herdr × Hermes AgenticOS: 멀티 팀(w1, w2...) 및 AI 직원(p1, p2...) 오케스트레이션 CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="사용할 하위 명령어")

    # 1. setup
    subparsers.add_parser(
        "setup",
        help="대화형 온보딩 마법사 실행 (Herdr 연동, 오너 프로필, 멀티 메신저, 초기 팀 구성)",
    )

    # 2. doctor
    subparsers.add_parser(
        "doctor",
        help="Herdr 서버, 설치된 AI CLI, .env 메신저 설정, 기억장/스킬 폴더 상태 점검",
    )

    # 3. team (create | list)
    team_parser = subparsers.add_parser("team", help="부서(Workspace) 생성 및 목록 조회")
    team_sub = team_parser.add_subparsers(dest="team_cmd", help="team 하위 명령")

    tc_parser = team_sub.add_parser(
        "create",
        help="새 부서(w2, w3...) 및 직원별 창(p1, p2, p3)과 지침서 자동 생성",
    )
    tc_parser.add_argument("--name", "--team", dest="name", default="", help="생성할 팀(부서) 이름")
    tc_parser.add_argument(
        "--roles",
        default="",
        help="직책:AI엔진:설명 형식 (쉼표 구분, 예: '팀장(PM):agy:총괄,리서처:claude:조사,개발자:codex:구현')",
    )
    tc_parser.add_argument(
        "--launch",
        action="store_true",
        help="창 생성과 동시에 각 직원의 AI 에이전트 CLI를 즉시 실행",
    )

    team_sub.add_parser(
        "list",
        help="전체 Herdr 워크스페이스, 창 상태 및 배정된 직원 역할 조회",
    )

    # 4. employee (assign | prompt)
    emp_parser = subparsers.add_parser("employee", help="개별 창(Pane) 직원 직책 배정 및 업무 지시")
    emp_sub = emp_parser.add_subparsers(dest="emp_cmd", help="employee 하위 명령")

    ea_parser = emp_sub.add_parser(
        "assign",
        help="특정 창(예: w1:p2)에 직책과 임무를 배정하고 맞춤 지침서 생성",
    )
    ea_parser.add_argument("pane_id", help="대상 창 ID (예: w1:p1, w1:p2, w2:p1)")
    ea_parser.add_argument("--role", required=True, help="직책 이름 (예: 팀장(PM), 리서처, 개발자, 작가, 검수자(QA))")
    ea_parser.add_argument(
        "--agent",
        default="claude",
        choices=list(SUPPORTED_AGENTS.keys()),
        help="사용할 AI 엔진 (agy, claude, codex, opencode, gemini)",
    )
    ea_parser.add_argument("--mission", required=True, help="핵심 임무 설명")
    ea_parser.add_argument("--team", default=None, help="소속 부서 이름 (생략 시 워크스페이스 이름 자동 감지)")
    ea_parser.add_argument("--launch", action="store_true", help="배정 후 해당 창에서 즉시 AI CLI 실행")

    ep_parser = emp_sub.add_parser(
        "prompt",
        help="특정 창(예: w1:p2)의 직원에게 업무 지시 전송 (`herdr pane run`)",
    )
    ep_parser.add_argument("pane_id", help="대상 창 ID (예: w1:p2)")
    ep_parser.add_argument("instruction", nargs="+", help="전달할 업무 지시 내용")

    # 5. skill (list | create)
    skill_parser = subparsers.add_parser("skill", help="헤르메스식 재사용 스킬(skills/) 조회 및 생성")
    skill_sub = skill_parser.add_subparsers(dest="skill_cmd", help="skill 하위 명령")

    skill_sub.add_parser("list", help="등록된 모든 스킬 목록 조회")

    sc_parser = skill_sub.add_parser("create", help="새 재사용 스킬 템플릿 생성")
    sc_parser.add_argument("name", help="스킬 이름 (예: web-research-sop)")
    sc_parser.add_argument("description", nargs="+", help="스킬 한 줄 설명")

    # 6. gateway (start)
    gw_parser = subparsers.add_parser("gateway", help="멀티 메신저(Telegram/Slack/Discord) 브릿지 제어")
    gw_sub = gw_parser.add_subparsers(dest="gw_cmd", help="gateway 하위 명령")
    gws_parser = gw_sub.add_parser("start", help="메신저 브릿지 데몬 시작 (gateways/messenger_bridge.py)")
    gws_parser.add_argument("extra", nargs=argparse.REMAINDER, help="브릿지 스크립트에 전달할 추가 인자")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "setup":
        return cmd_setup(args)
    if args.command == "doctor":
        return cmd_doctor(args)
    if args.command == "team":
        if args.team_cmd == "create":
            return cmd_team_create(args)
        if args.team_cmd == "list":
            return cmd_team_list(args)
        parser.parse_args(["team", "--help"])
        return 0
    if args.command == "employee":
        if args.emp_cmd == "assign":
            return cmd_employee_assign(args)
        if args.emp_cmd == "prompt":
            return cmd_employee_prompt(args)
        parser.parse_args(["employee", "--help"])
        return 0
    if args.command == "skill":
        if args.skill_cmd == "list":
            return cmd_skill_list(args)
        if args.skill_cmd == "create":
            return cmd_skill_create(args)
        parser.parse_args(["skill", "--help"])
        return 0
    if args.command == "gateway":
        if args.gw_cmd == "start":
            return cmd_gateway_start(args)
        parser.parse_args(["gateway", "--help"])
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
