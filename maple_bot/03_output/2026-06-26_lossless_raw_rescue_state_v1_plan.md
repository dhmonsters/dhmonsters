# 무손실 raw rescue 상태 v1 계획.

## 목표.

raw 후보를 항상 selector 경쟁 family로 넣지 않고, track이 후보에서 멀어지거나 끊기는 구간에서만 제한적으로 raw 후보를 여는 rescue 상태를 검증한다.

## 성공 기준.

- rescue 상태가 track 정상 구간에서는 track 근처 후보를 유지한다.
- track이 탈선한 구간에서는 prediction과 후보 신호를 이용해 raw 후보로 재획득할 수 있다.
- 무손실 2판에서 기존 track-only replay와 rescue path 점수를 비교한다.
- 실패하면 어느 조건에서 실패했는지 프레임 단위로 기록한다.

## 진행 순서.

1. rescue path 생성 테스트를 먼저 추가한다.
2. track snap과 raw rescue를 분리한 경로 생성 함수를 구현한다.
3. 무손실 2판을 채점한다.
4. 결과를 보고서와 context notes에 남긴다.
5. 관련 테스트와 문법 검증 후 이번 파일만 커밋한다.
