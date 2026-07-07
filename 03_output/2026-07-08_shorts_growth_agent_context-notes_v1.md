# Shorts Growth Agent Context Notes

## 2026-07-08

- 사용자는 1번 방식으로 진행하기로 선택했다. 이는 작업별 하위 에이전트 구현, 리뷰, 커밋 흐름을 의미한다.
- 현재 작업 범위는 새 폴더 `shorts_growth_agent`와 `03_output` 진행 문서로 제한한다.
- 기존 `maple_bot` 변경과 루트의 기존 미추적 파일은 건드리지 않는다.
- Git 메타데이터 쓰기 권한을 받아 작업별 커밋이 가능하도록 정리했다.
- 작업 브랜치는 `codex/shorts-growth-agent-mvp`를 사용한다.
- 구현은 `03_output/2026-07-08_shorts_growth_agent_implementation_plan_v1.md`의 순서를 따른다.
- Task 1은 하위 에이전트가 구현했고 별도 리뷰어가 승인했다.
- 작업자 환경에서 `python` 명령을 찾지 못해 최초 검증이 막혔으나, 컨트롤러가 번들 Python으로 `.venv`를 만들고 `.\.venv\Scripts\python.exe -m pytest tests/test_health.py -q`를 실행해 `1 passed in 0.35s`를 확인했다.
- 최신 Starlette 테스트 클라이언트 경고는 외부 의존성 경고 하나만 대상으로 하는 pytest 필터로 정리했다.
