# live state-coast family 컨텍스트 노트

## 2026-06-26 시작

- 이전 진단에서 현재 live source pool은 best source 기준 `balanced_viterbi` 6/16이 상한이었다.
- 따라서 지금 문제는 selector가 아니라 live family 후보 생성 부족으로 본다.
- offline `offset_state`는 미래 프레임을 쓰는 보간이 섞여 있으므로 그대로 live에 넣지 않는다.
- live에서는 과거 안정 프레임만 사용해 현재 프레임을 예측하는 causal 방식으로 구현한다.

## 2026-06-26 구현 결과

- `TransparentLiveFamilyPool`에 `*_state_coast`, `*_offset_coast` family를 추가했다.
- 병합 후보 중심이 데칼 쪽으로 밀린 synthetic 장면에서는 `balanced_viterbi_center_mild_state_coast`가 과거 안정 속도로 중심을 복원한다.
- 기존 live family 테스트와 새 테스트는 통과했다.
- 16개 GT source upper 재채점 결과 `balanced_viterbi`는 6/16에서 7/16으로, `strict_transition_viterbi`는 1/16에서 2/16으로 올랐다.
- 좋아진 클립은 `000_0614_121417`, `000_0615_062325` 쪽이다.
- 하지만 16/16과는 아직 거리가 크다. 병합 중심 복원만으로는 부족하고, 다음 병목은 장기 window 부재 또는 offline `phase_catalog`/`decal_strict` 계열 source가 live pool에 없다는 점이다.
