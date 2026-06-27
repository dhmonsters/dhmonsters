# Task75-78 guarded signal stats plan

## Goal

`guarded_decal_identity`가 `background_signal`에서 막히는 원인을 숫자로 분해한다.

## Success Criteria

- `live_family.debug.guarded_decal_identity`의 숫자 필드를 reason별로 요약한다.
- GT replay report에 reason counts와 debug stats가 함께 표시된다.
- batch report에도 같은 debug stats가 표시된다.
- 대표 2개 clip replay에서 `background_frames`, `expected_frames`, `background_ratio`, `max_step` 분포를 확인한다.
- 관련 unittest와 문법 검사를 통과한다.

## Steps

1. debug stats 요약 테스트를 먼저 추가한다.
2. GT replay scorer에 stats 요약 함수를 추가한다.
3. batch report에 동일한 stats 요약을 추가한다.
4. 대표 replay 리포트를 재생성한다.
5. context notes에 결과와 다음 판단을 기록한다.
6. 커밋한다.
