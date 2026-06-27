# 퍼즐 감시 대기 CCTV 메모리 preview 전환 계획.

## 목표.

F1로 솔버 감시만 켠 상태에서는 PNG 파일을 저장하지 않고, CCTV 화면을 메모리 프레임으로만 갱신한다. 퍼즐이 감지되어 녹화가 시작된 뒤의 세션 preview 저장은 유지한다.

## 수정 방향.

- `WatchStartResult`에 `preview_frame` 필드를 추가한다.
- 대기 감시 루프는 `live_watch_preview.png`를 쓰지 않고 `render_planet_cctv_preview` 결과를 메모리에 보관한다.
- UI는 `preview_frame`이 있으면 파일 경로보다 우선해서 메모리 프레임을 표시한다.
- 녹화 중에는 기존 `latest_preview_path` 기반 세션 preview 표시를 유지한다.

## 성공 기준.

- 녹화 전 대기 감시 상태에서 `live_watch_preview.png` 저장 코드가 호출되지 않는다.
- CCTV는 메모리 preview 프레임으로 갱신된다.
- 녹화 시작 후 `snapshots/live_preview_*.png` 저장은 기존처럼 유지된다.
