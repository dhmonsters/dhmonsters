# 퍼즐 감시 대기 CCTV 메모리 preview 컨텍스트 메모.

## 결정.

녹화 전 CCTV preview는 더 이상 `03_output/...transparent_puzzle_watch/live_watch_preview.png`로 저장하지 않는다. 감시 쓰레드가 최신 preview 프레임을 메모리에 들고 있고, UI가 live status polling으로 그 프레임을 받아 표시한다.

## 이유.

사용자는 녹화 전에는 파일 저장이 필요 없고, CCTV 화면만 실시간이면 충분하다고 확인했다. 대기 상태에서 PNG를 계속 덮어쓰면 불필요한 디스크 쓰기와 산출물 혼동이 생긴다.

## 유지한 부분.

퍼즐이 감지되어 녹화가 시작된 뒤에는 `LiveRecordingRuntime`의 세션 preview 저장을 그대로 유지했다. 이 파일들은 검증 자료와 녹화 세션 리포트에 필요하다.

## 검증 메모.

처음 추가한 테스트는 기존 코드에서 실패했다. 구현 후 `tests.test_puzzle_console_f1_hotkey`, `tests.test_puzzle_live_watch`, `tests.test_puzzle_live_recording`, `tests.test_puzzle_planet_live`가 통과했다. Pytest가 없는 환경이라 GUI smoke 일부는 직접 호출했고, AST 문법 검사도 통과했다.
