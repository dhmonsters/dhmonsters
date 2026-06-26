# 투명도형 퍼즐 Task 12 컨텍스트 노트

- Task 12의 목적은 추적 성공률 검증이 아니라 입력, 세션, trace, recorder, report가 한 번에 이어지는 smoke를 만드는 것이다.
- headless replay는 GUI와 PyQt6를 import하지 않아야 한다.
- 이미지 시퀀스와 JSONL replay를 같은 세션 산출물 구조로 처리한다.
- 기본 처리 상한은 5프레임으로 둔다.
- RED는 `run_gui()`가 headless에서도 PyQt6를 먼저 import하는 실패로 확인했다.
- 구현 후 `python puzzle.py --headless --replay <path>` 경로는 PyQt6 없이 replay를 처리한다.
- Task 12 수동 테스트 2개를 통과했다.
- Task 1부터 Task 12까지 수동 회귀 테스트 38개를 통과했다.
- 새 변경 파일 AST 파싱 7개를 통과했다.
- 번들 Python에는 `pytest`가 없어 `python -m pytest ...` 명령은 실행할 수 없었다.
