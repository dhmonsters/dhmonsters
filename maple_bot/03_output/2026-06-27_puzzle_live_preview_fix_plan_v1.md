# 투명도형 퍼즐 라이브 preview 수정 계획

## 목표

라이브 감시와 녹화 중에도 CCTV preview에 현재 퍼즐 화면이 보이게 한다.

## 원인

replay 경로는 실제 PNG 파일을 `source_frame_path`로 넘기지만, live 경로는 `live_screen#frame=...` 같은 가상 경로만 넘긴다. UI preview는 실제 파일만 읽기 때문에 live 중에는 `preview 없음`에서 멈춘다.

## 성공 기준

- live 녹화가 시작되면 preview용 이미지 파일이 생성된다.
- UI 상태 폴링이 preview 파일을 받아 CCTV preview를 갱신한다.
- 기존 replay preview 동작은 유지된다.
- 관련 테스트와 headless 프리플라이트가 통과한다.
