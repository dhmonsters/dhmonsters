# 퍼즐 감시 대기 CCTV 메모리 preview 체크리스트.

- [x] `WatchStartResult`가 메모리 preview 프레임을 담는 테스트를 추가했다.
- [x] UI가 녹화 전 `preview_frame`을 표시하는 테스트를 추가했다.
- [x] 대기 preview 생성이 PNG 파일 저장 없이 프레임만 반환하는 테스트를 추가했다.
- [x] 대기 감시 루프를 파일 경로 저장에서 메모리 프레임 저장으로 변경했다.
- [x] UI가 `preview_frame`을 우선 표시하도록 변경했다.
- [x] 녹화 중 세션 preview 경로 동작은 유지했다.
- [x] 관련 unittest, smoke, AST 문법 검사를 실행했다.
