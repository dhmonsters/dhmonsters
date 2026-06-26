# 투명도형 퍼즐 Task 10 컨텍스트 노트

- Task 10의 목적은 실제 분석 루프 연결이 아니라 UI 골격과 진입점을 고정하는 것이다.
- 첫 화면은 랜딩 페이지가 아니라 바로 분석 콘솔이다.
- 중앙은 CCTV 화면, 왼쪽은 입력과 ROI 설정, 오른쪽은 상태와 evidence 요약, 아래는 타임라인과 로그다.
- 실제 PyQt6는 현재 번들 Python에 없으므로 smoke test는 fake Qt 모듈로 objectName 계약을 검증한다.
- 실제 실행 환경에서는 `PyQt6`와 기존 `core_ui.theme.build_qss()`를 사용한다.
- `PuzzleConsoleWindow`는 기존 UI 흐름을 참고해 좌측 입력, 중앙 CCTV, 우측 분석, 하단 타임라인과 로그를 첫 화면으로 배치했다.
- `puzzle.py`는 GUI 진입점과 추후 headless replay 연결 지점을 함께 제공한다.
- Task 10 smoke test 3개, Task 1부터 Task 10까지의 수동 회귀 테스트 32개, 새 파일 AST 파싱 8개를 통과했다.
- 사용자가 커밋을 뒤로 미루기로 했으므로 이번 단계는 변경사항을 커밋하지 않는다.
