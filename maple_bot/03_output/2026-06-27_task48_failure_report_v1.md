# Task48 temporal identity 실패 분류

| clip | reason | first bad frame | temporal | raw center | raw box |
|---|---|---:|---:|---:|---:|
| `000_0614_111417` | box_internal_reconstruction | 64 | 200.6 | 50.9 | 35.7 OK |
| `000_0614_114417` | success | - | 10.2 OK | 10.0 OK | 0.8 OK |
| `000_0614_121417` | candidate_selection | 81 | 102.4 | 16.0 OK | 7.5 OK |
| `000_0614_124417` | candidate_selection | 65 | 69.1 | 35.3 OK | 21.7 OK |
| `000_0614_185318` | candidate_selection | 76 | 101.7 | 37.4 OK | 22.4 OK |
| `000_0614_204718` | candidate_selection | 75 | 92.7 | 27.8 OK | 14.8 OK |
| `000_0614_220518` | success | - | 13.8 OK | 13.0 OK | 2.1 OK |
| `000_0614_233218` | candidate_selection | 124 | 77.6 | 34.6 OK | 20.1 OK |
| `000_0615_000258` | candidate_selection | 55 | 135.2 | 35.5 OK | 22.2 OK |
| `000_0615_015619` | success | - | 10.1 OK | 10.1 OK | 2.2 OK |
| `000_0615_022618` | success | 105 | 20.7 OK | 13.7 OK | 3.8 OK |
| `000_0615_025624` | success | 63 | 20.2 OK | 20.2 OK | 10.8 OK |
| `000_0615_035137` | success | - | 11.7 OK | 11.7 OK | 2.8 OK |
| `000_0615_042024` | success | - | 12.1 OK | 12.1 OK | 1.6 OK |
| `000_0615_044401` | candidate_selection | 63 | 112.2 | 18.1 OK | 6.9 OK |
| `000_0615_062325` | candidate_selection | 61 | 112.0 | 33.3 OK | 20.4 OK |

## 요약

- `box_internal_reconstruction`: 1.
- `candidate_selection`: 8.
- `success`: 7.

## 해석

실패 9개 중 8개는 raw center oracle이 성공하므로 후보 선택 실패다.

1개는 raw center가 실패하고 raw box만 성공하므로 박스 내부 중심 복원 문제다.

이번 단계에서 먼저 올릴 대상은 후보를 더 만드는 작업이 아니라 후보별 비용 함수다.
