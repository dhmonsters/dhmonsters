# Shorts Growth Agent

쇼츠 기획/운영 API 중심의 테스트 프로젝트입니다.

## Development

### Backend install and run

- `cd C:\Users\PC\Desktop\02_work\05_AI\shorts_growth_agent\backend`
- `python -m venv .venv` (첫 세팅만)
- `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"`
- `.\.venv\Scripts\python.exe -m uvicorn shorts_agent.main:app --reload`

### Frontend install and run

- `cd C:\Users\PC\Desktop\02_work\05_AI\shorts_growth_agent\frontend`
- `npm.cmd install`
- `npm.cmd run dev`
- `npm.cmd run build`

### Verification commands

- Backend smoke test: `.\.venv\Scripts\python.exe -m pytest tests/test_mvp_flow.py -q`
- Backend 전체 테스트: `.\.venv\Scripts\python.exe -m pytest -q`
- Frontend 테스트: `cmd /c "subst X: C:\Users\PC\Desktop\02_work\05_AI\shorts_growth_agent\frontend && X: && npm.cmd test"`
- Frontend 빌드: `cmd /c "subst X: C:\Users\PC\Desktop\02_work\05_AI\shorts_growth_agent\frontend && X: && npm.cmd run build"`

Temp 권한 이슈가 나면 백엔드 폴더에서 아래처럼 로컬 임시 폴더를 지정합니다.

- `New-Item -ItemType Directory -Force .\.pytest_tmp | Out-Null; $env:TMP=(Resolve-Path .\.pytest_tmp).Path; $env:TEMP=(Resolve-Path .\.pytest_tmp).Path; .\.venv\Scripts\python.exe -m pytest -q`
