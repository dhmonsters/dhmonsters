# Task48 변경 후 16GT 채점 결과

## 요약

| source | success | mean_error |
|---|---:|---:|
| track | 0/16 | 107.7px |
| engine | 0/16 | nan |
| temporal_identity | 7/16 | 68.9px |
| raw_center_oracle | 15/16 | 23.7px |
| raw_box_oracle | 16/16 | 12.2px |

## 결과

task48에서 색상 시간 감쇠 입력, 겹침 후보 비용, hold 이후 복원 보너스를 selector 구조에 추가했다.

기본값으로 활성화한 뒤에도 16GT 점수는 7/16으로 유지됐다.

즉 이번 변경은 구조 확장이며, 현재 실패 9개를 바로 복구하지는 못했다.

## 추가 진단

- 실패 클립은 대부분 `TRACK_CONFIDENT`만 나온다.
- hold 상태가 거의 열리지 않으므로 현재 실패는 겹침 상태머신 부족보다 후보 비용 함수 문제에 가깝다.
- keep/branch를 `48/8`에서 `160/16`까지 키워도 성공 개수는 7/16으로 유지됐다.
- `240/24`에서는 6/16으로 떨어졌다.
- 따라서 빔 폭 부족이 아니라 좋은 후보의 누적 비용이 아직 잘못 계산되는 문제다.

## 다음 관측 신호

후보 박스 내부 중심 복원과 후보별 appearance residual이 필요하다.

특히 `000_0614_111417`은 raw center oracle도 실패하고 raw box oracle만 성공하므로 박스 내부에서 타겟 중심을 복원하는 신호가 필요하다.

나머지 다수는 raw center oracle이 성공하므로 후보 선택 비용에 appearance 또는 local residual 신호를 추가해야 한다.
