# 🧠 Herdr × Hermes CLI AgenticOS

> **Multi-Workspace AI Terminal Orchestrator (`Herdr`) × Self-Improving Memory & Skill Engine (`Hermes`) × Multi-Messenger Remote Control (`Telegram` · `Slack` · `Discord`)**

**Herdr × Hermes CLI AgenticOS**는 여러 AI 에이전트(`Claude Code`, `Codex`, `Antigravity CLI` 등)를 부서(`w1`, `w2`, `w3`...)와 직책별 책상(`p1`, `p2`, `p3`...)으로 편성하고, **2단 영구 기억(`USER_PROFILE.md`, `COMPANY_MEMORY.md`, `TEAM_MEMORY.md`)과 자율 스킬 합성(`skills/`)**을 통해 스스로 진화하며, **텔레그램·슬랙·디스코드** 어디서나 실시간 양방향으로 지휘할 수 있는 오픈소스 AI 에이전트 운영체제입니다.

---

## ✨ 3대 핵심 아키텍처

| 축 (Pillar) | 역할 및 특징 |
| :--- | :--- |
| **1. 🖥️ Herdr 멀티 오케스트레이션** | • **워크스페이스(`w1`, `w2`, `w3`...)** = 부서/팀 사무실<br>• **페인(`p1`, `p2`, `p3`...)** = 직원별 독립 터미널 책상<br>• 팀장(`p1`)이 직접 모든 실무를 떠안아 컨텍스트(기억 용량)가 오염되는 것을 방지하고, 하위 창(`p2`, `p3`)에 업무를 분할·위임 |
| **2. 🧬 Hermes 자기 진화형 브레인** | • **2단 영구 기억:** 사용자 선호도(`./memory/USER_PROFILE.md`) + 전사 장기 기억(`./memory/COMPANY_MEMORY.md`) + 부서 수첩(`./teams/<팀>/TEAM_MEMORY.md`) 자동 동기화<br>• **자율 스킬 합성:** 한 번 해결한 복잡한 절차나 노하우를 `./skills/<name>/SKILL.md`로 스스로 문서화하여 다음 작업 시 재사용<br>• **5대 직무 프리셋 온보딩:** `./templates/roles/` 기반 즉시 투입 가능한 전문 사원증 자동 발급 |
| **3. 📱 멀티 메신저 양방향 브릿지** | • **외부 패키지 설치 불필요 (Pure Python 3 표준 라이브러리)**<br>• **Telegram / Slack / Discord** 동시 지원<br>• AI가 질문(`blocked`)하거나 작업을 끝내면(`done`) 즉시 스마트폰/메신저로 알림 전송 및 **답장(Reply)으로 해당 창에 직접 입력** |

---

## 📂 디렉터리 구조 (100% 상대 경로 · Portable 설계)

어떤 PC, 어떤 폴더에 `git clone`하더라도 하드코딩된 경로 없이 즉시 작동합니다.

```text
./
├── AGENTS.md / CLAUDE.md / GEMINI.md   # 📜 전사 헌법 (모든 AI 직원이 출근 시 읽는 헤르메스 루프 규칙)
├── herdr_os.py                         # ⚙️ 통합 CLI 제어기 (setup / status / team / role / delegate)
├── install.ps1 / install.sh            # 🚀 Windows / macOS / Linux 원클릭 설치 스크립트
├── start_all.bat                       # 📡 멀티 메신저 브릿지 원클릭 실행기 (Windows)
├── .env.example                        # 🔑 메신저 봇 토큰 설정 템플릿 (.env로 복사하여 사용)
├── Herdr_사용설명서_및_단축키.md         # ⌨️ Herdr 마우스·키보드 단축키 및 CLI 완벽 가이드
├── memory/                             # 🧠 헤르메스 2단 영구 기억 저장소
│   ├── USER_PROFILE.md                 # 사용자(사장님) 성향, 선호 문체, 작업 원칙
│   └── COMPANY_MEMORY.md               # 전사 공유 마일스톤 및 아키텍처 결정 로그
├── templates/roles/                    # 🪪 5대 표준 직무 프리셋 템플릿
│   ├── pm_leader.md                    # 총괄 기획 팀장 (오케스트레이터 & 컨텍스트 수호자)
│   ├── researcher.md                   # 수석 리서처 (고밀도 요약 & 토큰 절약 전문가)
│   ├── developer.md                    # 수석 개발자 (코드 구현, 테스트 & 스킬 자산화)
│   ├── writer.md                       # 콘텐츠·문서 작가 (보고서, 기획서, 기술 문서, 대본)
│   └── qa_reviewer.md                  # 품질·보안 검수자 (비판적 검증 & 엣지 케이스 탐지)
├── skills/                             # 🔄 AI가 스스로 생성·축적하는 재사용 스킬 보관함
│   └── herdr-orchestrator/SKILL.md     # 멀티 팀/직원 생성 및 부서 간 위임 표준 스킬
├── gateways/                           # 💬 메신저 게이트웨이
│   └── messenger_bridge.py             # Telegram ↔ Slack ↔ Discord ↔ Herdr 양방향 브릿지
├── scripts/                            # 🛠️ 유틸리티 스크립트
│   ├── create_team.py                  # 부서 및 직원 창 일괄 생성 스크립트
│   └── paste_clipboard_image.ps1       # Alt+V 클립보드 캡처 이미지 즉시 붙여넣기 도구
└── teams/                              # 🏢 생성된 각 부서(w1, w2...) 및 직원별 작업 폴더
```

---

## 🚀 1분 퀵스타트 (`uv` 가상환경 + 헤르메스 관리 콘솔 UI)

> **초기 클론 시 100% 깨끗한 초기값(Zero-State) 보장**: 처음 `git clone` 했을 때는 어떤 팀(`teams/`), 기억(`memory/`), 스킬(`skills/`)도 강제로 등록되어 있지 않습니다. 아래 **웹 관리 콘솔 UI(`uv run herdr-os ui`)** 또는 **대화형 터미널 메뉴(`uv run herdr-os`)**에서 클릭/번호 선택만으로 원하는 스킬과 팀·직원을 자유롭게 구성하세요!

### 🪟 Windows (PowerShell)
```powershell
# 1. 저장소 복제 및 폴더 이동
git clone https://github.com/garmoov-ux/herdr.git
cd herdr

# 2. uv 가상환경(.venv) 동기화 및 원클릭 설치
uv sync
powershell -ExecutionPolicy Bypass -File .\install.ps1

# 3. 명령어 입력 없이 [헤르메스 스타일 웹 관리 콘솔 UI] 실행 (http://127.0.0.1:8765)
uv run herdr-os ui

# 또는 [터미널 대화형 메뉴(TUI)] 실행
uv run herdr-os
```

### 🍎 macOS / 🐧 Linux (Bash / Zsh)
```bash
# 1. 저장소 복제 및 폴더 이동
git clone https://github.com/garmoov-ux/herdr.git
cd herdr

# 2. uv 가상환경(.venv) 동기화 및 원클릭 설치
uv sync
chmod +x ./install.sh && ./install.sh

# 3. 헤르메스 스타일 웹 관리 콘솔 UI 실행 (http://127.0.0.1:8765)
uv run herdr-os ui
```

---

## 🎛️ 헤르메스 스타일 관리 콘솔 UI (`uv run herdr-os ui`)

명령어를 일일이 외우거나 타이핑할 필요 없이, 브라우저(`http://127.0.0.1:8765`) 또는 터미널 메뉴(`uv run herdr-os`)에서 모든 기능을 클릭으로 관리할 수 있습니다:

1. **🧩 스킬 허브 (Skills Hub)**: 내장 스킬 카탈로그(`templates/skills/`)에서 **원클릭 장착/해제**, 새 커스텀 스킬 생성, 웹 에디터에서 `SKILL.md` 즉시 수정 및 삭제
2. **🏢 팀 & 직원 배치 (Teams & Employees)**: 부서 이름 입력 후 드롭다운에서 직책(`총괄팀장`, `수석개발자`, `UI디자이너`, `수석리서처`, `콘텐츠작가`, `품질검수자`)과 AI 엔진(`agy`, `claude`, `codex`)을 골라 **원클릭으로 Herdr 창 분할 + 사원증 발급 + 업무 지시 전송**
3. **🧠 기억 & 헌법 편집기 (Memory & Brain)**: `USER_PROFILE.md`, `COMPANY_MEMORY.md`, `AGENTS.md` 및 부서별 `TEAM_MEMORY.md`를 웹 에디터에서 바로 열람·수정
4. **💬 멀티 메신저 설정 (Messenger Gateway)**: Telegram, Slack, Discord 봇 토큰(`.env`) 입력 및 저장
5. **🔄 순수 초기값 리셋 (Factory Reset)**: 언제든 `uv run herdr-os reset` 또는 웹 UI의 **[초기값으로 전체 리셋]** 버튼 하나로 처음 클론했을 때의 깨끗한 초기 상태로 즉시 되돌리기

---

## 🏢 새 팀(`w1`, `w2`, `w3`...) 생성 및 직책(`p1`, `p2`, `p3`...) 배정 방법

상황에 따라 **3가지 방법(CLI 명령어 / AI에게 대화로 지시 / 메신저 원격 명령)** 중 가장 편한 방식을 선택하세요.

### 방법 1: 통합 CLI (`herdr_os.py`)로 정교하게 제어하기
```bash
# 1) 5대 직무 프리셋을 조합하여 새 부서(워크스페이스) + 직원 창(p1~p3) 한 번에 생성
python ./herdr_os.py team create --name "마케팅팀" --roles "팀장:agy:pm_leader,리서처:claude:researcher,작가:codex:writer"

# 2) 이미 열려 있는 특정 창(예: w1:p2)에 직책 프리셋과 특별 임무 부여
python ./herdr_os.py role assign --pane w1:p2 --role developer --agent claude --mission "결제 API 모듈 리팩토링 및 단위 테스트 작성"

# 3) 현재 편성된 모든 부서, 창 상태, 기억/스킬 현황 한눈에 보기
python ./herdr_os.py status
```

### 방법 2: Herdr 안의 AI(팀장 `p1`)에게 자연어로 시키기
팀장 창(`w1:p1`)에 있는 AI에게 일상 대화하듯 말하면, AI가 스스로 `./skills/herdr-orchestrator/SKILL.md`를 참조해 팀을 만들고 업무를 배분합니다:
> 💬 *"유튜브기획팀 새로 만들고, p1은 총괄팀장(agy), p2는 수석리서처(claude), p3는 대본작가(codex)로 세팅해서 AI 트렌드 영상 기획안 만들어 줘."*

### 방법 3: 외출 중 Telegram / Slack / Discord에서 명령어로 제어하기
메신저 채팅창에서 아래 슬래시 명령어를 입력하거나 알림 메시지에 **답장(Reply)**을 보내면 해당 창으로 즉시 전달됩니다:

| 메신저 명령어 | 동작 설명 |
| :--- | :--- |
| `/panes` | 현재 실행 중인 모든 부서(`w1`, `w2`...)와 창(`w1:p1`, `w1:p2`...) 상태 조회 |
| `/newteam 마케팅팀 팀장:agy,리서처:claude,작가:codex` | 원격으로 새 부서 워크스페이스 생성 및 직원별 창 분할·사원증 발급 |
| `/assign w1:p2 researcher claude 경쟁사 가격 정책 조사` | 특정 창(`w1:p2`)에 직책·AI·임무를 즉시 부여 |
| `/read w1:p2` | `w1:p2` 창의 최근 터미널 화면 출력 읽어오기 |
| `/use w1:p2` | 기본 대화 전송 대상 창을 `w1:p2`로 변경 |
| `/key w1:p2 enter` (또는 `esc`) | 해당 창에 특수 키(`enter`, `esc` 등) 전송 |
| **알림 메시지에 '답장(Reply)'하기** | 어떤 창을 기본으로 선택해 두었든 **답장한 알림의 원래 창(`w2:p3` 등)**으로 정확히 입력 전송 |

---

## 🪪 5대 기본 직무 프리셋 (`./templates/roles/`)

| 프리셋 이름 | 추천 직책 | 핵심 역할 요약 |
| :---: | :---: | :--- |
| `pm_leader` | **총괄 기획 팀장 (`p1`)** | 실무를 직접 다 하지 않고 하위 창(`p2`, `p3`)에 분배하여 컨텍스트를 보호하며, `TEAM_MEMORY.md`와 `COMPANY_MEMORY.md`를 총괄 관리하는 오케스트레이터 |
| `researcher` | **수석 리서처 (`p2`)** | 웹·문서·코드베이스를 조사한 뒤 **핵심 요약과 출처만 `TEAM_MEMORY.md`에 기록**하여 팀장의 토큰 소모를 줄이는 정보 전문가 |
| `developer` | **수석 개발자 (`p3`)** | 경로 독립적 클린 코드 구현, 자동화 테스트 실행, 반복 기술을 `./skills/<name>/SKILL.md`로 자산화하는 엔지니어 |
| `writer` | **콘텐츠·문서 작가 (`p3`)** | 리서치 팩트를 바탕으로 보고서, 기획서, 블로그, 대본, 매뉴얼을 가독성 높게 집필하는 문서 전문가 |
| `qa_reviewer` | **품질·보안 검수자 (`p4`)** | 다른 직원의 코드/문서를 비판적으로 검증하고 하드코딩, 보안 노출, 엣지 케이스를 찾아내는 최종 게이트키퍼 |
