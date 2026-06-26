# Task 18 Context Notes

## 결정
- Timeline은 상세 그래프가 아니라 최근 이벤트 요약으로 시작한다.
- 표시 대상은 `CANDIDATES`, `EVIDENCE`, `IDENTITY_STATE`로 제한한다.
- `FRAME_REPLAYED`는 프레임마다 너무 자주 발생하므로 현재 단계에서는 표시하지 않는다.

## 이유
- 이번 단계의 핵심은 replay 결과를 사람이 빠르게 확인하는 것이다.
- 자세한 시각화는 이후 CCTV 화면과 frame overlay가 붙은 뒤 확장하는 편이 안전하다.

## 진행 기록
- `puzzleTimelineDetail` 라벨을 추가해 최근 trace 이벤트를 한 줄로 표시한다.
- 후보, 근거, 정체성 상태 이벤트만 timeline에 누적한다.
- 최근 5개만 남겨 긴 replay에서도 UI 텍스트가 과하게 커지지 않게 했다.
- `test_puzzle_*` 스모크 묶음 45개가 통과했다.
