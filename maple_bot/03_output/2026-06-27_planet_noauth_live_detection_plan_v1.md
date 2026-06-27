# planet_solver_noauth 라이브 감지 이식 계획.

## 목표.

퍼즐 콘솔의 라이브 감지와 CCTV를 `planet_live_solver.py`의 noauth 방식에 맞춘다. 사용자가 본 `HDR score=0.63 / thr=0.65`처럼 템플릿 임계값 때문에 퍼즐이 시작되지 않는 문제를 없앤다.

## 변경 방향.

- 팝업 시작 감지는 템플릿 매칭 대신 noauth의 헤더 dark ratio 방식으로 바꾼다.
- ROI 상수는 noauth의 `HDR_*`, `BRD_*` 값을 그대로 공유한다.
- detect ROI는 noauth처럼 보드 전체를 사용한다.
- 라이브 도형 검출은 `planet_live_solver.load_models()`에서 가져온 M1 검출기를 기본으로 사용한다.
- CCTV polling은 500ms에서 50ms로 줄이고, 대기 preview는 매 프레임 갱신한다.

## 성공 기준.

- 어두운 팝업 헤더가 있으면 `popup_board`로 감지된다.
- preview crop 크기가 noauth ROI 기준인 948x717이 된다.
- 기본 도형 검출 호출이 `m1.detect(board, 192, 0.2)` 형태를 따른다.
- 관련 테스트와 smoke 검증이 통과한다.
