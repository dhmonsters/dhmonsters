# 2026-06-29 라이브 dry-run 테스트 게이트 컨텍스트

## 핵심 정의

프레임별 정답 선택기가 아니라, 처음 타겟의 신분을 보류하고 복원할 수 있는 시간축 판별기를 라이브 경로에서 검증한다.

## 5~7 결정

첫 인게임 테스트는 마우스 제어를 끈 dry-run으로 시작한다. 이때 중요한 것은 퍼즐 감지, 후보 검출, selector family 선택, 녹화 지속 여부를 확인하는 것이며, 실제 클릭 성공 여부는 다음 단계로 미룬다.

GUI에는 `마우스 제어` 체크박스를 둔다. `--live-dry-run`으로 실행하면 체크가 꺼진 상태로 시작한다. 체크가 꺼져 있으면 solver 판단은 유지하지만 `MOUSE_MOVE` 이벤트는 `reason=disabled`로 남아야 한다.

세션 종료 후 `live_session_review.md`를 자동 생성한다. 이 파일은 trace만 읽으며 GT 좌표나 정답 경로를 사용하지 않는다.

## 검증 결과

- `tests.test_puzzle_live_session_review`, `tests.test_puzzle_planet_live`, `tests.test_puzzle_live_watch`, `tests.test_transparent_family_selector_runtime`, `tests.test_transparent_selector_shadow` 묶음 89개 테스트 통과.
- GUI 마우스 제어 체크박스, CLI dry-run, runtime mouse flag, 캡처 ROI 관련 pytest 스타일 테스트는 직접 호출 방식으로 통과.
- `_live_temporal_selector_gt_score.py --summary-only` 결과는 16/16, 평균 오차 26.3176px로 유지됐다.
