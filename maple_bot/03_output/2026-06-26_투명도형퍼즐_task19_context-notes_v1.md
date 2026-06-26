# 투명도형퍼즐 Task 19 컨텍스트 노트

## 결정
- 이번 단계는 실제 QLabel 이미지 렌더링이 아니라 frame source metadata 연결까지만 다룬다.
- 이미지 렌더링과 overlay 탐색은 다음 단계에서 `current_frame_sources`를 기반으로 붙인다.
- 영상 입력은 아직 개별 이미지 파일이 없으므로 `video_path#frame=N` 문자열로 추적 가능한 출처만 남긴다.

## 이유
- UI가 frame 번호와 원본 경로를 먼저 알아야 타임라인 클릭, CCTV 렌더링, overlay 렌더링을 안정적으로 붙일 수 있다.
- trace schema에 frame 출처가 남으면 replay 결과를 나중에 재검증하기 쉬워진다.

## 진행 기록
- `FramePacket.source_path`를 추가했다.
- 이미지 시퀀스와 JSONL replay는 실제 resolved image path를 보존한다.
- 영상 replay는 `video_path#frame=N` 형식의 출처 문자열을 남긴다.
- headless replay의 `FRAME_REPLAYED` 이벤트에 `source_frame_path`가 기록된다.
- UI는 `FRAME_REPLAYED`를 받으면 `current_frame_sources`와 CCTV 상태 라벨을 갱신한다.
- `test_puzzle_*` 스모크 묶음 47개가 통과했다.
- 수정 파일 7개의 `py_compile` 검증이 통과했다.
