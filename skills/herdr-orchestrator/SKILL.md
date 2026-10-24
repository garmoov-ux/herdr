---
name: herdr-orchestrator
description: "Herdr 멀티 팀(w1, w2, w3...) 및 창(p1, p2, p3...) 생성, 5대 직책 프리셋(pm_leader, researcher, developer, writer, qa_reviewer) 사원증 부여, 부서 간 업무 지시 및 결과 수령을 담당하는 핵심 오케스트레이션 스킬입니다."
---

# Herdr × Hermes 멀티 팀 오케스트레이션 스킬

## 1. 새로운 팀(`w2`, `w3`...)과 직원(`p1`, `p2`, `p3`) 한 번에 생성하기
사용자가 *"마케팅팀(w2) 새로 만들고 팀장, 리서처, 작가 배치해 줘"*라고 요청하면 아래 명령어를 실행합니다:

```bash
# 통합 CLI (권장)
python ./herdr_os.py team create --name "마케팅팀" --roles "팀장:agy:pm_leader,리서처:claude:researcher,작가:codex:writer"

# 또는 스크립트 직접 실행
python ./scripts/create_team.py --team "마케팅팀" --roles "팀장:agy:전체 기획 및 검수,리서처:claude:트렌드 및 경쟁사 조사,작가:codex:원고 및 카피 작성"
```
- 자동으로 `./teams/마케팅팀/` 아래에 직원별 폴더(`p1_팀장`, `p2_리서처`, `p3_작가`)와 맞춤 지침서(`ROLE_GUIDE.md`, `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`) 및 팀 공유 수첩(`TEAM_MEMORY.md`)이 생성됩니다.
- 동시에 Herdr에 새 워크스페이스(`w2`, `w3`...)가 생성되고 직원 수만큼 창(Pane)이 분할됩니다.

## 2. 특정 창(`w1:p2` 등)에 직무 프리셋 부여하기
`./templates/roles/`에 준비된 5대 표준 직무 프리셋(`pm_leader`, `researcher`, `developer`, `writer`, `qa_reviewer`)을 특정 창에 즉시 배정할 수 있습니다:

```bash
python ./herdr_os.py role assign --pane w1:p2 --role researcher --agent claude --mission "경쟁사 기능 비교 조사 후 TEAM_MEMORY.md 요약"
```

## 3. 다른 창/다른 팀 직원에게 업무 지시 및 결과 수령하기
```bash
# 전체 창 목록 확인
herdr pane list

# 특정 창(예: w2:p2)에 명령 또는 프롬프트 전송
herdr pane run w2:p2 "주어진 키워드를 조사해서 ../TEAM_MEMORY.md 에 요약 기록해줘"

# 결과 화면 읽기
herdr pane read w2:p2 --source recent-unwrapped --lines 40
```
