# 2026-06-30 HDR preview alignment 컨텍스트 노트 v1

## 고정 문장
프레임별 정답 선택기가 아니라, 처음 타겟의 신분을 보류하고 복원할 수 있는 시간축 판별기를 만든다.

## 이번 문제
사용자 스크린샷에서 노란 HDR 박스와 주황 DET 박스 사이가 떠 보였다. 특히 노란 박스의 높이와 위치가 위쪽으로 붙어 있어 실제 팝업 헤더 위치와 다르게 보였다.

## 원인
`render_planet_cctv_preview`는 preview crop을 BRD 기준으로 잘라놓고도, HDR 박스를 `y=0`부터 `frame_h * 0.061` 높이로 그렸다. 실제 HDR ROI는 preview crop 시작점보다 아래에 있으므로 `header_roi.y - popup_roi.y` 만큼 내려서 그려야 한다.

## 결정
HDR 박스는 `fixed_popup_header_roi`를 사용해 실제 ROI 좌표를 구하고, 이를 preview 내부 좌표로 변환해 그린다. DET 박스는 기존처럼 `fixed_detect_roi` 기준으로 유지한다.

## 수치
1920x1080 기준 preview 크기는 `695x634`다. HDR top은 `15`, HDR bottom은 `80`, DET top은 `83`이며 두 박스의 간격은 `3px`이다.

## 예외 처리
단위 테스트의 8x6 같은 초소형 프레임에서는 HDR ROI 높이가 0이 될 수 있다. 이 경우 HDR 박스만 생략하고 preview 렌더링은 계속한다.
