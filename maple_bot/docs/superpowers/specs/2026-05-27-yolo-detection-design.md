# YOLO 몬스터 감지 기능 설계 문서

## Goal
기존 OpenCV 템플릿 매칭 방식을 YOLO11 커스텀 모델로 대체하여, 몬스터 인지 범위 박스 내 몬스터를 감지하고 캐릭터 기준 좌/우 방향 판단 및 공격 범위 진입 시 공격키를 입력하는 기능을 구현한다.

## Architecture

### 레이어 분리 원칙
- **Vision Layer** (`YoloDetector`): YOLO 추론만 수행, raw detections 반환
- **Decision Layer** (`AttackDecision`): 방향 판단, 공격 범위 계산, 명령 생성
- **Utility Layer** (`ROIManager`): 비율→픽셀 변환, 게임 창 크기 감지
- **Orchestration** (`bot_loop`): 위 레이어 조율 및 Input 실행

### 폴백 전략
- 모델 파일 없거나 로드 실패 → 기존 `Detector` (템플릿 매칭) 자동 사용
- 폴백 시 방향 판단 없이 현재 방식 그대로 동작

---

## 파일 구조

| 파일 | 역할 | 상태 |
|------|------|------|
| `core/yolo_detector.py` | YOLO11 추론 — character + monster raw detections | 신규 |
| `core/roi_manager.py` | 비율→픽셀 변환, 게임 창 크기 감지 | 신규 |
| `core/attack_decision.py` | 방향 판단, 캐릭터 중심 공격 범위 계산 | 신규 |
| `core/detector.py` | 기존 템플릿 매칭 — 폴백용 | 유지 |
| `core/bot_loop.py` | Pipeline 조율 | 수정 |
| `core/config_manager.py` | yolo 설정 섹션 추가 | 수정 |
| `ui/tab_settings1.py` | YOLO UI (dev_mode=true일 때만 드래그/수정 노출) | 수정 |

---

## Config 구조

```json
"yolo": {
  "model_path": "",
  "confidence": 0.5,
  "iou": 0.45,
  "dev_mode": false,

  "detection_roi_ratio": [0.25, 0.15, 0.75, 0.70],
  "central_area_ratio":  [0.20, 0.10, 0.80, 0.85],

  "attack_range": {
    "left":     300,
    "right":    300,
    "vertical": 180,
    "y_offset": -40
  }
}
```

- `detection_roi_ratio`: 몬스터 탐지 영역 (화면 비율 0~1, [left, top, right, bottom])
- `central_area_ratio`: 캐릭터 탐지 영역 (화면 비율 0~1)
- `attack_range`: 캐릭터 중심 기준 공격 범위 픽셀 offset

---

## 인터페이스 정의

### ROIManager

```python
class ROIManager:
    def get_absolute_roi(self, frame_shape: tuple, ratio: list) -> tuple:
        """비율(0~1) → 절대 픽셀 (x, y, w, h) 변환"""

    def get_game_window_size(self) -> tuple[int, int]:
        """현재 게임 창 크기 (width, height) 반환 — win32gui 사용"""
```

### YoloDetector

```python
class YoloDetector:
    def __init__(self, model_path: str, confidence: float, iou: float): ...

    def detect(self, frame: np.ndarray, roi: tuple | None = None) -> dict:
        """
        반환:
        {
            "monsters":  [{"box": [x1,y1,x2,y2], "conf": 0.9}, ...],
            "character": {"center": (cx, cy), "conf": 0.95},  # 미감지 시 None
            "detections": [...]  # 전체 raw (확장용)
        }
        """
```

- 캐릭터 미감지 시: 이전 프레임 위치 + 이동 평균(Tracking)으로 보완
- roi 지정 시 해당 영역만 크롭 후 추론

### AttackDecision

```python
class AttackDecision:
    def __init__(self, attack_range: dict): ...

    def calculate(
        self,
        character_center: tuple[int, int],
        monsters: list[dict],
    ) -> dict:
        """
        반환:
        {
            "direction":  "left" | "right" | None,
            "can_attack": True | False,
        }
        """
```

- `direction`: 캐릭터 좌/우 몬스터 수 비교, 많은 쪽 반환. 동수이면 현재 방향 유지
- `can_attack`: attack_range(캐릭터 중심 + offset) 내 몬스터 존재 여부

---

## 매 루프 흐름

```
스크린샷 캡처
  ↓
ROIManager.get_absolute_roi(frame, detection_roi_ratio)
  ↓
YoloDetector.detect(frame, detection_roi)
  → character.center  (미감지 시 이전값 + 이동 평균)
  → monsters 리스트
  ↓
AttackDecision.calculate(character_center, monsters)
  → attack_range = character_center + offset
  → 좌/우 몬스터 수 비교 → direction
  → attack_range 내 몬스터 존재 → can_attack
  ↓
bot_loop
  → direction → MapNavigator.walk_toward
  → can_attack → 공격키 입력
```

---

## DEV_MODE UI

| 기능 | dev_mode=true | dev_mode=false (배포) |
|------|--------------|----------------------|
| 드래그로 ROI 설정 | 노출 | 숨김 |
| detection_roi / attack_range 수치 편집 | 노출 | 숨김 |
| "게임 창 기준 자동 적용" 버튼 | 노출 | 숨김 |
| 모델 경로 파일 브라우저 | 노출 | 노출 |
| confidence / iou 슬라이더 | 노출 | 노출 |

드래그 설정 시 실제 픽셀 좌표를 비율로 변환해서 `detection_roi_ratio`에 저장.

---

## 확장 계획 (Phase 2)

YOLO 모델이 몬스터 감지를 안정적으로 수행하면 아래 항목을 추가 클래스로 확장:

- HP/MP 바 감지 → `HPDetector`
- 거짓말 탐지기 감지 → `LieDetector` 대체
- 맵 이름 감지 (사냥터 이탈) → `MapNameDetector`
- 자동 판매 UI 감지 → `ShopDetector`

각 항목은 `YoloDetector.detect()`의 `detections` raw 결과를 공유해 추론을 1회만 실행하도록 설계.

---

## 기술 스택

- YOLO11 (Ultralytics): `pip install ultralytics`
- 모델 파일: 사용자 학습 `.pt` 파일
- 창 크기 감지: `win32gui` (기존 프로젝트 의존성)
- 캐릭터 Tracking: 이동 평균 (간단한 ExponentialMovingAverage)
