# 투명도형 퍼즐 Task 11 컨텍스트 노트

- Task 11의 목적은 실제 네트워크 알림이 아니라 퍼즐 세션 이벤트를 안전하게 기록하고, 검증 가능한 로컬 리포트를 만드는 것이다.
- 텔레그램 연동은 기존 `core.notify.telegram.TelegramNotifier`의 `send()` 계약만 감싼다.
- snapshot 인자는 현재 전송 첨부가 아니라 메시지와 trace에 스냅샷 경로를 남기는 용도로 둔다.
- trace와 리포트에는 토큰, Chat ID 같은 민감 정보를 직접 기록하지 않는다.
- RED는 `core.puzzle.notify` import 실패로 확인했다.
- GREEN은 Task 11 수동 테스트 4개 통과로 확인했다.
