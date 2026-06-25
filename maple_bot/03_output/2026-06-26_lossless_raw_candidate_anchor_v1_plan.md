# 무손실 raw 후보 anchor v1 계획.

## 목표.

무손실 2판에서 raw 후보가 정답을 포함하는지 확인한 뒤, 그 후보들을 selector shadow replay의 path pool에 넣을 수 있게 만든다.

## 성공 기준.

- raw 후보 family 생성이 테스트로 검증된다.
- replay가 raw 후보 family를 선택할 수 있음이 테스트로 검증된다.
- 무손실 2판에서 기존 replay와 raw-anchor replay 점수를 비교한다.
- raw-anchor가 도움이 되는지, 아니면 다음 단계가 필요한지 숫자로 판단한다.

## 진행 순서.

1. raw 후보 rank/continuity family 테스트를 먼저 추가한다.
2. raw 후보 family 생성 함수를 구현한다.
3. replay에 opt-in 옵션으로 연결한다.
4. 무손실 2판을 채점한다.
5. 결과를 보고서와 context notes에 남긴다.
