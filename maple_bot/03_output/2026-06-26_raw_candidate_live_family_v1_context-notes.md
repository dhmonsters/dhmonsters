# Raw Candidate Live Family 컨텍스트 노트

## 2026-06-26

- source gap partition 결과 raw 후보 중심 oracle은 15/16, raw 후보 박스 oracle은 16/16이었다.
- 이미 작업트리에 raw rank/continuity family 1차 구현이 있었다. 이 변경은 되돌리지 않고 이어서 사용한다.
- 다음 보강은 111417처럼 후보 중심이 틀어진 병합 박스에서 직전 속도 예측점을 박스 내부 위치로 쓰는 box-offset family다.
- 병합 여부는 기존 `TransparentLiveFamilyPool._is_merge_like_candidate` 기준을 재사용한다.
- raw MHT는 중심 후보 경로 선택용이므로 grid를 펼치지 않는다. 병합 박스 내부 위치 복원은 box-offset family가 맡는다.
- raw MHT는 7개 실패 클립 확인에서도 1분 이상 걸려 기본 비활성화로 내렸다. 기본 live source는 rank, continuity, box-offset만 사용한다.
- source 상한 채점에는 `--raw-fast`를 추가했다. 이 모드는 phase catalog와 bg MHT를 끄고 raw family 성능만 빠르게 본다.
- 1차 raw-fast 채점은 실패 7개 중 015619만 성공했다. 후보가 있는데도 family에 안 올라오는 판이 있어 raw rank/continuity 기본 가설 수를 늘린다.
- 가설 수를 늘려도 1/7이었다. 초기 continuity에 타겟이 안 타거나 중간에 바뀌는 판이 있어, 매 프레임 spawn 가능한 가벼운 raw beam family를 추가한다.
- raw beam 추가 후에도 실패 7개 raw-fast 상한은 1/7이었다. 단순 경로 생성 문제가 아니라 후보별 비용 함수가 약한 문제로 봐야 한다.
- 다음은 raw beam candidate cost에 `anom`, `viol`, background identity, ring/background 감점을 넣는 쪽이 맞다.
