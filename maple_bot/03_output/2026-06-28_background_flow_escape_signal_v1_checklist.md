# 2026-06-28 background-flow escape signal v1 체크리스트

- [x] 핵심 목표 문장을 루트 context-notes에 고정한다.
- [x] 현재 병목이 검출이 아니라 겹침 후 신분 복원임을 문서화한다.
- [x] "겹침 중 판단 보류, 분리 순간 배경 흐름 이탈 가지 선택" 원칙을 문서화한다.
- [ ] split/release event에서 배경 예상 위치에 남는 가지와 이탈하는 가지를 분리하는 테스트를 만든다.
- [ ] box size가 커지는 순간의 두 방향 확장 후보를 feature로 기록한다.
- [ ] 분리 후 몇 프레임 동안 background flow에서 벗어나는지 누적 점수화한다.
- [ ] GT 16개에서 단독 신호와 기존 selector 결합 점수를 비교한다.

## 성공 기준

- GT는 selector 입력으로 사용하지 않는다.
- 현재 selected-family 6/16보다 올라가면 채택한다.
- 10/16 이상이면 `puzzle.py` 연결 전 검토 후보로 승격한다.
