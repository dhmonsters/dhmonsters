# 투명 도형 YOLO 솔버 — 구현 플랜 (체크리스트)

스펙: [yolo_shape_spec.md](yolo_shape_spec.md). 작성 2026-05-31.

## Phase 1 — 코드 (데이터 불필요, 지금 구현 가능)
- [ ] **T1. `core/shape_yolo.py`** — ncnn 추론 모듈
  - `planet_yolo_verify.py`의 `HyungYolo` 디코드 이식(1클래스 전용으로 단순화)
  - 모델 경로 `models/shape_yolo.param/.bin` 없으면 `_enabled=False`
  - `detect(board_bgr, score_thr=0.3) -> (cx,cy,score)|None`
  - 검증: 모델 없을 때 import/생성이 예외 없이 `_enabled=False`
- [ ] **T2. `transparent_shape_game.py` 통합** — Stage 0 추가
  - `__init__`에서 `ShapeYolo` lazy 생성(실패해도 무시)
  - `find_shape_in_board`에 Stage 0(YOLO) 추가, 기존 Stage1/2는 폴백
  - 검증: 모델 없을 때 기존 휴리스틱 그대로 동작(회귀 없음)
- [ ] **T3. `tools/shape_capture.py`** — 실게임 board 프레임 수집기
  - config board_roi 또는 인자로 ROI, N프레임마다 PNG 저장 → `dataset/raw/`
- [ ] **T4. `tools/shape_autolabel.py`** — 반자동 라벨러
  - 흰색영역 자동 박스 → YOLO txt, 결측 프레임 선형 전파, 미검출은 스킵 리스트
  - 산출: `dataset/images/`, `dataset/labels/`, `dataset/data.yaml`
- [ ] **T5. `tools/shape_train.py`** — 학습 + export
  - ultralytics YOLOv8n, imgsz=192, → `best.pt` → `yolo export format=ncnn` → `models/`

## Phase 2 — 데이터/학습 (사용자 실행 필요)
- [ ] **T6.** 도형 4종 실게임 캡처 (`shape_capture.py`)
- [ ] **T7.** 자동라벨 + 수동 보정 (`shape_autolabel.py`)
- [ ] **T8.** 학습 실행 → `models/shape_yolo.param/.bin` 생성 (`shape_train.py`)

## Phase 3 — 검증
- [ ] **T9.** `debug_overlay=True`로 실게임/샘플 추적 정확도 확인
- [ ] **T10.** 단일 nano 부족 시 앙상블/데이터 보강 판단

## 진행 메모
- Phase 1은 모델 없이도 안전(폴백). 먼저 구현·커밋.
- Phase 2는 사용자 손이 필요 → 도구만 준비해 핸드오프.
- ncnn .exe 번들은 별도 작업으로 분리.
```
