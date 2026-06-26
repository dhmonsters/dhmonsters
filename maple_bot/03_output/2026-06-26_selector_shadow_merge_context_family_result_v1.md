# 2026-06-26 selector shadow merge context family 결과

## 변경 요약

- `TransparentLiveFamilyPool`이 기존 `bg_split_viterbi_center_mild_state_mild` MHT point를 `merge_context_center_mild_state_mild`로도 노출한다.
- `TransparentSelectorShadow`가 `merge_context` family를 선택했을 때도 병합 gate가 열려 있으면 rescue를 허용한다.
- batch report와 merge gate sweep은 `merge_context` family를 split-like rescue family로 같이 집계한다.

## 16개 GT 전체 재생 결과

- 조건: `limit=0`, `window=24`, `min_frames=8`, `shadow_min_frames=1`, `emit_every=10`, `max_candidates=8`, `live_max_candidates=8`, `merge gate=175/1.30`.
- 전체 `selector_shadow` 출력: 144회.
- split-like family 선택: 85회.
- rescue allowed: 13회.

## allowed가 생긴 클립

- `000_0614_124417.jsonl`: 3회, 첫 allowed `15793`.
- `000_0614_185318.jsonl`: 2회, 첫 allowed `5292`.
- `000_0614_233218.jsonl`: 5회, 첫 allowed `3778`.
- `000_0615_000258.jsonl`: 1회, 첫 allowed `1187`.
- `000_0615_062325.jsonl`: 2회, 첫 allowed `3766`.

## 남은 문제

- `000_0615_035137.jsonl`은 split-like family가 4회 선택됐지만 `merge_frames=0`이라 rescue가 열리지 않았다.
- 따라서 alias는 selector 선택 문제를 완화하지만, 035137류는 “박스 크기 기반 병합 감지 실패”를 별도 trace해야 한다.
- 다음 단계는 allowed가 새로 생긴 5개 클립의 GT 오차가 실제로 좋아졌는지 확인하고, 035137은 크기 외 merge 감지 신호를 추가하는 것이다.
