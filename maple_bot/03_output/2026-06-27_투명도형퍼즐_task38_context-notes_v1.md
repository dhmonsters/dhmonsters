# Task 38 맥락 노트

## 결정
- Task37의 약한 후보 신호는 2/16까지 올렸지만 대부분의 배경 데칼을 구분하지 못했다.
- 이번에는 이전 실험에서 이미 만든 background identity 매칭을 frame cost로 직접 연결한다.

## 이유
- 초기 설계의 핵심은 타겟을 그 순간 구분하는 것이 아니라, 시간축에서 배경으로 설명되는 후보를 누적 감점하는 것이다.
- 배경 후보는 한 바퀴 전 위치와 모양으로 설명될 가능성이 높다.
- 타겟 후보는 같은 배경 ID로 오래 설명되면 안 된다.

## 신호 관찰
- 단일 frame에서 background position 매칭만 쓰면 정답 raw 후보도 자주 배경으로 매칭된다.
- 따라서 `matched_ratio` 자체를 frame cost로 쓰는 것은 위험하다.
- 나쁜 temporal 경로는 같은 background ID로 오래 이어지는 `run_identity_ratio`가 1.0인 경우가 많다.
- raw oracle은 matched가 있더라도 background ID가 자주 바뀌어 run이 낮은 경우가 많다.
- Task38 구현은 단일 frame 감점이 아니라 동일 background ID 장기 run 감점으로 가야 한다.
