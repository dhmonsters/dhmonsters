# 2026-06-26 selector shadow 병합 맥락 gate 맥락 노트

- 기존 `rescue_allowed`는 family 이름이 `bg_split_viterbi`로 시작하면 true였다.
- 그 방식은 bg_split family가 선택된 가짜 발화까지 health selector에 rescue 후보로 넣을 수 있다.
- 이번 gate는 선택 family가 bg_split이어도 최근 후보들에 병합 후보가 없으면 rescue를 막는 방향이다.
- 예전 JSONL에는 w/h가 없어 병합 gate가 전부 blocked로 보일 수 있다.
- `.wjsonl` sidecar를 자동으로 붙여 offline backfill에서도 후보 크기를 복원한다.
- sidecar 적용 6개 샘플에서 bg_split 4개 중 rescue_allowed 1개만 통과했다.
