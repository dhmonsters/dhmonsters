# ShapeYolo 로더 수정 결과

## 변경 내용

- `PlanetNoAuthDetector`가 `ShapeYolo`를 먼저 시도한 뒤 실패하면 `planet_live_solver` 로딩 경로를 거친 다음 `ShapeYolo`를 한 번 더 재시도하게 했다.
- 이 재시도는 주입된 테스트 detector에는 적용하지 않고, 기본 런타임 로딩일 때만 1회 실행한다.
- 실패 재현 테스트를 추가해 `ShapeYolo` 첫 로딩 실패 후 재시도 동작을 고정했다.

## 검증

- RED 확인: 신규 테스트가 기존 코드에서 `[]` 반환으로 실패했다.
- GREEN 확인: 신규 테스트 통과.
- `python -m unittest maple_bot.tests.test_puzzle_planet_live` 결과 21개 통과.
- `py_compile` 통과.
- `git diff --check` 통과.

## 최근 세션 재생 결과

대상 세션은 `20260630_141458_001`이다.

- 총 프레임: 85.
- `raw_nonzero`: 0.
- `white_nonzero`: 31.
- `coast_nonzero`: 18.
- `candidate_nonzero`: 49.
- `LOST`: 32.
- 첫 `no target`: 65프레임.
- 마지막 target: 64프레임.

현재 샌드박스 검증 환경에서는 `planet_live_solver`가 `mss`를 못 찾고, `planet_yolo_verify`가 `ncnn`을 못 찾아 raw 후보 생성기가 올라오지 않는다. 따라서 이 환경의 최근 세션 재생은 아직 통과가 아니다.

## 다음 판단

실제 사용자가 실행하는 AppData Python은 샌드박스에서 실행 권한이 막혀 직접 확인하지 못했다. 인게임 테스트에서 로그의 `detector_error`가 사라지고 `raw_count`가 fade 이후 1 이상으로 나오는지 확인해야 한다.
