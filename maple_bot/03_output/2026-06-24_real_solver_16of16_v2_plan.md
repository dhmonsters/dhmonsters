# 2026-06-24 실제 적용형 투명도형 solver 16/16 계획 v2

## 목표

GT 빨간 점을 직접 쓰는 오라클이 아니라, 라이브에서 관측 가능한 후보, 박스 크기, 배경 반복, raw motion, rigid violation, 궤적 연속성만으로 `_gt_frames` 16판을 모두 평균 오차 40px 이하로 통과하는 solver를 만든다.

## 기준

- 오프라인 GT 기준 16/16 통과를 목표로 한다.
- 기존 단위 테스트는 유지한다.
- 새 solver가 기존 selector 9/16보다 낮으면 live 기본 교체를 하지 않는다.
- `planet_solver_noauth.py`에는 먼저 shadow로 연결하고, 16/16 확인 후 default 전환을 판단한다.

## 접근

1. 기존 `box-grid oracle`, `best-family oracle`, `segment-splice oracle`이 보여준 구조를 실제 규칙으로 바꾼다.
2. YOLO 박스 중심 하나가 아니라 박스 내부 5x5 후보점을 상태로 유지한다.
3. 단일 선택이 아니라 beam/MHT 방식으로 여러 궤적을 살린다.
4. GT 대신 배경 설명 가능성, raw anom, viol, 내부 offset 안정성, 병합 맥락, 분리 후 연속성으로 점수를 만든다.
5. 오프라인 replay 채점으로 먼저 증명하고, 통과한 뒤 live 연결을 바꾼다.

## 산출물

- 새 solver 또는 기존 `core/vision/transparent_puzzle_engine.py`의 실제 적용형 family.
- 오프라인 replay 채점 스크립트 또는 기존 스크립트 확장.
- `03_output` 점수표와 작업 기록.
- 필요 시 `planet_solver_noauth.py` shadow 연결 갱신.

## 위험

- 16/16 오라클은 GT를 사용했으므로 그대로 적용할 수 없다.
- 특정 16판에 과적합하면 새 랜덤 판에서 흔들릴 수 있다.
- 기존 작업트리가 많이 dirty 상태라서 수정 범위를 좁혀야 한다.
