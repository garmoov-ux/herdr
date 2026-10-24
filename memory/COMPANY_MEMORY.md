# 🏛️ 전사 공유 영구 기억 노트 (COMPANY_MEMORY.md)

> 이 파일은 헤르메스(Hermes) 아키텍처의 장기 기억(Long-term Memory) 저장소입니다.  
> 각 팀(`w1`, `w2`, `w3`...)의 팀장 AI는 주요 작업이 완료되거나 새로운 결정이 내려질 때마다 이 파일 하단에 날짜와 함께 핵심 요약을 기록합니다.

---

## 📅 기록 로그 (History)

### [2026-10-24] Herdr × Hermes CLI AgenticOS 오픈소스 패키징 및 고도화 완료
- **100% 경로 독립형(Portable) 브레인 전환:** `./AGENTS.md`, `./CLAUDE.md`, `./GEMINI.md`, `./memory/`, `./skills/`, `./templates/roles/` 전체를 상대 경로 기반으로 표준화하여 어떤 PC/폴더에 `git clone`하더라도 즉시 동작하도록 구축.
- **5대 직무 프리셋 템플릿 구축 (`./templates/roles/`):** 총괄 기획 팀장(`pm_leader`), 수석 리서처(`researcher`), 수석 개발자(`developer`), 콘텐츠·문서 작가(`writer`), 품질·보안 검수자(`qa_reviewer`) 표준 페르소나 완비.
- **멀티 메신저 게이트웨이 구축 (`./gateways/messenger_bridge.py`):** 외부 패키지 설치 없이 순수 Python 표준 라이브러리만으로 Telegram, Slack, Discord 양방향 알림 및 원격 명령(`/panes`, `/newteam`, `/assign`, `/read`, `/use`, 답장 전송) 지원.
- **원클릭 크로스플랫폼 인스톨러 제공:** Windows(`install.ps1`, `start_all.bat`) 및 macOS/Linux(`install.sh`) 원클릭 설치·실행 스크립트 구축 완료.
- **1팀 본부(`w1_main_hq`) 기본 역할 가이드 구축:** `./teams/w1_main_hq/TEAM_OVERVIEW.md`에 1팀 본부의 좌석별(`w1:p1`~`p5`) 표준 직무(팀장·리서처·개발자·작가·검수자), 4단계 협업 프로토콜 및 제어 명령어 체계 문서화 완료.
