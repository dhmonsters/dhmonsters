# 2026-06-28 live GT identity signal v2 체크리스트

- [x] occlusion 후보에 원본 path 대비 보정량 점수를 추가했다.
- [x] occlusion 후보에 배경 충돌 비율 점수를 추가했다.
- [x] occlusion 후보에 release 이후 재결합 여부 점수를 추가했다.
- [x] switch 후보에 전환 전후 속도/가속도 불연속 감점을 추가했다.
- [x] switch 후보에 anchor 신분 유지 감점을 추가했다.
- [x] box-rel 후보에 같은 box 내부 상대 위치 일관성 judge를 추가했다.
- [x] 세 신호의 단위 테스트를 먼저 추가하고 실패를 확인했다.
- [x] 구현 후 관련 단위 테스트 통과를 확인했다.
- [x] GT 16개 기준 live-usable selector 점수를 재측정했다.
- [x] 추가 후보 신호인 clip signal과 shortlist Viterbi를 비교했다.

## 결과

- 이전 selector 점수: 4/16.
- 이번 신호 추가 후 selector 점수: 4/16.
- clip signal 단독: 최대 2/16.
- shortlist consensus Viterbi: 3/16.
- 결론: 이번 세 신호는 구현됐지만 selector 성능을 올리지는 못했다.
