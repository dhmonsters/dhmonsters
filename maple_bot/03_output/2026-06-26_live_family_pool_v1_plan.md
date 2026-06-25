# live family pool 계획

## 목표

16/16 캐시 selector가 기대하던 실제 family 재료를 live 루프에서도 만들 수 있게 한다.
이번 단계는 전체 solver 교체가 아니라, sliding Viterbi 계열 family를 `planet_solver_noauth`의 selector shadow 입력으로 공급하는 것이다.

## 작업 순서

1. `TransparentLiveFamilyPool` 테스트를 먼저 만든다.
2. 후보 history, gray frame, white anchor를 받아 sliding Viterbi family path를 생성한다.
3. `balanced_viterbi_center_mild_state_mild`, `strict_transition_viterbi_center_mild_state_mild` 이름으로 최신 family point를 내보낸다.
4. `planet_solver_noauth.py`의 selector shadow anchors에 이 family point들을 추가한다.
5. 16GT와 무손실 noauth-equivalent를 다시 채점해 점수 변화를 확인한다.

## 성공 기준

- 단위 테스트가 통과한다.
- `planet_solver_noauth.py` 문법 검증이 통과한다.
- shadow family가 pre-box/box/engine 세 anchor만 쓰던 상태보다 더 다양한 family point를 만든다.
- noauth-equivalent 점수가 악화되면 조종 좌표에는 연결하지 않는다.
