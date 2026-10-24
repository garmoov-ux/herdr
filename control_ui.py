#!/usr/bin/env python3
"""
Herdr × Hermes AgenticOS Control Center (control_ui.py)
Provides:
1. Clean-State Reset & Template Catalog Management (Skills, Roles, Teams, Memory, Messengers)
2. Interactive Terminal TUI Menu (Arrow keys ↑/↓ + Number selection)
3. Hermes-Style Web Control Console UI (http://127.0.0.1:8765, 100% Python stdlib)
"""

import datetime
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent
MEMORY_DIR = ROOT_DIR / "memory"
TEAMS_DIR = ROOT_DIR / "teams"
SKILLS_DIR = ROOT_DIR / "skills"
TEMPLATES_DIR = ROOT_DIR / "templates"
ROLE_TEMPLATES_DIR = TEMPLATES_DIR / "roles"
SKILL_TEMPLATES_DIR = TEMPLATES_DIR / "skills"
GATEWAYS_DIR = ROOT_DIR / "gateways"
ENV_FILE = ROOT_DIR / ".env"

ROLE_CATALOG: List[Dict[str, str]] = [
    {
        "code": "pm_leader",
        "name": "총괄 기획 팀장(PM)",
        "default_agent": "agy",
        "mission": "사장님 지시 접수, 전체 업무 기획, 하위 창(p2, p3...) 업무 분배 및 최종 품질 검수를 담당합니다.",
    },
    {
        "code": "researcher",
        "name": "수석 리서처",
        "default_agent": "claude",
        "mission": "웹·공식 문서·코드베이스 심층 조사, 팩트체크 및 3줄 핵심 요약을 TEAM_MEMORY.md에 기록합니다.",
    },
    {
        "code": "developer",
        "name": "수석 개발자",
        "default_agent": "codex",
        "mission": "이식성 100% 클린 코드 구현, 자동화 스크립트 작성, 테스트 검증 및 기술 스킬 자산화를 담당합니다.",
    },
    {
        "code": "ui_designer",
        "name": "수석 UI/UX 디자이너",
        "default_agent": "agy",
        "mission": "직관적인 정보 구조(IA), UI/UX 프로토타입, 디자인 시스템 및 개발 친화적 디자인 토큰 명세를 담당합니다.",
    },
    {
        "code": "writer",
        "name": "콘텐츠·문서 작가",
        "default_agent": "claude",
        "mission": "비개발자도 단번에 이해할 수 있는 기획서, 매뉴얼, 보고서, 아티클 및 대본 집필을 담당합니다.",
    },
    {
        "code": "qa_reviewer",
        "name": "품질·보안 검수자(QA)",
        "default_agent": "codex",
        "mission": "경로 하드코딩, 보안 취약점, 엣지 케이스, 오탈자를 검증하고 PASS/REJECT 판정을 수행합니다.",
    },
]


# =====================================================================
# Core State & File Management Helpers
# =====================================================================

def ensure_clean_gitkeep_dirs() -> None:
    """Ensure memory/, skills/, teams/ exist and contain .gitkeep files."""
    for folder in (MEMORY_DIR, SKILLS_DIR, TEAMS_DIR):
        folder.mkdir(parents=True, exist_ok=True)
        gitkeep = folder / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.write_text("", encoding="utf-8")


def reset_to_clean_state(reset_env: bool = False) -> Dict[str, Any]:
    """
    Reset the workspace to a 100% pure initial state (Clean State):
    - Removes all user-created teams in `teams/` (except `.gitkeep`)
    - Removes all installed skills in `skills/` (except `.gitkeep`)
    - Removes `memory/USER_PROFILE.md` and `memory/COMPANY_MEMORY.md` (except `.gitkeep`)
    - Optionally clears `.env` if `reset_env=True`
    """
    ensure_clean_gitkeep_dirs()
    removed_teams: List[str] = []
    removed_skills: List[str] = []
    removed_memories: List[str] = []

    if TEAMS_DIR.exists():
        for item in TEAMS_DIR.iterdir():
            if item.name == ".gitkeep":
                continue
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
                removed_teams.append(item.name)
            else:
                item.unlink(missing_ok=True)
                removed_teams.append(item.name)

    if SKILLS_DIR.exists():
        for item in SKILLS_DIR.iterdir():
            if item.name == ".gitkeep":
                continue
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
                removed_skills.append(item.name)
            else:
                item.unlink(missing_ok=True)
                removed_skills.append(item.name)

    if MEMORY_DIR.exists():
        for item in MEMORY_DIR.iterdir():
            if item.name == ".gitkeep":
                continue
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
                removed_memories.append(item.name)
            else:
                item.unlink(missing_ok=True)
                removed_memories.append(item.name)

    if reset_env and ENV_FILE.exists():
        ENV_FILE.unlink(missing_ok=True)

    return {
        "ok": True,
        "removed_teams": removed_teams,
        "removed_skills": removed_skills,
        "removed_memories": removed_memories,
        "reset_env": reset_env,
    }


def list_skill_catalog_and_installed(herdr_os_mod: Any) -> Dict[str, Any]:
    """Return both installed skills (`skills/*`) and catalog templates (`templates/skills/*`)."""
    ensure_clean_gitkeep_dirs()
    installed: List[Dict[str, str]] = []
    installed_names = set()

    if SKILLS_DIR.exists():
        for sf in sorted(SKILLS_DIR.glob("*/SKILL.md")):
            s_name, s_desc = herdr_os_mod.parse_skill_frontmatter(sf)
            folder_name = sf.parent.name
            installed_names.add(folder_name)
            installed.append(
                {
                    "id": folder_name,
                    "name": s_name,
                    "description": s_desc,
                    "path": f"./skills/{folder_name}/SKILL.md",
                    "content": sf.read_text(encoding="utf-8", errors="replace"),
                }
            )

    catalog: List[Dict[str, Any]] = []
    if SKILL_TEMPLATES_DIR.exists():
        for tf in sorted(SKILL_TEMPLATES_DIR.glob("*/SKILL.md")):
            t_name, t_desc = herdr_os_mod.parse_skill_frontmatter(tf)
            folder_name = tf.parent.name
            catalog.append(
                {
                    "id": folder_name,
                    "name": t_name,
                    "description": t_desc,
                    "template_path": f"./templates/skills/{folder_name}/SKILL.md",
                    "installed": folder_name in installed_names,
                    "content": tf.read_text(encoding="utf-8", errors="replace"),
                }
            )

    return {"installed": installed, "catalog": catalog}


def install_skill_from_template(herdr_os_mod: Any, template_id: str) -> Tuple[bool, str]:
    """Copy a skill from `templates/skills/<template_id>` into `skills/<template_id>`."""
    safe_id = herdr_os_mod.sanitize_folder_name(template_id.strip())
    src_dir = SKILL_TEMPLATES_DIR / safe_id
    src_file = src_dir / "SKILL.md"
    if not src_file.exists():
        return False, f"템플릿 스킬을 찾을 수 없습니다: {safe_id}"

    dst_dir = SKILLS_DIR / safe_id
    dst_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_file, dst_dir / "SKILL.md")
    return True, f"스킬 [{safe_id}] 장착 완료 (./skills/{safe_id}/SKILL.md)"


def save_skill(
    herdr_os_mod: Any, skill_id: str, description: str = "", content: str = ""
) -> Tuple[bool, str]:
    """Create or update a skill under `skills/<skill_id>/SKILL.md`."""
    raw_name = skill_id.strip()
    if not raw_name:
        return False, "스킬 이름을 입력해 주세요."
    safe_id = herdr_os_mod.sanitize_folder_name(raw_name.lower().replace(" ", "-"))
    skill_dir = SKILLS_DIR / safe_id
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    today = datetime.date.today().isoformat()

    if not content.strip():
        desc = description.strip() or f"{raw_name} 표준 수행 절차 및 노하우 스킬"
        content = f"""---
name: {safe_id}
description: "{desc}"
---

# 🛠️ {raw_name} ({safe_id})

> 생성일: {today}  
> 이 스킬은 Herdr × Hermes 자기 진화 루프(Self-Improving Skill Loop)를 통해 생성된 재사용 가능 업무 표준 절차서(SOP)입니다.

## 1. 언제 이 스킬을 사용하는가 (Trigger)
- {desc}

## 2. 표준 수행 절차 (Step-by-Step Procedure)
1. 관련 컨텍스트(`./memory/COMPANY_MEMORY.md` 또는 `TEAM_MEMORY.md`)를 먼저 확인합니다.
2. 아래 검증된 명령어 및 절차를 순서대로 실행합니다.
3. 실행 결과를 검증하고 새롭게 발견한 엣지 케이스가 있다면 이 `SKILL.md`를 업데이트합니다.

## 3. 주의사항 및 노하우 (Best Practices)
- 특정 PC 드라이브 경로를 하드코딩하지 않고 항상 저장소 루트 기준 상대 경로(`./...`)를 사용합니다.
"""
    skill_file.write_text(content, encoding="utf-8")
    return True, f"스킬 [{safe_id}] 저장 완료 (./skills/{safe_id}/SKILL.md)"


def delete_skill(herdr_os_mod: Any, skill_id: str) -> Tuple[bool, str]:
    """Delete an installed skill folder from `skills/<skill_id>`."""
    safe_id = herdr_os_mod.sanitize_folder_name(skill_id.strip())
    target = SKILLS_DIR / safe_id
    if not target.exists() or not target.is_dir():
        return False, f"삭제할 스킬 폴더가 존재하지 않습니다: {safe_id}"
    shutil.rmtree(target, ignore_errors=True)
    return True, f"스킬 [{safe_id}] 삭제 완료"


def get_role_template_text(role_code_or_name: str) -> str:
    """Return the markdown body from `templates/roles/<code_or_matched>.md` if available."""
    code_map = {
        "pm_leader": "pm_leader.md",
        "팀장": "pm_leader.md",
        "총괄 기획 팀장(pm)": "pm_leader.md",
        "팀장(pm)": "pm_leader.md",
        "researcher": "researcher.md",
        "리서처": "researcher.md",
        "수석 리서처": "researcher.md",
        "developer": "developer.md",
        "개발자": "developer.md",
        "수석 개발자": "developer.md",
        "ui_designer": "ui_designer.md",
        "디자이너": "ui_designer.md",
        "수석 ui/ux 디자이너": "ui_designer.md",
        "writer": "writer.md",
        "작가": "writer.md",
        "콘텐츠·문서 작가": "writer.md",
        "qa_reviewer": "qa_reviewer.md",
        "검수자": "qa_reviewer.md",
        "품질·보안 검수자(qa)": "qa_reviewer.md",
        "검수자(qa)": "qa_reviewer.md",
    }
    key = role_code_or_name.strip().lower()
    fname = code_map.get(key)
    if fname and (ROLE_TEMPLATES_DIR / fname).exists():
        return (ROLE_TEMPLATES_DIR / fname).read_text(encoding="utf-8", errors="replace")
    return ""


def list_teams_and_live_panes(herdr_os_mod: Any) -> Dict[str, Any]:
    """Return local teams (`teams/*`), live Herdr workspaces/panes, and role catalog."""
    ensure_clean_gitkeep_dirs()
    local_teams: List[Dict[str, Any]] = []
    if TEAMS_DIR.exists():
        for t_dir in sorted(TEAMS_DIR.iterdir()):
            if not t_dir.is_dir():
                continue
            members: List[Dict[str, Any]] = []
            for sub in sorted(t_dir.iterdir()):
                if not sub.is_dir():
                    continue
                meta_file = sub / "EMPLOYEE_META.json"
                if meta_file.exists():
                    try:
                        m = json.loads(meta_file.read_text(encoding="utf-8"))
                        m["folder"] = sub.name
                        members.append(m)
                    except Exception:
                        pass
                elif (sub / "ROLE_GUIDE.md").exists():
                    members.append(
                        {
                            "folder": sub.name,
                            "team_name": t_dir.name,
                            "role_name": sub.name,
                            "agent": "-",
                            "mission": "ROLE_GUIDE.md 참조",
                            "pane_id": None,
                        }
                    )
            tm_file = t_dir / "TEAM_MEMORY.md"
            local_teams.append(
                {
                    "id": t_dir.name,
                    "name": t_dir.name,
                    "path": f"./teams/{t_dir.name}",
                    "has_memory": tm_file.exists(),
                    "memory_content": (
                        tm_file.read_text(encoding="utf-8", errors="replace")
                        if tm_file.exists()
                        else ""
                    ),
                    "members": members,
                }
            )

    rc_ws, ws_out, _ = herdr_os_mod.run_herdr(["workspace", "list"])
    rc_p, p_out, _ = herdr_os_mod.run_herdr(["pane", "list"])
    workspaces = (
        herdr_os_mod.parse_herdr_json(ws_out).get("result", {}).get("workspaces", [])
        if rc_ws == 0
        else []
    )
    panes = (
        herdr_os_mod.parse_herdr_json(p_out).get("result", {}).get("panes", [])
        if rc_p == 0
        else []
    )

    return {
        "local_teams": local_teams,
        "live_workspaces": workspaces,
        "live_panes": panes,
        "herdr_connected": (rc_ws == 0 and rc_p == 0),
        "role_catalog": ROLE_CATALOG,
        "supported_agents": list(herdr_os_mod.SUPPORTED_AGENTS.keys()),
    }


def delete_team_folder(herdr_os_mod: Any, team_id: str) -> Tuple[bool, str]:
    """Delete a team directory from `teams/<team_id>`."""
    safe_id = herdr_os_mod.sanitize_folder_name(team_id.strip())
    target = TEAMS_DIR / safe_id
    if not target.exists() or not target.is_dir():
        return False, f"삭제할 팀 폴더가 존재하지 않습니다: {safe_id}"
    shutil.rmtree(target, ignore_errors=True)
    return True, f"부서 [{safe_id}] 폴더 삭제 완료"


def get_memory_state() -> Dict[str, Any]:
    """Return contents and existence state of USER_PROFILE.md, COMPANY_MEMORY.md, AGENTS.md, and team memories."""
    ensure_clean_gitkeep_dirs()
    up_path = MEMORY_DIR / "USER_PROFILE.md"
    cm_path = MEMORY_DIR / "COMPANY_MEMORY.md"
    ag_path = ROOT_DIR / "AGENTS.md"

    team_memories: List[Dict[str, str]] = []
    if TEAMS_DIR.exists():
        for t_dir in sorted(TEAMS_DIR.iterdir()):
            if not t_dir.is_dir():
                continue
            tm = t_dir / "TEAM_MEMORY.md"
            if tm.exists():
                team_memories.append(
                    {
                        "team_id": t_dir.name,
                        "path": f"./teams/{t_dir.name}/TEAM_MEMORY.md",
                        "content": tm.read_text(encoding="utf-8", errors="replace"),
                    }
                )

    return {
        "user_profile": {
            "exists": up_path.exists(),
            "path": "./memory/USER_PROFILE.md",
            "content": up_path.read_text(encoding="utf-8", errors="replace")
            if up_path.exists()
            else "",
        },
        "company_memory": {
            "exists": cm_path.exists(),
            "path": "./memory/COMPANY_MEMORY.md",
            "content": cm_path.read_text(encoding="utf-8", errors="replace")
            if cm_path.exists()
            else "",
        },
        "agents_md": {
            "exists": ag_path.exists(),
            "path": "./AGENTS.md",
            "content": ag_path.read_text(encoding="utf-8", errors="replace")
            if ag_path.exists()
            else "",
        },
        "team_memories": team_memories,
    }


def save_memory_doc(herdr_os_mod: Any, doc_type: str, content: str, team_id: str = "") -> Tuple[bool, str]:
    """Save USER_PROFILE.md, COMPANY_MEMORY.md, AGENTS.md, or a team's TEAM_MEMORY.md."""
    ensure_clean_gitkeep_dirs()
    if doc_type == "user_profile":
        target = MEMORY_DIR / "USER_PROFILE.md"
        target.write_text(content, encoding="utf-8")
        return True, "./memory/USER_PROFILE.md 저장 완료"
    if doc_type == "company_memory":
        target = MEMORY_DIR / "COMPANY_MEMORY.md"
        target.write_text(content, encoding="utf-8")
        return True, "./memory/COMPANY_MEMORY.md 저장 완료"
    if doc_type == "agents_md":
        target = ROOT_DIR / "AGENTS.md"
        target.write_text(content, encoding="utf-8")
        return True, "./AGENTS.md 저장 완료"
    if doc_type == "team_memory" and team_id:
        safe_team = herdr_os_mod.sanitize_folder_name(team_id)
        t_dir = TEAMS_DIR / safe_team
        t_dir.mkdir(parents=True, exist_ok=True)
        target = t_dir / "TEAM_MEMORY.md"
        target.write_text(content, encoding="utf-8")
        return True, f"./teams/{safe_team}/TEAM_MEMORY.md 저장 완료"
    return False, f"알 수 없는 기억 문서 종류입니다: {doc_type}"


def delete_memory_doc(doc_type: str) -> Tuple[bool, str]:
    """Delete USER_PROFILE.md or COMPANY_MEMORY.md to return memory to clean state."""
    if doc_type == "user_profile":
        target = MEMORY_DIR / "USER_PROFILE.md"
        target.unlink(missing_ok=True)
        return True, "./memory/USER_PROFILE.md 초기화(삭제) 완료"
    if doc_type == "company_memory":
        target = MEMORY_DIR / "COMPANY_MEMORY.md"
        target.unlink(missing_ok=True)
        return True, "./memory/COMPANY_MEMORY.md 초기화(삭제) 완료"
    return False, "삭제할 수 없는 문서 종류입니다."


# =====================================================================
# HTML / JS Single-Page Application for Hermes Web Control Console
# =====================================================================

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Herdr × Hermes AgenticOS Control Center</title>
<style>
  :root {
    --bg: #0b0f19;
    --panel: #131a2a;
    --panel-alt: #1a2337;
    --border: #283552;
    --primary: #6366f1;
    --primary-hover: #818cf8;
    --accent: #10b981;
    --danger: #ef4444;
    --warn: #f59e0b;
    --text: #f1f5f9;
    --muted: #94a3b8;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Pretendard", "Malgun Gothic", sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
    padding-bottom: 60px;
  }
  header {
    background: linear-gradient(135deg, #111827 0%, #1e1b4b 100%);
    border-bottom: 1px solid var(--border);
    padding: 18px 28px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
  }
  .brand { display: flex; align-items: center; gap: 12px; }
  .brand h1 { font-size: 1.35rem; font-weight: 700; letter-spacing: -0.02em; }
  .badge {
    font-size: 0.78rem;
    padding: 4px 10px;
    border-radius: 999px;
    background: rgba(99, 102, 241, 0.2);
    border: 1px solid var(--primary);
    color: #c7d2fe;
  }
  .badge.ok { background: rgba(16, 185, 129, 0.18); border-color: var(--accent); color: #a7f3d0; }
  .container { max-width: 1280px; margin: 0 auto; padding: 22px 24px; }
  .tabs {
    display: flex;
    gap: 8px;
    border-bottom: 1px solid var(--border);
    padding-bottom: 12px;
    margin-bottom: 22px;
    flex-wrap: wrap;
  }
  .tab-btn {
    background: var(--panel);
    color: var(--muted);
    border: 1px solid var(--border);
    padding: 10px 18px;
    border-radius: 10px;
    cursor: pointer;
    font-weight: 600;
    font-size: 0.92rem;
    transition: all 0.15s;
  }
  .tab-btn:hover { color: var(--text); border-color: var(--primary); }
  .tab-btn.active {
    background: var(--primary);
    color: #fff;
    border-color: var(--primary);
    box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35);
  }
  .tab-pane { display: none; }
  .tab-pane.active { display: block; }
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
  .grid-3 { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }
  @media (max-width: 900px) { .grid-2 { grid-template-columns: 1fr; } }
  .card {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 18px 20px;
    margin-bottom: 18px;
  }
  .card h2 { font-size: 1.08rem; margin-bottom: 6px; display: flex; align-items: center; gap: 8px; }
  .card p.sub { color: var(--muted); font-size: 0.86rem; margin-bottom: 14px; }
  .btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 14px;
    border-radius: 8px;
    font-weight: 600;
    font-size: 0.86rem;
    border: 1px solid transparent;
    cursor: pointer;
    background: var(--primary);
    color: #fff;
    transition: opacity 0.15s, background 0.15s;
  }
  .btn:hover { background: var(--primary-hover); }
  .btn.success { background: var(--accent); color: #052e16; }
  .btn.danger { background: rgba(239, 68, 68, 0.18); border-color: var(--danger); color: #fca5a5; }
  .btn.danger:hover { background: var(--danger); color: #fff; }
  .btn.secondary { background: var(--panel-alt); border-color: var(--border); color: var(--text); }
  .btn.sm { padding: 5px 10px; font-size: 0.8rem; }
  input, select, textarea {
    width: 100%;
    padding: 9px 12px;
    background: #0d1322;
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    font-family: inherit;
    font-size: 0.9rem;
    margin-top: 4px;
    margin-bottom: 12px;
  }
  textarea { font-family: "Consolas", "Monaco", monospace; min-height: 220px; resize: vertical; }
  label { font-size: 0.84rem; font-weight: 600; color: #cbd5e1; display: block; }
  .item-box {
    background: var(--panel-alt);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: 10px;
  }
  .item-box h3 { font-size: 0.98rem; display: flex; justify-content: space-between; align-items: center; }
  .item-box p { font-size: 0.84rem; color: var(--muted); }
  .role-row {
    display: grid;
    grid-template-columns: 1.4fr 0.9fr 2fr auto;
    gap: 8px;
    align-items: center;
    margin-bottom: 8px;
  }
  .role-row input, .role-row select { margin: 0; }
  #toast {
    position: fixed;
    bottom: 24px;
    right: 24px;
    background: #1e293b;
    border-left: 4px solid var(--accent);
    color: #fff;
    padding: 12px 20px;
    border-radius: 8px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.5);
    display: none;
    z-index: 9999;
    font-size: 0.9rem;
  }
  .empty-state {
    text-align: center;
    padding: 28px 16px;
    color: var(--muted);
    border: 1px dashed var(--border);
    border-radius: 10px;
    font-size: 0.9rem;
  }
</style>
</head>
<body>

<header>
  <div class="brand">
    <span style="font-size:1.7rem;">🧠</span>
    <div>
      <h1>Herdr × Hermes AgenticOS 관리 콘솔</h1>
      <div style="font-size:0.82rem; color:var(--muted);">명령어 없이 클릭만으로 스킬 · 팀/직원 · 기억장 · 메신저를 통합 제어합니다</div>
    </div>
  </div>
  <div style="display:flex; gap:10px; align-items:center;">
    <span id="herdr-status-badge" class="badge">Herdr 상태 확인 중...</span>
    <button class="btn secondary sm" onclick="refreshAll()">🔄 새로고침</button>
    <button class="btn danger sm" onclick="confirmReset()">🗑️ 초기값 리셋 (Clean State)</button>
  </div>
</header>

<div class="container">
  <div class="tabs">
    <button class="tab-btn active" onclick="switchTab('skills', this)">📚 1. 스킬 카탈로그 & 보관함</button>
    <button class="tab-btn" onclick="switchTab('teams', this)">🏢 2. 팀 & 직원 (Teams & Roles)</button>
    <button class="tab-btn" onclick="switchTab('memory', this)">🧠 3. 기억장 & 헌법 편집기</button>
    <button class="tab-btn" onclick="switchTab('messenger', this)">💬 4. 멀티 메신저 연동</button>
    <button class="tab-btn" onclick="switchTab('doctor', this)">🩺 5. 시스템 진단 & 초기화</button>
  </div>

  <!-- TAB 1: SKILLS -->
  <div id="tab-skills" class="tab-pane active">
    <div class="card">
      <h2>📥 기본 제공 스킬 카탈로그 (`./templates/skills/`)</h2>
      <p class="sub">초기 클론 시 `./skills/` 폴더는 비어 있습니다. 필요한 스킬을 1클릭으로 내 에이전트 회사에 장착하세요.</p>
      <div id="skill-catalog-list" class="grid-3"></div>
    </div>

    <div class="grid-2">
      <div class="card">
        <h2>⚡ 현재 장착된 스킬 (`./skills/`)</h2>
        <p class="sub">AI 직원들이 작업 시 자동으로 검색·재사용하는 활성 스킬 목록입니다.</p>
        <div id="skill-installed-list"></div>
      </div>

      <div class="card">
        <h2>✍️ 새 스킬 직접 추가 / 마크다운 편집</h2>
        <p class="sub">새로운 업무 노하우(SOP)를 직접 만들거나 기존 스킬을 클릭해 수정합니다.</p>
        <label>스킬 ID (영문/숫자/하이픈 권장, 예: youtube-script-sop)</label>
        <input type="text" id="skill-id-input" placeholder="예: market-research-sop">
        <label>한 줄 요약 설명 (Trigger Description)</label>
        <input type="text" id="skill-desc-input" placeholder="예: 경쟁사 기능 비교 및 핵심 요약 리포트 작성 스킬">
        <label>SKILL.md 상세 지침 (비워두면 표준 템플릿으로 자동 생성됩니다)</label>
        <textarea id="skill-content-input" placeholder="---&#10;name: ...&#10;description: ...&#10;---"></textarea>
        <div style="display:flex; gap:8px;">
          <button class="btn" onclick="saveSkill()">💾 스킬 저장 / 업데이트</button>
          <button class="btn secondary" onclick="clearSkillForm()">초기화</button>
        </div>
      </div>
    </div>
  </div>

  <!-- TAB 2: TEAMS & ROLES -->
  <div id="tab-teams" class="tab-pane">
    <div class="grid-2">
      <div class="card">
        <h2>➕ 새 부서(Team) 및 직원 책상(Pane) 원클릭 생성</h2>
        <p class="sub">부서 이름을 입력하고 직책 프리셋(팀장/리서처/개발자/디자이너/작가/검수자)을 골라 한 번에 생성합니다.</p>
        <label>새 부서(Team) 이름</label>
        <input type="text" id="new-team-name" placeholder="예: 마케팅팀, 유튜브기획팀, 개발1팀" value="메인본부">

        <div style="display:flex; justify-content:space-between; align-items:center; margin:8px 0;">
          <label style="margin:0;">배치할 AI 직원 (창 p1, p2, p3...)</label>
          <button class="btn secondary sm" onclick="addRoleRow()">+ 직원(창) 추가</button>
        </div>
        <div id="team-roles-container"></div>

        <label style="display:flex; align-items:center; gap:8px; margin-top:10px; cursor:pointer;">
          <input type="checkbox" id="new-team-launch" style="width:auto; margin:0;">
          <span>창 생성과 동시에 각 AI 에이전트(agy/claude/codex) 즉시 실행</span>
        </label>
        <div style="margin-top:14px;">
          <button class="btn" onclick="createTeam()">🚀 부서 폴더 + Herdr 워크스페이스 생성</button>
        </div>
      </div>

      <div class="card">
        <h2>🪪 실시간 Herdr 창(Pane) 직책 배정 & 업무 지시</h2>
        <p class="sub">현재 열려 있는 Herdr 창(예: w1:p1, w1:p2)에 직책 사원증을 부여하거나 즉시 지시를 보냅니다.</p>
        <label>대상 창(Pane) 선택 또는 입력</label>
        <input type="text" id="assign-pane-id" placeholder="예: w1:p2">
        <div class="grid-2" style="gap:10px;">
          <div>
            <label>직책 프리셋 선택</label>
            <select id="assign-role-select" onchange="onAssignPresetChange()"></select>
          </div>
          <div>
            <label>주력 AI 엔진</label>
            <select id="assign-agent-select">
              <option value="agy">agy (Antigravity)</option>
              <option value="claude">claude (Claude Code)</option>
              <option value="codex">codex (OpenAI Codex)</option>
              <option value="opencode">opencode</option>
              <option value="gemini">gemini</option>
            </select>
          </div>
        </div>
        <label>핵심 임무 (Mission)</label>
        <input type="text" id="assign-mission-input" placeholder="이 창 직원이 수행할 핵심 임무">
        <div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:14px;">
          <button class="btn" onclick="assignPaneRole()">🪪 이 창에 직책/사원증 부여</button>
        </div>

        <hr style="border:none; border-top:1px solid var(--border); margin:14px 0;">
        <label>💬 특정 창에 즉시 업무 지시(Prompt) 보내기</label>
        <div style="display:flex; gap:8px; margin-top:6px;">
          <input type="text" id="prompt-text-input" placeholder="예: 주어진 주제를 조사해서 TEAM_MEMORY.md에 3줄 요약해줘" style="margin:0;">
          <button class="btn success" style="white-space:nowrap;" onclick="sendPanePrompt()">📨 지시 전송</button>
        </div>
      </div>
    </div>

    <div class="card">
      <h2>🏢 현재 구성된 부서 폴더 (`./teams/`) 및 실시간 Herdr 창 현황</h2>
      <p class="sub">생성된 부서를 확인하거나 삭제할 수 있으며, 실시간 Herdr 창을 클릭해 위 입력칸에 바로 불러올 수 있습니다.</p>
      <div id="live-panes-box" style="margin-bottom:16px;"></div>
      <div id="local-teams-list" class="grid-3"></div>
    </div>
  </div>

  <!-- TAB 3: MEMORY & CONSTITUTION -->
  <div id="tab-memory" class="tab-pane">
    <div class="card">
      <h2>🧠 헤르메스 2단 영구 기억장 & 전사 헌법 편집기</h2>
      <p class="sub">사장님 프로필(`USER_PROFILE.md`), 전사 장기 기억(`COMPANY_MEMORY.md`), 전사 헌법(`AGENTS.md`) 및 부서별 `TEAM_MEMORY.md`를 직접 편집·저장합니다.</p>
      <div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:14px;">
        <button class="btn secondary sm" onclick="loadMemoryEditor('user_profile')">👤 USER_PROFILE.md (사장님 프로필)</button>
        <button class="btn secondary sm" onclick="loadMemoryEditor('company_memory')">🏛️ COMPANY_MEMORY.md (전사 기억장)</button>
        <button class="btn secondary sm" onclick="loadMemoryEditor('agents_md')">📜 AGENTS.md (전사 헌법)</button>
        <button class="btn sm" onclick="initDefaultMemory()">✨ 기본 프로필/기억장 자동 생성</button>
      </div>
      <div id="team-memory-buttons" style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px;"></div>

      <label id="memory-editor-label">현재 편집 중인 문서: ./memory/USER_PROFILE.md</label>
      <textarea id="memory-editor-textarea" style="min-height:320px;"></textarea>
      <div style="display:flex; gap:10px; justify-content:space-between;">
        <button class="btn" onclick="saveMemoryEditor()">💾 현재 문서 저장하기</button>
        <button class="btn danger" onclick="deleteCurrentMemoryDoc()">🗑️ 이 기억 문서 초기화(삭제)</button>
      </div>
    </div>
  </div>

  <!-- TAB 4: MESSENGER -->
  <div id="tab-messenger" class="tab-pane">
    <div class="card">
      <h2>💬 멀티 메신저 원격 제어 설정 (`.env`)</h2>
      <p class="sub">외출 중에도 Telegram, Slack, Discord에서 집 PC의 모든 팀(`w1`, `w2`...)과 창(`p1`, `p2`...)을 양방향 제어합니다.</p>

      <label>활성화할 메신저 (쉼표 구분, 예: telegram,slack,discord)</label>
      <input type="text" id="env-enabled" placeholder="예: telegram">

      <div class="grid-3" style="margin-top:10px;">
        <div class="item-box">
          <h3>✈️ Telegram 설정</h3>
          <label>TELEGRAM_BOT_TOKEN (@BotFather)</label>
          <input type="password" id="env-tg-token" placeholder="123456:ABC-DEF...">
          <label>TELEGRAM_ALLOWED_CHAT_ID (선택)</label>
          <input type="text" id="env-tg-chat" placeholder="비워두면 첫 메시지 자동 등록">
        </div>

        <div class="item-box">
          <h3>💼 Slack 설정</h3>
          <label>SLACK_BOT_TOKEN (xoxb-...)</label>
          <input type="password" id="env-slack-token" placeholder="xoxb-...">
          <label>SLACK_CHANNEL_ID (C0123...)</label>
          <input type="text" id="env-slack-channel" placeholder="C0123456789">
          <label>SLACK_WEBHOOK_URL (선택)</label>
          <input type="text" id="env-slack-webhook" placeholder="https://hooks.slack.com/...">
        </div>

        <div class="item-box">
          <h3>🎮 Discord 설정</h3>
          <label>DISCORD_BOT_TOKEN</label>
          <input type="password" id="env-discord-token" placeholder="Discord Bot Token">
          <label>DISCORD_CHANNEL_ID</label>
          <input type="text" id="env-discord-channel" placeholder="채널 ID 숫자">
          <label>DISCORD_WEBHOOK_URL (선택)</label>
          <input type="text" id="env-discord-webhook" placeholder="https://discord.com/api/webhooks/...">
        </div>
      </div>

      <div style="margin-top:16px; display:flex; gap:10px;">
        <button class="btn" onclick="saveMessengerEnv()">💾 메신저 설정(.env) 저장</button>
        <button class="btn secondary" onclick="togglePasswordVisibility()">👁️ 토큰 표시/숨기기</button>
      </div>
    </div>
  </div>

  <!-- TAB 5: DOCTOR & RESET -->
  <div id="tab-doctor" class="tab-pane">
    <div class="grid-2">
      <div class="card">
        <h2>🩺 실시간 시스템 진단 (Doctor)</h2>
        <p class="sub">Herdr 연결 상태, 설치된 AI CLI 엔진, 폴더 및 기억장 상태를 점검합니다.</p>
        <pre id="doctor-output" style="background:#090d16; padding:14px; border-radius:8px; border:1px solid var(--border); overflow-x:auto; font-size:0.84rem; color:#cbd5e1; white-space:pre-wrap;"></pre>
      </div>

      <div class="card">
        <h2>🔄 순수 초기 상태(Clean State)로 전체 리셋</h2>
        <p class="sub">저장소를 처음 `git clone`했을 때처럼 모든 런타임 팀(`teams/*`), 장착된 스킬(`skills/*`), 사용자 기억장(`memory/USER_PROFILE.md`, `COMPANY_MEMORY.md`)을 비우고 깨끗한 0-상태로 되돌립니다.</p>
        <div class="item-box" style="border-color:var(--danger); margin-top:14px;">
          <h3 style="color:#fca5a5;">⚠️ 초기화 시 유지되는 항목 vs 삭제되는 항목</h3>
          <p>• <b>유지됨 (원본 보존):</b> `./templates/roles/*`, `./templates/skills/*`, `./AGENTS.md`, 코어 스크립트<br>
             • <b>초기화됨 (0-상태 복원):</b> `./teams/*` 내 생성된 부서, `./skills/*` 내 장착된 스킬, `./memory/USER_PROFILE.md`, `./memory/COMPANY_MEMORY.md`</p>
          <label style="display:flex; align-items:center; gap:8px; margin-top:8px;">
            <input type="checkbox" id="reset-env-check" style="width:auto; margin:0;">
            <span>`.env` 메신저 토큰 설정 파일도 함께 초기화</span>
          </label>
          <button class="btn danger" style="margin-top:10px;" onclick="confirmReset()">🗑️ 지금 순수 초기 상태(Clean State)로 리셋</button>
        </div>
      </div>
    </div>
  </div>
</div>

<div id="toast"></div>

<script>
let STATE = {
  skills: { installed: [], catalog: [] },
  teams: { local_teams: [], live_workspaces: [], live_panes: [], role_catalog: [], supported_agents: [] },
  memory: {},
  env: {},
  currentMemoryDoc: "user_profile",
  currentTeamMemoryId: ""
};

function showToast(msg, isError=false) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.style.borderLeftColor = isError ? "#ef4444" : "#10b981";
  el.style.display = "block";
  clearTimeout(window._toastTimer);
  window._toastTimer = setTimeout(() => { el.style.display = "none"; }, 3500);
}

function switchTab(name, btn) {
  document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
  document.getElementById("tab-" + name).classList.add("active");
  if (btn) btn.classList.add("active");
}

async function apiGet(path) {
  const res = await fetch(path);
  return await res.json();
}

async function apiPost(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {})
  });
  return await res.json();
}

async function refreshAll() {
  const data = await apiGet("/api/state");
  STATE.skills = data.skills;
  STATE.teams = data.teams;
  STATE.memory = data.memory;
  STATE.env = data.env;

  const badge = document.getElementById("herdr-status-badge");
  if (STATE.teams.herdr_connected) {
    badge.textContent = `🟢 Herdr 연결됨 (창 ${STATE.teams.live_panes.length}개)`;
    badge.className = "badge ok";
  } else {
    badge.textContent = `⚪ Herdr 오프라인 (로컬 관리 모드)`;
    badge.className = "badge";
  }

  renderSkills();
  renderTeams();
  renderMemory();
  renderMessenger();
  document.getElementById("doctor-output").textContent = data.doctor_text || "";
}

function renderSkills() {
  const catBox = document.getElementById("skill-catalog-list");
  catBox.innerHTML = "";
  STATE.skills.catalog.forEach(item => {
    const div = document.createElement("div");
    div.className = "item-box";
    div.innerHTML = `
      <div>
        <h3><span>📦 ${item.id}</span> <span class="badge ${item.installed ? 'ok' : ''}">${item.installed ? '장착됨' : '미장착'}</span></h3>
        <p style="margin-top:6px;">${item.description || ''}</p>
      </div>
      <div style="display:flex; gap:8px;">
        <button class="btn sm ${item.installed ? 'secondary' : 'success'}" onclick="installSkillTemplate('${item.id}')">
          ${item.installed ? '🔄 템플릿으로 덮어쓰기' : '📥 1클릭 스킬 장착'}
        </button>
      </div>
    `;
    catBox.appendChild(div);
  });

  const instBox = document.getElementById("skill-installed-list");
  if (!STATE.skills.installed.length) {
    instBox.innerHTML = `<div class="empty-state">현재 장착된 스킬이 없습니다 (순수 초기 상태).<br>위의 카탈로그에서 [📥 1클릭 스킬 장착]을 누르거나 우측에서 새 스킬을 추가하세요.</div>`;
    return;
  }
  instBox.innerHTML = "";
  STATE.skills.installed.forEach(s => {
    const div = document.createElement("div");
    div.className = "item-box";
    div.style.marginBottom = "10px";
    div.innerHTML = `
      <div>
        <h3><span>⚡ ${s.id}</span> <span style="font-size:0.76rem; color:var(--muted);">${s.path}</span></h3>
        <p style="margin-top:4px;">${s.description || ''}</p>
      </div>
      <div style="display:flex; gap:8px;">
        <button class="btn secondary sm" onclick="editSkill('${s.id}')">✏️ 내용 편집</button>
        <button class="btn danger sm" onclick="deleteSkill('${s.id}')">🗑️ 삭제</button>
      </div>
    `;
    instBox.appendChild(div);
  });
}

async function installSkillTemplate(id) {
  const res = await apiPost("/api/skills/install", { id });
  showToast(res.message, !res.ok);
  await refreshAll();
}

function editSkill(id) {
  const found = STATE.skills.installed.find(x => x.id === id);
  if (!found) return;
  document.getElementById("skill-id-input").value = found.id;
  document.getElementById("skill-desc-input").value = found.description || "";
  document.getElementById("skill-content-input").value = found.content || "";
  showToast(`[${id}] 내용을 편집창에 불러왔습니다.`);
}

function clearSkillForm() {
  document.getElementById("skill-id-input").value = "";
  document.getElementById("skill-desc-input").value = "";
  document.getElementById("skill-content-input").value = "";
}

async function saveSkill() {
  const id = document.getElementById("skill-id-input").value.trim();
  const description = document.getElementById("skill-desc-input").value.trim();
  const content = document.getElementById("skill-content-input").value;
  if (!id) { showToast("스킬 ID를 입력해 주세요.", true); return; }
  const res = await apiPost("/api/skills/save", { id, description, content });
  showToast(res.message, !res.ok);
  if (res.ok) { clearSkillForm(); await refreshAll(); }
}

async function deleteSkill(id) {
  if (!confirm(`정말 [${id}] 스킬을 삭제하시겠습니까?`)) return;
  const res = await apiPost("/api/skills/delete", { id });
  showToast(res.message, !res.ok);
  await refreshAll();
}

function initRoleRowsIfNeeded() {
  const container = document.getElementById("team-roles-container");
  if (container.children.length > 0) return;
  const defaults = [
    { role: "총괄 기획 팀장(PM)", agent: "agy", mission: "팀 전체 업무 기획, 하위 창 분배 및 최종 검수" },
    { role: "수석 리서처", agent: "claude", mission: "자료 조사, 팩트체크 및 TEAM_MEMORY.md 핵심 요약 기록" },
    { role: "수석 개발자", agent: "codex", mission: "코드 구현, 자동화 검증 및 재사용 스킬 자산화" }
  ];
  defaults.forEach(d => addRoleRow(d.role, d.agent, d.mission));
}

function addRoleRow(roleName="", agentName="claude", missionText="") {
  const container = document.getElementById("team-roles-container");
  const row = document.createElement("div");
  row.className = "role-row";
  const catalog = STATE.teams.role_catalog.length ? STATE.teams.role_catalog : [
    { name: "총괄 기획 팀장(PM)", default_agent: "agy", mission: "팀 전체 업무 기획 및 최종 검수" },
    { name: "수석 리서처", default_agent: "claude", mission: "심층 자료 조사 및 핵심 요약" },
    { name: "수석 개발자", default_agent: "codex", mission: "클린 코드 구현 및 테스트" },
    { name: "수석 UI/UX 디자이너", default_agent: "agy", mission: "UI/UX 설계 및 디자인 토큰 명세" },
    { name: "콘텐츠·문서 작가", default_agent: "claude", mission: "보고서 및 매뉴얼 집필" },
    { name: "품질·보안 검수자(QA)", default_agent: "codex", mission: "품질·보안·이식성 검수" }
  ];

  const chosenRole = roleName || catalog[0].name;
  const optionsHtml = catalog.map(r => `<option value="${r.name}" ${r.name === chosenRole ? 'selected' : ''}>${r.name}</option>`).join("");
  const agents = ["agy", "claude", "codex", "opencode", "gemini"];
  const agentHtml = agents.map(a => `<option value="${a}" ${a === agentName ? 'selected' : ''}>${a}</option>`).join("");

  row.innerHTML = `
    <select class="r-name" onchange="onRowRoleChange(this)">${optionsHtml}</select>
    <select class="r-agent">${agentHtml}</select>
    <input type="text" class="r-mission" value="${missionText || catalog[0].mission}" placeholder="상세 임무">
    <button class="btn danger sm" onclick="this.parentElement.remove()">✕</button>
  `;
  container.appendChild(row);
}

function onRowRoleChange(sel) {
  const row = sel.parentElement;
  const found = STATE.teams.role_catalog.find(r => r.name === sel.value);
  if (found) {
    row.querySelector(".r-agent").value = found.default_agent;
    row.querySelector(".r-mission").value = found.mission;
  }
}

function renderTeams() {
  initRoleRowsIfNeeded();

  // Populate assign-role-select
  const sel = document.getElementById("assign-role-select");
  if (!sel.options.length && STATE.teams.role_catalog.length) {
    STATE.teams.role_catalog.forEach(r => {
      const opt = document.createElement("option");
      opt.value = r.name;
      opt.textContent = r.name;
      sel.appendChild(opt);
    });
    onAssignPresetChange();
  }

  // Live panes
  const lpBox = document.getElementById("live-panes-box");
  if (STATE.teams.live_panes && STATE.teams.live_panes.length) {
    const chips = STATE.teams.live_panes.map(p => {
      const label = p.label ? `${p.pane_id} (${p.label})` : `${p.pane_id} [${p.agent || 'shell'}]`;
      return `<button class="btn secondary sm" onclick="selectPane('${p.pane_id}')">🖥️ ${label}</button>`;
    }).join(" ");
    lpBox.innerHTML = `<div style="margin-bottom:8px; font-size:0.85rem; color:var(--muted);">실시간 Herdr 창 클릭 시 위 입력칸에 자동 선택됩니다:</div><div style="display:flex; gap:8px; flex-wrap:wrap;">${chips}</div>`;
  } else {
    lpBox.innerHTML = "";
  }

  const tBox = document.getElementById("local-teams-list");
  if (!STATE.teams.local_teams.length) {
    tBox.innerHTML = `<div class="empty-state" style="grid-column:1/-1;">생성된 부서(Team)가 없습니다 (순수 초기 상태).<br>좌측 상단에서 부서 이름과 직책을 선택해 [🚀 부서 폴더 + Herdr 워크스페이스 생성]을 눌러보세요!</div>`;
    return;
  }
  tBox.innerHTML = "";
  STATE.teams.local_teams.forEach(t => {
    const membersHtml = t.members.map(m => `
      <div style="font-size:0.82rem; padding:6px 8px; background:#0d1322; border-radius:6px; margin-top:6px;">
        <b>[${m.pane_id || m.folder}] ${m.role_name}</b> <span class="badge">${m.agent}</span>
        <div style="color:var(--muted); margin-top:2px;">${m.mission || ''}</div>
      </div>
    `).join("");

    const div = document.createElement("div");
    div.className = "item-box";
    div.innerHTML = `
      <div>
        <h3><span>🏢 ${t.name}</span> <span style="font-size:0.76rem; color:var(--muted);">직원 ${t.members.length}명</span></h3>
        <div style="margin-top:8px;">${membersHtml || '<p>배정된 직원이 없습니다.</p>'}</div>
      </div>
      <div style="display:flex; gap:8px; margin-top:10px;">
        <button class="btn secondary sm" onclick="openTeamMemory('${t.id}')">📋 팀 기억장 편집</button>
        <button class="btn danger sm" onclick="deleteTeam('${t.id}')">🗑️ 부서 삭제</button>
      </div>
    `;
    tBox.appendChild(div);
  });
}

function selectPane(paneId) {
  document.getElementById("assign-pane-id").value = paneId;
  showToast(`창 [${paneId}] 선택됨`);
}

function onAssignPresetChange() {
  const val = document.getElementById("assign-role-select").value;
  const found = STATE.teams.role_catalog.find(r => r.name === val);
  if (found) {
    document.getElementById("assign-agent-select").value = found.default_agent;
    document.getElementById("assign-mission-input").value = found.mission;
  }
}

async function createTeam() {
  const name = document.getElementById("new-team-name").value.trim();
  if (!name) { showToast("부서 이름을 입력해 주세요.", true); return; }
  const rows = document.querySelectorAll("#team-roles-container .role-row");
  const roles = [];
  rows.forEach(r => {
    roles.push({
      role: r.querySelector(".r-name").value,
      agent: r.querySelector(".r-agent").value,
      mission: r.querySelector(".r-mission").value
    });
  });
  const launch = document.getElementById("new-team-launch").checked;
  showToast(`[${name}] 부서 및 창 생성 중...`);
  const res = await apiPost("/api/teams/create", { name, roles, launch });
  showToast(res.message, !res.ok);
  await refreshAll();
}

async function assignPaneRole() {
  const pane_id = document.getElementById("assign-pane-id").value.trim();
  const role = document.getElementById("assign-role-select").value;
  const agent = document.getElementById("assign-agent-select").value;
  const mission = document.getElementById("assign-mission-input").value.trim();
  if (!pane_id) { showToast("대상 창 ID(예: w1:p2)를 입력해 주세요.", true); return; }
  const res = await apiPost("/api/teams/assign", { pane_id, role, agent, mission });
  showToast(res.message, !res.ok);
  await refreshAll();
}

async function sendPanePrompt() {
  const pane_id = document.getElementById("assign-pane-id").value.trim();
  const prompt = document.getElementById("prompt-text-input").value.trim();
  if (!pane_id || !prompt) { showToast("창 ID와 지시 내용을 모두 입력해 주세요.", true); return; }
  const res = await apiPost("/api/teams/prompt", { pane_id, prompt });
  showToast(res.message, !res.ok);
  if (res.ok) document.getElementById("prompt-text-input").value = "";
}

async function deleteTeam(id) {
  if (!confirm(`정말 [${id}] 부서 폴더를 삭제하시겠습니까?`)) return;
  const res = await apiPost("/api/teams/delete", { id });
  showToast(res.message, !res.ok);
  await refreshAll();
}

function renderMemory() {
  const tmBtns = document.getElementById("team-memory-buttons");
  tmBtns.innerHTML = "";
  (STATE.memory.team_memories || []).forEach(tm => {
    const b = document.createElement("button");
    b.className = "btn secondary sm";
    b.textContent = `📋 [${tm.team_id}] TEAM_MEMORY.md`;
    b.onclick = () => loadTeamMemoryEditor(tm.team_id);
    tmBtns.appendChild(b);
  });
  loadMemoryEditor(STATE.currentMemoryDoc, true);
}

function loadMemoryEditor(docType, silent=false) {
  STATE.currentMemoryDoc = docType;
  const label = document.getElementById("memory-editor-label");
  const area = document.getElementById("memory-editor-textarea");
  if (docType === "user_profile") {
    label.textContent = `현재 편집 중인 문서: ./memory/USER_PROFILE.md ${STATE.memory.user_profile?.exists ? '(존재함)' : '(미생성 - 순수 초기 상태)'}`;
    area.value = STATE.memory.user_profile?.content || "";
  } else if (docType === "company_memory") {
    label.textContent = `현재 편집 중인 문서: ./memory/COMPANY_MEMORY.md ${STATE.memory.company_memory?.exists ? '(존재함)' : '(미생성 - 순수 초기 상태)'}`;
    area.value = STATE.memory.company_memory?.content || "";
  } else if (docType === "agents_md") {
    label.textContent = `현재 편집 중인 문서: ./AGENTS.md (전사 헌법)`;
    area.value = STATE.memory.agents_md?.content || "";
  } else if (docType === "team_memory") {
    const found = (STATE.memory.team_memories || []).find(x => x.team_id === STATE.currentTeamMemoryId);
    label.textContent = `현재 편집 중인 문서: ./teams/${STATE.currentTeamMemoryId}/TEAM_MEMORY.md`;
    area.value = found ? found.content : "";
  }
  if (!silent) showToast(`문서를 불러왔습니다.`);
}

function loadTeamMemoryEditor(teamId) {
  STATE.currentTeamMemoryId = teamId;
  loadMemoryEditor("team_memory");
}

function openTeamMemory(teamId) {
  STATE.currentTeamMemoryId = teamId;
  switchTab("memory", document.querySelectorAll(".tab-btn")[2]);
  loadMemoryEditor("team_memory");
}

async function saveMemoryEditor() {
  const content = document.getElementById("memory-editor-textarea").value;
  const res = await apiPost("/api/memory/save", {
    doc_type: STATE.currentMemoryDoc,
    team_id: STATE.currentTeamMemoryId,
    content
  });
  showToast(res.message, !res.ok);
  await refreshAll();
}

async function initDefaultMemory() {
  const res = await apiPost("/api/memory/init", {});
  showToast(res.message, !res.ok);
  await refreshAll();
}

async function deleteCurrentMemoryDoc() {
  if (STATE.currentMemoryDoc !== "user_profile" && STATE.currentMemoryDoc !== "company_memory") {
    showToast("USER_PROFILE.md 또는 COMPANY_MEMORY.md만 초기화할 수 있습니다.", true);
    return;
  }
  if (!confirm("선택한 기억장 문서를 삭제(초기화)하시겠습니까?")) return;
  const res = await apiPost("/api/memory/delete", { doc_type: STATE.currentMemoryDoc });
  showToast(res.message, !res.ok);
  await refreshAll();
}

function renderMessenger() {
  const e = STATE.env || {};
  document.getElementById("env-enabled").value = e.ENABLED_MESSENGERS || "";
  document.getElementById("env-tg-token").value = e.TELEGRAM_BOT_TOKEN || "";
  document.getElementById("env-tg-chat").value = e.TELEGRAM_ALLOWED_CHAT_ID || e.TELEGRAM_ALLOWED_CHAT_IDS || "";
  document.getElementById("env-slack-token").value = e.SLACK_BOT_TOKEN || "";
  document.getElementById("env-slack-channel").value = e.SLACK_CHANNEL_ID || "";
  document.getElementById("env-slack-webhook").value = e.SLACK_WEBHOOK_URL || "";
  document.getElementById("env-discord-token").value = e.DISCORD_BOT_TOKEN || "";
  document.getElementById("env-discord-channel").value = e.DISCORD_CHANNEL_ID || "";
  document.getElementById("env-discord-webhook").value = e.DISCORD_WEBHOOK_URL || "";
}

async function saveMessengerEnv() {
  const body = {
    ENABLED_MESSENGERS: document.getElementById("env-enabled").value.trim(),
    TELEGRAM_BOT_TOKEN: document.getElementById("env-tg-token").value.trim(),
    TELEGRAM_ALLOWED_CHAT_ID: document.getElementById("env-tg-chat").value.trim(),
    TELEGRAM_ALLOWED_CHAT_IDS: document.getElementById("env-tg-chat").value.trim(),
    SLACK_BOT_TOKEN: document.getElementById("env-slack-token").value.trim(),
    SLACK_CHANNEL_ID: document.getElementById("env-slack-channel").value.trim(),
    SLACK_WEBHOOK_URL: document.getElementById("env-slack-webhook").value.trim(),
    DISCORD_BOT_TOKEN: document.getElementById("env-discord-token").value.trim(),
    DISCORD_CHANNEL_ID: document.getElementById("env-discord-channel").value.trim(),
    DISCORD_WEBHOOK_URL: document.getElementById("env-discord-webhook").value.trim(),
  };
  const res = await apiPost("/api/messenger/save", body);
  showToast(res.message, !res.ok);
  await refreshAll();
}

function togglePasswordVisibility() {
  ["env-tg-token", "env-slack-token", "env-discord-token"].forEach(id => {
    const el = document.getElementById(id);
    el.type = el.type === "password" ? "text" : "password";
  });
}

async function confirmReset() {
  const resetEnv = document.getElementById("reset-env-check")?.checked || false;
  if (!confirm("모든 런타임 부서(teams/*), 장착된 스킬(skills/*), 기억장(USER_PROFILE.md, COMPANY_MEMORY.md)을 비우고 처음 클론했을 때의 순수 초기 상태(Clean State)로 리셋하시겠습니까?")) return;
  const res = await apiPost("/api/reset", { reset_env: resetEnv });
  showToast(res.message, !res.ok);
  await refreshAll();
}

window.addEventListener("DOMContentLoaded", refreshAll);
</script>
</body>
</html>
"""


def capture_doctor_text(herdr_os_mod: Any) -> str:
    """Capture `cmd_doctor` stdout into a string for display in the Web UI."""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            herdr_os_mod.cmd_doctor(None)
    except Exception as exc:
        buf.write(f"\n진단 중 오류: {exc}")
    return buf.getvalue()


def run_web_ui(herdr_os_mod: Any, port: int = 8765, open_browser: bool = True) -> int:
    """Start the Hermes-style local Web Control Console UI."""
    ensure_clean_gitkeep_dirs()

    class ControlHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return  # Keep terminal output clean

        def _send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _read_json(self) -> Dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length <= 0:
                return {}
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            try:
                return json.loads(raw)
            except Exception:
                return {}

        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path in ("/", "/index.html"):
                raw = DASHBOARD_HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return

            if parsed.path == "/api/state":
                env_data = herdr_os_mod.load_env_file(ENV_FILE)
                self._send_json(
                    {
                        "ok": True,
                        "skills": list_skill_catalog_and_installed(herdr_os_mod),
                        "teams": list_teams_and_live_panes(herdr_os_mod),
                        "memory": get_memory_state(),
                        "env": env_data,
                        "doctor_text": capture_doctor_text(herdr_os_mod),
                    }
                )
                return

            self._send_json({"ok": False, "message": "Not Found"}, status=404)

        def do_POST(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            body = self._read_json()

            if parsed.path == "/api/skills/install":
                ok, msg = install_skill_from_template(herdr_os_mod, str(body.get("id", "")))
                self._send_json({"ok": ok, "message": msg})
                return

            if parsed.path == "/api/skills/save":
                ok, msg = save_skill(
                    herdr_os_mod,
                    str(body.get("id", "")),
                    str(body.get("description", "")),
                    str(body.get("content", "")),
                )
                self._send_json({"ok": ok, "message": msg})
                return

            if parsed.path == "/api/skills/delete":
                ok, msg = delete_skill(herdr_os_mod, str(body.get("id", "")))
                self._send_json({"ok": ok, "message": msg})
                return

            if parsed.path == "/api/teams/create":
                t_name = str(body.get("name", "")).strip() or "메인본부"
                raw_roles = body.get("roles", [])
                role_tuples: List[Tuple[str, str, str]] = []
                for r in raw_roles:
                    if isinstance(r, dict):
                        role_tuples.append(
                            (
                                str(r.get("role", "팀원")).strip(),
                                str(r.get("agent", "claude")).strip(),
                                str(r.get("mission", "")).strip(),
                            )
                        )
                launch = bool(body.get("launch", False))
                ws_id = herdr_os_mod.create_team(
                    team_name=t_name,
                    launch_agents=launch,
                    role_items_override=role_tuples if role_tuples else None,
                )
                msg = (
                    f"부서 [{t_name}] 및 Herdr 워크스페이스({ws_id}) 생성 완료!"
                    if ws_id
                    else f"부서 [{t_name}] 로컬 폴더 및 지침서 생성 완료!"
                )
                self._send_json({"ok": True, "message": msg})
                return

            if parsed.path == "/api/teams/assign":
                pane_id = str(body.get("pane_id", "")).strip()
                role = str(body.get("role", "리서처")).strip()
                agent = str(body.get("agent", "claude")).strip()
                mission = str(body.get("mission", "")).strip()
                if not pane_id:
                    self._send_json({"ok": False, "message": "창 ID를 입력해 주세요."})
                    return
                herdr_os_mod.assign_employee_to_pane(
                    pane_id=pane_id, role_name=role, agent_name=agent, mission=mission
                )
                self._send_json(
                    {"ok": True, "message": f"창 [{pane_id}] -> {role} ({agent}) 배정 완료!"}
                )
                return

            if parsed.path == "/api/teams/prompt":
                pane_id = str(body.get("pane_id", "")).strip()
                prompt = str(body.get("prompt", "")).strip()
                rc, out, err = herdr_os_mod.run_herdr(["pane", "run", pane_id, prompt])
                if rc == 0:
                    self._send_json(
                        {"ok": True, "message": f"[{pane_id}] 창에 업무 지시를 전송했습니다."}
                    )
                else:
                    self._send_json(
                        {"ok": False, "message": f"전송 실패 (Herdr 연결 확인): {err or out}"}
                    )
                return

            if parsed.path == "/api/teams/delete":
                ok, msg = delete_team_folder(herdr_os_mod, str(body.get("id", "")))
                self._send_json({"ok": ok, "message": msg})
                return

            if parsed.path == "/api/memory/save":
                ok, msg = save_memory_doc(
                    herdr_os_mod,
                    str(body.get("doc_type", "")),
                    str(body.get("content", "")),
                    str(body.get("team_id", "")),
                )
                self._send_json({"ok": ok, "message": msg})
                return

            if parsed.path == "/api/memory/init":
                herdr_os_mod.generate_user_profile_and_memory(
                    owner_name="사장님",
                    preferred_lang="한국어",
                    work_style="비개발자도 직관적으로 이해할 수 있도록 비유와 핵심 요약 표를 사용해 명확하고 친절하게 설명",
                    overwrite_profile=False,
                )
                self._send_json(
                    {
                        "ok": True,
                        "message": "기본 USER_PROFILE.md 및 COMPANY_MEMORY.md 생성 완료!",
                    }
                )
                return

            if parsed.path == "/api/memory/delete":
                ok, msg = delete_memory_doc(str(body.get("doc_type", "")))
                self._send_json({"ok": ok, "message": msg})
                return

            if parsed.path == "/api/messenger/save":
                env_vars = herdr_os_mod.load_env_file(ENV_FILE)
                for k, v in body.items():
                    env_vars[str(k)] = str(v)
                herdr_os_mod.save_env_file(env_vars, ENV_FILE)
                self._send_json({"ok": True, "message": ".env 멀티 메신저 설정 저장 완료!"})
                return

            if parsed.path == "/api/reset":
                reset_env = bool(body.get("reset_env", False))
                res = reset_to_clean_state(reset_env=reset_env)
                self._send_json(
                    {
                        "ok": True,
                        "message": (
                            f"순수 초기 상태(Clean State) 리셋 완료! "
                            f"(팀 {len(res['removed_teams'])}개, 스킬 {len(res['removed_skills'])}개, "
                            f"기억파일 {len(res['removed_memories'])}개 정리됨)"
                        ),
                    }
                )
                return

            self._send_json({"ok": False, "message": "Unknown API endpoint"}, status=404)

    # Find an available port starting from `port`
    actual_port = port
    for candidate in range(port, port + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", candidate)) != 0:
                actual_port = candidate
                break

    url = f"http://127.0.0.1:{actual_port}"
    server = HTTPServer(("127.0.0.1", actual_port), ControlHandler)
    print("=" * 68)
    print(f"🌐 Herdr × Hermes 웹 관리 콘솔 UI가 시작되었습니다!")
    print(f"👉 브라우저 주소: {url}")
    print("   (종료하려면 Ctrl+C 를 누르세요)")
    print("=" * 68)

    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 웹 관리 콘솔 UI가 종료되었습니다.")
    finally:
        server.server_close()
    return 0


# =====================================================================
# Interactive Terminal Menu (TUI: Arrow Keys ↑/↓ + Number Selection)
# =====================================================================

def select_menu_option(title: str, options: List[str], subtitle: str = "") -> int:
    """
    Interactive menu selector supporting BOTH:
    - Arrow keys (↑/↓ + Enter) when running in an interactive Windows/Unix console
    - Direct number key press (1..N, or 0/q to go back)
    - Standard `input()` line fallback when stdin is not a tty
    Returns 0-based index of chosen option, or -1 if cancelled/exit.
    """
    if not sys.stdin.isatty():
        print(f"\n{title}")
        if subtitle:
            print(f"  {subtitle}")
        for idx, opt in enumerate(options, start=1):
            print(f"  [{idx}] {opt}")
        print("  [0] 돌아가기 / 종료")
        ans = input("번호 선택: ").strip()
        if not ans or ans in ("0", "q", "exit"):
            return -1
        try:
            v = int(ans)
            return v - 1 if 1 <= v <= len(options) else -1
        except ValueError:
            return -1

    # Interactive console with arrow-key support on Windows (msvcrt) or fallback prompt
    if os.name == "nt":
        try:
            import msvcrt

            idx = 0
            while True:
                os.system("cls")
                print("=" * 68)
                print(f"🧠 {title}")
                if subtitle:
                    print(f"   {subtitle}")
                print("=" * 68)
                print("  (방향키 ↑/↓ 이동 후 Enter, 또는 숫자 번호 입력 / 종료: 0 또는 Q)\n")
                for i, opt in enumerate(options):
                    prefix = " 👉 " if i == idx else "    "
                    hilite = f"[{i + 1}] {opt}"
                    print(f"{prefix}{hilite}")
                print("\n    [0] 종료 / 이전 메뉴로")
                print("=" * 68)

                ch = msvcrt.getwch()
                if ch in ("\r", "\n"):
                    return idx
                if ch in ("0", "q", "Q", "\x1b"):
                    return -1
                if ch.isdigit():
                    num = int(ch)
                    if 1 <= num <= len(options):
                        return num - 1
                if ch in ("\x00", "\xe0"):
                    ch2 = msvcrt.getwch()
                    if ch2 == "H":  # Up arrow
                        idx = (idx - 1) % len(options)
                    elif ch2 == "P":  # Down arrow
                        idx = (idx + 1) % len(options)
        except Exception:
            pass

    # Fallback interactive number prompt
    print("\n" + "=" * 68)
    print(f"🧠 {title}")
    if subtitle:
        print(f"   {subtitle}")
    print("=" * 68)
    for i, opt in enumerate(options, start=1):
        print(f"  [{i}] {opt}")
    print("  [0] 종료 / 이전 메뉴로")
    print("=" * 68)
    ans = herdr_prompt("번호를 선택하세요", "1")
    if ans.lower() in ("0", "q", "quit", "exit"):
        return -1
    try:
        v = int(ans)
        if 1 <= v <= len(options):
            return v - 1
    except ValueError:
        pass
    return -1


def herdr_prompt(question: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        ans = input(f"{question}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    return ans if ans else default


def pause_enter() -> None:
    if sys.stdin.isatty():
        try:
            input("\n[Enter 키를 누르면 메뉴로 돌아갑니다...]")
        except (EOFError, KeyboardInterrupt):
            pass


def run_tui_menu(herdr_os_mod: Any) -> int:
    """Run the interactive Hermes TUI menu loop."""
    ensure_clean_gitkeep_dirs()

    while True:
        state_skills = list_skill_catalog_and_installed(herdr_os_mod)
        state_teams = list_teams_and_live_panes(herdr_os_mod)
        state_mem = get_memory_state()
        subtitle = (
            f"장착 스킬: {len(state_skills['installed'])}개 | "
            f"부서: {len(state_teams['local_teams'])}개 | "
            f"프로필: {'등록됨' if state_mem['user_profile']['exists'] else '초기상태(미등록)'}"
        )
        main_options = [
            "🌐 웹 관리 콘솔 UI 열기 (브라우저에서 클릭으로 스킬/팀/기억/메신저 관리)",
            "📚 스킬(Skills) 관리 (카탈로그 원클릭 장착 / 새 스킬 생성 / 삭제)",
            "🏢 팀 & 직원(Teams & Roles) 관리 (부서 생성 / 창 직책 배정 / 업무 지시 / 삭제)",
            "🧠 기억장(Memory) 관리 (프로필·전사기억 조회 / 생성 / 메모 추가 / 초기화)",
            "💬 멀티 메신저(Telegram/Slack/Discord) 설정 및 게이트웨이 실행",
            "🩺 시스템 전체 진단 (doctor) & 온보딩 마법사 (setup)",
            "🔄 순수 초기 상태(Clean State)로 전체 리셋 (reset)",
        ]
        choice = select_menu_option(
            "Herdr × Hermes AgenticOS 통합 제어 메뉴 (TUI)", main_options, subtitle
        )
        if choice == -1:
            print("👋 통합 제어 메뉴를 종료합니다.")
            return 0

        if choice == 0:
            return run_web_ui(herdr_os_mod, port=8765, open_browser=True)

        if choice == 1:
            _tui_skills_submenu(herdr_os_mod)
        elif choice == 2:
            _tui_teams_submenu(herdr_os_mod)
        elif choice == 3:
            _tui_memory_submenu(herdr_os_mod)
        elif choice == 4:
            _tui_messenger_submenu(herdr_os_mod)
        elif choice == 5:
            herdr_os_mod.cmd_doctor(None)
            if herdr_os_mod.prompt_yes_no("\n대화형 온보딩 마법사(setup)도 이어서 실행할까요?", False):
                herdr_os_mod.cmd_setup(None)
            pause_enter()
        elif choice == 6:
            if herdr_os_mod.prompt_yes_no(
                "⚠️ 모든 런타임 부서(teams/*), 장착 스킬(skills/*), 기억장을 비우고 순수 초기 상태로 리셋할까요?",
                False,
            ):
                res = reset_to_clean_state(reset_env=False)
                print(
                    f"✅ 순수 초기 상태(Clean State) 리셋 완료! "
                    f"(팀 {len(res['removed_teams'])}개, 스킬 {len(res['removed_skills'])}개, 기억 {len(res['removed_memories'])}개 초기화)"
                )
            pause_enter()


def _tui_skills_submenu(herdr_os_mod: Any) -> None:
    while True:
        data = list_skill_catalog_and_installed(herdr_os_mod)
        opts = [
            f"📥 카탈로그에서 기본 스킬 장착하기 (보유 템플릿 {len(data['catalog'])}종)",
            f"📋 현재 장착된 스킬 목록 보기 ({len(data['installed'])}개)",
            "➕ 새 맞춤 스킬(SKILL.md) 직접 추가하기",
            "🗑️ 장착된 스킬 삭제하기",
        ]
        c = select_menu_option("📚 스킬(Skills) 관리", opts)
        if c == -1:
            return
        if c == 0:
            print("\n📦 [기본 제공 스킬 카탈로그]")
            for idx, item in enumerate(data["catalog"], start=1):
                status = "✅ 장착됨" if item["installed"] else "⚪ 미장착"
                print(f"  {idx}. {item['id']} [{status}] - {item['description']}")
            print(f"  {len(data['catalog']) + 1}. 전체 기본 스킬 일괄 장착")
            pick = herdr_prompt("장착할 스킬 번호를 입력하세요 (취소: 0)", "0")
            try:
                p_idx = int(pick)
                if 1 <= p_idx <= len(data["catalog"]):
                    ok, msg = install_skill_from_template(
                        herdr_os_mod, data["catalog"][p_idx - 1]["id"]
                    )
                    print(f"  -> {msg}")
                elif p_idx == len(data["catalog"]) + 1:
                    for item in data["catalog"]:
                        ok, msg = install_skill_from_template(herdr_os_mod, item["id"])
                        print(f"  -> {msg}")
            except ValueError:
                pass
            pause_enter()
        elif c == 1:
            herdr_os_mod.cmd_skill_list(None)
            pause_enter()
        elif c == 2:
            s_id = herdr_prompt("새 스킬 ID (예: youtube-script-sop)")
            if s_id:
                s_desc = herdr_prompt("스킬 한 줄 설명", f"{s_id} 표준 작업 절차")
                ok, msg = save_skill(herdr_os_mod, s_id, s_desc)
                print(f"  -> {msg}")
            pause_enter()
        elif c == 3:
            if not data["installed"]:
                print("\n⚠️ 현재 장착된 스킬이 없습니다.")
            else:
                for idx, item in enumerate(data["installed"], start=1):
                    print(f"  {idx}. {item['id']} ({item['description']})")
                pick = herdr_prompt("삭제할 스킬 번호 (취소: 0)", "0")
                try:
                    p_idx = int(pick)
                    if 1 <= p_idx <= len(data["installed"]):
                        ok, msg = delete_skill(herdr_os_mod, data["installed"][p_idx - 1]["id"])
                        print(f"  -> {msg}")
                except ValueError:
                    pass
            pause_enter()


def _tui_teams_submenu(herdr_os_mod: Any) -> None:
    while True:
        data = list_teams_and_live_panes(herdr_os_mod)
        opts = [
            f"🏢 전체 부서 및 실시간 Herdr 창 현황 보기 (부서 {len(data['local_teams'])}개)",
            "➕ 새 부서(Team) 및 직책별 AI 직원 책상(p1, p2, p3...) 생성",
            "🪪 특정 창(예: w1:p2)에 6대 표준 직책 프리셋 배정",
            "📨 특정 창(예: w1:p2)의 직원에게 업무 지시(Prompt) 보내기",
            "🗑️ 부서 폴더 삭제하기",
        ]
        c = select_menu_option("🏢 팀 & 직원(Teams & Roles) 관리", opts)
        if c == -1:
            return
        if c == 0:
            herdr_os_mod.cmd_team_list(None)
            pause_enter()
        elif c == 1:
            t_name = herdr_prompt("생성할 부서 이름 (예: 메인본부, 마케팅팀)", "메인본부")
            roles_override = herdr_os_mod.interactive_pick_roles(t_name)
            launch = herdr_os_mod.prompt_yes_no("각 창에 AI CLI를 즉시 실행할까요?", False)
            herdr_os_mod.create_team(
                team_name=t_name, launch_agents=launch, role_items_override=roles_override
            )
            pause_enter()
        elif c == 2:
            pane_id = herdr_prompt("직책을 배정할 창 ID (예: w1:p1, w1:p2)", "w1:p2")
            print("\n  [표준 직책 프리셋]")
            for idx, r in enumerate(ROLE_CATALOG, start=1):
                print(f"    {idx}. {r['name']} (권장 AI: {r['default_agent']}) - {r['mission']}")
            pick = herdr_prompt("직책 번호 선택 (1~6)", "2")
            try:
                r_item = ROLE_CATALOG[max(0, min(len(ROLE_CATALOG) - 1, int(pick) - 1))]
            except ValueError:
                r_item = ROLE_CATALOG[1]
            agent = herdr_prompt(
                "사용할 AI 엔진 (agy/claude/codex/opencode/gemini)", r_item["default_agent"]
            )
            mission = herdr_prompt("핵심 임무", r_item["mission"])
            herdr_os_mod.assign_employee_to_pane(
                pane_id=pane_id, role_name=r_item["name"], agent_name=agent, mission=mission
            )
            pause_enter()
        elif c == 3:
            pane_id = herdr_prompt("업무 지시를 보낼 창 ID (예: w1:p2)", "w1:p2")
            prompt_txt = herdr_prompt("전달할 지시 내용")
            if pane_id and prompt_txt:
                rc, out, err = herdr_os_mod.run_herdr(["pane", "run", pane_id, prompt_txt])
                print("✅ 전송 완료!" if rc == 0 else f"❌ 전송 실패: {err or out}")
            pause_enter()
        elif c == 4:
            if not data["local_teams"]:
                print("\n⚠️ 삭제할 부서 폴더가 없습니다.")
            else:
                for idx, t in enumerate(data["local_teams"], start=1):
                    print(f"  {idx}. {t['name']} (직원 {len(t['members'])}명)")
                pick = herdr_prompt("삭제할 부서 번호 (취소: 0)", "0")
                try:
                    p_idx = int(pick)
                    if 1 <= p_idx <= len(data["local_teams"]):
                        ok, msg = delete_team_folder(
                            herdr_os_mod, data["local_teams"][p_idx - 1]["id"]
                        )
                        print(f"  -> {msg}")
                except ValueError:
                    pass
            pause_enter()


def _tui_memory_submenu(herdr_os_mod: Any) -> None:
    while True:
        mem = get_memory_state()
        opts = [
            f"👤 사장님 프로필 (USER_PROFILE.md) 보기 [{'존재' if mem['user_profile']['exists'] else '미생성'}]",
            f"🏛️ 전사 공유 기억장 (COMPANY_MEMORY.md) 보기 [{'존재' if mem['company_memory']['exists'] else '미생성'}]",
            "✨ 기본 프로필 및 전사 기억장 설정/생성하기",
            "📝 전사 기억장(COMPANY_MEMORY.md)에 새 한 줄 기록 추가하기",
            "🗑️ 기억장 파일 초기화(삭제)하기",
        ]
        c = select_menu_option("🧠 기억장(Memory) 관리", opts)
        if c == -1:
            return
        if c == 0:
            print("\n" + "=" * 68)
            print(
                mem["user_profile"]["content"]
                or "(아직 USER_PROFILE.md가 생성되지 않은 순수 초기 상태입니다.)"
            )
            print("=" * 68)
            pause_enter()
        elif c == 1:
            print("\n" + "=" * 68)
            print(
                mem["company_memory"]["content"]
                or "(아직 COMPANY_MEMORY.md가 생성되지 않은 순수 초기 상태입니다.)"
            )
            print("=" * 68)
            pause_enter()
        elif c == 2:
            owner = herdr_prompt("사용자 호칭", "사장님")
            lang = herdr_prompt("기본 언어", "한국어")
            style = herdr_prompt(
                "업무 및 보고 스타일",
                "비개발자도 직관적으로 이해할 수 있도록 비유와 핵심 요약 표를 사용해 명확하고 친절하게 설명",
            )
            herdr_os_mod.generate_user_profile_and_memory(owner, lang, style, overwrite_profile=True)
            print("✅ USER_PROFILE.md 및 COMPANY_MEMORY.md 설정 완료!")
            pause_enter()
        elif c == 3:
            note = herdr_prompt("COMPANY_MEMORY.md에 기록할 메모 내용")
            if note:
                today = datetime.date.today().isoformat()
                cur = mem["company_memory"]["content"]
                if not cur:
                    herdr_os_mod.generate_user_profile_and_memory(
                        "사장님", "한국어", "핵심 요약 중심", overwrite_profile=False
                    )
                    cur = (MEMORY_DIR / "COMPANY_MEMORY.md").read_text(encoding="utf-8")
                updated = cur.rstrip() + f"\n- **[{today}]** {note}\n"
                save_memory_doc(herdr_os_mod, "company_memory", updated)
                print("✅ 전사 기억장에 기록되었습니다.")
            pause_enter()
        elif c == 4:
            if herdr_os_mod.prompt_yes_no(
                "USER_PROFILE.md와 COMPANY_MEMORY.md를 삭제하여 초기 상태로 되돌릴까요?", False
            ):
                delete_memory_doc("user_profile")
                delete_memory_doc("company_memory")
                print("✅ 기억장 초기화 완료!")
            pause_enter()


def _tui_messenger_submenu(herdr_os_mod: Any) -> None:
    while True:
        env_vars = herdr_os_mod.load_env_file(ENV_FILE)
        enabled = env_vars.get("ENABLED_MESSENGERS", "미설정")
        opts = [
            f"📋 현재 메신저 연동 설정 확인 (활성: {enabled})",
            "✈️ Telegram 봇 토큰 및 Chat ID 설정/수정",
            "💼 Slack 봇 토큰 및 채널 ID 설정/수정",
            "🎮 Discord 봇 토큰 및 채널 ID 설정/수정",
            "🚀 멀티 메신저 게이트웨이 데몬 시작 (gateway start)",
        ]
        c = select_menu_option("💬 멀티 메신저(Telegram/Slack/Discord) 관리", opts)
        if c == -1:
            return
        if c == 0:
            print("\n" + "=" * 68)
            for k in (
                "ENABLED_MESSENGERS",
                "TELEGRAM_BOT_TOKEN",
                "TELEGRAM_ALLOWED_CHAT_ID",
                "SLACK_BOT_TOKEN",
                "SLACK_CHANNEL_ID",
                "DISCORD_BOT_TOKEN",
                "DISCORD_CHANNEL_ID",
            ):
                val = env_vars.get(k, "")
                if "TOKEN" in k and val and len(val) > 8:
                    val = val[:4] + "..." + val[-4:]
                print(f"  {k:<28} = {val or '(비어있음)'}")
            print("=" * 68)
            pause_enter()
        elif c == 1:
            env_vars["TELEGRAM_BOT_TOKEN"] = herdr_prompt(
                "TELEGRAM_BOT_TOKEN", env_vars.get("TELEGRAM_BOT_TOKEN", "")
            )
            chat_id = herdr_prompt(
                "TELEGRAM_ALLOWED_CHAT_ID (선택)",
                env_vars.get("TELEGRAM_ALLOWED_CHAT_ID", ""),
            )
            env_vars["TELEGRAM_ALLOWED_CHAT_ID"] = chat_id
            env_vars["TELEGRAM_ALLOWED_CHAT_IDS"] = chat_id
            cur = [x.strip() for x in env_vars.get("ENABLED_MESSENGERS", "").split(",") if x.strip()]
            if env_vars["TELEGRAM_BOT_TOKEN"] and "telegram" not in cur:
                cur.append("telegram")
            env_vars["ENABLED_MESSENGERS"] = ",".join(cur)
            herdr_os_mod.save_env_file(env_vars, ENV_FILE)
            print("✅ Telegram 설정 저장 완료!")
            pause_enter()
        elif c == 2:
            env_vars["SLACK_BOT_TOKEN"] = herdr_prompt(
                "SLACK_BOT_TOKEN (xoxb-...)", env_vars.get("SLACK_BOT_TOKEN", "")
            )
            env_vars["SLACK_CHANNEL_ID"] = herdr_prompt(
                "SLACK_CHANNEL_ID (C0123...)", env_vars.get("SLACK_CHANNEL_ID", "")
            )
            cur = [x.strip() for x in env_vars.get("ENABLED_MESSENGERS", "").split(",") if x.strip()]
            if env_vars["SLACK_BOT_TOKEN"] and "slack" not in cur:
                cur.append("slack")
            env_vars["ENABLED_MESSENGERS"] = ",".join(cur)
            herdr_os_mod.save_env_file(env_vars, ENV_FILE)
            print("✅ Slack 설정 저장 완료!")
            pause_enter()
        elif c == 3:
            env_vars["DISCORD_BOT_TOKEN"] = herdr_prompt(
                "DISCORD_BOT_TOKEN", env_vars.get("DISCORD_BOT_TOKEN", "")
            )
            env_vars["DISCORD_CHANNEL_ID"] = herdr_prompt(
                "DISCORD_CHANNEL_ID", env_vars.get("DISCORD_CHANNEL_ID", "")
            )
            cur = [x.strip() for x in env_vars.get("ENABLED_MESSENGERS", "").split(",") if x.strip()]
            if env_vars["DISCORD_BOT_TOKEN"] and "discord" not in cur:
                cur.append("discord")
            env_vars["ENABLED_MESSENGERS"] = ",".join(cur)
            herdr_os_mod.save_env_file(env_vars, ENV_FILE)
            print("✅ Discord 설정 저장 완료!")
            pause_enter()
        elif c == 4:
            herdr_os_mod.cmd_gateway_start(None)
            pause_enter()
