# phase-catalog engine replay 결과

## 요약

- replay 어댑터 수정 전에는 모든 프레임이 `white_anchor`로 들어가 엔진이 실제 후보 선택을 거의 하지 않았다.
- replay 어댑터를 수정해 `frame_index < prep_end`에서만 `white_anchor`를 넘기도록 했다.
- 수정 후 `transparent_engine`은 16개 GT에서 0/16이었다.
- 평균은 `inf`로 나왔다. 일부 클립은 후보 선택 이후 GT coverage 자체가 부족했다.

## 결과

| clip | mean | coverage | result |
|---|---:|---:|---|
| `000_0614_111417` | 414.0 | 1.00 | FAIL |
| `000_0614_114417` | 292.0 | 1.00 | FAIL |
| `000_0614_121417` | 407.8 | 1.00 | FAIL |
| `000_0614_124417` | 438.3 | 1.00 | FAIL |
| `000_0614_185318` | 368.2 | 1.00 | FAIL |
| `000_0614_204718` | 201.7 | 1.00 | FAIL |
| `000_0614_220518` | 404.1 | 1.00 | FAIL |
| `000_0614_233218` | inf | 0.00 | FAIL |
| `000_0615_000258` | 576.0 | 0.94 | FAIL |
| `000_0615_015619` | 1039.2 | 0.94 | FAIL |
| `000_0615_022618` | 482.0 | 1.00 | FAIL |
| `000_0615_025624` | 1371.6 | 0.55 | FAIL |
| `000_0615_035137` | 516.8 | 0.88 | FAIL |
| `000_0615_042024` | inf | 0.00 | FAIL |
| `000_0615_044401` | 125.0 | 1.00 | FAIL |
| `000_0615_062325` | 345.9 | 1.00 | FAIL |

## 판단

`TransparentPuzzleEngine` 단독은 현재 solver source로 쓰기 어렵다.
`BackgroundCatalog` 기반 후보 제거는 synthetic에서는 맞지만 실제 판에서는 안전한 selector source가 아니다.
다음은 offline `phase_catalog` 또는 `decal_filter_mht`의 구조를 live family pool에 맞게 다시 만드는 쪽이다.
