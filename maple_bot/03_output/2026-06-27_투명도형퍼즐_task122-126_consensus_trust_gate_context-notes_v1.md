# 투명도형퍼즐 task122-126 consensus trust gate 컨텍스트 노트

## 시작 판단

현재 단계는 후보 생성보다 선택 신뢰 판단이 병목이다.

## 이전 결과 요약

- `000_0614_121417`에서 track mean은 109.0px이다.
- consensus rescue only mean은 124.8px로 더 나쁘다.
- GT oracle best(track, consensus) mean은 81.9px로 개선 여지는 있다.
- 즉 consensus는 일부 프레임에서만 써야 한다.

## 이번 작업의 핵심 결정

consensus rescue를 기본으로 강제하지 않고, live에서 볼 수 있는 특징으로 신뢰할 때만 허용한다.

## 진행 로그

- task122-126 작업을 시작했다.
- `tests.test_consensus_rescue_gate_report`를 먼저 작성했고 `_consensus_rescue_gate_report` 모듈 부재로 RED를 확인했다.
- `consensus_gate_feature_rows`와 `summarize_consensus_gate_rows`를 최소 구현했고 단위 테스트 2개가 통과했다.
- `consensus_gate_passes`, `gate_sweep_rows`, `markdown_report`를 추가했고 gate 분석 테스트 9개가 통과했다.
- 대표 clip `000_0614_121417`의 row 55부터 96까지 부분 재생 결과, 기본 gate 후보 4개가 모두 5프레임을 통과시켰고 5개 모두 consensus가 더 좋은 프레임이었다.
- 위험 샘플은 `consensus_step`이 157px부터 226px처럼 큰 경우가 많아서 `max_consensus_step`이 핵심 방어 신호로 보인다.
- `apply_live_health_selection`에 `consensus_gate_config` opt-in 옵션을 붙였고, 강한 consensus는 허용하고 약한 consensus는 일반 rescue로 fallback하는 테스트를 추가했다.
- `score_gt_clip`과 CLI에 `--consensus-gate` 옵션을 연결했다.
