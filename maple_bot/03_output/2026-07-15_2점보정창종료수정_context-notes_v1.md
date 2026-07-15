# 2점 보정 창 종료 수정 판단 기록

## 2026-07-15

- 사용자는 `2점 보정 적용`을 누르면 창이 꺼진다고 보고했다.
- 버튼은 `WorldMapEditor.apply_calibration()`에 직접 연결되어 있었다.
- `apply_calibration()`은 내부 테스트와 직접 호출에서 실패를 알리기 위해 `ValueError`를 유지하는 것이 맞다.
- UI 버튼에는 별도 안전 래퍼를 연결해 예외를 경고창으로 바꾸는 방식이 가장 작다.
- 회귀 테스트는 수정 전 `_apply_calibration_from_ui` 미구현으로 실패했고, 수정 후 통과했다.
- 관련 테스트는 `tests/test_world_map_editor.py tests/test_world_map.py --basetemp=03_output/pytest_tmp_2point_calibration` 기준 `12 passed`다.
- 빌드는 기존 산출물을 지우지 않고 `.obf_build_2point_fix`와 `03_output/Claude_v2.1.5_portable_2point_fix`에 새로 만들었다.
- PyInstaller 빌드 중 Ultralytics가 `lap==0.5.13`을 자동 설치했다.
- 새 설치파일은 `03_output/Claude_v2.1.5_Setup_v3.exe`다.
- 설치파일 크기는 2,236,176,552 bytes, SHA256은 `A52FCFA57033631C6B1D1ACE16CC82FA3880AC8E4705EF9A98770176E1AA6095`다.
- v3는 torch/CUDA 의존성이 포함되어 기존 v2보다 훨씬 크다.
