# live 후보 상한 sweep 문맥 노트

## 시작 판단

직전 guarded consensus trace에서 `000_0614_121417`의 f5337, f5347 모두 GT 근처 raw 후보가 존재했지만 score rank가 각각 11, 19라 `live_max_candidates=8` 안에 들어오지 못했다.

따라서 다음 실험은 guarded cost 조정이 아니라 후보 상한을 `8,16,24`로 열었을 때 정답 근처 후보가 live family pool에 들어오는지 확인하는 것이다.

## 대표 2개 sweep 결과

`000_0614_111417`, `000_0614_121417` 기준으로 `min_bg=2`, `match_px=16`, `shape_pct=6`, `max_step=180`을 고정하고 `live_max_candidates=8,16,24`를 비교했다.

- `live_max=8`: guarded emitted 52, guarded mean 264.4, selected mean 169.3.
- `live_max=16`: guarded emitted 129, guarded mean 173.5, selected mean 169.3.
- `live_max=24`: guarded emitted 124, guarded mean 171.5, selected mean 169.3.

후보 상한을 늘리면 guarded 후보가 더 많이 살아나고 guarded 자체 평균 오차도 개선된다. 하지만 `guarded_selected_frames`는 계속 0이고 최종 `selected_mean`은 그대로다.

따라서 병목은 두 겹이다. 첫째, top8 후보 상한이 정답 근처 후보를 자른다. 둘째, 후보가 살아나도 최종 selector가 guarded 후보를 선택하지 않는다. 다음 단계는 후보 상한을 16으로 열어둔 상태에서 selector 비용 함수가 왜 guarded 후보를 이기게 만들지 못하는지 추적해야 한다.
