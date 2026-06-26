# 2026-06-26 selector shadow 병합 맥락 gate 결과

`rescue_allowed`를 bg_split family 단독 조건에서 bg_split family와 병합 후보 맥락 동시 조건으로 바꿨다.

## 관측 결과

기존 빠른 batch 10개 샘플은 `bg_split 4`, `rescue_allowed 4`였다.

병합 gate를 붙이고 w/h 없는 오래된 JSONL만 보면 `bg_split 4`, `rescue_allowed 0`이 된다. 원인은 예전 JSONL 후보에는 w/h가 없어서 후보 크기가 기본값 24px로만 보이기 때문이다.

그래서 `.wjsonl` sidecar를 자동으로 참고하도록 backfill을 보강했다.

## sidecar 적용 샘플

`--files 6 --limit 80 --emit-every 10 --max-candidates 12 --live-max-candidates 12`로 실행했다.

- 실행 시간은 약 76초였다.
- shadow 프레임은 33개였다.
- bg_split 프레임은 4개였다.
- rescue_allowed 프레임은 1개였다.
- `000_0614_121417.jsonl`에서 f5269가 통과했다.

의미는 병합 gate가 전부 차단하는 벽이 아니라, w/h가 있는 데이터에서 병합 후보가 확인된 bg_split만 통과시키는 필터라는 점이다.

## 주의

후보 수를 12개로 늘리면 batch가 느려진다. 탐색 기본값은 8개 후보로 유지하고, 병합 gate 검증은 sidecar가 있는 의심 클립에 대해 12개 후보로 좁혀 돌리는 편이 낫다.
