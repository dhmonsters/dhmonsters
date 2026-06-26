# 2026-06-26 selector shadow 병합 리포트 개선 맥락 노트

- 현재 batch report는 bg_split과 rescue_allowed 수만 보여준다.
- 병합 gate 적용 뒤에는 blocked bg_split이 왜 막혔는지 `merge_context.max_size`, `merge_context.max_ratio`, `merge_context.frames`로 확인해야 한다.
- 전체 JSONL 재생 없이 summary만 강화하면 live 테스트 전 판단 근거를 빠르게 볼 수 있다.
- 실패 테스트를 먼저 추가했고, 기존 구현에서 `merge_context_frames`와 이벤트 `merge_context`가 없어 실패하는 것을 확인했다.
- 구현은 selector 동작을 바꾸지 않고 이미 들어있는 `selector_shadow.merge_context`만 요약과 markdown 표에 노출하는 방식으로 제한했다.
