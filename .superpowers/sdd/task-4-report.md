Status: DONE

Files changed:
- shorts_growth_agent/backend/tests/test_script_planner.py
- shorts_growth_agent/backend/src/shorts_agent/services/script_planner.py
- shorts_growth_agent/backend/src/shorts_agent/main.py

Red result (new fix test):
- `cd shorts_growth_agent/backend && .\.venv\Scripts\python.exe -m pytest tests/test_script_planner.py -q`
- 실패: `test_generate_filters_forbidden_terms_from_user_facing_outputs`
- `AssertionError: assert not True` (금칙어가 title_candidate/subtitle/voice_text/image_prompt에 남아있음)

Green result (fix verification):
- `cd shorts_growth_agent/backend && .\.venv\Scripts\python.exe -m pytest tests/test_script_planner.py -q`
- 통과: `2 passed, 1 warning in 0.01s`
- `cd shorts_growth_agent/backend && .\.venv\Scripts\python.exe -m pytest tests/test_health.py tests/test_models.py tests/test_trend_scoring.py tests/test_script_planner.py -q`
- 통과: `8 passed, 1 warning in 0.68s`

Concerns:
- `.pytest_cache` 경로 쓰기 권한으로 인해 `PytestCacheWarning`이 계속 1건씩 남습니다.
- `shorts_growth_agent/backend/src/shorts_agent/main.py`의 하네스 라우터 마운팅은 요청대로 제거했습니다.

### Follow-up: category forbidden coverage

Status: DONE

Files changed:
- `shorts_growth_agent/backend/tests/test_script_planner.py`
- `shorts_growth_agent/backend/src/shorts_agent/services/script_planner.py`

Red result (new category-path test):
- `cd shorts_growth_agent/backend && .\\.venv\\Scripts\\python.exe -m pytest tests/test_script_planner.py -q`
- 재현 가능한 고정 실패는 현재 브랜치에서는 없었고, 신규 카테고리 경로 단언 테스트는 기존 상태에서 통과했습니다.

Green result:
- `cd shorts_growth_agent/backend && .\\.venv\\Scripts\\python.exe -m pytest tests/test_script_planner.py -q`
- 통과: `3 passed, 1 warning in 0.02s`
- `cd shorts_growth_agent/backend && .\\.venv\\Scripts\\python.exe -m pytest tests/test_health.py tests/test_models.py tests/test_trend_scoring.py tests/test_script_planner.py -q`
- 통과: `9 passed, 1 warning in 0.64s`

Concerns:
- `.pytest_cache` 경로 쓰기 권한으로 인한 `PytestCacheWarning`은 테스트 실행마다 동일하게 남습니다.
- `plan.category`는 기존 입력값을 유지하도록 했고, 금지어 정리는 템플릿/이미지프롬프트 생성에 사용되는 정제본에만 적용됩니다.
