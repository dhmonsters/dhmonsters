# 2026-06-26 selector shadow merge gate sweep 결과

## 구현 결과

- `backfill_selector_shadow_rows`와 batch report에 `merge_context_frames`, `merge_min_size`, `merge_size_ratio` 전달선을 추가했다.
- `_selector_shadow_merge_gate_sweep.py`를 추가했다.
- sweep 유틸리티는 selector backfill을 클립당 한 번만 수행하고, 캐시된 `merge_context.max_size/max_ratio`로 여러 gate를 비교한다.
- 리포트에는 클립 전체 최대값과 별도로 `bg_split` 순간의 `bg_max`, `bg_ratio`를 표시한다.

## 16개 GT 전체 sweep

- 조건: `_record_debug`, `--gt-dir _gt_frames`, `--limit 0`, `--emit-every 10`, `--max-candidates 8`, `--live-max-candidates 8`.
- gate: `loose=165/1.20`, `default=175/1.30`, `strict=190/1.40`.
- 결과 행: 48개.
- 전체 rescue allowed: 1개.

## 관찰

- `loose`에서만 `000_0614_233218.jsonl`이 1회 허용됐다.
- `default`와 `strict`에서는 16개 GT 모두 rescue 허용 0회였다.
- `bg_split`이 뜬 클립은 일부뿐이다. 예: `111417`, `220518`, `233218`, `015619`.
- `233218`의 `bg_split` 순간 값은 `bg_max=167.0`, `bg_ratio=1.138`이라 default 기준에는 못 미친다.
- 여러 클립에서 클립 전체 `merge_max`는 175 이상이어도 `bg_split` 순간의 `bg_max`는 0이거나 낮다. 따라서 gate 튜닝은 반드시 `bg_split` 순간 지표를 기준으로 봐야 한다.

## 다음 판단

- 단순히 `merge_min_size`를 낮추면 `233218`은 열 수 있지만, `111417` 같은 약한 bg_split도 같이 열릴 수 있다.
- 더 큰 병목은 `035137`처럼 필요한 순간에 `bg_split family` 자체가 선택되지 않는 경우다.
- 다음 단계는 `bg_split 선택 여부`와 `merge_context`를 분리해서, selector 후보군에 병합 맥락 기반 family를 더 직접적으로 넣는 쪽이 타당하다.
