# 2026-06-28 box grid live selector v3 체크리스트

- [x] 기존 box-rel 후보가 box 내부 grid 역할을 하는지 확인한다.
- [x] grid selector 단위 테스트를 먼저 추가한다.
- [x] grid selector를 live-usable 신호만 사용하도록 구현한다.
- [x] GT 16개에서 grid selector 단독 점수를 측정한다.
- [x] 현재 selector와 결합할지 판단한다.
- [x] 테스트와 diff check를 통과했는지 남긴다.
- [x] 결과와 다음 계획을 문서화한다.

## 성공 기준

- GT를 선택 입력으로 사용하지 않는다.
- grid selector 단독 또는 결합 점수가 4/16보다 올라가면 다음 단계로 채택한다.
- 10/16 이상이면 `puzzle.py` 연결 전 검토 후보로 승격한다.

## 측정 결과

- 기존 selector는 4/16이다.
- box grid selector 단독은 5/16이다.
- box grid threshold hybrid는 6/16이다.
- 개선은 있었지만 `puzzle.py` 연결 기준인 10/16에는 아직 부족하다.
