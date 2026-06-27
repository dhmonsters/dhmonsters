# trace live 후보 상한 계획

## 목표

`_guarded_trace_report.py`에서도 `live_max_candidates`를 바꿔 같은 worst frame을 비교할 수 있게 한다.

## 성공 기준

- `trace_clip`이 `live_max_candidates` 인자를 받는다.
- backfill에 해당 값이 전달된다.
- markdown config에 `live_max`가 표시된다.
- CLI에서 `--live-max-candidates`를 사용할 수 있다.
- 관련 테스트가 통과한다.

## 이유

대표 sweep에서 후보 상한을 키우면 guarded 후보는 살아나지만 최종 선택은 그대로였다. 이제 프레임 단위 trace도 같은 후보 상한으로 찍어야 selector가 어떤 후보를 무시하는지 볼 수 있다.
