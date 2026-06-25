# 2026-06-25 local-box family 계획

## 목표

기존 family 경로가 후보 박스 중심에서 약간 밀려 실패하는 판을 위해, family 주변 후보 박스 내부점 중 시간축이 가장 자연스러운 경로를 새 family로 만든다.

## 현재 근거

- 후보 박스 내부 oracle은 16/16 상한을 가진다.
- 111417, 124417, 062325는 기존 whole-family가 40px을 조금 넘지만, 주변 후보 박스 내부점으로 보정하면 성공한다.
- 모든 family에 local-box variant를 붙인 하드판 진단에서 111417, 124417, 000258, 062325가 성공 family를 확보했다.

## 접근

1. 각 family의 anchor point 주변 후보 박스를 고른다.
2. 박스 내부 grid point를 상태로 만든다.
3. Viterbi로 시간축이 매끄러운 내부점 경로를 고른다.
4. `lb_smooth`, `lb_loose`, `lb_free` 세 variant를 만든다.
5. 먼저 best-family 상한을 확인하고, 이후 selector는 별도 단계로 다룬다.

## 성공 기준

- synthetic 테스트에서 잘못된 anchor 대신 매끄러운 내부점 경로를 고른다.
- 하드판 best-family 상한이 16/16에 도달하는지 확인한다.
