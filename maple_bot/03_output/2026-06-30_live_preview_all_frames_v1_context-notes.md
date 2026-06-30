# 2026-06-30 live preview all frames v1 context notes

## 관찰

세션 `20260630_183859_001`은 `live_session_review.md` 기준 82프레임이다.

하지만 `snapshots`에는 `live_preview_000000.png`, `live_preview_000005.png`, `live_preview_000010.png`처럼 5프레임 간격 PNG만 있다.

원인은 `core/puzzle/live_recording.py`의 `_preview_stride = 5`와 `_write_live_preview()`의 `frame_index % stride` 조건이다.

## 결정

검증 단계에서는 프레임 단위 분석이 중요하므로 PNG 저장을 throttle하지 않는다. 녹화 중 생성되는 preview frame은 모든 프레임마다 저장한다.

## 검증 기록

기존 테스트를 `test_live_recording_keeps_memory_preview_and_writes_every_snapshot_frame`로 바꾸고, 7프레임 녹화 시 7장의 `live_preview_*.png`가 생기도록 기대값을 변경했다.

수정 전에는 이 테스트가 실패했다. 실제 저장 파일이 `live_preview_000000.png`, `live_preview_000005.png`뿐이었기 때문이다.

`_preview_stride` 필드와 `_write_live_preview()`의 stride 조건을 제거한 뒤 같은 테스트가 통과했다.

`live_recording.py`와 `test_puzzle_live_recording.py` 문법 검사도 통과했다.

기존 세션 `20260630_183859_001`은 `raw_cctv.mkv`와 `trace.jsonl`을 이용해 누락 PNG를 보강했다. 영상 82프레임 중 기존 17장은 유지했고, 빠진 65장을 생성했다. 최종 `snapshots`의 `live_preview_*.png` 개수는 82장이고 0~81번 누락은 없다.
