# 투명도형 퍼즐 task48 기준선 16GT 채점 결과

## 실행

- 실행 대상: `_fast_gt_score.py`.
- 실행 결과 파일 직접 저장은 Python 권한 문제로 실패했다.
- 콘솔 출력 기준으로 결과를 기록한다.

## 요약

| source | success | mean_error |
|---|---:|---:|
| track | 0/16 | 107.7px |
| engine | 0/16 | nan |
| temporal_identity | 7/16 | 68.9px |
| raw_center_oracle | 15/16 | 23.7px |
| raw_box_oracle | 16/16 | 12.2px |

## 실패 clip

| clip | temporal_identity | raw_center_oracle | raw_box_oracle |
|---|---:|---:|---:|
| 000_0614_111417 | 200.6px | 50.9px | 35.7px OK |
| 000_0614_121417 | 102.4px | 16.0px OK | 7.5px OK |
| 000_0614_124417 | 69.1px | 35.3px OK | 21.7px OK |
| 000_0614_185318 | 101.7px | 37.4px OK | 22.4px OK |
| 000_0614_204718 | 92.7px | 27.8px OK | 14.8px OK |
| 000_0614_233218 | 77.6px | 34.6px OK | 20.1px OK |
| 000_0615_000258 | 135.2px | 35.5px OK | 22.2px OK |
| 000_0615_044401 | 112.2px | 18.1px OK | 6.9px OK |
| 000_0615_062325 | 112.0px | 33.3px OK | 20.4px OK |

## 해석

raw box oracle은 16/16이므로 후보 박스 내부에는 답이 있다.

raw center oracle이 15/16인 점을 보면 대부분의 실패는 후보 부재가 아니라 후보 선택과 박스 내부 중심 복원 문제다.
