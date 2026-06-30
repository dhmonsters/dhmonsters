# 2026-06-30 live no target diagnosis v1 plan

## Goal

세션 `20260630_103258_001`에서 알림과 녹화는 됐지만 마우스가 움직이지 않은 원인을 확인하고, 다음 테스트에서 같은 문제가 로그에 명확히 드러나게 한다.

## Findings

- 세션 산출물은 정상 저장됐다.
- `raw_cctv.mkv`, `overlay.mkv`, `board_crop.mkv`, `trace.jsonl`, `report.md`, `live_session_review.md`가 생성됐다.
- trace 기준 `PUZZLE_ACTIVATED`는 1회 발생했다.
- `CANDIDATES`는 37프레임 모두 `count=0`이었다.
- `MOUSE_MOVE`는 37프레임 모두 `reason=no_target`이었다.
- 저장 프레임에는 흰색 도형이 보이므로 마우스 입력 실패가 아니라 후보 검출 실패다.

## Fix Direction

- `PlanetNoAuthDetector`가 `planet_live_solver` 의존성 import 실패 시 `planet_yolo_verify`로 모델 로드를 폴백한다.
- 모델 로드 실패나 detector 비활성 상태를 `CANDIDATES.debug`에 기록한다.
- UI 로그에서 후보 0개일 때 detector 오류를 바로 보여준다.
- 같은 세션에서 `recording start` 로그가 반복되지 않게 한다.
