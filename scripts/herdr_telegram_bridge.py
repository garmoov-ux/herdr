import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE_DIR = Path("F:/herdr")
ENV_FILE = BASE_DIR / ".env"
STATE_FILE = BASE_DIR / "scripts" / "state.json"

USER_PATH = os.environ.get("PATH", "")
LOCAL_BIN = str(Path.home() / ".local" / "bin")
if LOCAL_BIN not in USER_PATH:
    os.environ["PATH"] = f"{LOCAL_BIN};{USER_PATH}"


def load_env():
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


ENV_VARS = load_env()
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or ENV_VARS.get("TELEGRAM_BOT_TOKEN", "")
if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
    print("[오류] F:\\herdr\\.env 파일에 TELEGRAM_BOT_TOKEN을 설정해 주세요.")
    sys.exit(1)


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    legacy = Path("F:/herdr-telegram/state.json")
    if legacy.exists():
        try:
            return json.loads(legacy.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "chat_id": None,
        "active_pane": "w1:p2",
        "last_update_id": 0,
        "pane_statuses": {},
        "message_pane_map": {},
    }


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def tg_api(method, payload=None, timeout=15):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
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


def run_herdr(args):
    cmd = ["herdr"] + args
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except Exception as e:
        return 1, "", str(e)


def get_panes():
    code, out, _ = run_herdr(["pane", "list"])
    if code != 0 or not out:
        return []
    try:
        return json.loads(out).get("result", {}).get("panes", [])
    except Exception:
        return []


def read_pane_output(pane_id, lines=25):
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


def send_to_pane(pane_id, text):
    code, out, err = run_herdr(["pane", "run", pane_id, text])
    return code == 0, err or out


def send_keys_to_pane(pane_id, key_name):
    code, out, err = run_herdr(["pane", "send-keys", pane_id, key_name])
    return code == 0, err or out


def status_badge(status):
    mapping = {
        "working": "🟢 작업중(working)",
        "blocked": "🟡 응답대기(blocked)",
        "done": "🔵 완료(done)",
        "idle": "⚪ 대기(idle)",
        "unknown": "⚪ 일반창(shell)",
    }
    return mapping.get(status, f"⚪ {status}")


def build_main_keyboard(active_pane):
    return {
        "keyboard": [
            [{"text": "📋 창 목록 보기"}, {"text": f"📺 현재 창({active_pane}) 화면 보기"}],
            [{"text": "➕ 새 창 나누기(오른쪽)"}, {"text": "❓ 도움말"}],
        ],
        "resize_keyboard": True,
    }


def build_pane_inline_buttons(pane_id):
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


def html_escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def send_panes_summary(chat_id, state):
    panes = get_panes()
    if not panes:
        tg_api("sendMessage", {"chat_id": chat_id, "text": "⚠️ 현재 실행 중인 Herdr 창을 찾을 수 없습니다."})
        return

    active_pane = state.get("active_pane") or panes[0]["pane_id"]
    lines = ["🖥️ <b>현재 Herdr 전체 팀·창(Pane) 목록</b>\n"]
    inline_rows = []

    for p in panes:
        pid = p.get("pane_id")
        ws = p.get("workspace_id", "w1")
        agent = p.get("agent") or "일반 터미널"
        st = status_badge(p.get("agent_status", "unknown"))
        is_target = " 👈 <b>[선택됨]</b>" if pid == active_pane else ""
        lines.append(f"• [<b>{ws}</b>] <code>{pid}</code> | <b>{agent}</b> | {st}{is_target}")
        inline_rows.append(
            [
                {"text": f"🎯 {pid} 선택", "callback_data": f"use:{pid}"},
                {"text": f"📺 {pid} 화면 보기", "callback_data": f"read:{pid}"},
            ]
        )

    lines.append(
        f"\n💬 지금 메시지를 입력하면 <b><code>{active_pane}</code></b> 창으로 바로 전송됩니다!"
    )
    tg_api(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": "\n".join(lines),
            "parse_mode": "HTML",
            "reply_markup": {"inline_keyboard": inline_rows},
        },
    )


def send_pane_screen(chat_id, pane_id, state):
    output = read_pane_output(pane_id, lines=30)
    msg = (
        f"📺 <b>[{pane_id}] 최근 터미널 화면 출력</b>\n\n"
        f"<pre>{html_escape(output)}</pre>\n\n"
        f"💡 <i>이 메시지에 '답장'하거나 아래 버튼을 눌러 제어할 수 있습니다.</i>"
    )
    res = tg_api(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "HTML",
            "reply_markup": build_pane_inline_buttons(pane_id),
        },
    )
    if res.get("ok"):
        state["message_pane_map"][str(res["result"]["message_id"])] = pane_id
        save_state(state)


def handle_message(msg, state):
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    if not chat_id:
        return

    text = (msg.get("text") or "").strip()
    first_bind = state.get("chat_id") != chat_id
    state["chat_id"] = chat_id

    panes = get_panes()
    pane_ids = [p["pane_id"] for p in panes]
    if pane_ids and state.get("active_pane") not in pane_ids:
        state["active_pane"] = "w1:p2" if "w1:p2" in pane_ids else pane_ids[0]
    save_state(state)

    if first_bind or text in ("/start", "/help", "❓ 도움말"):
        active = state.get("active_pane", "w1:p2")
        welcome = (
            "🎉 <b>Herdr × Hermes 텔레그램 원격 제어 브릿지</b>\n\n"
            f"현재 기본 제어 대상 창: <code>{active}</code>\n\n"
            "<b>[단축 명령어]</b>\n"
            "• <code>/panes</code> : 모든 팀(w1, w2...) 및 창 목록 보기\n"
            "• <code>/newteam 마케팅팀</code> : 새 부서(w2, w3...) + 3인 직원(팀장/리서처/실무자) 책상 자동 생성!\n"
            "• <code>/read w1:p2</code> : 특정 창 화면 읽어오기\n"
            "• <code>/use w1:p2</code> : 기본 입력 창 변경\n"
            "• <code>/split</code> : 현재 팀에 새 창 오른쪽 분할 생성"
        )
        tg_api(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": welcome,
                "parse_mode": "HTML",
                "reply_markup": build_main_keyboard(active),
            },
        )
        send_panes_summary(chat_id, state)
        return

    if text.startswith("/newteam"):
        parts = text.split(maxsplit=1)
        team_name = parts[1].strip() if len(parts) > 1 else f"신규팀_{int(time.time()) % 1000}"
        res = subprocess.run(
            [sys.executable, str(BASE_DIR / "scripts" / "create_team.py"), "--team", team_name],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        tg_api(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": f"🏢 <b>새 팀 생성 결과:</b>\n<pre>{html_escape(res.stdout or res.stderr)}</pre>",
                "parse_mode": "HTML",
            },
        )
        send_panes_summary(chat_id, state)
        return

    if text in ("/panes", "📋 창 목록 보기"):
        send_panes_summary(chat_id, state)
        return

    if text.startswith("📺 현재 창") or text == "/read":
        send_pane_screen(chat_id, state.get("active_pane", "w1:p2"), state)
        return

    if text.startswith("/read "):
        send_pane_screen(chat_id, text.split(maxsplit=1)[1].strip(), state)
        return

    if text.startswith("/use "):
        target = text.split(maxsplit=1)[1].strip()
        state["active_pane"] = target
        save_state(state)
        tg_api(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": f"🎯 기본 제어 창이 <b><code>{target}</code></b> 로 변경되었습니다!",
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
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": f"➕ 새 창 <b><code>{new_pane}</code></b> 생성 완료!",
                    "parse_mode": "HTML",
                    "reply_markup": build_main_keyboard(new_pane),
                },
            )
        else:
            tg_api("sendMessage", {"chat_id": chat_id, "text": f"❌ 창 분할 실패: {err or out}"})
        return

    reply_to = msg.get("reply_to_message", {})
    reply_msg_id = str(reply_to.get("message_id", ""))
    target_pane = state.get("message_pane_map", {}).get(reply_msg_id) or state.get("active_pane", "w1:p2")

    ok, err = send_to_pane(target_pane, text)
    if ok:
        time.sleep(1.2)
        output = read_pane_output(target_pane, lines=20)
        resp_text = (
            f"📨 <b><code>{target_pane}</code> 창에 전송 완료:</b> <code>{html_escape(text)}</code>\n\n"
            f"<pre>{html_escape(output)}</pre>"
        )
        res = tg_api(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": resp_text,
                "parse_mode": "HTML",
                "reply_markup": build_pane_inline_buttons(target_pane),
            },
        )
        if res.get("ok"):
            state["message_pane_map"][str(res["result"]["message_id"])] = target_pane
            save_state(state)
    else:
        tg_api(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": f"❌ <code>{target_pane}</code> 전송 실패: {html_escape(err)}",
                "parse_mode": "HTML",
            },
        )


def handle_callback(cb, state):
    cb_id = cb.get("id")
    data = cb.get("data", "")
    msg = cb.get("message", {})
    chat_id = msg.get("chat", {}).get("id") or state.get("chat_id")

    if data.startswith("use:"):
        pane_id = data.split(":", 1)[1]
        state["active_pane"] = pane_id
        save_state(state)
        tg_api("answerCallbackQuery", {"callback_query_id": cb_id, "text": f"{pane_id} 선택됨!"})
        tg_api(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": f"🎯 기본 제어 창이 <b><code>{pane_id}</code></b> 로 변경되었습니다!",
                "parse_mode": "HTML",
                "reply_markup": build_main_keyboard(pane_id),
            },
        )
    elif data.startswith("read:"):
        pane_id = data.split(":", 1)[1]
        tg_api("answerCallbackQuery", {"callback_query_id": cb_id, "text": f"{pane_id} 화면 불러오는 중..."})
        send_pane_screen(chat_id, pane_id, state)
    elif data.startswith("run:"):
        rest = data[len("run:") :]
        pane_id, cmd_text = rest.rsplit(":", 1)
        send_to_pane(pane_id, cmd_text)
        tg_api("answerCallbackQuery", {"callback_query_id": cb_id, "text": f"{pane_id}에 '{cmd_text}' 전송!"})
        time.sleep(1.0)
        send_pane_screen(chat_id, pane_id, state)
    elif data.startswith("key:"):
        rest = data[len("key:") :]
        pane_id, key_name = rest.rsplit(":", 1)
        send_keys_to_pane(pane_id, key_name)
        tg_api("answerCallbackQuery", {"callback_query_id": cb_id, "text": f"{pane_id}에 [{key_name}] 키 전송!"})
        time.sleep(1.0)
        send_pane_screen(chat_id, pane_id, state)


def push_to_pixel_agents(payload):
    server_json = Path.home() / ".pixel-agents" / "server.json"
    if not server_json.exists():
        return
    try:
        srv = json.loads(server_json.read_text(encoding="utf-8"))
        port = srv.get("port")
        token = srv.get("token")
        if not port or not token:
            return
        url = f"http://127.0.0.1:{port}/api/hooks/claude"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )
        urllib.request.urlopen(req, timeout=1.5).read()
    except Exception:
        pass


def sync_pane_to_pixel_agents(pane, old_st, state):
    agent = pane.get("agent")
    if not agent or agent == "claude":
        return
    pid = pane.get("pane_id", "w1:p1")
    st = pane.get("agent_status", "unknown")
    sid = f"herdr-{pid.replace(':', '-')}-{agent}"
    cwd = pane.get("cwd") or "F:\\herdr"
    registered = state.setdefault("pixel_registered", {})

    if not registered.get(sid):
        push_to_pixel_agents(
            {"hook_event_name": "SessionStart", "session_id": sid, "cwd": cwd, "source": "startup"}
        )
        push_to_pixel_agents(
            {
                "hook_event_name": "PreToolUse",
                "session_id": sid,
                "tool_name": "Bash",
                "tool_input": {"command": f"{agent} ({pid})"},
            }
        )
        registered[sid] = True

    if old_st != st:
        if st == "working":
            push_to_pixel_agents(
                {
                    "hook_event_name": "PreToolUse",
                    "session_id": sid,
                    "tool_name": "Edit",
                    "tool_input": {"file_path": f"{pid}-{agent}"},
                }
            )
        elif st == "blocked":
            push_to_pixel_agents({"hook_event_name": "PermissionRequest", "session_id": sid})
        elif st in ("done", "idle"):
            push_to_pixel_agents({"hook_event_name": "Stop", "session_id": sid})


def check_pane_alerts(state):
    chat_id = state.get("chat_id")
    panes = get_panes()
    prev_statuses = state.get("pane_statuses", {})
    changed = False

    for p in panes:
        pid = p.get("pane_id")
        st = p.get("agent_status", "unknown")
        agent = p.get("agent") or "shell"
        old_st = prev_statuses.get(pid)

        sync_pane_to_pixel_agents(p, old_st, state)

        if chat_id and old_st is not None and old_st != st:
            if st in ("blocked", "done"):
                output = read_pane_output(pid, lines=25)
                if st == "blocked":
                    header = f"🔔 <b>[응답 대기 알림] <code>{pid}</code> ({agent})</b>\nAI가 질문이나 승인을 기다리고 있습니다!"
                else:
                    header = f"✅ <b>[작업 완료 알림] <code>{pid}</code> ({agent})</b>\nAI가 작업을 마쳤습니다!"

                text = f"{header}\n\n<pre>{html_escape(output)}</pre>\n\n💬 <i>이 메시지에 답장하거나 아래 버튼을 눌러 응답하세요.</i>"
                res = tg_api(
                    "sendMessage",
                    {
                        "chat_id": chat_id,
                        "text": text,
                        "parse_mode": "HTML",
                        "reply_markup": build_pane_inline_buttons(pid),
                    },
                )
                if res.get("ok"):
                    state["message_pane_map"][str(res["result"]["message_id"])] = pid
        prev_statuses[pid] = st
        changed = True

    if changed:
        state["pane_statuses"] = prev_statuses
        save_state(state)


def main():
    state = load_state()
    me = tg_api("getMe")
    bot_username = me.get("result", {}).get("username", "UnknownBot")
    print(f"[Herdr-Telegram Bridge] Started for @{bot_username} (Root: F:\\herdr)", flush=True)

    while True:
        try:
            offset = state.get("last_update_id", 0) + 1
            res = tg_api("getUpdates", {"offset": offset, "timeout": 2}, timeout=6)
            if res.get("ok"):
                for upd in res.get("result", []):
                    uid = upd["update_id"]
                    if uid > state.get("last_update_id", 0):
                        state["last_update_id"] = uid
                        save_state(state)
                    if "message" in upd:
                        handle_message(upd["message"], state)
                    elif "callback_query" in upd:
                        handle_callback(upd["callback_query"], state)

            check_pane_alerts(state)
        except Exception as e:
            print(f"[Loop Error] {e}", flush=True)
            time.sleep(2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[Herdr-Telegram Bridge] 종료되었습니다.")
        sys.exit(0)
