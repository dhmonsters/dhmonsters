# 무손실 selector shadow replay v1 결과

기존 무손실 JSONL의 `cands`와 `track`을 입력으로 `selector_shadow`를 오프라인 재생했다.

## 점수

| 클립 | 이상 프레임 | 채점 프레임 | raw 후보 oracle | 기존 track | shadow replay |
|---|---|---:|---|---|---|
| `000_0621_165634` | `f0031.png` | 92 | mean 7.4px, median 6.1px, max 26.0px, n 92, 성공 | mean 195.3px, median 196.5px, max 578.1px, n 72, 실패 | mean 172.6px, median 191.6px, max 425.9px, n 69, 실패 |
| `000_0621_180636` | 없음 | 120 | mean 9.8px, median 6.6px, max 49.1px, n 120, 성공 | mean 11.4px, median 5.6px, max 240.6px, n 120, 성공 | mean 15.9px, median 8.5px, max 98.9px, n 113, 성공 |

## 프레임별 비교

### `000_0621_165634`.

- track worst는 `f83 578.1px`, `f78 566.2px`, `f82 565.3px`.
- shadow worst는 `f81 425.9px`, `f80 422.2px`, `f79 415.4px`.
- 둘 다 있는 69프레임 중 shadow가 5px 이상 개선한 프레임은 24개, 5px 이상 악화한 프레임은 16개다.
- 가장 큰 개선은 `f83`에서 track 578.1px → shadow 305.0px이다.
- 하지만 평균 172.6px로 여전히 실패다.

### `000_0621_180636`.

- track worst는 `f0 240.6px`, `f1 120.7px`, `f2 56.6px`, `f94 49.1px`.
- shadow worst는 `f115 98.9px`, `f84 98.7px`, `f69 90.3px`.
- 둘 다 있는 113프레임 중 shadow가 5px 이상 개선한 프레임은 3개, 5px 이상 악화한 프레임은 32개다.
- 가장 큰 악화는 `f84`에서 track 2.1px → shadow 98.7px이다.
- 평균 기준으로는 성공이지만 기존 track보다 안정적이지 않다.

## 결론

- raw 후보 oracle은 2/2 성공이므로 후보 안에는 답이 있다.
- 기존 `track`만 anchor로 삼은 shadow replay는 1/2 성공이다.
- 실패판에서는 큰 오차를 일부 줄였지만 정답 경로로 복귀하지 못했다.
- 성공판에서는 기존 track보다 흔들리는 프레임이 많다.
- 따라서 다음 단계는 selector 승격이 아니라 raw 후보 기반 anchor family를 추가하는 것이다.
