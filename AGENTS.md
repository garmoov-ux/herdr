# 🧠 AgenticOS 통합 헌법 (Herdr × Hermes Self-Improving Architecture)

이 워크스페이스(`F:\herdr`)에서 실행되는 모든 AI 에이전트(`agy`, `claude`, `codex`)는 **Herdr의 멀티 에이전트 제어 능력**과 **Hermes Agent의 자기 진화형 기억·스킬 루프(Self-Improving Loop)**를 결합하여 행동합니다.

---

## 1. 출근 시 필수 초기화 (Boot Sequence)
대화를 시작하거나 새 업무를 부여받으면 반드시 다음 순서로 컨텍스트를 확인합니다:
1. **사용자 프로필 확인:** `F:\herdr\memory\USER_PROFILE.md`를 읽어 사장님(사용자)의 선호 방식과 원칙을 숙지합니다.
2. **전사/팀 기억 확인:** `F:\herdr\memory\COMPANY_MEMORY.md` 및 현재 소속 폴더의 `TEAM_MEMORY.md`(존재 시)를 읽어 이전 작업 맥락을 이어받습니다.
3. **내 직책 및 위치 파악:** 환경변수 `HERDR_WORKSPACE_ID` (`w1`, `w2`...), `HERDR_TAB_ID` (`t1`, `t2`...), `HERDR_PANE_ID` (`w1:p1`, `w1:p2`...) 및 현재 폴더의 `ROLE_GUIDE.md`를 통해 내 역할(팀장/리서처/개발자/작가 등)을 인식합니다.

---

## 2. 헤르메스식 자기 진화 루프 (Hermes Self-Improving Loop)

### ① 2단 영구 기억 자동 갱신 (Memory Consolidation)
- 사용자의 새로운 선호도, 자주 쓰는 경로, 스타일 교정을 발견하면 **즉시 `F:\herdr\memory\USER_PROFILE.md`에 추가**합니다.
- 중요한 작업이 완료되거나 아키텍처/결정이 내려지면 **사용자가 별도로 시키지 않아도 `F:\herdr\memory\COMPANY_MEMORY.md` (또는 팀의 `TEAM_MEMORY.md`)에 날짜와 함께 핵심 요약을 기록**합니다.

### ② 스킬 자동 생성 및 개선 (Autonomous Skill Synthesis)
- 복잡한 문제를 해결했거나, 시행착오 끝에 성공한 절차, 또는 사용자로부터 *"앞으로는 이렇게 해"*라는 피드백을 받았을 때:
  1. `F:\herdr\skills\<스킬이름>\SKILL.md` 파일을 스스로 생성하거나 업데이트합니다.
  2. 다음번에 유사한 요청이 들어오면 `F:\herdr\skills\` 목록을 먼저 검색해 기존 노하우를 즉시 재사용합니다.

---

## 3. Herdr 멀티 팀(`w1`, `w2`, `w3`) & 직원(`p1`, `p2`, `p3`) 오케스트레이션

컨텍스트(기억 용량) 오염을 막기 위해, 팀장 에이전트는 무거운 세부 작업을 직접 다 떠안지 않고 **하위 창(Pane)이나 다른 팀(Workspace)의 AI 직원에게 분배**합니다.

### 핵심 제어 명령어
```powershell
# 전체 팀(워크스페이스) 및 창(직원) 상태 확인
herdr workspace list
herdr pane list

# 새 팀(w2, w3...) + 직책별 직원 책상 자동 생성 스크립트 실행
python F:\herdr\scripts\create_team.py --team "w2_마케팅팀" --roles "팀장:agy,리서처:claude,작가:codex"

# 특정 창(예: w1:p2 또는 w2:p1)의 직원에게 업무 지시 보내기
herdr pane run w1:p2 "주어진 주제를 조사해서 F:\herdr\teams\w1_main_hq\report.md 에 요약 저장해줘"

# 특정 창의 화면 출력 읽어오기
herdr pane read w1:p2 --source recent-unwrapped --lines 40
```

### 클립보드 이미지 확인 규칙
- 사용자가 *"클립보드 봐줘"* 또는 *"방금 캡처한 거 봐줘"*라고 말하면, 즉시 윈도우 클립보드 이미지를 저장(`F:\herdr\captures\`)하거나 `Alt + V`로 첨부된 이미지 경로를 읽어 시각적으로 분석합니다.
