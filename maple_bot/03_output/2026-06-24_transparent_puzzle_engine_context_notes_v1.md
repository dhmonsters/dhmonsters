# 2026-06-24 transparent puzzle engine 컨텍스트 노트 v1

- 사용자는 `planet_solver_noauth.py`의 불필요한 추적 실험 흔적을 지우고, 새 설계로 넣는 방향을 승인했다.
- 단, UI, 캡처, YOLO, 마우스, 녹화는 유지한다.
- 새 엔진은 먼저 오프라인 replay로 검증한다.
- replay가 기존 consensus 9/16보다 좋아지기 전까지 live 기본 경로로 켜지 않는다.
- live 연결은 shadow mode를 우선한다.
- 핵심 병목은 후보 검출이 아니라 merged blob 내부의 타겟 중심 복원이다.
