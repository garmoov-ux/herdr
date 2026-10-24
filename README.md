# 🏢 AgenticOS (Herdr × Hermes × Telegram × Pixel Agents)

> **Herdr**의 멀티 터미널 오케스트레이션 + **Hermes Agent**의 자기 진화형 기억/스킬 루프(`USER_PROFILE.md`, `COMPANY_MEMORY.md`, `skills/`) + **텔레그램 원격 제어** + **Pixel Agents 가상 오피스**를 하나로 결합한 통합 AI 에이전트 회사 프레임워크입니다.

---

## 📂 폴더 구조

```text
F:\herdr\
├── AGENTS.md / CLAUDE.md / GEMINI.md   # 모든 AI 직원이 출근 시 읽는 전사 헌법 (헤르메스 루프 내장)
├── Herdr_사용설명서_및_단축키.md         # Herdr 단축키 및 사용 가이드
├── start_all.bat                       # 텔레그램 브릿지 + Pixel Agents 가상오피스 원클릭 실행기
├── .env.example                        # 환경변수 템플릿 (복사하여 .env 생성 후 토큰 입력)
├── memory\                             # 🧠 헤르메스식 2단 영구 기억 저장소
│   ├── USER_PROFILE.md                 # 사장님(사용자) 프로필 및 선호 원칙
│   └── COMPANY_MEMORY.md               # 전사 공유 장기 기억 로그
├── skills\                             # 🔄 AI가 스스로 생성·축적하는 재사용 스킬 보관함
│   └── herdr-orchestrator\SKILL.md     # 멀티 팀/직원 생성 및 제어 스킬
├── teams\                              # 🏢 팀(w1, w2, w3...) 및 직원별(p1, p2, p3...) 작업방·사원증
└── scripts\                            # 🛠️ 자동화 스크립트 모음
    ├── herdr_telegram_bridge.py        # 텔레그램 ↔ Herdr ↔ Pixel Agents 양방향 브릿지
    ├── create_team.py                  # 새 팀(w2, w3) 및 직책별 창(p1, p2, p3) 원클릭 생성기
    └── paste_clipboard_image.ps1       # Alt+V 클립보드 캡처 즉시 붙여넣기 도구
```

---

## 🚀 새 컴퓨터에 복구(설치)하는 방법 (Git Clone 이후)

1. **저장소 복제 및 `.env` 설정**
   ```powershell
   git clone <내-깃허브-저장소-주소> F:\herdr
   cd F:\herdr
   copy .env.example .env
   # .env 파일을 열어 TELEGRAM_BOT_TOKEN 입력
   ```
2. **필수 도구 설치 (Herdr & Pixel Agents)**
   ```powershell
   powershell -ExecutionPolicy Bypass -c "irm https://herdr.dev/install.ps1 | iex"
   npm install --global pixel-agents
   ```
3. **통합 실행**
   * `F:\herdr\start_all.bat` 더블클릭 (또는 Herdr 안에서 `herdr_telegram_bridge.py` 실행)

---

## 🏢 새 팀(`w2`, `w3`...)과 직원 역할(`p1`, `p2`, `p3`) 추가하는 법

1. **AI에게 말로 시키기:**  
   > *"유튜브기획팀 새로 만들고, p1은 팀장, p2는 자료조사원, p3는 대본작가로 세팅해 줘"*
2. **텔레그램에서 명령어로 만들기:**  
   > `/newteam 유튜브기획팀`
3. **터미널 명령어로 만들기:**
   ```powershell
   python F:\herdr\scripts\create_team.py --team "유튜브기획팀" --roles "팀장:agy:기획 총괄,조사원:claude:자료 조사,작가:codex:대본 작성"
   ```
