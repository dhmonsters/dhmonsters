# 투명도형퍼즐 Task 20 컨텍스트 노트

## 결정
- 이번 단계는 이미지 파일 preview만 다룬다.
- 영상 `video_path#frame=N` 출처는 상태 문자열로만 표시한다.
- 실제 overlay drawing은 후보 박스와 선택 path가 준비되는 다음 단계에서 붙인다.

## 이유
- Task 19에서 frame source metadata가 준비되었으므로, 다음 최소 UI 가치는 사람이 replay frame을 눈으로 확인할 수 있는 preview 슬롯이다.
- preview 라벨을 먼저 고정하면 이후 timeline click, overlay, split view를 같은 라벨 위에 확장할 수 있다.

## 진행 기록
- 중앙 CCTV 영역에 `puzzleCctvFramePreview` 라벨을 추가했다.
- `FRAME_REPLAYED`의 `source_frame_path`가 실제 파일이면 `QPixmap`으로 preview 라벨에 설정한다.
- 마지막으로 로드한 preview 경로는 `current_cctv_source_path`에 저장한다.
- `test_puzzle_*` 스모크 묶음 49개가 통과했다.
- `puzzle_console.py`와 `test_puzzle_console_smoke.py`의 `py_compile` 검증이 통과했다.
