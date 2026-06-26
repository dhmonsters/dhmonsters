# live source별 상한 분리 컨텍스트 노트

## 2026-06-26 시작

- 예전 16/16은 offline family pool 상한에 가깝고, 현재 live family pool의 best-family 상한은 그보다 낮다.
- 다음 수정은 selector가 아니라 source 생성 보강일 가능성이 높다.
- 먼저 기존 JSONL에 남아 있는 `track`, `engine`, live family의 source별 기여를 분리한다.

## 2026-06-26 결과

- 16개 기존 GT JSONL에는 `engine` 로그가 없다. 즉 과거 녹화만으로는 `phase_catalog` 계열을 replay할 수 없다.
- `transparent_engine` 단독 replay는 0/16이었다. 엔진을 켜는 것만으로는 예전 16/16을 재현하지 못한다.
- 현재 live source별 local-box 상한은 `balanced_viterbi`가 6/16으로 가장 높다.
- `panel_default`는 1/16, `strict_transition_viterbi`는 1/16, `bg_split_viterbi`와 `merge_context`는 0/16이다.
- 결론은 selector가 잘못 고르는 문제가 아니라, live로 생성되는 family pool 자체가 예전 offline 상한의 후보를 충분히 포함하지 못한다는 것이다.

## 다음 판단

다음 구현은 GT 없이 고르는 selector보다 먼저 live-causal 후보 family를 늘리는 쪽이 맞다.
특히 `_offset_state_score.py`에서 좋았던 중심 복원과 상태 coasting을 live에서 causal하게 재현하는 family가 우선순위다.
