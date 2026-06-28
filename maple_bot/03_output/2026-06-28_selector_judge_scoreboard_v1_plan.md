# 2026-06-28 selector judge scoreboard v1 계획

핵심 문장은 다음과 같이 고정한다.

`프레임별로 그 순간 제일 그럴듯한 점을 찍는 솔버가 아니라, 처음 타겟의 신분을 시간축에서 보류하고 복원할 수 있는 판별기를 만든다.`

이번 단계의 목표는 후보를 더 많이 만드는 것이 아니라, 이미 생성된 후보 중에서 타겟 신분을 가장 잘 보존한 후보를 고르는 selector를 강화하는 것이다.

성공 기준은 다음과 같다.

- 라이브에서 사용할 수 있는 family pool과 selector 조합으로 GT 16개 selected-family 16/16을 통과한다.
- GT 정답 좌표를 selector feature로 직접 사용하지 않는다.
- 후보별 score는 candidate support, 배경 동일성, 겹침 후 분리, switch 시점, box offset 일관성 같은 라이브에서 계산 가능한 신호만 사용한다.
- 기존 box_grid가 충분히 강한 경우에는 점수판 1등이 있어도 덮지 않는다.
- 기존 선택이 약하거나 흔들린 경우에만 trusted rescue를 허용한다.

진행 순서는 다음과 같다.

1. 현재 기준선을 재확인한다.
2. confidence, background identity, occlusion, switch timing을 각각 심판으로 분리한다.
3. 심판 점수판을 selector에 연결한다.
4. 실패 clip에서 잘못 구출된 후보와 구출해야 할 후보를 분리한다.
5. rescue gate를 좁혀서 기존 성공 clip을 깨지 않게 한다.
6. GT 16개 전체를 다시 채점한다.
7. 16/16이 나오면 puzzle.py 연결 전 검토 단계로 넘긴다.
