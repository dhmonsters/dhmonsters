# 2026-06-30 HDR preview alignment 계획 v1

## 목표
- `puzzle.py` CCTV에서 노란 HDR 박스와 주황 DET 박스가 실제 ROI 상대 위치대로 표시되게 만든다.
- 노란 HDR 박스가 preview crop 맨 위에 붙는 것이 아니라, 실제 HDR ROI 위치만큼 아래로 내려와 DET와 거의 맞닿게 한다.

## 성공 기준
- 1920x1080 기준 HDR 박스 top이 preview 내부 `15px` 부근으로 내려온다.
- HDR bottom과 DET top의 간격이 `4px` 이하로 유지된다.
- 작은 테스트 프레임에서도 preview 렌더링이 실패하지 않는다.
- 기존 live preview 회귀 테스트가 통과한다.

## 진행 순서
- 현재 렌더링 코드가 HDR ROI의 `y` 오프셋을 무시하는지 확인한다.
- HDR ROI 오프셋을 검증하는 테스트를 추가한다.
- 실제 HDR ROI 좌표를 preview 좌표로 변환해서 노란 박스를 그린다.
- 회귀 테스트를 실행한다.
