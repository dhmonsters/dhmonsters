# 투명도형 퍼즐 라이브 preview 수정 작업 메모

## 2026-06-27

- 사용자가 라이브 녹화 중 preview가 보이지 않는다고 보고했다.
- 스크린샷에서는 `recording start` 로그와 세션 경로는 보이지만 중앙 CCTV는 `preview 없음`으로 남아 있다.
- 코드 확인 결과 UI preview는 실제 이미지 파일 경로만 표시한다.
- live 녹화 이벤트는 실제 이미지 파일이 아니라 `live_screen#frame=...` 문자열을 기록한다.
- 따라서 live 녹화 중 preview용 이미지 파일을 별도로 생성하고, UI 폴링 결과에 그 경로를 포함시키는 방향으로 수정한다.
- `LiveRecordingRuntime.latest_preview_path`를 추가했고, 녹화 중 보드 프레임 preview PNG를 `snapshots/live_preview_*.png`로 저장한다.
- `WatchStartResult.preview_path`를 추가해 UI 상태 폴링에서 preview 파일 경로를 받을 수 있게 했다.
- UI는 live status에 preview 파일이 있으면 `_load_cctv_frame_preview()`로 CCTV 화면을 갱신한다.
- `tests.test_puzzle_console_f1_hotkey`, `tests.test_puzzle_live_watch`, 문법 확인, headless 프리플라이트가 통과했다.
