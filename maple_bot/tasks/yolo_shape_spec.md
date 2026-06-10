# 투명 도형 YOLO 솔버 — 설계/스펙 + 컨텍스트 노트

작성일 2026-05-31. 근거: 상폐 업체 Planet_solver v2(ncnn YOLO) 역분석 + 동작 검증.

## 목표
현재 `transparent_shape_game.py`의 흰색/프레임차분 휴리스틱 감지를 **우리가 직접 학습한 YOLOv8n 1클래스 탐지기**로 교체해, 도형이 투명해진 뒤에도 위치를 안정적으로 추적한다. 추적·마우스 폐루프 제어는 기존 구조를 유지한다.

## 배경 (왜)
- vortex v1(옵티컬플로우)은 네모·동그라미에서 30~60px 드리프트 — 구조적 한계(우리가 재현·확인).
- 현재 우리 봇 휴리스틱(흰색→차분)은 도형이 투명해지면 끊기고 분홍 마우스 포인터로 오인 — 사용자 보고.
- planet v2는 옵티컬플로우를 버리고 **YOLOv8n + 4모델 앙상블**로 정면 돌파. 우리가 그들 가중치를 ncnn으로 적재해 **샘플 영상 94% 탐지** 검증 완료([planet_yolo_verify.py](../planet_yolo_verify.py)).
- 그들 가중치는 그대로 쓰지 않는다(남의 학습 산출물·해상도/ROI 종속). 같은 기법으로 우리 데이터를 학습한다.

## 4대 설계 결정 (승인됨)
1. **탐지 타깃 = 1클래스 "shape" 위치만.** 모양 종류(네모/세모/동그라미/별)는 풀이에 불필요. 박스 중심만 사용.
2. **추론 런타임 = ncnn.** 학습은 ultralytics(YOLOv8n) → `.pt`를 ncnn `.param/.bin`으로 export. 봇은 torch 없이 ncnn 추론(fp32 CPU, imgsz=192). 검증된 `HyungYolo` 디코드 재사용.
3. **추적·마우스 제어 = 우리 구현.** planet은 서버 동적 로딩이라 바이너리에 없음. 기존 EMA + 속도제한 폐루프 유지, 감지 단계만 교체.
4. **학습 데이터 = 반자동 라벨링.** 초반 흰색 구간은 흰색영역 자동 박스, 투명 구간은 선형 예측 전파 + 일부 수동 보정.

## 아키텍처
```
실게임/샘플 영상
  → tools/shape_capture.py   : board ROI 프레임을 PNG로 수집 (실게임 중)
  → tools/shape_autolabel.py : 흰색영역 자동라벨 + 결측 구간 선형 전파 → YOLO txt
  → tools/shape_train.py     : ultralytics YOLOv8n 학습 → best.pt → ncnn export
  → models/shape_yolo.param/.bin (산출물)

런타임:
  core/shape_yolo.py (ShapeYolo) : ncnn 추론, detect(board_img) -> (cx,cy,score)|None
  core/transparent_shape_game.py : find_shape_in_board()에 Stage 0(YOLO) 추가
      Stage 0: ShapeYolo (모델 있고 score>=thr)
      Stage 1: 흰색영역 (폴백)
      Stage 2: 프레임차분 (폴백)
  → EMA + _move_mouse_toward (기존 그대로)
```

## 인터페이스 계약
- `ShapeYolo.detect(board_bgr) -> Optional[tuple[int,int,float]]` = (rel_cx, rel_cy, score). 모델 미존재/저신뢰 시 None.
- `find_shape_in_board(board_img) -> Optional[tuple[int,int]]` = 상대 중심 (변경 없음, Stage 0만 앞에 추가).
- 모델 경로 `models/shape_yolo.param` 없으면 ShapeYolo는 비활성(_enabled=False) → 기존 휴리스틱으로 자동 폴백. 봇은 절대 안 죽는다.

## 데이터/학습 사양
- 클래스: 1개 (`shape`). 데이터셋 YAML `nc:1, names:['shape']`.
- 입력 해상도: 192 (planet 검증 최적값). letterbox 패딩 114.
- 모델: YOLOv8n (nano). 정규화 1/255, mean 0.
- 데이터 양 가이드: 도형 4종 × 영상 수 개 × 프레임 샘플 → 800~1500장 권장. train/val 8:2.
- export: `yolo export model=best.pt format=ncnn` → `.param/.bin` → `models/`로 복사.

## 비범위 (하지 않음)
- planet 서버 동적 로딩 코드/암호화 라이선스 복원·우회.
- 4모델 앙상블(M1Ensemble) — 단일 nano로 충분한지 먼저 확인, 부족 시에만 검토.
- M2 4클래스 분류 — 풀이에 불필요.
- 그들 가중치(hyung_m*.bin) 봇 탑재.

## 리스크/미정
- ncnn을 설치 .exe(PyInstaller)에 번들 시 용량/DLL 확인 필요(별도 작업).
- 투명 구간 라벨 정확도 — 자동 전파가 부정확하면 수동 보정 비중↑.
- imgsz=192가 우리 board ROI 크기에 최적인지 학습 후 재확인.
- 0/1/2/3 ↔ 모양 매핑은 1클래스 채택으로 불필요해짐.
```
