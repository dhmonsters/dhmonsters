# 2026-06-30 live trace log clarity v1 checklist

- [x] 디스크 공간 확보를 위해 불필요한 `03_output` 녹화 산출물 삭제를 사용자에게 위임했다.
- [x] `PUZZLE_ACTIVATED` 이벤트를 `PUZZLE DETECTED` 로그로 표시한다.
- [x] `CANDIDATES` 이벤트에서 후보 수, 첫 후보 id, 중심, 점수를 표시한다.
- [x] `TEMPORAL_SELECTOR` 이벤트에서 시간축 선택 좌표, family, reason을 표시한다.
- [x] `MOUSE_MOVE` 이벤트에서 실제 이동 여부, client 좌표, reason을 표시한다.
- [x] `IDENTITY_STATE` 이벤트에서 상태, confidence, candidate, reason을 표시한다.
- [x] 라이브 `trace.jsonl` tail 이벤트가 UI 로그로 들어오는지 테스트했다.
- [x] 콘솔 및 live 관련 회귀 테스트를 통과했다.
