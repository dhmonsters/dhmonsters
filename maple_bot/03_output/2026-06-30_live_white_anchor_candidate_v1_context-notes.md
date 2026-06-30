# 라이브 흰색 시작 도형 후보 보강 컨텍스트 노트

## 고정된 문제 정의

이번 실패는 퍼즐 감지 문제가 아니다. `PUZZLE_ACTIVATED`와 녹화는 성공했지만, `CANDIDATES`가 37프레임 전부 0개라 시간축 판별기가 입력을 받지 못했다.

## 근거

- 세션 `20260630_110258_001`에서 `PUZZLE_ACTIVATED`는 1회 발생했다.
- `CANDIDATES`는 37회 모두 `count=0`, `raw_count=0`이었다.
- `IDENTITY_STATE`는 37회 모두 `LOST / no_identity`였다.
- `TEMPORAL_SELECTOR`는 37회 모두 `none / no_points`였다.
- `MOUSE_MOVE`는 37회 모두 `False / no_target`이었다.
- 0번 프레임 스냅샷에는 흰색 삼각형이 선명하게 보였다.

## 결정

YOLO 후보만 기다리면 시작점부터 후보가 비어 시간축 판별기가 작동하지 않는다. 준비 시간의 흰색 도형은 정체성 시작점이므로 `white_anchor` 후보로 직접 생성해 후보 목록의 앞에 둔다.

## 다음 검증 기준

인게임 테스트 로그에서 최소한 첫 프레임 근처에 `white=1`, `merged=1`, `IDENTITY INIT_VISIBLE`, `TEMP target`, `MOUSE moved`가 보여야 한다.

