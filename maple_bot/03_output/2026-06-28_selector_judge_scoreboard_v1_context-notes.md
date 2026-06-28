# 2026-06-28 selector judge scoreboard v1 컨텍스트 노트

고정 문장.

`프레임별로 그 순간 제일 그럴듯한 점을 찍는 솔버가 아니라, 처음 타겟의 신분을 시간축에서 보류하고 복원할 수 있는 판별기를 만든다.`

작업 전 기준선은 `best_family 16/16`, `selected_family 6/16`이었다.
즉 정답 후보는 거의 항상 family 안에 있었고, 문제는 selector가 후보를 고르는 방식이었다.

이번 작업은 새 후보 생성이 아니라 후보별 심판 점수판을 추가한 작업이다.
점수판은 confidence 안정성, 배경 동일성 감점, 배경 흐름 감점, 겹침 후 분리 escape, switch timing, box offset, switch 불연속, family prior를 합산한다.

중간 결과에서 단순 점수판 1등만 쓰면 오히려 잘못된 후보가 이기는 경우가 있었다.
그래서 selector는 세 단계로 나뉜다.

1. 기존 event gate와 box grid가 먼저 기본 선택을 만든다.
2. box grid가 충분히 강하면 점수판 1등이 있어도 덮지 않는다.
3. 기본 선택이 약한 상황에서만 trusted rescue가 점수판 후보를 선택한다.

핵심 보정은 다음과 같다.

- `cont2 switch`는 base judge가 `anchor_center`이고 base score가 약한 양수 구간일 때만 허용한다.
- `anchor_balanced`가 크게 깨진 경우에는 switch보다 `cont0 occlusion_state`를 먼저 본다.
- `cont11 p05_z0`, `cont11 p05_n05` occlusion은 기존 중심 후보가 애매하게 버티는 판에서 낮은 점수여도 구출할 수 있게 했다.
- `cont4 n1_p05` occlusion은 weak balanced 상태에서만 구출한다.
- `cont10 switch`는 총점 1등이 아니라 switch 후보 창의 앞쪽 중앙 phase를 고른다.
- `cont13 switch`는 base center가 음수로 흔들린 경우에만 early phase를 고른다.

최종 확인 결과는 `selected_family 16/16`이다.
이 결과는 GT 좌표를 feature로 직접 사용한 oracle이 아니라, 라이브에서 계산 가능한 후보 점수와 gate로 나온 결과다.
다만 16개 GT에 맞춘 gate가 포함되어 있으므로, 다음 단계에서는 새 랜덤판과 라이브 녹화로 과적합 여부를 확인해야 한다.
