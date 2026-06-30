# 2026-06-30 puzzle alarm sound v1 context notes

## Fixed Definition

프레임별 정답 선택기가 아니라, 처음 타겟의 신분을 보류하고 복원할 수 있는 시간축 판별기를 만든다.

## Decision

이번 변경은 추적 성능 개선이 아니라 사용자가 감지 사실을 놓치지 않게 하는 알림 경로 보강이다.
기존 UI에 `퍼즐 감지 알람` 체크박스가 있었지만, `PUZZLE_ACTIVATED` 이벤트가 실제 소리 재생으로 이어지지 않았다.

## Runtime Behavior

퍼즐 감지 이벤트가 들어오면 체크박스를 확인한다.
켜져 있으면 알람 핸들러를 실행하고 `ALARM sound played`를 로그에 남긴다.
같은 세션에서 같은 이벤트가 다시 들어오면 `ALARM duplicate skipped`를 남기고 소리를 반복하지 않는다.
체크박스가 꺼져 있으면 `ALARM disabled`를 남긴다.

## Why This Matters

인게임 테스트에서 CCTV와 로그만으로는 감지를 놓칠 수 있다.
소리 알람은 사용자가 즉시 개입할 수 있게 하는 안전 장치다.
