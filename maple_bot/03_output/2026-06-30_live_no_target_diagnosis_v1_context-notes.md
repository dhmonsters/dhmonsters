# 2026-06-30 live no target diagnosis v1 context notes

## Fixed Definition

프레임별 정답 선택기가 아니라, 처음 타겟의 신분을 보류하고 복원할 수 있는 시간축 판별기를 만든다.

## Diagnosis

사용자가 보고한 “알림은 왔고 저장도 된 것 같은데 마우스는 안 움직였다”는 세션 `20260630_103258_001` 기준으로 확인했다.
녹화와 trace 저장은 정상이다.
마우스 제어 체크박스도 켜져 있었고 `MOUSE_MOVE` 이벤트도 37개 기록됐다.
하지만 모든 이벤트가 `moved=false`, `reason=no_target`이었다.

핵심 원인은 selector가 고를 후보가 없었다는 점이다.
`CANDIDATES` 이벤트가 37프레임 모두 `count=0`이었고, `TEMPORAL_SELECTOR`도 모두 `source=none`, `reason=no_points`였다.
저장된 첫 프레임에는 흰색 도형이 보였으므로 녹화 ROI 자체가 빈 화면은 아니었다.

## Code Decision

`PlanetNoAuthDetector`는 기존에 `planet_live_solver.load_models`만 사용했다.
그 모듈은 모델 로드와 직접 관련 없는 `mss`, `win32api` 같은 라이브 CLI 의존성도 상단에서 import한다.
해당 import가 실패하면 모델 로드도 실패하고, 기존 코드는 이 실패를 조용히 후보 0개로 바꿨다.

따라서 `planet_live_solver` 경로가 실패하면 `planet_yolo_verify.load_models`를 시도하도록 폴백을 추가했다.
또한 두 경로가 모두 실패하면 `last_error`에 실패 이유를 저장하고, 라이브 trace의 `CANDIDATES.debug`에 `detector_error`를 남기게 했다.

## UI Decision

다음 인게임 테스트에서는 UI 로그에 아래처럼 원인이 직접 보인다.

```text
f0 YOLO candidates 0 detector=PlanetNoAuthDetector enabled=False error=...
```

또한 같은 녹화 세션에서 `recording start`가 반복되는 로그 노이즈를 막았다.
상태 라벨은 `LOST` 같은 분석 상태로 바뀔 수 있으므로, 새 녹화 여부는 `session_dir` 변경만으로 판단한다.
