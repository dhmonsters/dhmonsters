# planet_solver_noauth 라이브 감지 이식 컨텍스트 메모.

## 원인.

기존 콘솔은 팝업 헤더 템플릿 매칭 점수 `0.65` 이상을 요구했다. 사용자가 첨부한 화면은 `HDR score=0.63 / thr=0.65`였기 때문에 ROI는 보이지만 녹화 시작 감지가 되지 않았다.

## noauth와 달랐던 부분.

`planet_live_solver.py`는 템플릿 매칭이 아니라 헤더 영역에서 RGB가 모두 80 미만인 픽셀 비율을 계산하고, dark ratio가 `0.50` 이상이면 팝업으로 본다. 또한 보드 ROI는 `x=0.254..0.748`, `y=0.292..0.880`이며, 도형 검출은 M1 모델에 `detect(board, 192, 0.2)`로 요청한다.

## 결정.

콘솔 쪽 라이브 감지는 noauth 방식을 기준으로 통일했다. 시작 조건은 dark ratio로 단순화했고, 녹화 시작 뒤의 도형 검출도 `PlanetNoAuthDetector` 어댑터를 통해 noauth M1 검출기를 사용한다.

## UI 메모.

CCTV가 느려 보인 이유는 UI live status timer가 500ms였고 대기 preview도 5프레임마다 갱신했기 때문이다. timer는 50ms로 줄였고 대기 preview는 매 프레임 갱신하도록 바꿨다.
