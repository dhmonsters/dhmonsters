# 무손실 raw rescue 상태 v1 context notes.

## 시작 판단.

- raw candidate oracle은 무손실 2판 모두 성공한다.
- raw 후보를 `raw_rank*`, `raw_cont*` family로 상시 투입하면 selector가 잘못된 family를 과선택한다.
- 따라서 raw 후보는 항상 열린 후보가 아니라, track 탈선 또는 비검출 상태에서만 쓰는 rescue 상태로 다뤄야 한다.

## 이번 단계의 가설.

- track이 정상일 때는 track에 가장 가까운 후보가 좋은 anchor다.
- track과 후보가 과도하게 멀어지거나 track이 사라지면 기존 velocity prediction 근처 후보를 우선한다.
- 단, 단순 continuity만 쓰면 데칼에 붙을 수 있으므로 실제 점수는 무손실 2판으로 바로 확인한다.

## 실행 결과.

- greedy rescue는 `000_0621_165634`를 mean 195.3px에서 90.7px까지 낮췄지만 실패했다.
- greedy rescue는 `000_0621_180636`에서 mean 13.5px로 성공을 유지했다.
- beam rescue는 여러 가지를 유지했지만 `000_0621_165634` best mean 94.7px로 실패했다.
- 실패 시작은 f49가 아니라 f43이다. f36~f42는 커서 GT 제외 구간이지만 solver 상태는 그 사이에 탈선한다.
- ShapeYolo 박스 재검출은 현재 Python 환경에 `ncnn`이 없어 비활성이다.

## 해석.

- 단일 상태와 beam 상태 모두 continuity만으로는 부족하다.
- `000_0621_165634`의 f43 이후에는 정답 가지와 데칼 가지가 둘 다 매끄럽다.
- 따라서 다음 단계는 위치 기반 rescue가 아니라 후보별 시각 패치 evidence 또는 재검출 w/h evidence가 필요하다.
