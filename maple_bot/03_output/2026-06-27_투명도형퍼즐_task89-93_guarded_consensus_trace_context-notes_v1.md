# Task89-93 context notes

## Start Decision

Task84-88에서 GT 근처 후보가 후보군 안에 있는데도 guarded path가 먼 후보 섬을 유지하는 것을 확인했다. 이제 cost를 바꾸기 전에, live에서 실제로 쓸 수 있는 다른 family 신호가 GT 근처를 가리키는지 확인해야 한다.

## Hypothesis

raw continuity, raw rank, phase catalog 계열 family 중 일부가 GT 근처 후보를 이미 가리키고 있다면 guarded cost에 합의 보너스를 넣을 수 있다. 반대로 모든 family가 먼 후보 섬을 가리킨다면 cost 수정이 아니라 새 관측 신호가 필요하다.

## Implementation Result

`_guarded_trace_report.py`에 live family point의 GT 기준/선택점 기준 근접 목록을 추가했다. 또한 raw candidate의 score rank와 `live8` 포함 여부를 함께 표시했다.

## Trace Result

`000_0614_121417`에서 GT 근처 후보는 존재했지만 `live_max_candidates=8` 안에 들어오지 못했다. f5337의 GT nearest candidate는 GT에서 1.3px였지만 score rank 11이라 live8 밖이었다. f5347의 GT nearest candidate도 GT에서 15.2px였지만 score rank 19라 live8 밖이었다.

live family points 역시 GT 근처 후보를 직접 가리키지 못했다. f5337의 GT 기준 nearest live family는 d_gt=93.1px였고, f5347은 d_gt=61.7px였다. 즉 family consensus 보너스만으로는 정답 후보를 끌어오기 어렵다.

`000_0614_111417`에서는 GT nearest candidate가 rank 11, d_gt=56.1px였고, 일부 live8 후보는 있었지만 GT와 충분히 가깝지 않았다.

## Next Decision

다음 단계는 guarded cost 조정보다 먼저 `live_max_candidates` 후보 상한을 sweep해야 한다. 현재 top8 컷이 정답 후보를 버리는 장면이 확인됐기 때문이다. 추천 sweep은 `live_max_candidates=8,16,24`와 기존 guarded 조합 `min_bg=2`, `match_px=16`, `max_step=180`이다.
