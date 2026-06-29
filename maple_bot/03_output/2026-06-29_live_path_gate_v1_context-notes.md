# 2026-06-29 라이브 경로 게이트 컨텍스트

## 핵심 정의

프레임별로 그 순간 제일 그럴듯한 후보를 고르는 솔버가 아니라, 처음 타겟의 신분을 시간축에서 보류하고 복원할 수 있는 판별기를 만든다.

## 현재 판단

직전 단계의 16/16은 `LiveTemporalSelector` 단독 점수가 아니라, 후보 family pool과 selector scoreboard가 결합된 경로에서 나온 결과다. 따라서 이번 단계의 핵심은 “점수가 좋았던 오프라인 채점기가 존재한다”가 아니라, `puzzle.py`의 실제 라이브 분석 경로가 그 계열을 호출하는지 확인하는 것이다.

## 주의점

GT 좌표는 평가용 정답지로만 사용한다. 라이브에서 사용할 수 없는 GT 좌표, 미래 프레임 정답, 사람이 미리 찍은 정답 경로를 solver 입력 feature로 넣으면 안 된다.

## 1~4 진행 결과

- `PlanetLiveSolver` 기본 경로가 `LiveTemporalSelector`를 만들고, 그 내부 runtime이 judge scoreboard를 켜는지 테스트로 고정했다.
- `LiveRecordingRuntime`에 `mouse_enabled` 스위치를 추가했다. dry-run에서는 solver 판단과 trace 기록은 유지하지만 클릭만 막는다.
- `puzzle.py --live-record --live-dry-run` 옵션을 추가했다. GUI 기본 의미는 유지하고, CLI에서 무마우스 검증을 할 수 있게 했다.
- ROI 테스트의 예전 기대값을 `planet_solver_noauth` 기준 상대좌표인 `0.254,0.292,0.494,0.588`로 맞췄다.
- 후보 family 점수판 기준선은 `selected_summary 16/16`으로 재확인했다.
- 라이브형 causal selector도 `summary 16/16`, 평균 오차 약 `26.32px`로 재확인했다.
- 현재 Codex 셸에서는 실제 화면 캡처가 실패했다. 원인은 `mss` 미설치와 `ImageGrab` 화면 접근 실패다. fake frame 기반 캡처, ROI, 녹화 흐름 검증은 통과했다.
