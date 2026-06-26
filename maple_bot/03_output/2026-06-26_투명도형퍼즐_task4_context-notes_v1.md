# 투명도형 퍼즐 Task 4 컨텍스트 노트

- `planet_solver_noauth.py`의 실시간 캡처 구조를 바로 옮기지 않고, 먼저 replay 가능한 입력 소스를 만든다.
- 모든 `FramePacket.board_frame`은 `PuzzleSession.board_roi` 기준 crop 결과로 고정한다.
- 이미지 시퀀스는 파일명 정렬을 기본으로 하고, timestamp는 기본 30fps 간격으로 만든다.
- JSONL 리플레이는 우선 `payload.source_frame_path`를 읽는 최소 adapter로 시작한다.
- 실시간 화면 감시는 UI 단계에서 붙이고, 이번 Task 4에는 넣지 않는다.
- RED 확인 결과는 `ModuleNotFoundError: No module named 'core.puzzle.frame_source'`였고, 기대한 실패였다.
- GREEN 확인은 번들 Python과 `.codex_pydeps`를 함께 잡아 OpenCV/NumPy 기반 수동 테스트로 수행했다.
- `VideoFrameSource`는 같은 인터페이스로 추가했지만, 이번 테스트 범위는 이미지 시퀀스와 JSONL replay adapter에 집중했다.
