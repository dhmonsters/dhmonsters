# Raw Candidate Live Family 계획

## 목표

현재 source 상한 9/16을 raw 후보 family로 끌어올리고, 중심이 틀어진 병합 프레임은 box-offset family로 보강한다.

## 구현 설계

1. raw rank family는 현재 프레임 후보 score 순서대로 후보 중심을 노출한다.
2. raw continuity family는 직전 위치와 가장 가까운 후보를 이어붙여 후보 ID 없이도 부드러운 raw 후보 경로를 만든다.
3. raw box-offset family는 continuity family가 큰 병합 후보를 따라갈 때, 후보 중심 대신 직전 속도 예측점을 병합 박스 안으로 clamp한다.
4. 채점 도구는 raw family를 `raw_candidate` source로 묶어 상한을 확인한다.

## 성공 기준

- raw rank/continuity/box-offset 동작 테스트가 통과한다.
- `_live_source_upper_score.py` 문법 검사가 통과한다.
- 16개 GT source 상한에서 raw 후보 source가 추가로 성공하는지 확인한다.
