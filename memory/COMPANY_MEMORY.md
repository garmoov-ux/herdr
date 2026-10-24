# 🏛️ 전사 공유 영구 기억 노트 (COMPANY_MEMORY.md)

> 이 파일은 헤르메스(Hermes) 아키텍처의 장기 기억(Long-term Memory) 저장소입니다.  
> 각 팀(`w1`, `w2`, `w3`...)의 팀장 AI는 주요 작업이 완료되거나 새로운 결정이 내려질 때마다 이 파일 하단에 날짜와 함께 핵심 요약을 기록합니다.

---

## 📅 기록 로그 (History)

### [2026-10-24] Herdr × Hermes × Telegram × Pixel Agents 통합 구축 완료
- **Herdr 0.9.5 설치 완료:** Windows 네이티브 및 WSL Ubuntu 양쪽 설치, `claude`, `codex`, `antigravity-cli`(`agy`) 공식 훅 연동 완료.
- **텔레그램 양방향 브릿지 구축:** `F:\herdr\scripts\herdr_telegram_bridge.py`를 통해 `@hskang_herdr_bot`과 모든 Herdr 창(`w1`, `w2`...) 연결 및 Pixel Agents 캐릭터 상태 중계 완료.
- **클립보드 이미지 즉시 붙여넣기:** Herdr `config.toml`에 `Alt + V` (및 `Ctrl+B` → `i`) 단축키 등록 완료.
- **멀티 팀·직원 역할 자동 부여 시스템:** `F:\herdr\scripts\create_team.py` 및 `F:\herdr\teams\` 구조 구축 완료.
