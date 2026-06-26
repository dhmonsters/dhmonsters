# 2026-06-26 selector shadow live 튜닝 결과

병합 gate 기본값을 실제 w/h 분포 기준으로 조정했다.

## 측정 기준

- `.wjsonl` 16개 파일, 1521프레임, 27697개 후보를 측정했다.
- 후보 size p50은 121.1, p95는 160.4, p99는 169.0이었다.
- 프레임별 max size p95는 174.2였다.
- 프레임별 max/median ratio p99는 1.31이었다.

## 적용값

- `merge_min_size=175.0`.
- `merge_size_ratio=1.30`.
- `merge_context_frames=6`.

## 샘플 확인

`000_0614_121417.jsonl`은 이전 낮은 기준에서는 allowed였지만, 실제 f5269 후보 max size가 128.0, ratio가 1.099라 새 기준에서는 blocked가 맞다.

`000_0614_233218.jsonl`은 `--limit 180 --emit-every 10 --max-candidates 12 --live-max-candidates 12`에서 bg_split 1개와 rescue_allowed 1개가 나왔다. 강한 크기 outlier가 있는 경우 gate가 살아난다.

## 결론

새 기준은 약한 bg_split false-positive를 줄이고, w/h outlier가 있는 구조적 병합 프레임만 selector rescue 후보로 통과시키는 방향이다.
