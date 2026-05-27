# YOLO 몬스터 감지 기능 설계 문서

## Goal
기존 OpenCV 템플릿 매칭 방식을 YOLO11 커스텀 모델로 대체하여, 몬스터 인지 범위 박스 내 몬스터를 감지하고 캐릭터 기준 좌/우 방향 판단 및 공격 범위 진입 시 공격키를 입력하는 기능을 구현한다.

## Architecture

### 레이어 분리 원칙
- **Vision Layer** (`YoloDetector`): YOLO 추론만 수행, raw detections 반환
- **Tracking Layer** (`CharacterTracker`): 캐릭터 위치 보정 및 이력 관리
- **Decision Layer** (`AttackDecision`): 방향 판단, 공격 범위 계산, 명령 생성
- **Utility Layer** (`ROIManager`): 비율→픽셀 변환, 게임 창 핸들링
- **Orchestration** (`bot_loop`): 위 레이어 조율 및 Input 실행

### 폴백 전략
- `yolo.enabled = false` 또는 모델 파일 없거나 로드 실패 → 기존 `Detector` (템플릿 매칭) 자동 사용
- 폴백 시 방향 판단 없이 현재 방식 그대로 동작

---

## 파일 구조

| 파일 | 역할 | 상태 |
|------|------|------|
| `core/yolo_detector.py` | YOLO11 추론 — character + monster raw detections | 신규 |
| `core/character_tracker.py` | EMA + Kalman Filter 옵션 — 캐릭터 위치 보정 | 신규 |
| `core/roi_manager.py` | 비율→픽셀 변환, 게임 창 핸들링 | 신규 |
| `core/attack_decision.py` | 방향 판단, 캐릭터 중심 공격 범위 계산 | 신규 |
| `core/detector.py` | 기존 템플릿 매칭 — 폴백용 | 유지 |
| `core/bot_loop.py` | Pipeline 조율 | 수정 |
| `core/config_manager.py` | yolo 설정 섹션 추가 | 수정 |
| `ui/tab_settings1.py` | YOLO UI (dev_mode=true일 때만 드래그/수정 노출) | 수정 |

---

## Config 구조

```json
"yolo": {
  "enabled": true,
  "model_path": "",
  "confidence": 0.5,
  "iou": 0.45,
  "max_det": 20,
  "every_n_frame": 1,
  "dev_mode": false,

  "detection_roi_ratio": [0.22, 0.18, 0.78, 0.72],
  "central_area_ratio":  [0.20, 0.10, 0.80, 0.85],

  "attack_range": {
    "left":     300,
    "right":    300,
    "vertical": 180,
    "y_offset": -40
  }
}
```

- `enabled`: false이면 YOLO 비활성화, 템플릿 매칭 폴백
- `max_det`: 추론당 최대 감지 수 (성능 제한)
- `every_n_frame`: N 프레임마다 추론 실행 (1=매 프레임, 2=격 프레임)
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

    def get_game_window_rect(self) -> tuple:
        """게임 창 위치 및 크기 (x, y, w, h) 반환"""

    def find_game_window(self, window_title: str = "MapleStory") -> bool:
        """win32gui로 게임 창 핸들 탐색, 성공 시 True"""
```

### CharacterTracker

```python
class CharacterTracker:
    """
    캐릭터 위치 이력 관리 및 보정.
    - 기본: Exponential Moving Average (EMA)
    - 옵션: Kalman Filter (config에서 선택)
    """
    def update(self, detected_center: tuple | None) -> tuple:
        """
        detected_center: YOLO 감지 결과 (없으면 None)
        반환: 보정된 캐릭터 center (cx, cy)
        """

    def reset(self) -> None:
        """추적 이력 초기화"""
```

- 감지 실패 시 EMA 기반 이전 위치로 보완
- 연속 N 프레임 미감지 시 `reset()` 후 중앙 영역 기본값 사용

### YoloDetector

```python
class YoloDetector:
    def __init__(
        self,
        model_path: str,
        confidence: float = 0.5,
        iou: float = 0.45,
        max_det: int = 20,
    ): ...

    def detect(self, frame: np.ndarray, roi: tuple | None = None) -> dict:
        """
        반환:
        {
            "monsters":   [{"box": [x1,y1,x2,y2], "conf": 0.9}, ...],
            "character":  {"center": (cx, cy), "conf": 0.95},  # 미감지 시 None
            "detections": [...]  # 전체 raw (Phase 2 확장용)
        }
        예외: 모델 오류 시 빈 dict 반환 (크래시 없음)
        """
```

- `roi` 지정 시 해당 영역만 크롭 후 추론
- YOLO 모델이 None 반환하거나 예외 발생 시 `{"monsters": [], "character": None, "detections": []}` 반환

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

**방향 판단 우선순위:**
1. 공격 범위 안에 이미 몬스터가 있으면 `direction = None` (제자리 공격)
2. 좌/우 몬스터 수 비교 → 많은 쪽 방향
3. 동수일 경우 캐릭터 중심에 가까운 몬스터가 있는 쪽 우선
4. 가장 가까운 몬스터 기준으로 최종 결정

---

## 매 루프 흐름

```
스크린샷 캡처
  ↓
every_n_frame 체크 — 스킵 프레임이면 이전 결과 재사용
  ↓
ROIManager.get_absolute_roi(frame, detection_roi_ratio)
  ↓
YoloDetector.detect(frame, detection_roi)          ← 예외 시 빈 결과 반환
  → character.center (None이면 CharacterTracker 보정값 사용)
  → monsters 리스트
  ↓
CharacterTracker.update(character.center)
  → 보정된 character_center
  ↓
AttackDecision.calculate(character_center, monsters)
  → attack_range = character_center + offset
  → 우선순위 방향 판단 → direction
  → attack_range 내 몬스터 존재 → can_attack
  ↓
bot_loop
  → direction → MapNavigator.walk_toward (또는 현재 방향 유지)
  → can_attack → 공격키 입력
```

---

## DEV_MODE UI

| 기능 | dev_mode=true | dev_mode=false (배포) |
|------|--------------|----------------------|
| 드래그로 ROI 설정 | 노출 | 숨김 |
| detection_roi / attack_range 수치 편집 | 노출 | 숨김 |
| "게임 창 기준 자동 적용" 버튼 | 노출 | 숨김 |
| every_n_frame / max_det 설정 | 노출 | 숨김 |
| 모델 경로 파일 브라우저 | 노출 | 노출 |
| confidence / iou 슬라이더 | 노출 | 노출 |
| enabled 체크박스 | 노출 | 노출 |

드래그 설정 시 실제 픽셀 좌표를 비율로 변환해서 `detection_roi_ratio`에 저장.

---

## 확장 계획 (Phase 2)

YOLO 모델이 몬스터 감지를 안정적으로 수행하면 아래 항목을 추가 클래스로 확장.
`YoloDetector.detect()`의 `detections` raw 결과를 공유해 추론을 1회만 실행.

| 클래스 | 감지 대상 |
|--------|----------|
| `HPDetector` | HP/MP 바 |
| `LieDetector` (YOLO 대체) | 거짓말 탐지기 |
| `MapNameDetector` | 맵 이름 (사냥터 이탈 감지) |
| `ShopDetector` | 자동 판매 UI |

---

## 기술 스택

- YOLO11 (Ultralytics): `pip install ultralytics`
- 모델 파일: 사용자 학습 `.pt` 파일
- 창 핸들링: `win32gui` (기존 프로젝트 의존성)
- 캐릭터 Tracking: EMA (기본) / Kalman Filter (옵션)
