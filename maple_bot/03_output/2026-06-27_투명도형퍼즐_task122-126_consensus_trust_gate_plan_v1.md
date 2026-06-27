# 투명도형퍼즐 task122-126 consensus trust gate 계획

## 목표

새 랜덤판에서도 무조건 consensus rescue를 쓰지 않고, 믿을 만한 프레임에서만 rescue를 허용하는 신뢰 게이트를 만든다.

## 현재 병목

- consensus 후보는 일부 프레임에서 GT에 더 가깝다.
- 하지만 consensus를 항상 쓰면 평균 오차가 악화된다.
- live health selector는 primary가 건강하다고 판단하는 동안 rescue를 실제로 쓰지 않는다.
- 따라서 다음 병목은 rescue 생성이 아니라 rescue 신뢰 판단이다.

## 성공 기준

- GT 없는 특징만으로 consensus가 유리한 프레임과 불리한 프레임을 분리한다.
- 대표 clip에서 `rescue_used_frames`가 0보다 커진다.
- 대표 clip에서 `selected_mean`이 기존 169.3px보다 낮아진다.
- 16GT 채점에서 평균 성능이 악화되면 기본값은 비활성으로 둔다.
- live 실행 경로에는 GT 정보를 절대 넣지 않는다.

## 작업 순서

1. consensus gate 분석 리포트 함수를 테스트 먼저 만든다.
2. 대표 clip에서 consensus가 이긴 프레임과 진 프레임의 특징 차이를 본다.
3. 단순 threshold 후보를 리포트로 비교한다.
4. 가장 안전한 threshold를 opt-in 옵션으로 `apply_live_health_selection`에 연결한다.
5. 대표 GT와 16GT를 다시 채점한다.
6. 인게임 첫 테스트 전 체크리스트를 갱신한다.

## 변경 예상 파일

- `maple_bot/_consensus_rescue_gate_report.py`.
- `maple_bot/tests/test_consensus_rescue_gate_report.py`.
- `maple_bot/_selector_shadow_gt_replay_score.py`.
- `maple_bot/tests/test_selector_shadow_gt_replay_score.py`.
- `maple_bot/03_output/2026-06-27_투명도형퍼즐_task122-126_consensus_trust_gate_checklist_v1.md`.
- `maple_bot/03_output/2026-06-27_투명도형퍼즐_task122-126_consensus_trust_gate_context-notes_v1.md`.

## 설계 원칙

- GT는 분석 라벨에만 사용한다.
- live 선택 시에는 `selector_shadow`, `live_family.debug`, `track`, 이전 결정 상태만 사용한다.
- 복잡한 모델보다 설명 가능한 gate를 먼저 쓴다.
- gate가 증거 없이 평균을 악화시키면 live 기본값에 넣지 않는다.
