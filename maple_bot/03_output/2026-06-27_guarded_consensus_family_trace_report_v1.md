# guarded consensus family trace 요약

- clip: `000_0614_121417`
- config: min_bg=2, match_px=16.0, shape_pct=6.0, max_step=180.0, live_max=16

## 확인된 개선

- row 80에서 `guarded_decal_identity_consensus_center_mild_state_mild`가 `[167,184]`를 냈고 GT와 17.9px였다.
- row 79에서 같은 consensus family가 `[156,179]`를 냈고 GT와 21.5px였다.

## 남은 문제

- row 81, 84, 85의 worst frame에서는 consensus family가 GT top5에 들어오지 못했다.
- 최종 selector는 consensus family를 선택하지 않았다.

## 다음 판단

다음 단계는 selector shadow가 guarded consensus family를 후보로 받았을 때 모델 점수상 왜 선택하지 않는지 확인하는 것이다. 필요하면 GT-free selector의 feature row에 consensus source prior를 주거나, health rescue 단계에서 guarded consensus를 별도 rescue 후보로 평가해야 한다.
