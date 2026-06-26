# 2026-06-26 selector shadow 배치 리포트 맥락 노트

- solver gate 조정 전에는 여러 클립에서 `bg_split`과 `rescue_allowed`가 실제로 얼마나 자주 나오는지 알아야 한다.
- 전체 JSONL을 저장하지 않고 메모리에서 backfill 후 요약만 만들면 저장 권한 문제와 대용량 로그 문제를 피할 수 있다.
- 기본 배치 옵션은 빠른 탐색용으로 `limit`, `emit_every`, `live_max_candidates`, local-box 제외를 우선한다.
- 10개 샘플 탐색에서 shadow 61프레임, bg_split 4프레임, rescue_allowed 4프레임이 나왔다.
- 3개 샘플 검증은 약 5.9초였고, 2개 클립에서 bg_split과 rescue_allowed가 같은 프레임에 발생했다.
- `first_rescue_allowed_frame`은 bg_split 첫 프레임이 아니라 실제 `rescue_allowed=True`인 첫 프레임만 보도록 고쳤다.
