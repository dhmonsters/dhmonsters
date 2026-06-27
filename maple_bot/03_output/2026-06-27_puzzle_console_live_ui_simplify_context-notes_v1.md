# 2026-06-27_puzzle_console_live_ui_simplify_context-notes_v1

## 2026-06-27

- 사용자 화면에서 CCTV 영역이 이미지 대신 `live_watch_preview.png` 텍스트만 보여졌다.
- 원인은 `_load_cctv_frame_preview()`가 `QLabel.setPixmap()` 뒤에 `QLabel.setText(path.name)`을 호출해 pixmap 표시를 텍스트로 다시 덮는 구조였다.
- preview 로딩 후 라벨 텍스트를 빈 문자열로 설정하도록 수정했다.
- replay, 영상, JSONL, 기본 테스트, ROI 설정, 캡처 점검, 녹화 폴더 버튼은 화면에서 제거했다.
- 기존 테스트와 내부 기능 호환을 위해 legacy 버튼 객체는 생성하지만 레이아웃에는 추가하지 않는다.
- 실전 화면은 CCTV와 제어 패널만 보인다.
- 제어 패널에는 솔버 시작, 솔버 종료, 녹화 종료 버튼과 텔레그램, GPU, 퍼즐 감지 알람 체크박스, 로그만 둔다.
- 후보, evidence, identity, guarded 텍스트는 화면에서는 숨겼지만 내부 상태 갱신용 라벨은 유지했다.
