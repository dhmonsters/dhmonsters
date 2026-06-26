# Raw Candidate Live Source Upper 실패 7개 재채점

`--raw-fast --no-local-box`로 phase catalog와 bg MHT를 끄고, raw rank, continuity, box-offset, beam family만 빠르게 확인했다.

## 결과

| clip | GT | best raw_candidate | 성공 |
|---|---:|---:|---|
| `000_0614_111417` | 12 | 53.0px | 실패 |
| `000_0614_124417` | 41 | 67.6px | 실패 |
| `000_0614_204718` | 16 | 92.7px | 실패 |
| `000_0615_000258` | 17 | 53.3px | 실패 |
| `000_0615_015619` | 17 | 14.0px | 성공 |
| `000_0615_022618` | 15 | 42.4px | 실패 |
| `000_0615_044401` | 21 | 105.0px | 실패 |

## 요약

- raw-fast source 상한은 실패 7개 중 1개만 성공했다.
- raw 후보 중심 oracle은 6개를 더 풀 수 있었지만, 단순 rank, continuity, box-offset, beam family는 그 후보를 안정적으로 경로화하지 못했다.
- 다음 단계는 family 수를 더 늘리는 것이 아니라, 후보별 판별 신호를 넣어 beam 비용을 바꾸는 쪽이다.
- 특히 `anom`, `viol`, background identity 감점, ring/background texture 감점을 raw beam의 per-candidate cost로 합쳐야 한다.
