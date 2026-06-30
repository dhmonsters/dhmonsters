# 주황 DET ROI raw 후보 복구 결과

- ROI 결론은 주황색 `DET` 영역 유지다.
- 최근 세션 `20260630_141458_001`은 퍼즐 감지와 녹화는 성공했지만, 기존 trace에서 `raw_count=0`이 계속 나와 후반 `no_target`으로 끊겼다.
- `PlanetNoAuthDetector`는 이제 기본 M1 score `0.2`에서 후보가 0개면 `0.12`, `0.08`, `0.05` 순서로 재시도한다.
- 후보가 살아나면 최대 24개까지만 selector에 넘긴다.
- trace와 UI 로그에 `m1_score_used`, `m1_attempts`, `detector_max_rows`가 표시된다.
- 다음 인게임 테스트 성공 신호는 투명화 이후 `YOLO candidates` 로그에 `raw`가 1 이상이고, 필요 시 `m1=0.08` 또는 `m1=0.05`가 표시되는 것이다.
- 번들 테스트 환경에서는 `mss`, `ncnn`이 없어 최근 영상에 실제 모델을 다시 얹는 검증은 수행하지 못했다.
