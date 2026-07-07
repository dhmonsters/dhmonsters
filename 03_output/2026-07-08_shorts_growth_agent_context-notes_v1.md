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
- Task 2는 데이터 모델, 저장소, 스키마, 모델 테스트까지 구현했고 별도 리뷰어가 승인했다.
- `datetime.utcnow` 경고는 Python 3.12에서 반복 재현되어 `_utc_now()` 함수로 대체했고, `-W error::DeprecationWarning` 기준에서도 `3 passed in 0.43s`를 확인했다.
- Task 1+2 합산 테스트는 `.\.venv\Scripts\python.exe -m pytest tests/test_health.py tests/test_models.py -q` 기준 `4 passed in 0.67s`로 통과했다.
- Task 3는 YouTube 인기 영상 신호 타입, 교체 가능한 YouTube 어댑터, 상승 속도 기반 트렌드 점수화, `/api/trends` 라우트를 구현했고 별도 리뷰어가 승인했다.
- Task 3 최종 검증은 `.\.venv\Scripts\python.exe -m pytest tests/test_trend_scoring.py -q` 기준 `2 passed in 0.07s`, Task 1-3 합산은 `6 passed in 0.73s`로 통과했다.
- `/api/trends` 직접 API 테스트는 리뷰어가 Minor 보강으로 언급했다. 계획상 API 통합 단계인 Task 9에서 다시 다룬다.
- Task 4는 대본 하네스 기본값, 결정적 ScriptPlanner, 장면 필드, 금칙어 필터링 테스트를 구현했고 재리뷰에서 승인됐다.
- 최초 리뷰에서 금칙어가 일부 사용자 노출 필드에 남는 문제가 발견되어, `title_candidate`, `subtitle`, `voice_text`, `image_prompt` 전체에 금칙어 제거를 적용했다.
- `main.py` 하네스 라우터 연결은 Task 4 원 계획 범위를 벗어난 것으로 판단되어 제거했다. 하네스 API 연결은 나중 API 통합 단계에서 다시 다룬다.
- Task 4 최종 검증은 `tests/test_script_planner.py` 기준 `3 passed in 0.01s`, Task 1-4 합산은 `9 passed in 0.70s`로 통과했다.
- Task 5는 교체 가능한 TTS 어댑터 인터페이스, silent WAV placeholder, 자막 cue 균등 분배 서비스를 구현했고 별도 리뷰어가 승인했다.
- `api/projects.py`는 Task 9 API 통합을 위한 라우터 placeholder만 남겼고, 아직 `main.py`에는 연결하지 않았다.
- Task 5 최종 검증은 `tests/test_subtitle_sync.py` 기준 `1 passed in 0.01s`, Task 1-5 합산은 `10 passed in 0.67s`로 통과했다.
- Task 6는 AI 이미지 어댑터, 밈 어댑터, 장면별 소스 추천 서비스를 구현했고 별도 리뷰어가 승인했다.
- `clip_candidate`는 항상 `requires_user_review=True`로 반환해 사용자가 구간과 사용 가능 여부를 확인하도록 유지한다.
- Task 6 최종 검증은 `tests/test_source_recommender.py` 기준 `2 passed in 0.01s`, Task 1-6 합산은 `12 passed in 0.73s`로 통과했다.
- Task 7은 9:16 렌더 매니페스트, FFmpeg 명령 빌더, 렌더 명령 미리보기 라우터를 구현했고 재리뷰에서 승인됐다.
- 리뷰에서 렌더 API 미리보기 직접 테스트가 부족하다는 지적이 있어 `preview_render_command()` 테스트를 추가했다.
- Windows 경로 구분자 문제는 `RenderManifest`의 `Path` 계약을 유지하고, `FfmpegCommandBuilder`에서 `Path.as_posix()`로 명령 토큰을 생성하는 방식으로 해결했다.
- Task 7 최종 검증은 `tests/test_render_manifest.py` 기준 `3 passed in 0.35s`, Task 1-7 합산은 `15 passed in 0.76s`로 통과했다.
