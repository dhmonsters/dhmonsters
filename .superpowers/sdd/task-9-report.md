# Task 9 실행 보고

## 변경 파일
- `shorts_growth_agent/backend/src/shorts_agent/api/projects.py`
- `shorts_growth_agent/backend/src/shorts_agent/main.py`
- `shorts_growth_agent/backend/tests/test_api_projects.py`
- `.superpowers/sdd/task-9-report.md`

## Red 테스트(구현 전 확인된 실패)
- `.\.venv\Scripts\python.exe -m pytest tests/test_api_projects.py -q`
- 실패 원인: `create_app()` 기본 경로/세션 초기화와 인메모리 DB 공유 이슈로 라우트 동작이 깨짐.
- 주요 에러:
  - `sqlite3.OperationalError: no such table: video_projects`
  - `sqlite3.OperationalError: unable to open database file`
  - `requests.exceptions.HTTPError: 404` 패턴(예상 라우트 미등록)

## Green 테스트(최종 통과)
- `.\.venv\Scripts\python.exe -m pytest tests/test_api_projects.py -q`
  - `3 passed, 1 warning in 0.72s`
- `.\.venv\Scripts\python.exe -m pytest tests/test_health.py tests/test_models.py tests/test_trend_scoring.py tests/test_script_planner.py tests/test_subtitle_sync.py tests/test_source_recommender.py tests/test_render_manifest.py tests/test_performance_analysis.py tests/test_api_projects.py -q`
  - `22 passed, 1 warning in 0.81s`

## 컨트롤러 검증

- `shorts_growth_agent/backend/src/shorts_agent/db.py`에 생긴 의도치 않은 인코딩 변경을 원복했습니다.
- 테스트 데이터를 계획서의 `게임 이슈` / `게임` / `업데이트` 예시와 맞췄습니다.
- `.\.venv\Scripts\python.exe -m pytest tests/test_api_projects.py -q` → `3 passed`
- `.\.venv\Scripts\python.exe -m pytest tests/test_health.py tests/test_models.py tests/test_trend_scoring.py tests/test_script_planner.py tests/test_subtitle_sync.py tests/test_source_recommender.py tests/test_render_manifest.py tests/test_performance_analysis.py tests/test_api_projects.py -q` → `22 passed`

## 리뷰 반영

- 리뷰어가 `app = create_app()` import 시 기본 DB 파일이 생성될 수 있는 부작용을 Important로 지적했습니다.
- `test_create_app_does_not_create_sqlite_file_until_project_route`를 먼저 추가했고, 기존 구현에서 앱 생성 직후 DB 파일이 존재해 실패하는 것을 확인했습니다.
- `create_app()`은 `database_url`만 보관하고, 프로젝트 API 세션이 처음 필요할 때 DB 엔진과 테이블을 초기화하도록 지연 초기화로 변경했습니다.
- `.\.venv\Scripts\python.exe -m pytest tests/test_api_projects.py -q` → `4 passed`
- `.\.venv\Scripts\python.exe -m pytest tests/test_health.py tests/test_models.py tests/test_trend_scoring.py tests/test_script_planner.py tests/test_subtitle_sync.py tests/test_source_recommender.py tests/test_render_manifest.py tests/test_performance_analysis.py tests/test_api_projects.py -q` → `23 passed`
