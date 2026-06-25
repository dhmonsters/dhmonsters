# 16GT 선택 family 실제 경로 재생 검증 계획

## 목표
- 캐시 기반 16GT baseline selector가 고른 family 이름을 실제 local-box path generator에서 다시 생성해 채점한다.
- 단순 캐시 점수가 아니라 현재 코드에 연결 가능한 family인지 확인한다.
- 결과가 16/16이면 다음 단계인 GT 없는 selector 설계로 넘어간다.

## 절차
1. 선택된 family 이름을 clip별로 추출한다.
2. clip별 GT 프레임 기준으로 local-box family path를 다시 생성한다.
3. 선택 family가 실제 생성 결과에 존재하는지 확인한다.
4. 존재하면 GT와 평균 오차를 채점한다.
5. 전체 16판 성공 수와 평균 오차를 기록한다.

## 성공 기준
- 16개 GT clip 모두 평균 오차 40px 이하를 통과한다.
- 누락 family가 없어야 한다.
