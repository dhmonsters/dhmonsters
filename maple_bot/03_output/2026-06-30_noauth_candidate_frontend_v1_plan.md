# noauth 후보 생성기 결합 계획

## 목표
- `puzzle.py`의 시간축 selector는 유지한다.
- `planet_solver_noauth`에서 후보를 잘 살리던 `ShapeYolo + weak detect + cursor inpaint`만 `PlanetNoAuthDetector` 앞단에 붙인다.

## 설계
- `PlanetNoAuthDetector.detect_all()`은 먼저 `ShapeYolo.detect_all(score_thr=0.10)`을 시도한다.
- 분홍 커서가 보이면 작은 원형 영역만 inpaint한 검출용 프레임을 ShapeYolo에 넣는다.
- ShapeYolo가 비활성, 실패, 후보 0개이면 기존 M1 검출 `m1.detect(imgsz=192, score=0.2)`로 fallback한다.
- 반환 형태는 기존과 같은 `(cx, cy, score, w, h)`를 유지해 `PlanetLiveSolver`와 시간축 selector는 바꾸지 않는다.

## 성공 기준
- ShapeYolo 후보가 있으면 M1 fallback 없이 그 후보를 반환한다.
- ShapeYolo 호출 시 score threshold는 `0.10`이다.
- 커서가 있는 입력은 inpaint된 프레임으로 ShapeYolo에 전달된다.
- 기존 M1 fallback 테스트는 계속 통과한다.
