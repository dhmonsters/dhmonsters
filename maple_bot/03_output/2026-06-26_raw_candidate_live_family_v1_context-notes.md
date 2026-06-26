# Raw Candidate Live Family 컨텍스트 노트

## 2026-06-26

- source gap partition 결과 raw 후보 중심 oracle은 15/16, raw 후보 박스 oracle은 16/16이었다.
- 이미 작업트리에 raw rank/continuity family 1차 구현이 있었다. 이 변경은 되돌리지 않고 이어서 사용한다.
- 다음 보강은 111417처럼 후보 중심이 틀어진 병합 박스에서 직전 속도 예측점을 박스 내부 위치로 쓰는 box-offset family다.
- 병합 여부는 기존 `TransparentLiveFamilyPool._is_merge_like_candidate` 기준을 재사용한다.
