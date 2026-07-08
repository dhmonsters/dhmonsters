# Shorts Growth Agent

쇼츠 기획/운영 API 중심의 테스트 프로젝트입니다.

## MVP 사용 흐름

1. 백엔드와 프론트를 실행합니다.
2. 프론트 화면에서 카테고리와 키워드를 선택합니다.
3. `후보 검색`을 눌러 한국 인기 영상 후보를 확인합니다.
4. `이 후보로 대본 만들기`를 누르면 프로젝트와 대본 초안이 생성됩니다.
5. 각 단계의 `커스터마이징` 입력란에서 검색, 대본, 음성, 편집, 출력 기준을 조정합니다.

`SHORTS_YOUTUBE_API_KEY`가 없으면 한국 샘플 트렌드 데이터로 동작합니다. 키를 넣으면 YouTube 인기 영상 API를 우선 사용하고, 호출 실패 시 샘플 데이터로 fallback합니다.

## Development

### Backend install and run

- `cd C:\Users\PC\Desktop\02_work\05_AI\shorts_growth_agent\backend`
- `python -m venv .venv` (첫 세팅만)
- `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"`
- `.\.venv\Scripts\python.exe -m uvicorn shorts_agent.main:app --reload`
- API 확인: `http://127.0.0.1:8000/api/health`

### Frontend install and run

- `cd C:\Users\PC\Desktop\02_work\05_AI\shorts_growth_agent\frontend`
- `npm.cmd install`
- `npm.cmd run dev`
- `npm.cmd run build`
- 화면 확인: `http://127.0.0.1:5173/`

### Verification commands

- Backend smoke test: `.\.venv\Scripts\python.exe -m pytest tests/test_mvp_flow.py -q`
- Backend 전체 테스트: `.\.venv\Scripts\python.exe -m pytest -q`
- Frontend 테스트: `cmd /c "subst X: C:\Users\PC\Desktop\02_work\05_AI\shorts_growth_agent\frontend && X: && npm.cmd test"`
- Frontend 빌드: `cmd /c "subst X: C:\Users\PC\Desktop\02_work\05_AI\shorts_growth_agent\frontend && X: && npm.cmd run build"`

Temp 권한 이슈가 나면 백엔드 폴더에서 아래처럼 로컬 임시 폴더를 지정합니다.

- `New-Item -ItemType Directory -Force .\.pytest_tmp | Out-Null; $env:TMP=(Resolve-Path .\.pytest_tmp).Path; $env:TEMP=(Resolve-Path .\.pytest_tmp).Path; .\.venv\Scripts\python.exe -m pytest -q`
