# 2026-06-30 live preview all frames v1 plan

## 목표

라이브 투명도형 세션의 `snapshots` 폴더에 모든 프레임의 preview PNG를 저장한다.

## 성공 기준

- 새 라이브 녹화에서 `live_preview_000000.png`부터 모든 프레임 번호가 저장된다.
- 기존 throttling 테스트를 모든 프레임 저장 테스트로 바꾼다.
- 요청받은 기존 세션 `20260630_183859_001`의 누락 PNG를 가능한 범위에서 보강한다.

## 변경 범위

- `core/puzzle/live_recording.py`.
- `tests/test_puzzle_live_recording.py`.
