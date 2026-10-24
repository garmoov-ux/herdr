#!/usr/bin/env python3
"""
Herdr Multi-Messenger Gateway Bridge (Telegram, Slack, Discord)
Pure Python 3 standard library implementation (zero external pip dependencies).

Features:
- Real-time auto-alerting when any Herdr pane transitions to `blocked` or `done`
- Bidirectional command & reply routing across Telegram, Slack, and Discord:
  - /panes : List all workspaces (w1, w2...) and panes (w1:p1, w1:p2...)
  - /newteam <팀이름> [직책1:AI,직책2:AI...] : Create a new team workspace & split panes
  - /assign <pane_id> <직책> <AI종류> <임무> : Assign a role and mission to a specific pane
  - /use <pane_id> : Set the default active target pane
  - /read [pane_id] : Read recent terminal output from a pane
  - /split : Split a new pane to the right
  - /key <pane_id> <enter|esc|...> : Send special keys to a pane
  - Plain text / reply-to-message : Send input directly to the target Herdr pane
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT_DIR / ".env"
STATE_FILE = ROOT_DIR / "gateways" / "state.json"
LEGACY_STATE_FILE = ROOT_DIR / "scripts" / "state.json"

USER_PATH = os.environ.get("PATH", "")
LOCAL_BIN = str(Path.home() / ".local" / "bin")
if LOCAL_BIN not in USER_PATH:
    os.environ["PATH"] = f"{LOCAL_BIN}{os.pathsep}{USER_PATH}"


def load_env() -> dict:
    env = {}
    if ENV_FILE.exists():
        try:
            for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                v = v.strip()
                if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                    v = v[1:-1]
                env[k.strip()] = v
        except Exception as e:
            print(f"[Env Warning] Failed to read {ENV_FILE}: {e}", flush=True)
    return env


def get_config() -> dict:
    env_vars = load_env()

    def _get(key: str, default: str = "") -> str:
        val = os.environ.get(key) or env_vars.get(key, default)
        if val.startswith("YOUR_") and val.endswith("_HERE"):
            return ""
        return val.strip()

    return {
        "telegram_bot_token": _get("TELEGRAM_BOT_TOKEN"),
        "telegram_allowed_chat_id": _get("TELEGRAM_ALLOWED_CHAT_ID"),
        "slack_bot_token": _get("SLACK_BOT_TOKEN"),
        "slack_channel_id": _get("SLACK_CHANNEL_ID"),
        "discord_bot_token": _get("DISCORD_BOT_TOKEN"),
        "discord_channel_id": _get("DISCORD_CHANNEL_ID"),
        "discord_webhook_url": _get("DISCORD_WEBHOOK_URL"),
    }


def load_state() -> dict:
    default_state = {
        "chat_id": None,
        "active_pane": "w1:p2",
        "last_update_id": 0,
        "pane_statuses": {},
        "message_pane_map": {},
        "slack_last_ts": "0",
        "slack_thread_pane_map": {},
        "slack_thread_last_ts": {},
        "discord_last_message_id": None,
        "discord_msg_pane_map": {},
    }
    for candidate in (STATE_FILE, LEGACY_STATE_FILE):
        if candidate.exists():
            try:
                loaded = json.loads(candidate.read_text(encoding="utf-8"))
                default_state.update(loaded)
                return default_state
            except Exception:
                pass
    return default_state


def save_state(state: dict) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[State Warning] Could not save state: {e}", flush=True)


# =====================================================================
# Herdr CLI Helpers
# =====================================================================

def run_herdr(args: list) -> tuple:
    cmd = ["herdr"] + args
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=12,
        )
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except Exception as e:
        return 1, "", str(e)


def get_panes() -> list:
    code, out, _ = run_herdr(["pane", "list"])
    if code != 0 or not out:
        return []
    try:
        return json.loads(out).get("result", {}).get("panes", [])
    except Exception:
        return []


def read_pane_output(pane_id: str, lines: int = 25) -> str:
    code, out, _ = run_herdr(
        ["pane", "read", pane_id, "--source", "recent-unwrapped", "--lines", str(lines)]
    )
    if code != 0 or not out:
        return "(화면 출력 없음)"
    try:
        text = json.loads(out).get("result", {}).get("text", "") or out
    except Exception:
        text = out
    cleaned = "\n".join(line.rstrip() for line in text.splitlines() if line.strip())
    if not cleaned:
        return "(빈 화면)"
    if len(cleaned) > 2500:
        cleaned = "...\n" + cleaned[-2500:]
    return cleaned


def send_to_pane(pane_id: str, text: str) -> tuple:
    code, out, err = run_herdr(["pane", "run", pane_id, text])
    return code == 0, err or out


def send_keys_to_pane(pane_id: str, key_name: str) -> tuple:
    code, out, err = run_herdr(["pane", "send-keys", pane_id, key_name])
    return code == 0, err or out


def status_badge(status: str) -> str:
    mapping = {
        "working": "🟢 작업중(working)",
        "blocked": "🟡 응답대기(blocked)",
        "done": "🔵 완료(done)",
        "idle": "⚪ 대기(idle)",
        "unknown": "⚪ 일반창(shell)",
    }
    return mapping.get(status, f"⚪ {status}")


def html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def ensure_valid_active_pane(state: dict) -> str:
    panes = get_panes()
    pane_ids = [p["pane_id"] for p in panes if "pane_id" in p]
    if pane_ids and state.get("active_pane") not in pane_ids:
        state["active_pane"] = "w1:p2" if "w1:p2" in pane_ids else pane_ids[0]
        save_state(state)
    return state.get("active_pane", "w1:p2")


# =====================================================================
# Team & Role Assignment Actions (/newteam, /assign)
# =====================================================================

def execute_newteam(arg_text: str) -> str:
    """
    Parses `/newteam <팀이름> [직책1:AI,직책2:AI...]` and invokes create_team.py (or herdr_os.py).
    """
    parts = arg_text.strip().split(maxsplit=1)
    team_name = parts[0].strip() if parts else f"신규팀_{int(time.time()) % 1000}"
    roles_spec = parts[1].strip() if len(parts) > 1 else ""

    create_team_script = ROOT_DIR / "scripts" / "create_team.py"
    herdr_os_script = ROOT_DIR / "herdr_os.py"

    cmd = [sys.executable]
    if create_team_script.exists():
        cmd += [str(create_team_script), "--team", team_name]
        if roles_spec:
            cmd += ["--roles", roles_spec]
    elif herdr_os_script.exists():
        cmd += [str(herdr_os_script), "newteam", "--team", team_name]
        if roles_spec:
            cmd += ["--roles", roles_spec]
    else:
        return "❌ create_team.py 또는 herdr_os.py 스크립트를 찾을 수 없습니다."

    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        output = (res.stdout or "") + ("\n" + res.stderr if res.stderr else "")
        return output.strip() or f"✅ [{team_name}] 생성 명령 실행 완료"
    except Exception as e:
        return f"❌ 새 팀 생성 중 오류 발생: {e}"


def execute_assign(arg_text: str) -> str:
    """
    Parses `/assign <pane_id> <직책> <AI종류> <임무>` and assigns a role to the specified pane.
    """
    parts = arg_text.strip().split(maxsplit=3)
    if len(parts) < 3:
        return (
            "⚠️ 사용법: `/assign <창ID> <직책> <AI종류> [임무설명]`\n"
            "예시: `/assign w1:p2 백엔드개발 claude API 서버 엔드포인트 구현 및 테스트`"
        )
    pane_id = parts[0].strip()
    role_name = parts[1].strip()
    ai_type = parts[2].strip()
    mission = parts[3].strip() if len(parts) > 3 else f"{role_name} 담당 업무 수행"

    herdr_os_script = ROOT_DIR / "herdr_os.py"
    if herdr_os_script.exists():
        try:
            res = subprocess.run(
                [
                    sys.executable,
                    str(herdr_os_script),
                    "assign",
                    pane_id,
                    role_name,
                    ai_type,
                    mission,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            pass

    # Built-in role assignment & guide generation
    safe_pane = pane_id.replace(":", "_")
    role_dir = ROOT_DIR / "teams" / "assigned" / f"{safe_pane}_{role_name}"
    role_dir.mkdir(parents=True, exist_ok=True)
    guide = (
        f"# 🪪 사원증 및 직무 지침서 ({pane_id} - {role_name})\n\n"
        f"- **창 번호(Pane ID):** `{pane_id}`\n"
        f"- **담당 직책:** {role_name}\n"
        f"- **배정 AI:** {ai_type}\n\n"
        f"## 🎯 핵심 임무\n{mission}\n\n"
        f"## 🧠 전사 규칙 참조\n"
        f"- 전사 헌법: `{ROOT_DIR / 'AGENTS.md'}`\n"
        f"- 사용자 프로필: `{ROOT_DIR / 'memory' / 'USER_PROFILE.md'}`\n"
    )
    for fname in ("ROLE_GUIDE.md", "AGENTS.md", "CLAUDE.md", "GEMINI.md"):
        (role_dir / fname).write_text(guide, encoding="utf-8")

    run_herdr(["pane", "rename", pane_id, f"{role_name}({ai_type})"])
    banner_cmd = f'echo "=== [직무 배정] {pane_id}: {role_name} ({ai_type}) | 임무: {mission} ==="'
    send_to_pane(pane_id, banner_cmd)

    return (
        f"✅ [{pane_id}] 직무 배정 완료!\n"
        f"• 직책: {role_name} ({ai_type})\n"
        f"• 임무: {mission}\n"
        f"• 지침서 폴더: {role_dir}"
    )


# =====================================================================
# Telegram API & Handlers
# =====================================================================

def tg_api(token: str, method: str, payload: dict = None, timeout: int = 15) -> dict:
    if not token:
        return {"ok": False, "error": "No Telegram token"}
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[TG API Error] {method}: {e}", flush=True)
        return {"ok": False, "error": str(e)}


def build_main_keyboard(active_pane: str) -> dict:
    return {
        "keyboard": [
            [{"text": "📋 창 목록 보기"}, {"text": f"📺 현재 창({active_pane}) 화면 보기"}],
            [{"text": "➕ 새 창 나누기(오른쪽)"}, {"text": "❓ 도움말"}],
        ],
        "resize_keyboard": True,
    }


def build_pane_inline_buttons(pane_id: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": f"🎯 {pane_id} 선택", "callback_data": f"use:{pane_id}"},
                {"text": f"📺 {pane_id} 화면 보기", "callback_data": f"read:{pane_id}"},
            ],
            [
                {"text": "⭕ Enter 보내기", "callback_data": f"key:{pane_id}:enter"},
                {"text": "✅ y 입력", "callback_data": f"run:{pane_id}:y"},
                {"text": "❌ Esc(취소)", "callback_data": f"key:{pane_id}:esc"},
            ],
        ]
    }


def tg_send_panes_summary(token: str, chat_id: int, state: dict) -> None:
    panes = get_panes()
    if not panes:
        tg_api(token, "sendMessage", {"chat_id": chat_id, "text": "⚠️ 현재 실행 중인 Herdr 창을 찾을 수 없습니다."})
        return

    active_pane = ensure_valid_active_pane(state)
    lines = ["🖥️ <b>현재 Herdr 전체 팀·창(Pane) 목록</b>\n"]
    inline_rows = []

    for p in panes:
        pid = p.get("pane_id")
        ws = p.get("workspace_id", "w1")
        agent = p.get("agent") or "일반 터미널"
        title = p.get("title") or ""
        label = f"{agent} ({title})" if title and title != agent else agent
        st = status_badge(p.get("agent_status", "unknown"))
        is_target = " 👈 <b>[선택됨]</b>" if pid == active_pane else ""
        lines.append(f"• [<b>{html_escape(ws)}</b>] <code>{html_escape(pid)}</code> | <b>{html_escape(label)}</b> | {st}{is_target}")
        inline_rows.append(
            [
                {"text": f"🎯 {pid} 선택", "callback_data": f"use:{pid}"},
                {"text": f"📺 {pid} 화면 보기", "callback_data": f"read:{pid}"},
            ]
        )

    lines.append(f"\n💬 지금 메시지를 입력하면 <b><code>{html_escape(active_pane)}</code></b> 창으로 바로 전송됩니다!")
    tg_api(
        token,
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": "\n".join(lines),
            "parse_mode": "HTML",
            "reply_markup": {"inline_keyboard": inline_rows},
        },
    )


def tg_send_pane_screen(token: str, chat_id: int, pane_id: str, state: dict) -> None:
    output = read_pane_output(pane_id, lines=30)
    msg = (
        f"📺 <b>[{html_escape(pane_id)}] 최근 터미널 화면 출력</b>\n\n"
        f"<pre>{html_escape(output)}</pre>\n\n"
        f"💡 <i>이 메시지에 '답장'하거나 아래 버튼을 눌러 제어할 수 있습니다.</i>"
    )
    res = tg_api(
        token,
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "HTML",
            "reply_markup": build_pane_inline_buttons(pane_id),
        },
    )
    if res.get("ok"):
        state.setdefault("message_pane_map", {})[str(res["result"]["message_id"])] = pane_id
        save_state(state)


def tg_handle_message(token: str, allowed_chat_id: str, msg: dict, state: dict) -> None:
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    if not chat_id:
        return
    if allowed_chat_id and str(chat_id) != str(allowed_chat_id):
        print(f"[Telegram] Ignored unauthorized chat_id={chat_id}", flush=True)
        return

    text = (msg.get("text") or "").strip()
    first_bind = state.get("chat_id") != chat_id
    state["chat_id"] = chat_id
    active = ensure_valid_active_pane(state)
    save_state(state)

    if first_bind or text in ("/start", "/help", "❓ 도움말"):
        welcome = (
            "🎉 <b>Herdr × Hermes 멀티 메신저 원격 제어 브릿지</b>\n\n"
            f"현재 기본 제어 대상 창: <code>{html_escape(active)}</code>\n\n"
            "<b>[단축 명령어]</b>\n"
            "• <code>/panes</code> : 모든 팀(w1, w2...) 및 창 목록 보기\n"
            "• <code>/newteam 마케팅팀 [직책:AI,...]</code> : 새 부서 워크스페이스 + 직원 창 자동 생성\n"
            "• <code>/assign w1:p2 개발자 claude API구현</code> : 특정 창에 직책·AI·임무 부여\n"
            "• <code>/read w1:p2</code> : 특정 창 화면 읽어오기\n"
            "• <code>/use w1:p2</code> : 기본 입력 창 변경\n"
            "• <code>/split</code> : 현재 팀에 새 창 오른쪽 분할 생성"
        )
        tg_api(
            token,
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": welcome,
                "parse_mode": "HTML",
                "reply_markup": build_main_keyboard(active),
            },
        )
        tg_send_panes_summary(token, chat_id, state)
        return

    if text.startswith("/newteam"):
        arg = text[len("/newteam"):].strip()
        result_text = execute_newteam(arg)
        tg_api(
            token,
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": f"🏢 <b>새 팀 생성 결과:</b>\n<pre>{html_escape(result_text)}</pre>",
                "parse_mode": "HTML",
            },
        )
        tg_send_panes_summary(token, chat_id, state)
        return

    if text.startswith("/assign"):
        arg = text[len("/assign"):].strip()
        result_text = execute_assign(arg)
        tg_api(
            token,
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": f"🪪 <b>직무 배정 결과:</b>\n<pre>{html_escape(result_text)}</pre>",
                "parse_mode": "HTML",
            },
        )
        return

    if text in ("/panes", "📋 창 목록 보기"):
        tg_send_panes_summary(token, chat_id, state)
        return

    if text.startswith("📺 현재 창") or text == "/read":
        tg_send_pane_screen(token, chat_id, active, state)
        return

    if text.startswith("/read "):
        target = text.split(maxsplit=1)[1].strip()
        tg_send_pane_screen(token, chat_id, target, state)
        return

    if text.startswith("/use "):
        target = text.split(maxsplit=1)[1].strip()
        state["active_pane"] = target
        save_state(state)
        tg_api(
            token,
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": f"🎯 기본 제어 창이 <b><code>{html_escape(target)}</code></b> 로 변경되었습니다!",
                "parse_mode": "HTML",
                "reply_markup": build_main_keyboard(target),
            },
        )
        return

    if text in ("/split", "➕ 새 창 나누기(오른쪽)"):
        code, out, err = run_herdr(["pane", "split", "--direction", "right", "--no-focus"])
        if code == 0:
            try:
                new_pane = json.loads(out)["result"]["pane"]["pane_id"]
            except Exception:
                new_pane = "새 창"
            state["active_pane"] = new_pane
            save_state(state)
            tg_api(
                token,
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": f"➕ 새 창 <b><code>{html_escape(new_pane)}</code></b> 생성 완료!",
                    "parse_mode": "HTML",
                    "reply_markup": build_main_keyboard(new_pane),
                },
            )
        else:
            tg_api(token, "sendMessage", {"chat_id": chat_id, "text": f"❌ 창 분할 실패: {err or out}"})
        return

    if not text:
        return

    reply_to = msg.get("reply_to_message", {})
    reply_msg_id = str(reply_to.get("message_id", ""))
    target_pane = state.get("message_pane_map", {}).get(reply_msg_id) or active

    ok, err = send_to_pane(target_pane, text)
    if ok:
        time.sleep(1.2)
        output = read_pane_output(target_pane, lines=20)
        resp_text = (
            f"📨 <b><code>{html_escape(target_pane)}</code> 창에 전송 완료:</b> <code>{html_escape(text)}</code>\n\n"
            f"<pre>{html_escape(output)}</pre>"
        )
        res = tg_api(
            token,
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": resp_text,
                "parse_mode": "HTML",
                "reply_markup": build_pane_inline_buttons(target_pane),
            },
        )
        if res.get("ok"):
            state.setdefault("message_pane_map", {})[str(res["result"]["message_id"])] = target_pane
            save_state(state)
    else:
        tg_api(
            token,
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": f"❌ <code>{html_escape(target_pane)}</code> 전송 실패: {html_escape(err)}",
                "parse_mode": "HTML",
            },
        )


def tg_handle_callback(token: str, allowed_chat_id: str, cb: dict, state: dict) -> None:
    cb_id = cb.get("id")
    data = cb.get("data", "")
    msg = cb.get("message", {})
    chat_id = msg.get("chat", {}).get("id") or state.get("chat_id")
    if allowed_chat_id and str(chat_id) != str(allowed_chat_id):
        return

    if data.startswith("use:"):
        pane_id = data.split(":", 1)[1]
        state["active_pane"] = pane_id
        save_state(state)
        tg_api(token, "answerCallbackQuery", {"callback_query_id": cb_id, "text": f"{pane_id} 선택됨!"})
        tg_api(
            token,
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": f"🎯 기본 제어 창이 <b><code>{html_escape(pane_id)}</code></b> 로 변경되었습니다!",
                "parse_mode": "HTML",
                "reply_markup": build_main_keyboard(pane_id),
            },
        )
    elif data.startswith("read:"):
        pane_id = data.split(":", 1)[1]
        tg_api(token, "answerCallbackQuery", {"callback_query_id": cb_id, "text": f"{pane_id} 화면 불러오는 중..."})
        tg_send_pane_screen(token, chat_id, pane_id, state)
    elif data.startswith("run:"):
        rest = data[len("run:"):]
        pane_id, cmd_text = rest.rsplit(":", 1)
        send_to_pane(pane_id, cmd_text)
        tg_api(token, "answerCallbackQuery", {"callback_query_id": cb_id, "text": f"{pane_id}에 '{cmd_text}' 전송!"})
        time.sleep(1.0)
        tg_send_pane_screen(token, chat_id, pane_id, state)
    elif data.startswith("key:"):
        rest = data[len("key:"):]
        pane_id, key_name = rest.rsplit(":", 1)
        send_keys_to_pane(pane_id, key_name)
        tg_api(token, "answerCallbackQuery", {"callback_query_id": cb_id, "text": f"{pane_id}에 [{key_name}] 키 전송!"})
        time.sleep(1.0)
        tg_send_pane_screen(token, chat_id, pane_id, state)


# =====================================================================
# Shared Text Command Processor for Slack & Discord
# =====================================================================

def format_panes_markdown(state: dict) -> str:
    panes = get_panes()
    if not panes:
        return "⚠️ 현재 실행 중인 Herdr 창을 찾을 수 없습니다."
    active_pane = ensure_valid_active_pane(state)
    lines = ["🖥️ **현재 Herdr 전체 팀·창(Pane) 목록**"]
    for p in panes:
        pid = p.get("pane_id")
        ws = p.get("workspace_id", "w1")
        agent = p.get("agent") or "일반 터미널"
        st = status_badge(p.get("agent_status", "unknown"))
        is_target = " 👈 **[선택됨]**" if pid == active_pane else ""
        lines.append(f"• [{ws}] `{pid}` | **{agent}** | {st}{is_target}")
    lines.append(f"\n💬 현재 기본 입력 창: `{active_pane}` (변경: `/use w1:p2`, 화면보기: `/read w1:p2`)")
    return "\n".join(lines)


def handle_generic_command(text: str, target_pane_override: str, state: dict) -> tuple:
    """
    Processes a command or plain text from Slack or Discord.
    Returns (response_text, associated_pane_id_or_None).
    """
    text = text.strip()
    active = ensure_valid_active_pane(state)

    if text in ("/start", "/help", "❓ 도움말"):
        help_msg = (
            "🎉 **Herdr × Hermes 원격 제어 브릿지**\n"
            f"현재 기본 제어 대상 창: `{active}`\n\n"
            "**[명령어 안내]**\n"
            "• `/panes` : 모든 팀(w1, w2...) 및 창 목록 보기\n"
            "• `/newteam 마케팅팀 [직책:AI,...]` : 새 부서 + 직원 창 자동 생성\n"
            "• `/assign w1:p2 개발자 claude API구현` : 특정 창에 직책·AI·임무 부여\n"
            "• `/read [창ID]` : 특정 창 최근 터미널 화면 출력\n"
            "• `/use <창ID>` : 기본 입력 창 변경\n"
            "• `/split` : 새 창 오른쪽 분할 생성\n"
            "• `/key <창ID> <enter|esc>` : 특수키 전송\n"
            "• 일반 텍스트 또는 알림 메시지에 스레드/답장 입력 : 해당 창에 즉시 명령 전송!"
        )
        return help_msg, active

    if text == "/panes":
        return format_panes_markdown(state), None

    if text.startswith("/newteam"):
        arg = text[len("/newteam"):].strip()
        res = execute_newteam(arg)
        return f"🏢 **새 팀 생성 결과:**\n```\n{res}\n```\n\n{format_panes_markdown(state)}", None

    if text.startswith("/assign"):
        arg = text[len("/assign"):].strip()
        res = execute_assign(arg)
        return f"🪪 **직무 배정 결과:**\n```\n{res}\n```", None

    if text == "/read" or text.startswith("/read "):
        parts = text.split(maxsplit=1)
        pid = parts[1].strip() if len(parts) > 1 else (target_pane_override or active)
        output = read_pane_output(pid, lines=30)
        return f"📺 **[{pid}] 최근 터미널 화면 출력**\n```\n{output}\n```", pid

    if text.startswith("/use "):
        target = text.split(maxsplit=1)[1].strip()
        state["active_pane"] = target
        save_state(state)
        return f"🎯 기본 제어 창이 `{target}` 로 변경되었습니다!", target

    if text == "/split":
        code, out, err = run_herdr(["pane", "split", "--direction", "right", "--no-focus"])
        if code == 0:
            try:
                new_pane = json.loads(out)["result"]["pane"]["pane_id"]
            except Exception:
                new_pane = "새 창"
            state["active_pane"] = new_pane
            save_state(state)
            return f"➕ 새 창 `{new_pane}` 생성 및 선택 완료!", new_pane
        return f"❌ 창 분할 실패: {err or out}", None

    if text.startswith("/key "):
        parts = text.split()
        if len(parts) >= 3:
            pid, key_name = parts[1], parts[2]
            ok, err = send_keys_to_pane(pid, key_name)
            time.sleep(1.0)
            output = read_pane_output(pid, lines=20)
            return f"⌨️ `{pid}` 에 `[{key_name}]` 키 전송 완료:\n```\n{output}\n```", pid
        return "⚠️ 사용법: `/key <창ID> <enter|esc>`", None

    target_pane = target_pane_override or active
    ok, err = send_to_pane(target_pane, text)
    if ok:
        time.sleep(1.2)
        output = read_pane_output(target_pane, lines=20)
        return f"📨 **`{target_pane}` 창에 전송 완료:** `{text}`\n```\n{output}\n```", target_pane
    return f"❌ `{target_pane}` 전송 실패: {err}", target_pane


# =====================================================================
# Slack REST API & Polling
# =====================================================================

def slack_api(token: str, method: str, payload: dict = None, query: dict = None, timeout: int = 12) -> dict:
    if not token:
        return {"ok": False, "error": "No Slack token"}
    url = f"https://slack.com/api/{method}"
    if query:
        url += "?" + urllib.parse.urlencode(query)
    headers = {"Authorization": f"Bearer {token}"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[Slack API Error] {method}: {e}", flush=True)
        return {"ok": False, "error": str(e)}


def slack_post_message(token: str, channel: str, text: str, pane_id: str = None, thread_ts: str = None, state: dict = None) -> None:
    payload = {"channel": channel, "text": text}
    if thread_ts:
        payload["thread_ts"] = thread_ts
    res = slack_api(token, "chat.postMessage", payload=payload)
    if res.get("ok") and state is not None and pane_id:
        msg_ts = res.get("ts")
        root_ts = thread_ts or msg_ts
        if root_ts:
            state.setdefault("slack_thread_pane_map", {})[root_ts] = pane_id
            state.setdefault("slack_thread_last_ts", {})[root_ts] = msg_ts
            save_state(state)


def poll_slack(token: str, channel: str, state: dict) -> None:
    if not token or not channel:
        return

    last_ts = state.get("slack_last_ts", "0")
    res = slack_api(token, "conversations.history", query={"channel": channel, "limit": 15})
    if res.get("ok"):
        messages = res.get("messages", [])
        if last_ts == "0":
            # Initialize cursor to current latest message so old history isn't re-executed
            if messages:
                state["slack_last_ts"] = messages[0].get("ts", "0")
                save_state(state)
        else:
            new_msgs = [m for m in reversed(messages) if float(m.get("ts", "0")) > float(last_ts)]
            for m in new_msgs:
                ts = m.get("ts", "0")
                state["slack_last_ts"] = ts
                save_state(state)
                if m.get("bot_id") or m.get("subtype"):
                    continue
                user_text = (m.get("text") or "").strip()
                if not user_text:
                    continue
                thread_ts = m.get("thread_ts")
                mapped_pane = state.get("slack_thread_pane_map", {}).get(thread_ts) if thread_ts else None
                reply_text, assoc_pane = handle_generic_command(user_text, mapped_pane, state)
                slack_post_message(token, channel, reply_text, pane_id=assoc_pane, thread_ts=thread_ts or ts, state=state)

    # Poll recent tracked threads for replies
    thread_map = state.get("slack_thread_pane_map", {})
    thread_last = state.setdefault("slack_thread_last_ts", {})
    for root_ts in list(thread_map.keys())[-10:]:
        pane_id = thread_map[root_ts]
        t_res = slack_api(token, "conversations.replies", query={"channel": channel, "ts": root_ts, "limit": 10})
        if not t_res.get("ok"):
            continue
        t_msgs = t_res.get("messages", [])
        last_seen = float(thread_last.get(root_ts, root_ts))
        for tm in t_msgs:
            tts = tm.get("ts", "0")
            if float(tts) <= last_seen:
                continue
            thread_last[root_ts] = tts
            save_state(state)
            if tm.get("bot_id") or tm.get("subtype"):
                continue
            user_text = (tm.get("text") or "").strip()
            if not user_text:
                continue
            reply_text, assoc_pane = handle_generic_command(user_text, pane_id, state)
            slack_post_message(token, channel, reply_text, pane_id=assoc_pane or pane_id, thread_ts=root_ts, state=state)


# =====================================================================
# Discord REST API & Polling
# =====================================================================

def discord_api(token: str, method: str, path: str, payload: dict = None, timeout: int = 12):
    url = f"https://discord.com/api/v10{path}"
    headers = {
        "Authorization": f"Bot {token}",
        "User-Agent": "HerdrMessengerBridge (https://github.com/herdr, 1.0)",
    }
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except Exception as e:
        print(f"[Discord API Error] {method} {path}: {e}", flush=True)
        return None


def discord_send_message(token: str, channel_id: str, webhook_url: str, content: str, pane_id: str = None, reply_to_id: str = None, state: dict = None) -> None:
    if len(content) > 1950:
        content = content[:1950] + "\n..."

    if token and channel_id:
        payload = {"content": content}
        if reply_to_id:
            payload["message_reference"] = {"message_id": reply_to_id}
        res = discord_api(token, "POST", f"/channels/{channel_id}/messages", payload=payload)
        if isinstance(res, dict) and res.get("id") and state is not None and pane_id:
            state.setdefault("discord_msg_pane_map", {})[str(res["id"])] = pane_id
            save_state(state)
    elif webhook_url:
        data = json.dumps({"content": content}).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "HerdrMessengerBridge (https://github.com/herdr, 1.0)",
            },
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=10).read()
        except Exception as e:
            print(f"[Discord Webhook Error] {e}", flush=True)


def poll_discord(token: str, channel_id: str, webhook_url: str, state: dict) -> None:
    if not token or not channel_id:
        return

    last_id = state.get("discord_last_message_id")
    if not last_id:
        msgs = discord_api(token, "GET", f"/channels/{channel_id}/messages?limit=1")
        if isinstance(msgs, list) and msgs:
            state["discord_last_message_id"] = str(msgs[0]["id"])
        else:
            state["discord_last_message_id"] = "0"
        save_state(state)
        return

    query = f"?after={last_id}&limit=20" if last_id != "0" else "?limit=5"
    msgs = discord_api(token, "GET", f"/channels/{channel_id}/messages{query}")
    if not isinstance(msgs, list) or not msgs:
        return

    for m in reversed(msgs):
        mid = str(m.get("id", ""))
        if not mid:
            continue
        state["discord_last_message_id"] = mid
        save_state(state)

        author = m.get("author", {})
        if author.get("bot"):
            continue
        content = (m.get("content") or "").strip()
        if not content:
            continue

        ref = m.get("message_reference", {})
        ref_id = str(ref.get("message_id", ""))
        mapped_pane = state.get("discord_msg_pane_map", {}).get(ref_id) if ref_id else None

        reply_text, assoc_pane = handle_generic_command(content, mapped_pane, state)
        discord_send_message(
            token,
            channel_id,
            webhook_url,
            reply_text,
            pane_id=assoc_pane,
            reply_to_id=mid,
            state=state,
        )


# =====================================================================
# Auto-Alerting on Pane Status Transitions (blocked / done)
# =====================================================================

def check_pane_alerts(cfg: dict, state: dict) -> None:
    panes = get_panes()
    prev_statuses = state.get("pane_statuses", {})
    changed = False

    tg_token = cfg["telegram_bot_token"]
    tg_chat_id = state.get("chat_id") or cfg["telegram_allowed_chat_id"]
    slack_token = cfg["slack_bot_token"]
    slack_channel = cfg["slack_channel_id"]
    discord_token = cfg["discord_bot_token"]
    discord_channel = cfg["discord_channel_id"]
    discord_webhook = cfg["discord_webhook_url"]

    for p in panes:
        pid = p.get("pane_id")
        st = p.get("agent_status", "unknown")
        agent = p.get("agent") or "shell"
        old_st = prev_statuses.get(pid)

        if old_st is not None and old_st != st and st in ("blocked", "done"):
            output = read_pane_output(pid, lines=25)
            if st == "blocked":
                title_plain = f"🔔 [응답 대기 알림] {pid} ({agent}) - AI가 질문이나 승인을 기다리고 있습니다!"
                title_html = f"🔔 <b>[응답 대기 알림] <code>{html_escape(pid)}</code> ({html_escape(agent)})</b>\nAI가 질문이나 승인을 기다리고 있습니다!"
            else:
                title_plain = f"✅ [작업 완료 알림] {pid} ({agent}) - AI가 작업을 마쳤습니다!"
                title_html = f"✅ <b>[작업 완료 알림] <code>{html_escape(pid)}</code> ({html_escape(agent)})</b>\nAI가 작업을 마쳤습니다!"

            # 1) Telegram Alert
            if tg_token and tg_chat_id:
                tg_text = (
                    f"{title_html}\n\n"
                    f"<pre>{html_escape(output)}</pre>\n\n"
                    f"💬 <i>이 메시지에 답장하거나 아래 버튼을 눌러 응답하세요.</i>"
                )
                res = tg_api(
                    tg_token,
                    "sendMessage",
                    {
                        "chat_id": tg_chat_id,
                        "text": tg_text,
                        "parse_mode": "HTML",
                        "reply_markup": build_pane_inline_buttons(pid),
                    },
                )
                if res.get("ok"):
                    state.setdefault("message_pane_map", {})[str(res["result"]["message_id"])] = pid

            # 2) Slack Alert
            if slack_token and slack_channel:
                slack_text = (
                    f"*{title_plain}*\n"
                    f"```\n{output}\n```\n"
                    f"💡 _이 메시지의 스레드(댓글)로 답장하면 `{pid}` 창에 즉시 전달됩니다._"
                )
                slack_post_message(slack_token, slack_channel, slack_text, pane_id=pid, state=state)

            # 3) Discord Alert
            if (discord_token and discord_channel) or discord_webhook:
                discord_text = (
                    f"**{title_plain}**\n"
                    f"```\n{output}\n```\n"
                    f"💡 *이 메시지에 답장(Reply)하거나 `/use {pid}` 후 입력하면 해당 창으로 전달됩니다.*"
                )
                discord_send_message(
                    discord_token,
                    discord_channel,
                    discord_webhook,
                    discord_text,
                    pane_id=pid,
                    state=state,
                )

        prev_statuses[pid] = st
        changed = True

    if changed:
        state["pane_statuses"] = prev_statuses
        save_state(state)


# =====================================================================
# Main Event Loop
# =====================================================================

def main() -> None:
    cfg = get_config()
    state = load_state()
    if cfg["telegram_allowed_chat_id"] and not state.get("chat_id"):
        try:
            state["chat_id"] = int(cfg["telegram_allowed_chat_id"])
        except ValueError:
            state["chat_id"] = cfg["telegram_allowed_chat_id"]
        save_state(state)

    enabled = []
    if cfg["telegram_bot_token"]:
        me = tg_api(cfg["telegram_bot_token"], "getMe")
        bot_username = me.get("result", {}).get("username", "UnknownBot")
        enabled.append(f"Telegram (@{bot_username})")
    if cfg["slack_bot_token"] and cfg["slack_channel_id"]:
        enabled.append(f"Slack (channel: {cfg['slack_channel_id']})")
    if cfg["discord_bot_token"] and cfg["discord_channel_id"]:
        enabled.append(f"Discord Bot (channel: {cfg['discord_channel_id']})")
    elif cfg["discord_webhook_url"]:
        enabled.append("Discord Webhook (one-way alerts)")

    if not enabled:
        print(
            f"[오류] 활성화된 메신저 설정이 없습니다 ({ENV_FILE}).\n"
            "  - Telegram: TELEGRAM_BOT_TOKEN\n"
            "  - Slack: SLACK_BOT_TOKEN 및 SLACK_CHANNEL_ID\n"
            "  - Discord: DISCORD_BOT_TOKEN 및 DISCORD_CHANNEL_ID (또는 DISCORD_WEBHOOK_URL)\n"
            "위 항목 중 최소 1개 이상을 .env 파일에 설정해 주세요.",
            flush=True,
        )
        sys.exit(1)

    print(
        f"[Herdr Multi-Messenger Bridge] Started! Root: {ROOT_DIR}\n"
        f"  Enabled Gateways: {', '.join(enabled)}",
        flush=True,
    )

    last_slack_discord_poll = 0.0

    while True:
        try:
            # 1. Poll Telegram (2s long-polling if enabled, else 2s sleep)
            if cfg["telegram_bot_token"]:
                offset = state.get("last_update_id", 0) + 1
                res = tg_api(
                    cfg["telegram_bot_token"],
                    "getUpdates",
                    {"offset": offset, "timeout": 2},
                    timeout=6,
                )
                if res.get("ok"):
                    for upd in res.get("result", []):
                        uid = upd["update_id"]
                        if uid > state.get("last_update_id", 0):
                            state["last_update_id"] = uid
                            save_state(state)
                        if "message" in upd:
                            tg_handle_message(
                                cfg["telegram_bot_token"],
                                cfg["telegram_allowed_chat_id"],
                                upd["message"],
                                state,
                            )
                        elif "callback_query" in upd:
                            tg_handle_callback(
                                cfg["telegram_bot_token"],
                                cfg["telegram_allowed_chat_id"],
                                upd["callback_query"],
                                state,
                            )
            else:
                time.sleep(2.0)

            # 2. Poll Slack & Discord every 3 seconds
            now = time.time()
            if now - last_slack_discord_poll >= 3.0:
                last_slack_discord_poll = now
                if cfg["slack_bot_token"] and cfg["slack_channel_id"]:
                    poll_slack(cfg["slack_bot_token"], cfg["slack_channel_id"], state)
                if cfg["discord_bot_token"] and cfg["discord_channel_id"]:
                    poll_discord(
                        cfg["discord_bot_token"],
                        cfg["discord_channel_id"],
                        cfg["discord_webhook_url"],
                        state,
                    )

            # 3. Check Herdr Pane Status Changes every ~2 seconds
            check_pane_alerts(cfg, state)

        except Exception as e:
            print(f"[Loop Error] {e}", flush=True)
            time.sleep(2.0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[Herdr Multi-Messenger Bridge] 종료되었습니다.")
        sys.exit(0)
