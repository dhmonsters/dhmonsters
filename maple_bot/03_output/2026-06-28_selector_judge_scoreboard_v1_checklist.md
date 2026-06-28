# 2026-06-28 selector judge scoreboard v1 체크리스트

- [x] 현재 GT 16개 selected-family 기준선을 고정했다.
- [x] confidence 안정성 심판 테스트를 추가했다.
- [x] 배경 동일성 감점 심판 테스트를 추가했다.
- [x] 여러 심판 점수 합산 selector 테스트를 추가했다.
- [x] 심판 점수판 모듈을 구현했다.
- [x] `_live_family_pool_gt_score.py`의 selector에 점수판을 연결했다.
- [x] switch 후보가 기존 선택을 과하게 덮지 않도록 rescue gate를 추가했다.
- [x] poor anchor 상태에서는 switch보다 occlusion 보정 후보를 먼저 보도록 고정했다.
- [x] cont10, cont13 switch 계열은 총점 1등이 아니라 전환 창의 phase로 시점을 고르게 했다.
- [x] GT 16개에서 selected-family 16/16을 확인했다.
- [x] 관련 단위 테스트를 실행했다.
- [x] 변경 내용을 다음 세션이 이어받을 수 있게 컨텍스트 노트에 기록했다.
