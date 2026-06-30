# 2026-06-30 live trace log clarity v1 context notes

## Fixed Definition

프레임별 정답 선택기가 아니라, 처음 타겟의 신분을 보류하고 복원할 수 있는 시간축 판별기를 만든다.

## Decision

이번 변경은 solver 성능 개선이 아니라 관측성 개선이다.
사용자는 인게임 테스트에서 “탐지 되고 있는지”를 즉시 알아야 하므로, UI 로그가 단순 대기 문구에서 끝나면 안 된다.

## Log Markers

- `PUZZLE DETECTED`는 퍼즐 팝업이 감지되어 세션 기록이 시작됐다는 뜻이다.
- `YOLO candidates`는 프레임에서 후보 도형이 몇 개 잡혔는지 보여준다.
- `TEMP target`은 시간축 판별기가 현재 따라가기로 선택한 지점을 보여준다.
- `MOUSE moved` 또는 `MOUSE not_moved`는 실제 입력 제어가 실행됐는지 보여준다.
- `IDENTITY`는 타겟 신분 유지 상태와 confidence를 보여준다.

## Why This Matters

라이브 실패를 분석할 때 먼저 구분해야 할 것은 감지 실패, 후보 부족, selector 오판, 마우스 입력 실패다.
이번 로그는 이 네 가지를 한 화면에서 분리해 보기 위한 최소 장치다.
