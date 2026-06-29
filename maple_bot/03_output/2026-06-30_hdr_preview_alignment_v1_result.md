# 2026-06-30 HDR preview alignment 결과 v1

## 변경
- `render_planet_cctv_preview`가 노란 HDR 박스를 실제 HDR ROI 위치에 그리도록 수정했다.
- HDR score 텍스트도 HDR 박스 내부 위치를 따라가게 바꿨다.
- 초소형 테스트 프레임에서 HDR ROI가 0 높이가 되면 HDR 박스만 생략하도록 보강했다.
- HDR 박스와 DET 박스의 상대 위치를 고정하는 테스트를 추가했다.

## 검증
- HDR/DET 위치 직접 확인.
- `hdr_top=15`, `hdr_bottom=80`, `det_top=83`, `gap=3`, `preview=(695, 634)`.
- 관련 테스트 5개 통과.
- 주요 회귀 테스트 94개 통과.

## 참고
이번 변경은 CCTV 미리보기 overlay 좌표만 수정했다. 후보 검출, 마우스 이동, 시간축 selector 로직은 변경하지 않았다.
