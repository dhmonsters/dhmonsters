# Task84-88 context notes

## Start Decision

Task79-83 sweep에서 threshold 완화는 후보 생성량을 늘렸지만 guarded mean error가 크게 올라갔다. 이는 path가 배경 후보나 엉뚱한 raw 후보로 점프하는 상황일 가능성이 높다.

## Hypothesis

worst frame의 선택점과 후보 목록을 같이 보면, 큰 오차가 `background match 부족`, `max_step 완화로 인한 먼 후보 선택`, `GT 근처 후보는 있었지만 scoring이 못 고른 상황` 중 어디에 가까운지 분해할 수 있다.

## Implementation Result

`_guarded_trace_report.py`를 추가해 guarded emitted path의 worst frame을 추적하도록 했다. 각 item에는 선택점 기준 가까운 후보와 GT 기준 가까운 후보를 모두 기록한다.

대표 조합은 `min_bg=2`, `match_px=16`, `shape_pct=6`, `max_step=180`으로 실행했다. Python 파일 쓰기는 기존과 같이 `PermissionError`가 발생했지만, 콘솔 출력은 성공했고 같은 내용을 산출물 파일로 보존했다.

## Trace Result

`000_0614_121417`에서 결정적 증거가 나왔다. f5337은 guarded 선택점이 GT에서 433.2px 떨어져 있었지만, GT 기준 가장 가까운 후보는 1.3px였다. f5347도 GT 근처 15.2px 후보가 있었고, f5351도 3.3px 후보가 있었다.

즉 이 구간은 후보 검출 실패가 아니다. 정답 후보는 후보군 안에 있는데, guarded path scoring이 먼 후보 섬을 identity로 유지하고 있다.

`000_0614_111417`도 선택 후보보다 GT에 훨씬 가까운 후보가 존재했다. 다만 GT 기준 가까운 후보가 56.1px, 74.0px, 81.3px 수준이라 두 번째 clip만큼 명확한 정답 후보는 아니다.

## Next Decision

다음 단계는 threshold를 더 완화하는 것이 아니라 cost 함수에 live에서 쓸 수 있는 path 품질 신호를 추가하는 것이다. 후보는 세 가지다.

- raw continuity 또는 phase prediction과 합의하는 후보에 보너스.
- 큰 점프 직전/직후 후보섬 전환에 감점.
- background expected와 너무 안정적으로 맞는 후보섬에 추가 감점.
