# 2026-06-30 HDR preview alignment 체크리스트 v1

- [x] 노란 HDR 박스가 preview top `0px`부터 그려지는 원인 확인.
- [x] 실제 HDR ROI 오프셋을 검증하는 테스트 추가.
- [x] 테스트가 기존 코드에서 실패하는지 확인.
- [x] `render_planet_cctv_preview`가 `fixed_popup_header_roi`를 사용하게 수정.
- [x] 작은 프레임에서는 HDR 박스를 생략하고 preview 렌더링은 계속되도록 보강.
- [x] HDR/DET 위치 수치 확인.
- [x] 회귀 테스트 통과 확인.
- [x] 커밋 생성.
