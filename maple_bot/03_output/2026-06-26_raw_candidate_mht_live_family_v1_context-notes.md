# Raw Candidate MHT Live Family 컨텍스트 노트

## 2026-06-26

- raw rank/continuity/box-offset family를 포함해도 보수 기준 source upper는 10/16이었다.
- raw candidate가 새로 살린 판은 `000_0615_015619` 하나였다.
- `000_0615_044401`은 부분 경로로는 좋아 보였지만, 커버율 90% 기준에서는 실패였다.
- greedy continuity는 초기 ID가 틀어지면 뒤에서 맞는 raw 후보가 있어도 전체 경로로 회복하기 어렵다.
- 따라서 raw 후보를 여러 가설로 유지하는 MHT family를 추가한다.
- 테스트는 `raw_candidate_mht_center_mild_state_mild`가 없어서 먼저 실패했다.
- 구현은 기존 `solve_mht`를 재사용하고, score보다 시작점/연속성을 더 크게 보는 별도 설정을 사용한다.
- 관련 24개 테스트와 py_compile이 통과했다.
- raw MHT는 실패판에서 새 성공을 만들지 못했고 비용도 커서 기본 비활성으로 유지했다.
- 대신 raw beam family를 연결하자 `000_0615_022618`이 39.7px로 새로 통과했다.
- 현재 보수 기준 source upper는 11/16으로 본다.
- 남은 실패 5판은 worst frame trace로 병목 프레임을 좁히는 단계가 필요하다.
