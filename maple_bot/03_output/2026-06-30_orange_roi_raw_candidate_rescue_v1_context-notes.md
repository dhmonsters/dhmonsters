# 주황 DET ROI raw 후보 복구 컨텍스트 노트

- 사용자는 비교 이미지에서 주황색 `DET` 영역이 가장 잘 맞는다고 판단했다.
- 따라서 YOLO 입력 ROI를 초록색 noauth 원본 영역으로 넓히지 않고, 주황색 `detect` ROI를 유지한다.
- 현재 문제는 주황색 ROI 내부에서도 `raw_count=0`이 지속되는 것이다.
- 1차 목표는 selector 개선이 아니라 후보 공급 복구다.
- `PlanetNoAuthDetector`는 기본 M1 score 0.2에서 후보가 0개면 0.12, 0.08, 0.05 순서로 약한 점수 재시도를 한다.
- 약한 점수에서 후보가 살아나면 최대 24개까지만 넘겨서 시간축 selector가 과도한 후보에 흔들리지 않게 한다.
- 라이브 로그의 `CANDIDATES.debug`에 `m1_attempts`, `m1_score_used`, `detector_max_rows`를 남겨 다음 인게임 테스트에서 “왜 후보가 0개인지”를 바로 볼 수 있게 했다.
