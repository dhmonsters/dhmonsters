Status: DONE

Files changed:
- shorts_growth_agent/backend/tests/test_subtitle_sync.py
- shorts_growth_agent/backend/src/shorts_agent/adapters/tts.py
- shorts_growth_agent/backend/src/shorts_agent/services/subtitle_sync.py
- shorts_growth_agent/backend/src/shorts_agent/api/projects.py

Red test result:
- `cd shorts_growth_agent/backend && .\.venv\Scripts\python.exe -m pytest tests/test_subtitle_sync.py -q`
- 실패: `ModuleNotFoundError: No module named 'shorts_agent.services.subtitle_sync'` (테스트 추가 직후 모듈 미존재 상태 확인)

Green test result:
- `cd shorts_growth_agent/backend && .\.venv\Scripts\python.exe -m pytest tests/test_subtitle_sync.py -q`
- 통과: `1 passed, 1 warning in 0.01s`
- `cd shorts_growth_agent/backend && .\.venv\Scripts\python.exe -m pytest tests/test_health.py tests/test_models.py tests/test_trend_scoring.py tests/test_script_planner.py tests/test_subtitle_sync.py -q`
- 통과: `10 passed, 1 warning in 0.68s`

Scope-alignment retest:
- `cd shorts_growth_agent/backend && .\.venv\Scripts\python.exe -m pytest tests/test_subtitle_sync.py -q`
- 통과: `1 passed, 1 warning in 0.01s`
- `cd shorts_growth_agent/backend && .\.venv\Scripts\python.exe -m pytest tests/test_health.py tests/test_models.py tests/test_trend_scoring.py tests/test_script_planner.py tests/test_subtitle_sync.py -q`
- 통과: `10 passed, 1 warning in 0.69s`

Concerns:
- `.pytest_cache` 경로 권한 이슈로 `PytestCacheWarning`이 계속 남습니다 (`Access is denied`).
