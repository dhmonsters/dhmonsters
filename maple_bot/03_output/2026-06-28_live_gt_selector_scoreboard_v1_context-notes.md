# 2026-06-28 live GT selector scoreboard context notes

## 목표 정의

프레임별 정답 선택기가 아니라, 처음 타겟의 신분을 보류하고 복원할 수 있는 시간축 판별기를 만든다.

GT는 선택기에 넣지 않는다. GT는 선택기가 고른 경로를 나중에 채점하는 라벨로만 사용한다.

## 진행 내용

선택기 scoreboard를 추가해서 best-family upper와 selected-family score를 분리했다. 이로써 16/16 upper가 실제 live 선택기 성능으로 오해되지 않도록 했다.

처음 event score는 occlusion 후보를 과신해서 0/16이었다. occlusion을 제외하면 switch 후보를 과신해서 1/16 수준이었다. 따라서 문제는 후보 부족이 아니라 후보 종류별 사전점수가 너무 강한 것이다.

occlusion/switch 조합을 제한하는 event judge를 추가했지만, switch 후보가 여전히 과신되어 0/16이었다.

초반 흰 도형이 보이는 구간의 track을 anchor로 쓰는 meta gate를 추가했다. 이 방식은 live에서도 사용 가능한 신호이며, 선택기 점수는 4/16까지 상승했다.

## 실패 분류

- `occlusion 과신`: 보정 후보가 정답처럼 정지하거나 부드럽게 보여도 실제 타겟이 아닐 수 있다.
- `switch 과신`: 허용된 전환 조합이어도 전환 시점과 원본 신분이 틀리면 바로 다른 도형으로 갈아탄다.
- `anchor 근접 오판`: 초반 anchor에 가까운 후보가 끝까지 맞는 후보와 다를 수 있다.
- `box 내부 중심 복원 부족`: 같은 후보 박스 안에서 어떤 상대 위치가 진짜 중심인지 아직 live 신호로 결정하지 못한다.

## 다음 계획

1. anchor gate 위에 release/merge lifecycle 신호를 추가한다.
2. occlusion 후보마다 원본 path와 보정 path의 차이, 배경 예상 위치와의 충돌 비율, release 직후 후보 재결합 여부를 점수화한다.
3. switch 후보는 전환 시점 전후의 속도/가속도 불연속과 anchor 신분 유지 여부를 함께 본다.
4. box-rel 후보는 같은 candidate box 내부 상대 위치 후보들을 묶어서, 시간축에서 가장 일관된 offset을 고르는 judge를 따로 만든다.
5. 선택기 점수가 4/16에서 올라가면 puzzle.py 통합 검토로 넘어가고, 올라가지 않으면 새 관측 신호를 추가한다.
