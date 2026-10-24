#!/usr/bin/env python3
"""
Herdr × Hermes AgenticOS CLI (herdr_os.py)
100% Portable, Zero-Hardcoded-Path Multi-Team & Multi-Employee CLI Framework.
Uses only the Python 3 standard library.
"""

import argparse
import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import urllib.parse
import webbrowser
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
TEMPLATES_DIR = ROOT_DIR / "templates"
ROLE_TEMPLATES_DIR = TEMPLATES_DIR / "roles"
SKILL_TEMPLATES_DIR = TEMPLATES_DIR / "skills"
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
    ("총괄 기획 팀장", "agy", "팀 전체 업무 기획, 하위 직원(창) 업무 분배 및 최종 결과물 검수를 담당합니다."),
    ("수석 리서처", "claude", "심층 자료 조사, 레퍼런스 수집, 팩트체크 및 핵심 요약을 담당합니다."),
    ("수석 개발자", "codex", "코드 설계, 구현, 버그 수정 및 자동화 테스트 작성을 담당합니다."),
    ("수석 UI/UX 디자이너", "agy", "직관적인 정보 구조(IA), UI/UX 프로토타입, 디자인 시스템 및 디자인 토큰 명세를 담당합니다."),
    ("콘텐츠 작가", "claude", "보고서, 기획서, 기술 문서 및 카피라이팅 초안 작성을 담당합니다."),
    ("품질 검수자", "codex", "결과물 품질 검증, 코드 리뷰, 엣지 케이스 점검 및 개선안 도출을 담당합니다."),
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


def install_skill_from_catalog(skill_name: str) -> Tuple[bool, str]:
    """Copy a skill template from `templates/skills/<skill_name>/SKILL.md` into `skills/<skill_name>/SKILL.md`."""
    safe_name = sanitize_folder_name(skill_name.strip().lower().replace(" ", "-"))
    src_file = SKILL_TEMPLATES_DIR / safe_name / "SKILL.md"
    if not src_file.exists():
        return False, f"카탈로그에서 '{safe_name}' 스킬 템플릿을 찾을 수 없습니다: {src_file}"
    dest_dir = SKILLS_DIR / safe_name
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / "SKILL.md"
    disabled_file = dest_dir / "SKILL.md.disabled"
    if disabled_file.exists():
        disabled_file.unlink()
    shutil.copyfile(src_file, dest_file)
    return True, str(dest_file)


def toggle_installed_skill(skill_name: str) -> Tuple[bool, bool, str]:
    """Toggle an installed skill between enabled (`SKILL.md`) and disabled (`SKILL.md.disabled`)."""
    safe_name = sanitize_folder_name(skill_name.strip())
    s_dir = SKILLS_DIR / safe_name
    active_f = s_dir / "SKILL.md"
    disabled_f = s_dir / "SKILL.md.disabled"
    if active_f.exists():
        active_f.rename(disabled_f)
        return True, False, f"'{safe_name}' 스킬이 비활성화(OFF) 되었습니다."
    if disabled_f.exists():
        disabled_f.rename(active_f)
        return True, True, f"'{safe_name}' 스킬이 활성화(ON) 되었습니다."
    return False, False, f"'{safe_name}' 스킬을 찾을 수 없습니다."


def delete_installed_skill(skill_name: str) -> Tuple[bool, str]:
    """Delete an installed skill directory from `skills/<skill_name>`."""
    safe_name = sanitize_folder_name(skill_name.strip())
    s_dir = SKILLS_DIR / safe_name
    if not s_dir.exists() or not s_dir.is_dir():
        return False, f"'{safe_name}' 스킬 폴더가 존재하지 않습니다."
    shutil.rmtree(s_dir, ignore_errors=True)
    return True, f"'{safe_name}' 스킬이 삭제되었습니다."


def perform_factory_reset(reset_env: bool = False) -> dict:
    """
    Wipe all registered teams (`teams/*` except `.gitkeep`),
    active skills (`skills/*` except `.gitkeep`),
    and user/company memories (`memory/USER_PROFILE.md`, `memory/COMPANY_MEMORY.md`)
    back to a clean 0-state.
    """
    removed_teams = 0
    removed_skills = 0
    removed_memories = 0

    TEAMS_DIR.mkdir(parents=True, exist_ok=True)
    for item in TEAMS_DIR.iterdir():
        if item.name == ".gitkeep":
            continue
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
            removed_teams += 1
        else:
            item.unlink(missing_ok=True)
    (TEAMS_DIR / ".gitkeep").touch()

    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    for item in SKILLS_DIR.iterdir():
        if item.name == ".gitkeep":
            continue
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
            removed_skills += 1
        else:
            item.unlink(missing_ok=True)
    (SKILLS_DIR / ".gitkeep").touch()

    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    for m_name in ("USER_PROFILE.md", "COMPANY_MEMORY.md"):
        mp = MEMORY_DIR / m_name
        if mp.exists():
            mp.unlink(missing_ok=True)
            removed_memories += 1
    (MEMORY_DIR / ".gitkeep").touch()

    for state_p in (ROOT_DIR / "state.json", GATEWAYS_DIR / "state.json", SCRIPTS_DIR / "state.json"):
        if state_p.exists():
            state_p.unlink(missing_ok=True)

    if reset_env and ENV_FILE.exists():
        ENV_FILE.unlink(missing_ok=True)

    return {
        "removed_teams": removed_teams,
        "removed_skills": removed_skills,
        "removed_memories": removed_memories,
    }


def collect_system_state() -> dict:
    """Gather complete live state for the Hermes-style Admin Control Center UI."""
    # 1. Herdr CLI & Workspaces & Panes
    herdr_bin = shutil.which("herdr")
    herdr_version = ""
    herdr_connected = False
    workspaces = []
    panes = []
    if herdr_bin:
        _, ver_out, _ = run_herdr(["--version"])
        herdr_version = ver_out
        rc_ws, ws_out, _ = run_herdr(["workspace", "list"])
        rc_p, p_out, _ = run_herdr(["pane", "list"])
        if rc_ws == 0 and rc_p == 0:
            herdr_connected = True
            workspaces = parse_herdr_json(ws_out).get("result", {}).get("workspaces", [])
            panes = parse_herdr_json(p_out).get("result", {}).get("panes", [])

    # 2. Local teams & employee metadata
    pane_meta_map: Dict[str, dict] = {}
    local_teams: List[dict] = []
    if TEAMS_DIR.exists():
        for t_dir in sorted(TEAMS_DIR.iterdir()):
            if not t_dir.is_dir() or t_dir.name.startswith("."):
                continue
            members = []
            for sub in sorted(t_dir.iterdir()):
                if not sub.is_dir():
                    continue
                meta_file = sub / "EMPLOYEE_META.json"
                if meta_file.exists():
                    try:
                        m = json.loads(meta_file.read_text(encoding="utf-8"))
                        members.append(m)
                        if m.get("pane_id"):
                            pane_meta_map[m["pane_id"]] = m
                    except Exception:
                        pass
                elif (sub / "ROLE_GUIDE.md").exists():
                    members.append(
                        {
                            "team_name": t_dir.name,
                            "role_name": sub.name,
                            "agent": "claude",
                            "mission": "ROLE_GUIDE.md 참조",
                            "pane_id": None,
                            "role_dir": str(sub),
                        }
                    )
            team_mem_file = t_dir / "TEAM_MEMORY.md"
            local_teams.append(
                {
                    "folder": t_dir.name,
                    "path": str(t_dir),
                    "has_memory": team_mem_file.exists(),
                    "members": members,
                }
            )

    for p in panes:
        pid = p.get("pane_id", "")
        if pid in pane_meta_map:
            p["assigned_meta"] = pane_meta_map[pid]

    # 3. Installed Skills & Catalog Skills
    installed_skills = []
    if SKILLS_DIR.exists():
        for s_dir in sorted(SKILLS_DIR.iterdir()):
            if not s_dir.is_dir() or s_dir.name.startswith("."):
                continue
            active_md = s_dir / "SKILL.md"
            disabled_md = s_dir / "SKILL.md.disabled"
            target_md = active_md if active_md.exists() else (disabled_md if disabled_md.exists() else None)
            if target_md:
                s_name, s_desc = parse_skill_frontmatter(target_md)
                content = target_md.read_text(encoding="utf-8", errors="replace")
                installed_skills.append(
                    {
                        "id": s_dir.name,
                        "name": s_name,
                        "description": s_desc,
                        "enabled": active_md.exists(),
                        "path": str(target_md),
                        "content": content,
                    }
                )

    installed_ids = {s["id"] for s in installed_skills}
    catalog_skills = []
    if SKILL_TEMPLATES_DIR.exists():
        for c_dir in sorted(SKILL_TEMPLATES_DIR.iterdir()):
            if not c_dir.is_dir() or c_dir.name.startswith("."):
                continue
            c_md = c_dir / "SKILL.md"
            if c_md.exists():
                c_name, c_desc = parse_skill_frontmatter(c_md)
                catalog_skills.append(
                    {
                        "id": c_dir.name,
                        "name": c_name,
                        "description": c_desc,
                        "installed": c_dir.name in installed_ids,
                        "content": c_md.read_text(encoding="utf-8", errors="replace"),
                    }
                )

    # 4. Memories & Constitution
    up_file = MEMORY_DIR / "USER_PROFILE.md"
    cm_file = MEMORY_DIR / "COMPANY_MEMORY.md"
    ag_file = ROOT_DIR / "AGENTS.md"

    # 5. Messenger (.env)
    env_vars = load_env_file(ENV_FILE)

    # 6. Installed AI CLI Engines
    installed_agents = detect_installed_agents()

    return {
        "root_dir": str(ROOT_DIR),
        "os_info": f"{platform.system()} {platform.release()} (Python {sys.version.split()[0]})",
        "herdr": {
            "installed": bool(herdr_bin),
            "bin_path": herdr_bin or "",
            "version": herdr_version,
            "connected": herdr_connected,
            "config_path": str(get_herdr_config_path()),
            "config_exists": get_herdr_config_path().exists(),
        },
        "agents": {k: {"installed": bool(v), "path": v or ""} for k, v in installed_agents.items()},
        "role_presets": [
            {"role": r, "agent": a, "mission": m} for (r, a, m) in ROLE_PRESETS
        ],
        "workspaces": workspaces,
        "panes": panes,
        "local_teams": local_teams,
        "installed_skills": installed_skills,
        "catalog_skills": catalog_skills,
        "memory": {
            "user_profile_exists": up_file.exists(),
            "user_profile": up_file.read_text(encoding="utf-8", errors="replace") if up_file.exists() else "",
            "company_memory_exists": cm_file.exists(),
            "company_memory": cm_file.read_text(encoding="utf-8", errors="replace") if cm_file.exists() else "",
            "agents_md_exists": ag_file.exists(),
            "agents_md": ag_file.read_text(encoding="utf-8", errors="replace") if ag_file.exists() else "",
        },
        "env": {
            "exists": ENV_FILE.exists(),
            "ENABLED_MESSENGERS": env_vars.get("ENABLED_MESSENGERS", ""),
            "TELEGRAM_BOT_TOKEN": env_vars.get("TELEGRAM_BOT_TOKEN", ""),
            "TELEGRAM_ALLOWED_CHAT_IDS": env_vars.get("TELEGRAM_ALLOWED_CHAT_IDS", ""),
            "SLACK_BOT_TOKEN": env_vars.get("SLACK_BOT_TOKEN", ""),
            "SLACK_APP_TOKEN": env_vars.get("SLACK_APP_TOKEN", ""),
            "SLACK_CHANNEL_ID": env_vars.get("SLACK_CHANNEL_ID", ""),
            "SLACK_WEBHOOK_URL": env_vars.get("SLACK_WEBHOOK_URL", ""),
            "DISCORD_BOT_TOKEN": env_vars.get("DISCORD_BOT_TOKEN", ""),
            "DISCORD_CHANNEL_ID": env_vars.get("DISCORD_CHANNEL_ID", ""),
            "DISCORD_WEBHOOK_URL": env_vars.get("DISCORD_WEBHOOK_URL", ""),
        },
    }



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
# Hermes-style Web Admin Control Center UI (`herdr_os.py ui`)
# =====================================================================

HERMES_UI_HTML = r"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Herdr × Hermes — Admin Control Center</title>
  <style>
    :root {
      --bg: #0b0e14;
      --bg-sidebar: #111622;
      --bg-card: #161c2a;
      --bg-input: #0e131d;
      --border: #252f42;
      --text: #e6edf3;
      --text-muted: #8b949e;
      --accent: #f59e0b;
      --accent-hover: #d97706;
      --blue: #3b82f6;
      --green: #10b981;
      --red: #ef4444;
      --purple: #8b5cf6;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Pretendard", "Malgun Gothic", "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
      display: flex;
      min-height: 100vh;
    }
    .sidebar {
      width: 280px;
      background: var(--bg-sidebar);
      border-right: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      padding: 20px 14px;
      flex-shrink: 0;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 6px 10px 20px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 16px;
    }
    .brand-logo {
      width: 38px;
      height: 38px;
      border-radius: 10px;
      background: linear-gradient(135deg, #f59e0b, #ef4444);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
      font-weight: bold;
    }
    .brand-title { font-size: 16px; font-weight: 700; color: #fff; }
    .brand-sub { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
    .nav-btn {
      width: 100%;
      text-align: left;
      background: transparent;
      color: var(--text-muted);
      border: 1px solid transparent;
      padding: 12px 14px;
      border-radius: 9px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 6px;
      transition: all 0.15s;
    }
    .nav-btn:hover { background: rgba(255,255,255,0.04); color: var(--text); }
    .nav-btn.active {
      background: rgba(245, 158, 11, 0.14);
      color: var(--accent);
      border-color: rgba(245, 158, 11, 0.35);
    }
    .sidebar-footer {
      margin-top: auto;
      padding: 12px;
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 9px;
      font-size: 12px;
      color: var(--text-muted);
      line-height: 1.5;
    }
    .main {
      flex: 1;
      padding: 28px 34px;
      overflow-y: auto;
      max-width: 1380px;
    }
    .topbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border);
    }
    .topbar h1 { font-size: 22px; font-weight: 700; }
    .topbar p { font-size: 13px; color: var(--text-muted); margin-top: 4px; }
    .status-pill {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      padding: 6px 13px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 600;
      background: var(--bg-card);
      border: 1px solid var(--border);
    }
    .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--green); }
    .dot.off { background: var(--red); }
    .tab-pane { display: none; }
    .tab-pane.active { display: block; }
    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
    .grid-3 { display: grid; grid-template-columns: repeat(auto-fill, minmax(310px, 1fr)); gap: 16px; }
    .card {
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
      margin-bottom: 20px;
    }
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
    }
    .card-title { font-size: 16px; font-weight: 700; display: flex; align-items: center; gap: 8px; }
    .card-desc { font-size: 13px; color: var(--text-muted); margin-bottom: 16px; line-height: 1.5; }
    label { display: block; font-size: 12px; font-weight: 600; color: var(--text-muted); margin-bottom: 6px; }
    input[type="text"], input[type="password"], select, textarea {
      width: 100%;
      background: var(--bg-input);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 10px 12px;
      border-radius: 8px;
      font-size: 13px;
      font-family: inherit;
      margin-bottom: 12px;
    }
    textarea { min-height: 90px; resize: vertical; font-family: "Consolas", "Monaco", monospace; line-height: 1.5; }
    input:focus, select:focus, textarea:focus { outline: none; border-color: var(--accent); }
    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      padding: 9px 15px;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 600;
      border: 1px solid var(--border);
      background: var(--bg-input);
      color: var(--text);
      cursor: pointer;
      transition: all 0.15s;
    }
    .btn:hover { border-color: var(--text-muted); background: rgba(255,255,255,0.06); }
    .btn-primary { background: var(--accent); color: #000; border-color: var(--accent); }
    .btn-primary:hover { background: var(--accent-hover); border-color: var(--accent-hover); }
    .btn-blue { background: var(--blue); color: #fff; border-color: var(--blue); }
    .btn-green { background: var(--green); color: #000; border-color: var(--green); }
    .btn-danger { background: rgba(239, 68, 68, 0.15); color: #fca5a5; border-color: rgba(239, 68, 68, 0.4); }
    .btn-danger:hover { background: var(--red); color: #fff; }
    .btn-sm { padding: 6px 10px; font-size: 12px; }
    .badge {
      display: inline-block;
      padding: 3px 8px;
      border-radius: 6px;
      font-size: 11px;
      font-weight: 700;
      background: rgba(59, 130, 246, 0.16);
      color: #93c5fd;
    }
    .badge.green { background: rgba(16, 185, 129, 0.16); color: #6ee7b7; }
    .badge.amber { background: rgba(245, 158, 11, 0.16); color: #fcd34d; }
    .badge.gray { background: rgba(139, 148, 158, 0.16); color: #9ca3af; }
    .slot-row {
      background: var(--bg-input);
      border: 1px solid var(--border);
      border-radius: 9px;
      padding: 12px;
      margin-bottom: 10px;
    }
    .slot-grid {
      display: grid;
      grid-template-columns: 1.2fr 1fr 0.9fr auto;
      gap: 8px;
      align-items: center;
    }
    .pane-item {
      background: var(--bg-input);
      border: 1px solid var(--border);
      border-radius: 9px;
      padding: 13px;
      margin-bottom: 10px;
      cursor: pointer;
      transition: border-color 0.15s;
    }
    .pane-item:hover, .pane-item.selected { border-color: var(--accent); }
    .toast {
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: #1e293b;
      border: 1px solid var(--accent);
      color: #fff;
      padding: 13px 18px;
      border-radius: 10px;
      font-size: 13px;
      font-weight: 600;
      box-shadow: 0 10px 30px rgba(0,0,0,0.5);
      display: none;
      z-index: 9999;
    }
    .modal-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.72);
      display: none;
      align-items: center;
      justify-content: center;
      z-index: 1000;
    }
    .modal {
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 12px;
      width: 92%;
      max-width: 760px;
      padding: 24px;
      max-height: 90vh;
      overflow-y: auto;
    }
    .empty-box {
      text-align: center;
      padding: 28px 16px;
      color: var(--text-muted);
      border: 1px dashed var(--border);
      border-radius: 10px;
      font-size: 13px;
    }
  </style>
</head>
<body>
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-logo">⚡</div>
      <div>
        <div class="brand-title">Herdr × Hermes</div>
        <div class="brand-sub">AgenticOS Admin Control Center</div>
      </div>
    </div>

    <button class="nav-btn active" onclick="switchTab('tab-teams', this)">🏢 팀 &amp; 직원 배치</button>
    <button class="nav-btn" onclick="switchTab('tab-skills', this)">⚡ 스킬 매니저 (Skills Hub)</button>
    <button class="nav-btn" onclick="switchTab('tab-memory', this)">🧠 기억장 &amp; 헌법 (Brain)</button>
    <button class="nav-btn" onclick="switchTab('tab-messenger', this)">💬 메신저 게이트웨이</button>
    <button class="nav-btn" onclick="switchTab('tab-doctor', this)">🔄 초기화 / 진단 (Reset)</button>

    <div class="sidebar-footer">
      <div><strong>Zero-Dependency Engine</strong></div>
      <div id="sidebar-stats" style="margin-top:6px;">로딩 중...</div>
    </div>
  </aside>

  <main class="main">
    <div class="topbar">
      <div>
        <h1>Hermes Agent Control Center</h1>
        <p>명령어 입력 없이 클릭만으로 팀(Workspace)·직원(Pane)·스킬(Skills)·기억장(Memory)·메신저를 통합 관리합니다.</p>
      </div>
      <div style="display:flex; gap:10px; align-items:center;">
        <div class="status-pill">
          <span class="dot" id="herdr-dot"></span>
          <span id="herdr-status-text">Herdr 상태 확인 중</span>
        </div>
        <button class="btn btn-sm" onclick="refreshAll()">🔄 새로고침</button>
      </div>
    </div>

    <!-- TAB 1: TEAMS & EMPLOYEES -->
    <section id="tab-teams" class="tab-pane active">
      <div class="grid-2">
        <!-- Left: Create New Team -->
        <div class="card">
          <div class="card-header">
            <div class="card-title">➕ 새 팀 만들기 (Team &amp; Pane Builder)</div>
            <button class="btn btn-sm" onclick="addEmployeeSlot()">+ 직원 슬롯 추가</button>
          </div>
          <div class="card-desc">
            부서 이름을 입력하고 직원 슬롯(프리셋 직책·AI 엔진·임무)을 구성한 뒤 버튼을 누르면, 로컬 지침서 폴더 생성과 Herdr 창 분할이 자동으로 실행됩니다.
          </div>

          <label>부서(팀) 이름</label>
          <input type="text" id="new-team-name" placeholder="예: 마케팅기획팀, 백엔드개발팀, 유튜브제작팀" value="" />

          <div style="display:flex; justify-content:space-between; align-items:center; margin: 6px 0 8px;">
            <label style="margin:0;">소속 직원(Pane) 슬롯 구성</label>
            <label style="margin:0; display:flex; align-items:center; gap:6px; cursor:pointer; color:var(--text);">
              <input type="checkbox" id="new-team-launch" /> 생성 즉시 AI CLI 자동 실행
            </label>
          </div>

          <div id="employee-slots-container"></div>

          <button class="btn btn-primary" style="width:100%; margin-top:10px; padding:12px;" onclick="submitCreateTeam()">
            🚀 팀 생성 및 Herdr 창 자동 배치
          </button>
        </div>

        <!-- Right: Live Herdr Workspaces & Panes + 1-Click Role Assignment -->
        <div>
          <div class="card">
            <div class="card-header">
              <div class="card-title">🖥️ 실시간 Herdr 창(Pane) &amp; 등록된 팀 목록</div>
            </div>
            <div class="card-desc">
              아래에서 Herdr 창(<code>w1:p1</code>, <code>w1:p2</code> 등)을 클릭하면 직책·AI 엔진을 즉시 변경하거나 업무 지시를 전송할 수 있습니다.
            </div>
            <div id="live-workspaces-box"></div>
          </div>

          <div class="card" id="pane-inspector-card">
            <div class="card-header">
              <div class="card-title">🪪 선택한 창(Pane) 직책 배정 &amp; 원클릭 지시</div>
              <span class="badge amber" id="selected-pane-badge">창을 선택하세요</span>
            </div>
            <input type="hidden" id="assign-pane-id" value="" />
            <div class="grid-2" style="gap:10px;">
              <div>
                <label>대상 창 ID (직접 입력 또는 위에서 클릭)</label>
                <input type="text" id="assign-pane-input" placeholder="예: w1:p1, w1:p2" />
              </div>
              <div>
                <label>직책 프리셋 선택</label>
                <select id="assign-preset-select" onchange="onAssignPresetChange(this.value)">
                  <option value="총괄 기획 팀장">총괄 기획 팀장 (PM)</option>
                  <option value="수석 리서처">수석 리서처</option>
                  <option value="수석 개발자">수석 개발자</option>
                  <option value="콘텐츠 작가">콘텐츠 작가</option>
                  <option value="품질 검수자">품질 검수자 (QA)</option>
                  <option value="custom">직접 입력</option>
                </select>
              </div>
            </div>
            <div class="grid-2" style="gap:10px;">
              <div>
                <label>직책 이름</label>
                <input type="text" id="assign-role-name" value="총괄 기획 팀장" />
              </div>
              <div>
                <label>AI 엔진</label>
                <select id="assign-agent">
                  <option value="agy">agy (Antigravity CLI)</option>
                  <option value="claude">claude (Claude Code)</option>
                  <option value="codex">codex (OpenAI Codex)</option>
                  <option value="opencode">opencode</option>
                  <option value="gemini">gemini</option>
                </select>
              </div>
            </div>
            <label>핵심 임무 프롬프트 (Mission)</label>
            <textarea id="assign-mission" style="min-height:66px;">팀 전체 업무 기획, 하위 직원(창) 업무 분배 및 최종 결과물 검수를 담당합니다.</textarea>
            <div style="display:flex; gap:8px; margin-bottom:16px;">
              <button class="btn btn-primary" onclick="submitAssignPane(false)">🪪 이 창에 직책·지침서 배정</button>
              <button class="btn btn-blue" onclick="submitAssignPane(true)">▶️ 배정 후 AI 엔진 즉시 실행</button>
            </div>

            <div style="border-top:1px solid var(--border); padding-top:14px;">
              <label>💬 선택한 창에 즉시 업무 지시 / 명령어 보내기</label>
              <div style="display:flex; gap:8px;">
                <input type="text" id="pane-prompt-text" placeholder="예: 주어진 주제를 조사해서 TEAM_MEMORY.md에 요약해줘" style="margin:0;" />
                <button class="btn btn-green" style="white-space:nowrap;" onclick="submitPanePrompt()">📨 지시 전송</button>
                <button class="btn btn-sm" style="white-space:nowrap;" onclick="readPaneScreen()">📺 화면 읽기</button>
              </div>
              <pre id="pane-screen-output" style="display:none; margin-top:10px; background:#07090e; padding:12px; border-radius:8px; border:1px solid var(--border); font-size:12px; max-height:220px; overflow:auto; color:#a5f3fc;"></pre>
            </div>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <div class="card-title">📂 등록된 부서 폴더 현황 (<code>teams/</code>)</div>
        </div>
        <div id="local-teams-box"></div>
      </div>
    </section>

    <!-- TAB 2: SKILLS HUB -->
    <section id="tab-skills" class="tab-pane">
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">⚡ 현재 장착된 활성 스킬 (Active Installed Skills — <code>skills/</code>)</div>
            <div class="card-desc" style="margin:4px 0 0;">모든 AI 직원이 공유하는 재사용 노하우(SOP)입니다. 토글(ON/OFF), 마크다운 편집, 삭제가 가능합니다.</div>
          </div>
          <button class="btn btn-primary" onclick="openSkillModal('', '', '')">+ 새 커스텀 스킬 만들기</button>
        </div>
        <div id="installed-skills-box" class="grid-3"></div>
      </div>

      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">📦 기본 제공 스킬 카탈로그 (Built-in Skill Catalog — <code>templates/skills/</code>)</div>
            <div class="card-desc" style="margin:4px 0 0;">클론 직후 깨끗한 초기 상태에서 필요한 표준 스킬을 원클릭으로 즉시 장착할 수 있습니다.</div>
          </div>
        </div>
        <div id="catalog-skills-box" class="grid-3"></div>
      </div>
    </section>

    <!-- TAB 3: MEMORY & BRAIN -->
    <section id="tab-memory" class="tab-pane">
      <div class="card">
        <div class="card-header">
          <div class="card-title">👤 사장님 프로필 빠른 생성기 (Quick Profile Generator)</div>
        </div>
        <div class="grid-3" style="margin-bottom:10px;">
          <div>
            <label>호칭 / 이름</label>
            <input type="text" id="quick-owner-name" value="사장님" />
          </div>
          <div>
            <label>선호 언어</label>
            <input type="text" id="quick-owner-lang" value="한국어" />
          </div>
          <div>
            <label>선호 보고 스타일</label>
            <input type="text" id="quick-owner-style" value="비개발자도 이해하기 쉬운 핵심 요약과 명확한 근거 중심" />
          </div>
        </div>
        <button class="btn btn-blue" onclick="generateQuickProfile()">✨ 프로필 &amp; 기본 기억장 자동 생성</button>
      </div>

      <div class="grid-2">
        <div class="card">
          <div class="card-header">
            <div class="card-title">👤 사용자(사장님) 프로필 (<code>memory/USER_PROFILE.md</code>)</div>
            <button class="btn btn-primary btn-sm" onclick="saveMemoryDoc('user_profile')">💾 저장하기</button>
          </div>
          <textarea id="editor-user-profile" style="min-height:280px;" placeholder="아직 등록된 사장님 프로필이 없습니다. 위 빠른 생성기를 누르거나 직접 작성 후 저장하세요."></textarea>
        </div>

        <div class="card">
          <div class="card-header">
            <div class="card-title">🏛️ 전사 공유 기억장 (<code>memory/COMPANY_MEMORY.md</code>)</div>
            <button class="btn btn-primary btn-sm" onclick="saveMemoryDoc('company_memory')">💾 저장하기</button>
          </div>
          <textarea id="editor-company-memory" style="min-height:280px;" placeholder="아직 기록된 전사 기억장이 없습니다."></textarea>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <div class="card-title">📜 전사 AI 헌법 (<code>AGENTS.md</code> — CLAUDE.md / GEMINI.md 연동)</div>
          <button class="btn btn-primary btn-sm" onclick="saveMemoryDoc('agents_md')">💾 저장하기</button>
        </div>
        <textarea id="editor-agents-md" style="min-height:260px;"></textarea>
      </div>
    </section>

    <!-- TAB 4: MESSENGER GATEWAY -->
    <section id="tab-messenger" class="tab-pane">
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">💬 멀티 메신저 게이트웨이 설정 (Telegram / Slack / Discord)</div>
            <div class="card-desc" style="margin:4px 0 0;">봇 토큰을 입력하고 저장하면 <code>.env</code> 파일에 즉시 반영됩니다. (Git에는 절대 업로드되지 않습니다)</div>
          </div>
          <span class="badge" id="env-status-badge">.env 확인 중</span>
        </div>

        <label>활성화할 메신저 (쉼표 구분: telegram, slack, discord)</label>
        <input type="text" id="env-enabled" placeholder="예: telegram,slack,discord" />

        <div class="grid-3">
          <div class="slot-row">
            <div style="font-weight:700; margin-bottom:10px; color:#38bdf8;">✈️ Telegram 설정</div>
            <label>Telegram Bot Token (@BotFather)</label>
            <input type="password" id="env-tg-token" placeholder="123456:ABC-DEF..." />
            <label>허용할 Chat ID (비워두면 첫 사용자 자동 등록)</label>
            <input type="text" id="env-tg-chats" placeholder="예: 123456789" />
          </div>

          <div class="slot-row">
            <div style="font-weight:700; margin-bottom:10px; color:#f472b6;">💼 Slack 설정</div>
            <label>Slack Bot Token (xoxb-...)</label>
            <input type="password" id="env-slack-bot" placeholder="xoxb-..." />
            <label>Slack Channel ID</label>
            <input type="text" id="env-slack-channel" placeholder="C0123456789" />
            <label>Slack Webhook URL (선택)</label>
            <input type="text" id="env-slack-webhook" placeholder="https://hooks.slack.com/..." />
          </div>

          <div class="slot-row">
            <div style="font-weight:700; margin-bottom:10px; color:#a78bfa;">🎮 Discord 설정</div>
            <label>Discord Bot Token</label>
            <input type="password" id="env-discord-bot" placeholder="Discord Bot Token" />
            <label>Discord Channel ID</label>
            <input type="text" id="env-discord-channel" placeholder="123456789012345678" />
            <label>Discord Webhook URL (선택)</label>
            <input type="text" id="env-discord-webhook" placeholder="https://discord.com/api/webhooks/..." />
          </div>
        </div>

        <div style="display:flex; gap:10px; margin-top:12px;">
          <button class="btn btn-primary" onclick="saveMessengerEnv()">💾 설정 저장 (.env)</button>
          <button class="btn btn-blue" onclick="startBridgeProcess()">📡 메신저 브릿지 백그라운드 시작</button>
        </div>
      </div>
    </section>

    <!-- TAB 5: DOCTOR & FACTORY RESET -->
    <section id="tab-doctor" class="tab-pane">
      <div class="grid-2">
        <div class="card">
          <div class="card-header">
            <div class="card-title">🩺 실시간 시스템 진단 (Doctor Checklist)</div>
            <button class="btn btn-sm" onclick="configureHerdrHooks()">⚡ Herdr 단축키 &amp; AI 훅 자동 연결</button>
          </div>
          <div id="doctor-checklist-box"></div>
        </div>

        <div class="card" style="border-color: rgba(239, 68, 68, 0.4);">
          <div class="card-header">
            <div class="card-title" style="color:#fca5a5;">🔄 초기값으로 전체 리셋 (Factory Reset)</div>
          </div>
          <div class="card-desc">
            처음 <code>git clone</code> 했을 때와 동일하게 <strong>등록된 모든 팀(<code>teams/*</code>), 장착된 스킬(<code>skills/*</code>), 사용자 프로필 및 전사 기억장(<code>memory/USER_PROFILE.md</code>, <code>COMPANY_MEMORY.md</code>)을 깨끗한 0-상태로 초기화</strong>합니다.<br/><br/>
            ※ <code>templates/roles/</code> 직무 템플릿과 <code>templates/skills/</code> 기본 스킬 카탈로그는 안전하게 보존되므로 언제든 다시 원클릭 장착할 수 있습니다.
          </div>
          <label style="display:flex; align-items:center; gap:8px; cursor:pointer; color:var(--text); margin-bottom:16px;">
            <input type="checkbox" id="reset-include-env" /> <code>.env</code> 메신저 토큰 설정 파일도 함께 삭제
          </label>
          <button class="btn btn-danger" style="width:100%; padding:13px;" onclick="runFactoryReset()">
            🗑️ 초기값으로 전체 리셋 (Factory Reset 실행)
          </button>
        </div>
      </div>
    </section>
  </main>

  <!-- SKILL CREATE / EDIT MODAL -->
  <div class="modal-backdrop" id="skill-modal">
    <div class="modal">
      <div class="card-header">
        <div class="card-title" id="skill-modal-title">⚡ 스킬 작성 / 편집</div>
        <button class="btn btn-sm" onclick="closeSkillModal()">✕ 닫기</button>
      </div>
      <label>스킬 ID (폴더명, 영문 소문자/하이픈 권장)</label>
      <input type="text" id="modal-skill-id" placeholder="예: youtube-script-writer" />
      <label>스킬 한 줄 설명 (Description)</label>
      <input type="text" id="modal-skill-desc" placeholder="예: 유튜브 영상 기획 및 대본 작성 표준 절차서" />
      <label>SKILL.md 상세 마크다운 지침 (Instructions)</label>
      <textarea id="modal-skill-content" style="min-height:280px;"></textarea>
      <div style="display:flex; justify-content:flex-end; gap:10px; margin-top:10px;">
        <button class="btn" onclick="closeSkillModal()">취소</button>
        <button class="btn btn-primary" onclick="saveSkillFromModal()">💾 스킬 저장</button>
      </div>
    </div>
  </div>

  <div class="toast" id="toast"></div>

  <script>
    let APP_STATE = null;
    const PRESET_MAP = {
      "총괄 기획 팀장": { agent: "agy", mission: "팀 전체 업무 기획, 하위 직원(창) 업무 분배 및 최종 결과물 검수를 담당합니다." },
      "수석 리서처": { agent: "claude", mission: "심층 자료 조사, 레퍼런스 수집, 팩트체크 및 핵심 요약을 담당합니다." },
      "수석 개발자": { agent: "codex", mission: "코드 설계, 구현, 버그 수정 및 자동화 테스트 작성을 담당합니다." },
      "콘텐츠 작가": { agent: "claude", mission: "보고서, 기획서, 기술 문서 및 카피라이팅 초안 작성을 담당합니다." },
      "품질 검수자": { agent: "codex", mission: "결과물 품질 검증, 코드 리뷰, 엣지 케이스 점검 및 개선안 도출을 담당합니다." }
    };

    function showToast(msg) {
      const t = document.getElementById('toast');
      t.textContent = msg;
      t.style.display = 'block';
      clearTimeout(window._toastTimer);
      window._toastTimer = setTimeout(() => { t.style.display = 'none'; }, 3500);
    }

    function switchTab(tabId, btn) {
      document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));
      document.getElementById(tabId).classList.add('active');
      if (btn) btn.classList.add('active');
    }

    async function apiPost(path, body) {
      const res = await fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body || {})
      });
      return await res.json();
    }

    function addEmployeeSlot(presetName = "총괄 기획 팀장", agent = "", mission = "") {
      const container = document.getElementById('employee-slots-container');
      const idx = container.children.length + 1;
      const info = PRESET_MAP[presetName] || { agent: "claude", mission: "" };
      const finalAgent = agent || info.agent;
      const finalMission = mission || info.mission;

      const div = document.createElement('div');
      div.className = 'slot-row';
      div.innerHTML = `
        <div class="slot-grid">
          <div>
            <label>직책 프리셋 (p${idx})</label>
            <select class="slot-preset" onchange="onSlotPresetChange(this)">
              <option value="총괄 기획 팀장" ${presetName==='총괄 기획 팀장'?'selected':''}>총괄 기획 팀장</option>
              <option value="수석 리서처" ${presetName==='수석 리서처'?'selected':''}>수석 리서처</option>
              <option value="수석 개발자" ${presetName==='수석 개발자'?'selected':''}>수석 개발자</option>
              <option value="콘텐츠 작가" ${presetName==='콘텐츠 작가'?'selected':''}>콘텐츠 작가</option>
              <option value="품질 검수자" ${presetName==='품질 검수자'?'selected':''}>품질 검수자</option>
              <option value="직접 입력" ${!PRESET_MAP[presetName]?'selected':''}>직접 입력</option>
            </select>
          </div>
          <div>
            <label>직책명</label>
            <input type="text" class="slot-role" value="${presetName === '직접 입력' ? '' : presetName}" placeholder="직책 입력" />
          </div>
          <div>
            <label>AI 엔진</label>
            <select class="slot-agent">
              <option value="agy" ${finalAgent==='agy'?'selected':''}>agy</option>
              <option value="claude" ${finalAgent==='claude'?'selected':''}>claude</option>
              <option value="codex" ${finalAgent==='codex'?'selected':''}>codex</option>
              <option value="opencode" ${finalAgent==='opencode'?'selected':''}>opencode</option>
              <option value="gemini" ${finalAgent==='gemini'?'selected':''}>gemini</option>
            </select>
          </div>
          <div style="padding-top:10px;">
            <button class="btn btn-danger btn-sm" onclick="this.closest('.slot-row').remove()">삭제</button>
          </div>
        </div>
        <label>세부 임무 프롬프트 (Mission)</label>
        <input type="text" class="slot-mission" value="${finalMission}" style="margin-bottom:0;" />
      `;
      container.appendChild(div);
    }

    function onSlotPresetChange(sel) {
      const row = sel.closest('.slot-row');
      const val = sel.value;
      if (PRESET_MAP[val]) {
        row.querySelector('.slot-role').value = val;
        row.querySelector('.slot-agent').value = PRESET_MAP[val].agent;
        row.querySelector('.slot-mission').value = PRESET_MAP[val].mission;
      } else {
        row.querySelector('.slot-role').value = '';
        row.querySelector('.slot-role').focus();
      }
    }

    function onAssignPresetChange(val) {
      if (PRESET_MAP[val]) {
        document.getElementById('assign-role-name').value = val;
        document.getElementById('assign-agent').value = PRESET_MAP[val].agent;
        document.getElementById('assign-mission').value = PRESET_MAP[val].mission;
      } else {
        document.getElementById('assign-role-name').value = '';
        document.getElementById('assign-role-name').focus();
      }
    }

    function selectPaneForAssign(paneId, roleName, agent, mission) {
      document.getElementById('assign-pane-input').value = paneId;
      document.getElementById('selected-pane-badge').textContent = `선택됨: ${paneId}`;
      if (roleName) document.getElementById('assign-role-name').value = roleName;
      if (agent && agent !== '-') document.getElementById('assign-agent').value = agent;
      if (mission) document.getElementById('assign-mission').value = mission;
      showToast(`창 [${paneId}] 선택됨 — 우측 카드에서 직책 변경 또는 지시 전송이 가능합니다.`);
    }

    async function submitCreateTeam() {
      const name = document.getElementById('new-team-name').value.trim();
      if (!name) { alert('생성할 부서(팀) 이름을 입력해 주세요.'); return; }
      const rows = document.querySelectorAll('#employee-slots-container .slot-row');
      if (!rows.length) { alert('최소 1명의 직원 슬롯을 추가해 주세요.'); return; }
      const roles = [];
      rows.forEach(r => {
        const rName = r.querySelector('.slot-role').value.trim() || '담당자';
        const rAgent = r.querySelector('.slot-agent').value;
        const rMission = r.querySelector('.slot-mission').value.trim();
        roles.push({ role: rName, agent: rAgent, mission: rMission });
      });
      const launch = document.getElementById('new-team-launch').checked;
      showToast(`⏳ [${name}] 팀 생성 및 Herdr 창 배치 중...`);
      const res = await apiPost('/api/team/create', { name, roles, launch });
      showToast(res.message || '팀 생성 완료!');
      document.getElementById('new-team-name').value = '';
      await refreshAll();
    }

    async function submitAssignPane(launch) {
      const pane_id = document.getElementById('assign-pane-input').value.trim();
      if (!pane_id) { alert('대상 창 ID(예: w1:p1, w1:p2)를 선택하거나 입력해 주세요.'); return; }
      const role = document.getElementById('assign-role-name').value.trim() || '담당자';
      const agent = document.getElementById('assign-agent').value;
      const mission = document.getElementById('assign-mission').value.trim();
      const res = await apiPost('/api/employee/assign', { pane_id, role, agent, mission, launch });
      showToast(res.message || '직책 배정 완료!');
      await refreshAll();
    }

    async function submitPanePrompt() {
      const pane_id = document.getElementById('assign-pane-input').value.trim();
      const prompt = document.getElementById('pane-prompt-text').value.trim();
      if (!pane_id) { alert('먼저 대상 창(예: w1:p1)을 선택하세요.'); return; }
      if (!prompt) { alert('전달할 업무 지시 내용을 입력하세요.'); return; }
      const res = await apiPost('/api/employee/prompt', { pane_id, prompt });
      showToast(res.message || '전송 완료');
      document.getElementById('pane-prompt-text').value = '';
    }

    async function readPaneScreen() {
      const pane_id = document.getElementById('assign-pane-input').value.trim();
      if (!pane_id) { alert('먼저 대상 창(예: w1:p1)을 선택하세요.'); return; }
      const res = await apiPost('/api/employee/read', { pane_id });
      const pre = document.getElementById('pane-screen-output');
      pre.style.display = 'block';
      pre.textContent = res.output || '(화면 출력 없음 또는 Herdr 비연결)';
    }

    async function deleteTeamFolder(folder) {
      if (!confirm(`정말 [${folder}] 부서 폴더와 지침서를 삭제하시겠습니까?`)) return;
      const res = await apiPost('/api/team/delete', { folder });
      showToast(res.message);
      await refreshAll();
    }

    async function installCatalogSkill(id) {
      const res = await apiPost('/api/skill/install', { id });
      showToast(res.message);
      await refreshAll();
    }

    async function toggleSkill(id) {
      const res = await apiPost('/api/skill/toggle', { id });
      showToast(res.message);
      await refreshAll();
    }

    async function deleteSkill(id) {
      if (!confirm(`정말 '${id}' 스킬을 삭제하시겠습니까?`)) return;
      const res = await apiPost('/api/skill/delete', { id });
      showToast(res.message);
      await refreshAll();
    }

    function openSkillModal(id, desc, content) {
      document.getElementById('modal-skill-id').value = id || '';
      document.getElementById('modal-skill-desc').value = desc || '';
      if (content) {
        document.getElementById('modal-skill-content').value = content;
      } else {
        document.getElementById('modal-skill-content').value = `---\nname: ${id || 'custom-skill'}\ndescription: "${desc || '스킬 설명을 입력하세요'}"\n---\n\n# 🛠️ 커스텀 스킬 지침\n\n## 1. 언제 사용하는가\n- \n\n## 2. 표준 수행 절차\n1. \n2. \n`;
      }
      document.getElementById('skill-modal').style.display = 'flex';
    }

    function closeSkillModal() {
      document.getElementById('skill-modal').style.display = 'none';
    }

    async function saveSkillFromModal() {
      const id = document.getElementById('modal-skill-id').value.trim();
      const desc = document.getElementById('modal-skill-desc').value.trim();
      const content = document.getElementById('modal-skill-content').value;
      if (!id) { alert('스킬 이름을 입력해 주세요.'); return; }
      const res = await apiPost('/api/skill/save', { id, description: desc, content });
      showToast(res.message);
      closeSkillModal();
      await refreshAll();
    }

    async function generateQuickProfile() {
      const owner_name = document.getElementById('quick-owner-name').value.trim() || '사장님';
      const preferred_lang = document.getElementById('quick-owner-lang').value.trim() || '한국어';
      const work_style = document.getElementById('quick-owner-style').value.trim();
      const res = await apiPost('/api/memory/generate', { owner_name, preferred_lang, work_style });
      showToast(res.message);
      await refreshAll();
    }

    async function saveMemoryDoc(target) {
      let content = '';
      if (target === 'user_profile') content = document.getElementById('editor-user-profile').value;
      if (target === 'company_memory') content = document.getElementById('editor-company-memory').value;
      if (target === 'agents_md') content = document.getElementById('editor-agents-md').value;
      const res = await apiPost('/api/memory/save', { target, content });
      showToast(res.message);
      await refreshAll();
    }

    async function saveMessengerEnv() {
      const payload = {
        ENABLED_MESSENGERS: document.getElementById('env-enabled').value.trim(),
        TELEGRAM_BOT_TOKEN: document.getElementById('env-tg-token').value.trim(),
        TELEGRAM_ALLOWED_CHAT_IDS: document.getElementById('env-tg-chats').value.trim(),
        SLACK_BOT_TOKEN: document.getElementById('env-slack-bot').value.trim(),
        SLACK_CHANNEL_ID: document.getElementById('env-slack-channel').value.trim(),
        SLACK_WEBHOOK_URL: document.getElementById('env-slack-webhook').value.trim(),
        DISCORD_BOT_TOKEN: document.getElementById('env-discord-bot').value.trim(),
        DISCORD_CHANNEL_ID: document.getElementById('env-discord-channel').value.trim(),
        DISCORD_WEBHOOK_URL: document.getElementById('env-discord-webhook').value.trim(),
      };
      const res = await apiPost('/api/env/save', payload);
      showToast(res.message);
      await refreshAll();
    }

    async function startBridgeProcess() {
      const res = await apiPost('/api/gateway/start', {});
      showToast(res.message);
    }

    async function configureHerdrHooks() {
      const res = await apiPost('/api/doctor/configure_herdr', {});
      showToast(res.message);
      await refreshAll();
    }

    async function runFactoryReset() {
      const reset_env = document.getElementById('reset-include-env').checked;
      if (!confirm('정말 모든 등록된 팀(teams/*), 장착된 스킬(skills/*), 기억장(USER_PROFILE.md, COMPANY_MEMORY.md)을 초기 상태로 리셋하시겠습니까?')) return;
      const res = await apiPost('/api/factory_reset', { reset_env });
      showToast(res.message);
      await refreshAll();
    }

    async function refreshAll() {
      const res = await fetch('/api/state');
      APP_STATE = await res.json();
      renderState(APP_STATE);
    }

    function renderState(st) {
      // Topbar status
      const dot = document.getElementById('herdr-dot');
      const txt = document.getElementById('herdr-status-text');
      if (st.herdr.connected) {
        dot.className = 'dot';
        txt.textContent = `Herdr 연결됨 (워크스페이스 ${st.workspaces.length}개 / 창 ${st.panes.length}개)`;
      } else if (st.herdr.installed) {
        dot.className = 'dot off';
        txt.textContent = `Herdr 설치됨 (${st.herdr.version}) · 오프라인/세션 외부`;
      } else {
        dot.className = 'dot off';
        txt.textContent = `Herdr 미설치`;
      }

      document.getElementById('sidebar-stats').innerHTML = `
        • 등록된 팀: <strong>${st.local_teams.length}개</strong><br/>
        • 활성 스킬: <strong>${st.installed_skills.filter(s=>s.enabled).length}개</strong><br/>
        • 사장님 프로필: <strong>${st.memory.user_profile_exists ? '등록됨' : '미등록(초기값)'}</strong>
      `;

      // Live Workspaces & Panes
      const wsBox = document.getElementById('live-workspaces-box');
      if (!st.workspaces.length) {
        wsBox.innerHTML = `<div class="empty-box">현재 활성화된 Herdr 워크스페이스가 없거나 Herdr 외부에서 실행 중입니다.<br/>좌측에서 새 팀을 생성하거나 아래에 창 ID(예: <code>w1:p1</code>)를 직접 입력해 지침서를 발급할 수 있습니다.</div>`;
      } else {
        wsBox.innerHTML = st.workspaces.map(ws => {
          const wsPanes = st.panes.filter(p => p.workspace_id === ws.workspace_id);
          const panesHtml = wsPanes.map(p => {
            const m = p.assigned_meta || {};
            const rName = m.role_name || p.label || '미배정 창';
            const rAgent = m.agent || p.agent || 'claude';
            const rMission = m.mission || '';
            return `
              <div class="pane-item" onclick='selectPaneForAssign(${JSON.stringify(p.pane_id)}, ${JSON.stringify(rName)}, ${JSON.stringify(rAgent)}, ${JSON.stringify(rMission)})'>
                <div style="display:flex; justify-content:space-between; align-items:center;">
                  <div>
                    <span class="badge amber">${p.pane_id}</span>
                    <strong style="margin-left:6px;">${rName}</strong>
                    <span class="badge" style="margin-left:6px;">AI: ${rAgent}</span>
                  </div>
                  <span class="badge ${p.agent_status==='running'?'green':'gray'}">${p.agent_status || 'idle'}</span>
                </div>
                <div style="font-size:12px; color:var(--text-muted); margin-top:6px;">
                  ${rMission ? rMission : `경로: ${p.cwd || ''}`}
                </div>
              </div>
            `;
          }).join('');
          return `
            <div style="margin-bottom:14px;">
              <div style="font-size:13px; font-weight:700; margin-bottom:8px; color:var(--accent);">
                🏢 [${ws.workspace_id}] ${ws.label || ws.workspace_id} (창 ${wsPanes.length}개)
              </div>
              ${panesHtml}
            </div>
          `;
        }).join('');
      }

      // Local Teams
      const ltBox = document.getElementById('local-teams-box');
      if (!st.local_teams.length) {
        ltBox.innerHTML = `<div class="empty-box">등록된 팀 폴더가 없습니다 (깨끗한 초기 상태). 위 <strong>[+ 새 팀 만들기]</strong>에서 첫 부서를 생성해 보세요!</div>`;
      } else {
        ltBox.innerHTML = `<div class="grid-3">` + st.local_teams.map(t => `
          <div class="slot-row">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
              <strong>📂 ${t.folder}</strong>
              <button class="btn btn-danger btn-sm" onclick='deleteTeamFolder(${JSON.stringify(t.folder)})'>삭제</button>
            </div>
            <div style="font-size:12px; color:var(--text-muted); margin-bottom:8px;">직원 ${t.members.length}명 · 공유 기억장(TEAM_MEMORY.md)</div>
            ${t.members.map(m => `
              <div style="font-size:12px; padding:6px 8px; background:var(--bg-card); border-radius:6px; margin-bottom:5px;">
                <span class="badge amber">${m.pane_id || '로컬'}</span>
                <strong>${m.role_name}</strong> <span class="badge">${m.agent}</span>
                <div style="color:var(--text-muted); margin-top:3px;">${m.mission || ''}</div>
              </div>
            `).join('')}
          </div>
        `).join('') + `</div>`;
      }

      // Installed Skills
      const skBox = document.getElementById('installed-skills-box');
      if (!st.installed_skills.length) {
        skBox.style.display = 'block';
        skBox.innerHTML = `<div class="empty-box">현재 장착된 스킬이 없습니다 (0개). 아래 <strong>기본 제공 스킬 카탈로그</strong>에서 <strong>[+ 원클릭 장착]</strong>을 눌러보세요!</div>`;
      } else {
        skBox.style.display = 'grid';
        skBox.innerHTML = st.installed_skills.map(s => `
          <div class="slot-row" style="display:flex; flex-direction:column; justify-content:space-between;">
            <div>
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                <strong>⚡ ${s.name}</strong>
                <span class="badge ${s.enabled?'green':'gray'}">${s.enabled ? '활성 (ON)' : '비활성 (OFF)'}</span>
              </div>
              <div style="font-size:12px; color:var(--text-muted); margin-bottom:14px; line-height:1.5;">${s.description || '설명 없음'}</div>
            </div>
            <div style="display:flex; gap:6px; flex-wrap:wrap;">
              <button class="btn btn-sm" onclick='toggleSkill(${JSON.stringify(s.id)})'>${s.enabled ? '⏸ 끄기' : '▶ 켜기'}</button>
              <button class="btn btn-sm" onclick='openSkillModal(${JSON.stringify(s.id)}, ${JSON.stringify(s.description)}, ${JSON.stringify(s.content)})'>✏️ 마크다운 편집</button>
              <button class="btn btn-danger btn-sm" onclick='deleteSkill(${JSON.stringify(s.id)})'>🗑 삭제</button>
            </div>
          </div>
        `).join('');
      }

      // Catalog Skills
      const catBox = document.getElementById('catalog-skills-box');
      catBox.innerHTML = st.catalog_skills.map(c => `
        <div class="slot-row" style="display:flex; flex-direction:column; justify-content:space-between;">
          <div>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
              <strong>📦 ${c.name}</strong>
              ${c.installed ? '<span class="badge green">장착됨</span>' : '<span class="badge gray">미장착</span>'}
            </div>
            <div style="font-size:12px; color:var(--text-muted); margin-bottom:14px; line-height:1.5;">${c.description}</div>
          </div>
          <button class="btn ${c.installed?'':'btn-primary'} btn-sm" onclick='installCatalogSkill(${JSON.stringify(c.id)})'>
            ${c.installed ? '🔄 초기 템플릿으로 재장착' : '➕ 원클릭 장착'}
          </button>
        </div>
      `).join('');

      // Memory Editors
      document.getElementById('editor-user-profile').value = st.memory.user_profile || '';
      document.getElementById('editor-company-memory').value = st.memory.company_memory || '';
      document.getElementById('editor-agents-md').value = st.memory.agents_md || '';

      // Messenger .env
      document.getElementById('env-status-badge').textContent = st.env.exists ? '.env 파일 존재함' : '.env 미생성 (초기 상태)';
      document.getElementById('env-enabled').value = st.env.ENABLED_MESSENGERS || '';
      document.getElementById('env-tg-token').value = st.env.TELEGRAM_BOT_TOKEN || '';
      document.getElementById('env-tg-chats').value = st.env.TELEGRAM_ALLOWED_CHAT_IDS || '';
      document.getElementById('env-slack-bot').value = st.env.SLACK_BOT_TOKEN || '';
      document.getElementById('env-slack-channel').value = st.env.SLACK_CHANNEL_ID || '';
      document.getElementById('env-slack-webhook').value = st.env.SLACK_WEBHOOK_URL || '';
      document.getElementById('env-discord-bot').value = st.env.DISCORD_BOT_TOKEN || '';
      document.getElementById('env-discord-channel').value = st.env.DISCORD_CHANNEL_ID || '';
      document.getElementById('env-discord-webhook').value = st.env.DISCORD_WEBHOOK_URL || '';

      // Doctor Checklist
      const agentRows = Object.entries(st.agents).map(([k, v]) =>
        `<div style="margin-bottom:6px;">${v.installed ? '✅' : '⚪'} <strong>${k}</strong>: ${v.installed ? v.path : '미설치'}</div>`
      ).join('');
      document.getElementById('doctor-checklist-box').innerHTML = `
        <div class="slot-row">
          <div><strong>💻 운영체제 / Python:</strong> ${st.os_info}</div>
          <div style="margin-top:6px;"><strong>📂 루트 경로:</strong> <code>${st.root_dir}</code></div>
          <div style="margin-top:6px;"><strong>🖥️ Herdr 바이너리:</strong> ${st.herdr.installed ? `✅ ${st.herdr.bin_path} (${st.herdr.version})` : '❌ 미설치'}</div>
          <div style="margin-top:6px;"><strong>⚙️ Herdr config.toml:</strong> ${st.herdr.config_exists ? `✅ ${st.herdr.config_path}` : '⚪ 미생성'}</div>
        </div>
        <div class="slot-row">
          <div style="font-weight:700; margin-bottom:8px;">🤖 감지된 AI 에이전트 CLI</div>
          ${agentRows}
        </div>
        <div class="slot-row">
          <div style="font-weight:700; margin-bottom:8px;">📊 현재 등록 상태 요약</div>
          <div>• 등록된 팀(<code>teams/</code>): <strong>${st.local_teams.length}개</strong></div>
          <div>• 장착된 스킬(<code>skills/</code>): <strong>${st.installed_skills.length}개</strong> (카탈로그 템플릿 ${st.catalog_skills.length}개)</div>
          <div>• 사장님 프로필(<code>USER_PROFILE.md</code>): <strong>${st.memory.user_profile_exists ? '✅ 존재' : '⚪ 미등록 (0-State)'}</strong></div>
          <div>• 전사 기억장(<code>COMPANY_MEMORY.md</code>): <strong>${st.memory.company_memory_exists ? '✅ 존재' : '⚪ 미등록 (0-State)'}</strong></div>
        </div>
      `;
    }

    // Initialize default 3 employee slots in builder
    window.addEventListener('DOMContentLoaded', () => {
      addEmployeeSlot("총괄 기획 팀장");
      addEmployeeSlot("수석 리서처");
      addEmployeeSlot("수석 개발자");
      refreshAll();
    });
  </script>
</body>
</html>
"""


class HermesAdminHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler for the Hermes-style Admin Control Center UI."""

    def log_message(self, format: str, *args) -> None:
        # Keep terminal output clean while clicking around UI
        pass

    def _send_json(self, data: dict, status: int = 200) -> None:
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_html(self, html: str) -> None:
        raw = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self._send_html(HERMES_UI_HTML)
            return
        if parsed.path == "/api/state":
            self._send_json(collect_system_state())
            return
        self._send_json({"error": "Not found"}, status=404)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace") if length > 0 else "{}"
        try:
            body = json.loads(raw_body) if raw_body else {}
        except Exception:
            body = {}

        path = parsed.path

        # 1. Create Team
        if path == "/api/team/create":
            team_name = str(body.get("name", "")).strip() or "신규부서"
            roles_list = body.get("roles", [])
            launch = bool(body.get("launch", False))
            role_tuples: List[Tuple[str, str, str]] = []
            for item in roles_list:
                r_name = str(item.get("role", "담당자")).strip()
                r_agent = str(item.get("agent", "claude")).strip()
                r_mission = str(item.get("mission", "")).strip() or f"{team_name}의 {r_name} 직무 수행"
                role_tuples.append((r_name, r_agent, r_mission))
            ws_id = create_team(
                team_name=team_name,
                launch_agents=launch,
                role_items_override=role_tuples if role_tuples else None,
            )
            msg = (
                f"✅ [{team_name}] 부서 생성 및 Herdr 워크스페이스({ws_id}) 창 배치 완료!"
                if ws_id
                else f"📁 [{team_name}] 로컬 부서 폴더 및 직원 지침서 생성 완료! (Herdr 미실행 상태)"
            )
            self._send_json({"ok": True, "workspace_id": ws_id, "message": msg})
            return

        # 2. Delete Team Folder
        if path == "/api/team/delete":
            folder = sanitize_folder_name(str(body.get("folder", "")))
            target = TEAMS_DIR / folder
            if target.exists() and target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
                self._send_json({"ok": True, "message": f"🗑️ [{folder}] 부서 폴더가 삭제되었습니다."})
            else:
                self._send_json({"ok": False, "message": "대상 부서 폴더를 찾을 수 없습니다."})
            return

        # 3. Assign Role to Existing Herdr Pane
        if path == "/api/employee/assign":
            pane_id = str(body.get("pane_id", "")).strip()
            role = str(body.get("role", "담당자")).strip()
            agent = str(body.get("agent", "claude")).strip()
            mission = str(body.get("mission", "")).strip()
            launch = bool(body.get("launch", False))
            role_dir = assign_employee_to_pane(
                pane_id=pane_id,
                role_name=role,
                agent_name=agent,
                mission=mission,
                launch=launch,
            )
            self._send_json(
                {
                    "ok": True,
                    "message": f"✅ 창 [{pane_id}] 직책 배정 완료: {role} ({agent}) -> {role_dir.name}",
                }
            )
            return

        # 4. Send Prompt / Command to Herdr Pane
        if path == "/api/employee/prompt":
            pane_id = str(body.get("pane_id", "")).strip()
            prompt_txt = str(body.get("prompt", "")).strip()
            rc, out, err = run_herdr(["pane", "run", pane_id, prompt_txt])
            if rc == 0:
                self._send_json({"ok": True, "message": f"📨 [{pane_id}] 창으로 지시 전송 완료!"})
            else:
                self._send_json({"ok": False, "message": f"⚠️ 전송 실패 (Herdr 연결 확인): {err or out}"})
            return

        # 5. Read Herdr Pane Output
        if path == "/api/employee/read":
            pane_id = str(body.get("pane_id", "")).strip()
            rc, out, err = run_herdr(["pane", "read", pane_id, "--source", "recent-unwrapped", "--lines", "40"])
            self._send_json({"ok": rc == 0, "output": out if rc == 0 else (err or out)})
            return

        # 6. Install Skill from Catalog
        if path == "/api/skill/install":
            skill_id = str(body.get("id", "")).strip()
            ok, info = install_skill_from_catalog(skill_id)
            self._send_json(
                {
                    "ok": ok,
                    "message": f"⚡ '{skill_id}' 스킬이 장착되었습니다!" if ok else info,
                }
            )
            return

        # 7. Toggle Installed Skill
        if path == "/api/skill/toggle":
            skill_id = str(body.get("id", "")).strip()
            ok, enabled, msg = toggle_installed_skill(skill_id)
            self._send_json({"ok": ok, "enabled": enabled, "message": msg})
            return

        # 8. Delete Installed Skill
        if path == "/api/skill/delete":
            skill_id = str(body.get("id", "")).strip()
            ok, msg = delete_installed_skill(skill_id)
            self._send_json({"ok": ok, "message": msg})
            return

        # 9. Save / Create Custom Skill
        if path == "/api/skill/save":
            raw_id = str(body.get("id", "")).strip()
            safe_id = sanitize_folder_name(raw_id.lower().replace(" ", "-"))
            desc = str(body.get("description", "")).strip() or f"{raw_id} 커스텀 스킬"
            content = str(body.get("content", "")).strip()
            s_dir = SKILLS_DIR / safe_id
            s_dir.mkdir(parents=True, exist_ok=True)
            if not content.startswith("---"):
                content = f'---\nname: {safe_id}\ndescription: "{desc}"\n---\n\n{content}\n'
            (s_dir / "SKILL.md").write_text(content + "\n", encoding="utf-8")
            disabled_f = s_dir / "SKILL.md.disabled"
            if disabled_f.exists():
                disabled_f.unlink()
            self._send_json({"ok": True, "message": f"💾 '{safe_id}' 스킬이 저장 및 활성화되었습니다!"})
            return

        # 10. Quick Generate User Profile & Company Memory
        if path == "/api/memory/generate":
            owner_name = str(body.get("owner_name", "사장님")).strip()
            preferred_lang = str(body.get("preferred_lang", "한국어")).strip()
            work_style = str(body.get("work_style", "핵심 요약 선호")).strip()
            ensure_root_constitution()
            generate_user_profile_and_memory(owner_name, preferred_lang, work_style, overwrite_profile=True)
            self._send_json({"ok": True, "message": "✨ 사장님 프로필 및 전사 기억장이 생성되었습니다!"})
            return

        # 11. Save Memory or AGENTS.md
        if path == "/api/memory/save":
            target = str(body.get("target", "")).strip()
            content = str(body.get("content", ""))
            MEMORY_DIR.mkdir(parents=True, exist_ok=True)
            if target == "user_profile":
                (MEMORY_DIR / "USER_PROFILE.md").write_text(content, encoding="utf-8")
                self._send_json({"ok": True, "message": "💾 USER_PROFILE.md 저장 완료!"})
                return
            if target == "company_memory":
                (MEMORY_DIR / "COMPANY_MEMORY.md").write_text(content, encoding="utf-8")
                self._send_json({"ok": True, "message": "💾 COMPANY_MEMORY.md 저장 완료!"})
                return
            if target == "agents_md":
                (ROOT_DIR / "AGENTS.md").write_text(content, encoding="utf-8")
                self._send_json({"ok": True, "message": "💾 AGENTS.md 전사 헌법 저장 완료!"})
                return
            self._send_json({"ok": False, "message": "알 수 없는 문서 대상입니다."})
            return

        # 12. Save Messenger .env
        if path == "/api/env/save":
            env_vars = load_env_file(ENV_FILE)
            for k in (
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
            ):
                if k in body:
                    env_vars[k] = str(body[k]).strip()
            # Auto-populate ENABLED_MESSENGERS if left blank but tokens exist
            if not env_vars.get("ENABLED_MESSENGERS"):
                auto_en = []
                if env_vars.get("TELEGRAM_BOT_TOKEN"):
                    auto_en.append("telegram")
                if env_vars.get("SLACK_BOT_TOKEN") or env_vars.get("SLACK_WEBHOOK_URL"):
                    auto_en.append("slack")
                if env_vars.get("DISCORD_BOT_TOKEN") or env_vars.get("DISCORD_WEBHOOK_URL"):
                    auto_en.append("discord")
                env_vars["ENABLED_MESSENGERS"] = ",".join(auto_en)
            save_env_file(env_vars, ENV_FILE)
            self._send_json({"ok": True, "message": "💾 메신저 게이트웨이 설정(.env)이 저장되었습니다!"})
            return

        # 13. Start Messenger Bridge in Background
        if path == "/api/gateway/start":
            gw_script = GATEWAYS_DIR / "messenger_bridge.py"
            if not gw_script.exists():
                self._send_json({"ok": False, "message": "gateways/messenger_bridge.py 파일이 없습니다."})
                return
            creationflags = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
            subprocess.Popen(
                [sys.executable, str(gw_script)],
                cwd=str(ROOT_DIR),
                creationflags=creationflags,
            )
            self._send_json({"ok": True, "message": "📡 멀티 메신저 브릿지가 새 프로세스로 시작되었습니다!"})
            return

        # 14. Configure Herdr Shortcuts & Integration Hooks
        if path == "/api/doctor/configure_herdr":
            cfg = configure_herdr_toml()
            installed = detect_installed_agents()
            hooked = []
            if shutil.which("herdr"):
                for ag, p in installed.items():
                    target = SUPPORTED_AGENTS.get(ag)
                    if p and target:
                        rc, _, _ = run_herdr(["integration", "install", target])
                        if rc == 0:
                            hooked.append(ag)
            self._send_json(
                {
                    "ok": True,
                    "message": f"⚡ Herdr 단축키({cfg.name}) 및 AI 훅({', '.join(hooked) or '없음'}) 설정 완료!",
                }
            )
            return

        # 15. Factory Reset
        if path == "/api/factory_reset":
            reset_env = bool(body.get("reset_env", False))
            res = perform_factory_reset(reset_env=reset_env)
            self._send_json(
                {
                    "ok": True,
                    "message": (
                        f"🔄 초기 상태로 전체 리셋 완료! "
                        f"(삭제된 팀: {res['removed_teams']}개, 스킬: {res['removed_skills']}개, 기억장: {res['removed_memories']}개)"
                    ),
                }
            )
            return

        self._send_json({"error": "Unknown endpoint"}, status=404)


def cmd_ui(args: argparse.Namespace) -> int:
    """Launch the Hermes-style Web Admin Control Center UI on http://127.0.0.1:8765."""
    host = getattr(args, "host", "127.0.0.1") or "127.0.0.1"
    port = int(getattr(args, "port", 8765) or 8765)
    no_open = bool(getattr(args, "no_browser", False))

    url = f"http://{host}:{port}"
    server = ThreadingHTTPServer((host, port), HermesAdminHandler)

    print("=" * 68)
    print("🌐 Herdr × Hermes Admin Control Center (웹 관리 콘솔 UI)")
    print("=" * 68)
    print(f"  🔗 접속 주소: {url}")
    print("  💡 브라우저에서 팀/직원 배치, 스킬 장착, 기억장 편집, 메신저 연동, 초기화를 클릭으로 관리하세요.")
    print("  🛑 종료하려면 터미널에서 Ctrl+C 를 누르세요.")
    print("=" * 68)

    if not no_open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 웹 관리 콘솔 UI 서버를 종료합니다.")
    finally:
        server.server_close()
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    """CLI handler for Factory Reset (`herdr_os.py reset`)."""
    force = bool(getattr(args, "yes", False))
    if not force:
        if not prompt_yes_no(
            "⚠️ 정말 등록된 모든 팀(teams/*), 스킬(skills/*), 기억장(USER_PROFILE.md, COMPANY_MEMORY.md)을 초기값(0-State)으로 리셋할까요?",
            False,
        ):
            print("취소되었습니다.")
            return 0
    res = perform_factory_reset(reset_env=bool(getattr(args, "include_env", False)))
    print(
        f"✅ 초기 상태(Factory Reset) 복원 완료! "
        f"(팀 {res['removed_teams']}개, 스킬 {res['removed_skills']}개, 기억장 {res['removed_memories']}개 초기화됨)"
    )
    return 0


def interactive_terminal_menu() -> int:
    """
    Interactive Terminal Menu TUI (`python herdr_os.py` with no args, or `herdr-os`).
    Lets users manage everything without memorizing CLI arguments.
    """
    while True:
        st = collect_system_state()
        active_skills = len([s for s in st["installed_skills"] if s["enabled"]])
        team_count = len(st["local_teams"])
        profile_ok = "등록됨" if st["memory"]["user_profile_exists"] else "미등록(초기값)"

        print("\n" + "=" * 72)
        print("⚡ Herdr × Hermes AgenticOS — 대화형 통합 관리 메뉴 (Interactive Menu)")
        print("=" * 72)
        print(
            f"📊 현재 상태: 등록된 팀 [{team_count}개] | 활성 스킬 [{active_skills}개] | 사장님 프로필 [{profile_ok}]"
        )
        print("-" * 72)
        print("  1. 🌐 관리 콘솔 UI 열기 (Hermes-style Web Control Center - 스킬/팀/직원/기억/메신저 클릭 관리)")
        print("  2. 🏢 팀 & 직원 관리 (새 팀 추가 / 직원 직책·역할 배정 / 현재 창 목록)")
        print("  3. ⚡ 스킬(Skills) 관리 (스킬 카탈로그에서 원클릭 추가 / 새 스킬 작성 / 스킬 삭제)")
        print("  4. 🧠 기억장(Memory) 관리 (사장님 프로필 / 전사 기억장 조회 및 초기화)")
        print("  5. 💬 메신저(Telegram/Slack/Discord) 연결 설정 및 브릿지 시작")
        print("  6. 🔄 초기 상태로 전체 리셋 (Factory Reset)")
        print("  0. 종료 (Exit)")
        print("=" * 72)

        choice = prompt_input("원하시는 메뉴 번호를 선택하세요 (0~6)", "1")

        if choice == "0" or choice.lower() in ("q", "quit", "exit"):
            print("👋 Herdr × Hermes 관리 메뉴를 종료합니다.")
            return 0

        # 1. Web UI
        if choice == "1":
            return cmd_ui(argparse.Namespace(host="127.0.0.1", port=8765, no_browser=False))

        # 2. Teams & Employees
        elif choice == "2":
            print("\n[🏢 팀 & 직원 관리]")
            print("  1) 새 팀(부서) 만들기 및 Herdr 창 자동 배치")
            print("  2) 기존 Herdr 창(w1:p1, w1:p2 등)에 직책·역할 배정")
            print("  3) 특정 창 직원에게 업무 지시(프롬프트) 보내기")
            print("  4) 현재 전체 팀 및 Herdr 창 목록 보기")
            print("  0) 이전 메뉴로")
            sub = prompt_input("선택", "1")
            if sub == "1":
                cmd_team_create(argparse.Namespace(name="", roles="", launch=False))
            elif sub == "2":
                cmd_team_list(argparse.Namespace())
                pid = prompt_input("직책을 부여할 창 ID (예: w1:p1, w1:p2)", "w1:p1")
                print("  [직책 프리셋] 1.총괄 기획 팀장(agy) 2.수석 리서처(claude) 3.수석 개발자(codex) 4.콘텐츠 작가(claude) 5.품질 검수자(codex) 6.직접 입력")
                p_idx = prompt_input("프리셋 번호 선택 (1~6)", "1")
                if p_idx in ("1", "2", "3", "4", "5"):
                    r_name, r_agent, r_desc = ROLE_PRESETS[int(p_idx) - 1]
                else:
                    r_name = prompt_input("직책 이름 입력", "전담 매니저")
                    r_agent = prompt_input("AI 엔진 (agy/claude/codex/opencode/gemini)", "claude")
                    r_desc = prompt_input("핵심 임무 입력", f"{r_name} 직무를 수행합니다.")
                launch_yn = prompt_yes_no("배정 후 즉시 AI CLI를 실행할까요?", False)
                assign_employee_to_pane(pid, r_name, r_agent, r_desc, launch=launch_yn)
            elif sub == "3":
                pid = prompt_input("지시를 보낼 창 ID (예: w1:p2)", "w1:p2")
                msg = prompt_input("전달할 업무 지시 내용")
                if msg:
                    cmd_employee_prompt(argparse.Namespace(pane_id=pid, instruction=[msg]))
            elif sub == "4":
                cmd_team_list(argparse.Namespace())

        # 3. Skills Hub
        elif choice == "3":
            print("\n[⚡ 스킬(Skills) 관리]")
            print("  1) 현재 장착된 스킬 및 기본 카탈로그 목록 보기")
            print("  2) 기본 스킬 카탈로그(templates/skills/)에서 원클릭 장착")
            print("  3) 새 커스텀 스킬 만들기")
            print("  4) 장착된 스킬 삭제")
            print("  0) 이전 메뉴로")
            sub = prompt_input("선택", "2")
            if sub == "1":
                cmd_skill_list(argparse.Namespace())
                print("\n📦 [기본 제공 스킬 카탈로그 (templates/skills/)]")
                for idx, c in enumerate(st["catalog_skills"], start=1):
                    status_str = "장착됨" if c["installed"] else "미장착"
                    print(f"  {idx}. {c['id']:<22} [{status_str}] - {c['description']}")
            elif sub == "2":
                print("\n📦 [기본 제공 스킬 카탈로그]")
                cats = st["catalog_skills"]
                for idx, c in enumerate(cats, start=1):
                    status_str = "✅장착됨" if c["installed"] else "⚪미장착"
                    print(f"  {idx}. {c['id']:<22} ({status_str}) : {c['description']}")
                print("  a. 전체 카탈로그 스킬 한 번에 모두 장착")
                pick = prompt_input("장착할 스킬 번호 또는 'a' 입력", "a")
                if pick.lower() == "a":
                    for c in cats:
                        install_skill_from_catalog(c["id"])
                    print(f"✅ 카탈로그 스킬 {len(cats)}종이 모두 skills/ 에 장착되었습니다!")
                else:
                    try:
                        c_item = cats[int(pick) - 1]
                        ok, info = install_skill_from_catalog(c_item["id"])
                        print(f"✅ '{c_item['id']}' 장착 완료 -> {info}" if ok else f"❌ {info}")
                    except Exception:
                        print("⚠️ 올바른 번호를 입력해 주세요.")
            elif sub == "3":
                s_name = prompt_input("새 스킬 이름 (영문 소문자/하이픈 권장, 예: blog-writer)")
                s_desc = prompt_input("스킬 한 줄 설명")
                if s_name:
                    cmd_skill_create(argparse.Namespace(name=s_name, description=[s_desc]))
            elif sub == "4":
                inst = st["installed_skills"]
                if not inst:
                    print("  ℹ️ 현재 장착된 스킬이 없습니다.")
                else:
                    for idx, s in enumerate(inst, start=1):
                        print(f"  {idx}. {s['id']} ({s['description']})")
                    d_pick = prompt_input("삭제할 스킬 번호 입력")
                    try:
                        target_s = inst[int(d_pick) - 1]
                        ok, msg = delete_installed_skill(target_s["id"])
                        print(f"🗑️ {msg}")
                    except Exception:
                        print("⚠️ 취소되었습니다.")

        # 4. Memory
        elif choice == "4":
            print("\n[🧠 기억장(Memory) 관리]")
            print("  1) 사장님 프로필(USER_PROFILE.md) 및 전사 기억장(COMPANY_MEMORY.md) 생성/수정")
            print("  2) 현재 기억장 내용 조회")
            print("  3) 기억장만 초기 상태(0-State)로 비우기")
            print("  0) 이전 메뉴로")
            sub = prompt_input("선택", "1")
            if sub == "1":
                owner = prompt_input("사용자 이름 또는 호칭", "사장님")
                lang = prompt_input("기본 응답 언어", "한국어")
                style = prompt_input(
                    "선호 업무/보고 스타일",
                    "비개발자도 직관적으로 이해할 수 있도록 핵심 요약과 명확한 설명 선호",
                )
                ensure_root_constitution()
                up_p, cm_p = generate_user_profile_and_memory(owner, lang, style, overwrite_profile=True)
                print(f"✅ 생성 완료:\n  - {up_p}\n  - {cm_p}")
            elif sub == "2":
                print("\n--- [USER_PROFILE.md] ---")
                print(st["memory"]["user_profile"] or "(비어 있음 - 미등록 상태)")
                print("\n--- [COMPANY_MEMORY.md] ---")
                print(st["memory"]["company_memory"] or "(비어 있음 - 미등록 상태)")
            elif sub == "3":
                for fn in ("USER_PROFILE.md", "COMPANY_MEMORY.md"):
                    p = MEMORY_DIR / fn
                    if p.exists():
                        p.unlink()
                print("🗑️ 기억장(USER_PROFILE.md, COMPANY_MEMORY.md)이 초기화되었습니다.")

        # 5. Messenger
        elif choice == "5":
            print("\n[💬 메신저(Telegram/Slack/Discord) 연결 설정 및 브릿지 시작]")
            print("  1) 메신저 봇 토큰 설정 (.env)")
            print("  2) 멀티 메신저 브릿지 즉시 시작")
            print("  0) 이전 메뉴로")
            sub = prompt_input("선택", "1")
            if sub == "1":
                env_vars = load_env_file(ENV_FILE)
                env_vars["TELEGRAM_BOT_TOKEN"] = prompt_input(
                    "Telegram Bot Token (@BotFather, 없으면 Enter)",
                    env_vars.get("TELEGRAM_BOT_TOKEN", ""),
                )
                env_vars["TELEGRAM_ALLOWED_CHAT_IDS"] = prompt_input(
                    "Telegram 허용 Chat ID (비워두면 첫 사용자 자동 등록)",
                    env_vars.get("TELEGRAM_ALLOWED_CHAT_IDS", ""),
                )
                env_vars["SLACK_BOT_TOKEN"] = prompt_input(
                    "Slack Bot Token (xoxb-..., 없으면 Enter)",
                    env_vars.get("SLACK_BOT_TOKEN", ""),
                )
                env_vars["SLACK_CHANNEL_ID"] = prompt_input(
                    "Slack Channel ID (없으면 Enter)",
                    env_vars.get("SLACK_CHANNEL_ID", ""),
                )
                env_vars["DISCORD_BOT_TOKEN"] = prompt_input(
                    "Discord Bot Token (없으면 Enter)",
                    env_vars.get("DISCORD_BOT_TOKEN", ""),
                )
                env_vars["DISCORD_CHANNEL_ID"] = prompt_input(
                    "Discord Channel ID (없으면 Enter)",
                    env_vars.get("DISCORD_CHANNEL_ID", ""),
                )
                auto_en = []
                if env_vars.get("TELEGRAM_BOT_TOKEN"):
                    auto_en.append("telegram")
                if env_vars.get("SLACK_BOT_TOKEN") or env_vars.get("SLACK_WEBHOOK_URL"):
                    auto_en.append("slack")
                if env_vars.get("DISCORD_BOT_TOKEN") or env_vars.get("DISCORD_WEBHOOK_URL"):
                    auto_en.append("discord")
                env_vars["ENABLED_MESSENGERS"] = ",".join(auto_en)
                save_env_file(env_vars, ENV_FILE)
                print(f"✅ .env 설정 저장 완료! (활성 메신저: {env_vars['ENABLED_MESSENGERS'] or '없음'})")
            elif sub == "2":
                cmd_gateway_start(argparse.Namespace(extra=[]))

        # 6. Factory Reset
        elif choice == "6":
            cmd_reset(argparse.Namespace(yes=False, include_env=False))



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

    # 7. ui / dashboard (Web Control Console)
    for ui_cmd in ("ui", "dashboard"):
        ui_parser = subparsers.add_parser(
            ui_cmd,
            help="헤르메스 스타일 웹 관리 콘솔 UI 실행 (브라우저에서 스킬/팀/기억/메신저 클릭 관리)",
        )
        ui_parser.add_argument("--host", default="127.0.0.1", help="웹 콘솔 바인딩 호스트 (기본: 127.0.0.1)")
        ui_parser.add_argument("--port", type=int, default=8765, help="웹 콘솔 포트 번호 (기본: 8765)")
        ui_parser.add_argument("--no-browser", action="store_true", help="브라우저 자동 열기 비활성화")

    # 8. menu / tui (Interactive Terminal Menu)
    for menu_cmd in ("menu", "tui"):
        subparsers.add_parser(
            menu_cmd,
            help="터미널 대화형 통합 제어 메뉴(TUI) 실행 (인자 없이 실행 시 기본 동작)",
        )

    # 9. reset (Clean State Reset)
    reset_parser = subparsers.add_parser(
        "reset",
        help="모든 런타임 팀(teams/*), 장착 스킬(skills/*), 기억장을 비우고 순수 초기 상태(Clean State)로 리셋",
    )
    reset_parser.add_argument("--yes", "--force", "-y", dest="yes", action="store_true", help="확인 질문 없이 즉시 초기화")
    reset_parser.add_argument("--include-env", "--reset-env", dest="include_env", action="store_true", help=".env 메신저 설정까지 함께 초기화")

    # 10. status (alias for doctor) & role assign (compatibility alias)
    subparsers.add_parser("status", help="시스템 상태 점검 (doctor와 동일)")

    role_parser = subparsers.add_parser("role", help="창(Pane)에 표준 직책 프리셋 배정")
    role_sub = role_parser.add_subparsers(dest="role_cmd", help="role 하위 명령")
    ra_parser = role_sub.add_parser("assign", help="특정 창에 직책과 임무 부여")
    ra_parser.add_argument("--pane", required=True, help="대상 창 ID (예: w1:p2)")
    ra_parser.add_argument("--role", required=True, help="직책 이름 또는 코드")
    ra_parser.add_argument("--agent", default="claude", help="사용할 AI 엔진")
    ra_parser.add_argument("--mission", default="", help="핵심 임무 설명")
    ra_parser.add_argument("--team", default=None, help="소속 부서 이름")
    ra_parser.add_argument("--launch", action="store_true", help="배정 후 즉시 AI 실행")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None or args.command in ("menu", "tui"):
        return interactive_terminal_menu()
    if args.command in ("ui", "dashboard"):
        return cmd_ui(args)
    if args.command == "reset":
        return cmd_reset(args)
    if args.command == "setup":
        return cmd_setup(args)
    if args.command in ("doctor", "status"):
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
    if args.command == "role":
        if args.role_cmd == "assign":
            mission = args.mission or f"{args.role}로서 배정된 과제를 수행하고 TEAM_MEMORY.md에 핵심 요약을 기록합니다."
            assign_employee_to_pane(
                pane_id=args.pane,
                role_name=args.role,
                agent_name=args.agent,
                mission=mission,
                team_name=args.team,
                launch=bool(args.launch),
            )
            return 0
        parser.parse_args(["role", "--help"])
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
