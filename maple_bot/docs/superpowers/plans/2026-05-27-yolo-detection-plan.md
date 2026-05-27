# YOLO 몬스터 감지 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** YOLO11 커스텀 모델로 몬스터·캐릭터를 감지하고, 캐릭터 기준 좌/우 방향 판단 및 공격 범위 진입 시 공격키를 입력하는 기능을 구현한다. 모델 파일 없으면 기존 템플릿 매칭으로 자동 폴백한다.

**Architecture:** `YoloDetector`(추론) → `CharacterTracker`(위치 보정) → `AttackDecision`(방향·공격 판단) → `bot_loop`(조율·입력) 의 4레이어 분리. `ROIManager`가 화면 비율→픽셀 변환을 담당하고, `bot_loop` 시작 시 모델 존재 여부로 YOLO/템플릿 자동 선택.

**Tech Stack:** Python 3.12+, YOLO11 (ultralytics), PyQt6, win32gui, numpy, opencv-python

---

## 파일 맵

| 파일 | 상태 | 역할 |
|------|------|------|
| `core/roi_manager.py` | 신규 | 비율→픽셀 변환, 게임 창 핸들 탐색 |
| `core/character_tracker.py` | 신규 | EMA 기반 캐릭터 위치 보정 |
| `core/yolo_detector.py` | 신규 | YOLO11 추론 — raw detections 반환 |
| `core/attack_decision.py` | 신규 | 방향 판단, 공격 범위 계산 |
| `core/config_manager.py` | 수정 | DEFAULT_CONFIG에 yolo 섹션 추가 |
| `core/bot_loop.py` | 수정 | YOLO detector 선택, 매 루프 YOLO 파이프라인 통합 |
| `ui/tab_settings1.py` | 수정 | YOLO 설정 UI 섹션 추가 (dev_mode 토글) |

---

## Task 1: ultralytics 의존성 확인 및 ROIManager 구현

**Files:**
- Create: `maple_bot/core/roi_manager.py`

- [ ] **Step 1: ultralytics 설치 확인**

```bash
pip show ultralytics
```

없으면:
```bash
pip install ultralytics
```

- [ ] **Step 2: `core/roi_manager.py` 작성**

```python
# 화면 비율 기반 ROI 계산 및 게임 창 핸들링 모듈
from __future__ import annotations
import win32gui


class ROIManager:
    """화면 비율(0~1) → 절대 픽셀 변환 및 게임 창 위치 감지."""

    def __init__(self) -> None:
        self._hwnd: int | None = None

    # ── 게임 창 탐색 ──────────────────────────────────────────────────
    def find_game_window(self, window_title: str = "MapleStory") -> bool:
        """win32gui로 게임 창 핸들을 탐색. 성공 시 True."""
        hwnd = win32gui.FindWindow(None, window_title)
        if hwnd:
            self._hwnd = hwnd
            return True
        # 부분 매칭 시도
        def _cb(h, _):
            if window_title.lower() in win32gui.GetWindowText(h).lower():
                self._hwnd = h
        win32gui.EnumWindows(_cb, None)
        return self._hwnd is not None

    def get_game_window_rect(self) -> tuple[int, int, int, int]:
        """게임 창 절대 위치와 크기 (x, y, w, h). 창 없으면 (0, 0, 1920, 1080)."""
        if self._hwnd:
            try:
                left, top, right, bottom = win32gui.GetClientRect(self._hwnd)
                cx, cy = win32gui.ClientToScreen(self._hwnd, (0, 0))
                return cx, cy, right - left, bottom - top
            except Exception:
                pass
        return 0, 0, 1920, 1080

    # ── 비율 → 픽셀 변환 ─────────────────────────────────────────────
    def get_absolute_roi(
        self,
        frame_shape: tuple,
        ratio: list[float],
    ) -> tuple[int, int, int, int]:
        """
        ratio = [left, top, right, bottom] (0~1 비율, 프레임 기준)
        반환: (x, y, w, h) 절대 픽셀
        """
        h, w = frame_shape[:2]
        x1 = int(w * ratio[0])
        y1 = int(h * ratio[1])
        x2 = int(w * ratio[2])
        y2 = int(h * ratio[3])
        return x1, y1, max(1, x2 - x1), max(1, y2 - y1)
```

- [ ] **Step 3: 동작 확인 스크립트 실행**

```python
# 터미널에서 python 실행 후 붙여넣기
from core.roi_manager import ROIManager
rm = ROIManager()
found = rm.find_game_window("MapleStory")
print("창 발견:", found, rm.get_game_window_rect())

import numpy as np
frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
roi = rm.get_absolute_roi(frame.shape, [0.22, 0.18, 0.78, 0.72])
print("ROI:", roi)  # 예상: (422, 194, 1075, 583)
```

Expected: 숫자가 비율에 맞게 출력되면 OK.

- [ ] **Step 4: 커밋**

```bash
git add maple_bot/core/roi_manager.py
git commit -m "feat: ROIManager — 비율→픽셀 변환 및 게임 창 핸들링"
```

---

## Task 2: CharacterTracker 구현

**Files:**
- Create: `maple_bot/core/character_tracker.py`

- [ ] **Step 1: `core/character_tracker.py` 작성**

```python
# YOLO 캐릭터 감지 위치를 EMA로 보정하는 트래커
from __future__ import annotations


class CharacterTracker:
    """
    EMA(지수이동평균) 기반 캐릭터 위치 보정.
    - 감지 성공 시: EMA 갱신 후 보정값 반환
    - 감지 실패 시: 이전 EMA 값 반환
    - 연속 max_miss 프레임 실패 시: 리셋 (중앙값 반환)
    """

    def __init__(
        self,
        alpha: float = 0.4,
        max_miss: int = 10,
        default_center: tuple[int, int] = (960, 540),
    ) -> None:
        self._alpha = alpha          # EMA 가중치 (0~1, 클수록 최신값 반영 강함)
        self._max_miss = max_miss    # 연속 미감지 허용 프레임 수
        self._default = default_center
        self._ema_x: float | None = None
        self._ema_y: float | None = None
        self._miss_count: int = 0

    def update(self, detected_center: tuple[int, int] | None) -> tuple[int, int]:
        """
        detected_center: YOLO가 반환한 (cx, cy) 또는 None
        반환: 보정된 캐릭터 위치 (cx, cy)
        """
        if detected_center is not None:
            cx, cy = detected_center
            self._miss_count = 0
            if self._ema_x is None:
                self._ema_x, self._ema_y = float(cx), float(cy)
            else:
                self._ema_x = self._alpha * cx + (1 - self._alpha) * self._ema_x
                self._ema_y = self._alpha * cy + (1 - self._alpha) * self._ema_y
        else:
            self._miss_count += 1
            if self._miss_count >= self._max_miss:
                self.reset()

        if self._ema_x is None:
            return self._default
        return int(self._ema_x), int(self._ema_y)

    def reset(self) -> None:
        """추적 이력 초기화."""
        self._ema_x = None
        self._ema_y = None
        self._miss_count = 0
```

- [ ] **Step 2: 동작 확인**

```python
from core.character_tracker import CharacterTracker
ct = CharacterTracker(alpha=0.4, max_miss=3, default_center=(960, 540))

# 감지 성공
print(ct.update((100, 200)))   # (100, 200) — 첫 감지
print(ct.update((110, 205)))   # EMA 적용, (104, 202) 근처

# 감지 실패
print(ct.update(None))   # 이전 EMA 유지
print(ct.update(None))
print(ct.update(None))   # max_miss=3 도달 → reset
print(ct.update(None))   # (960, 540) — 기본값
```

Expected: EMA 값이 이전 값과 신규 값 사이에 위치하고, 리셋 후 default_center 반환.

- [ ] **Step 3: 커밋**

```bash
git add maple_bot/core/character_tracker.py
git commit -m "feat: CharacterTracker — EMA 기반 캐릭터 위치 보정"
```

---

## Task 3: YoloDetector 구현

**Files:**
- Create: `maple_bot/core/yolo_detector.py`

> 전제: YOLO 모델의 클래스 인덱스는 학습 시 결정됨.
> 이 구현은 `character` 클래스 이름을 기준으로 캐릭터를 식별하고, 나머지를 몬스터로 취급.

- [ ] **Step 1: `core/yolo_detector.py` 작성**

```python
# YOLO11 추론 전담 모듈 — Vision Layer
from __future__ import annotations
import logging
import numpy as np

logger = logging.getLogger(__name__)


class YoloDetector:
    """
    YOLO11 (ultralytics) 추론만 수행.
    반환값은 raw detections — 방향 판단은 AttackDecision에서 처리.
    """

    CHARACTER_CLASS_NAME = "character"  # YOLO 모델의 캐릭터 클래스 이름

    def __init__(
        self,
        model_path: str,
        confidence: float = 0.5,
        iou: float = 0.45,
        max_det: int = 20,
    ) -> None:
        self._conf = confidence
        self._iou  = iou
        self._max_det = max_det
        self._model = None
        self._char_class_id: int | None = None
        self._load(model_path)

    def _load(self, model_path: str) -> None:
        """모델 로드. 실패 시 self._model = None (폴백 신호)."""
        try:
            from ultralytics import YOLO
            self._model = YOLO(model_path)
            # 클래스 이름에서 character 클래스 ID 탐색
            names = self._model.names  # {0: "monster", 1: "character", ...}
            for cid, name in names.items():
                if name.lower() == self.CHARACTER_CLASS_NAME:
                    self._char_class_id = cid
                    break
            logger.info("YoloDetector 로드 완료: %s (character class_id=%s)",
                        model_path, self._char_class_id)
        except Exception as e:
            self._model = None
            logger.warning("YoloDetector 로드 실패 — 템플릿 매칭 폴백: %s", e)

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def detect(
        self,
        frame: np.ndarray,
        roi: tuple[int, int, int, int] | None = None,
    ) -> dict:
        """
        frame: BGR numpy 배열 (전체 스크린샷)
        roi: (x, y, w, h) — 지정 시 해당 영역만 크롭 후 추론
        반환:
            {
                "monsters":   [{"box": [x1,y1,x2,y2], "conf": float}, ...],
                "character":  {"center": (cx, cy), "conf": float} | None,
                "detections": [...]  # 전체 raw (Phase 2 확장용)
            }
        오류 시 빈 결과 반환 (크래시 없음).
        """
        _empty = {"monsters": [], "character": None, "detections": []}
        if self._model is None:
            return _empty

        try:
            crop = frame
            ox, oy = 0, 0
            if roi is not None:
                rx, ry, rw, rh = roi
                crop = frame[ry:ry + rh, rx:rx + rw]
                ox, oy = rx, ry

            results = self._model.predict(
                crop,
                conf=self._conf,
                iou=self._iou,
                max_det=self._max_det,
                verbose=False,
            )

            monsters: list[dict] = []
            character: dict | None = None
            raw: list[dict] = []

            for r in results:
                boxes = r.boxes
                for box in boxes:
                    x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
                    # roi 오프셋 보정
                    x1 += ox; y1 += oy; x2 += ox; y2 += oy
                    conf   = float(box.conf[0])
                    cls_id = int(box.cls[0])
                    raw.append({"box": [x1, y1, x2, y2], "conf": conf, "cls": cls_id})

                    if cls_id == self._char_class_id:
                        # 가장 높은 신뢰도의 캐릭터 1개만 사용
                        if character is None or conf > character["conf"]:
                            character = {
                                "center": ((x1 + x2) // 2, (y1 + y2) // 2),
                                "conf": conf,
                            }
                    else:
                        monsters.append({"box": [x1, y1, x2, y2], "conf": conf})

            return {"monsters": monsters, "character": character, "detections": raw}

        except Exception as e:
            logger.warning("YoloDetector.detect 오류: %s", e)
            return _empty
```

- [ ] **Step 2: 모델 없이 폴백 확인**

```python
from core.yolo_detector import YoloDetector
import numpy as np

yd = YoloDetector("존재하지않는모델.pt")
print("loaded:", yd.is_loaded)   # False

frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
result = yd.detect(frame)
print(result)  # {"monsters": [], "character": None, "detections": []}
```

Expected: `is_loaded=False`, 빈 dict 반환, 크래시 없음.

- [ ] **Step 3: 실제 모델로 추론 확인 (모델 파일 있을 때)**

```python
from core.yolo_detector import YoloDetector
import mss, numpy as np

yd = YoloDetector("path/to/your_model.pt", confidence=0.5)
print("loaded:", yd.is_loaded)   # True

with mss.mss() as sct:
    shot = sct.grab(sct.monitors[1])
    frame = np.array(shot)[:, :, :3]   # BGRA → BGR

result = yd.detect(frame)
print("몬스터:", len(result["monsters"]))
print("캐릭터:", result["character"])
```

Expected: 몬스터/캐릭터 딕셔너리 출력.

- [ ] **Step 4: 커밋**

```bash
git add maple_bot/core/yolo_detector.py
git commit -m "feat: YoloDetector — YOLO11 추론 전담 클래스 (폴백 포함)"
```

---

## Task 4: AttackDecision 구현

**Files:**
- Create: `maple_bot/core/attack_decision.py`

- [ ] **Step 1: `core/attack_decision.py` 작성**

```python
# 방향 판단 및 공격 범위 계산 — Decision Layer
from __future__ import annotations


class AttackDecision:
    """
    캐릭터 위치 + 몬스터 목록을 받아 이동 방향과 공격 가능 여부를 반환.

    방향 판단 우선순위:
    1. 공격 범위 내 몬스터가 있으면 direction=None (제자리 공격)
    2. 좌/우 몬스터 수 비교 → 많은 쪽
    3. 동수이면 캐릭터에 가까운 몬스터가 있는 쪽
    4. 같으면 None (현재 방향 유지)
    """

    def __init__(self, attack_range: dict) -> None:
        """
        attack_range: {
            "left": int,      # 캐릭터 중심 기준 왼쪽 픽셀
            "right": int,     # 캐릭터 중심 기준 오른쪽 픽셀
            "vertical": int,  # 상하 픽셀 (캐릭터 중심 기준 ±vertical)
            "y_offset": int,  # Y 중심 오프셋 (음수=위쪽)
        }
        """
        self._ar = attack_range

    def _attack_box(self, char_cx: int, char_cy: int) -> tuple[int, int, int, int]:
        """공격 범위 박스 (x1, y1, x2, y2)."""
        cy = char_cy + self._ar.get("y_offset", 0)
        v  = self._ar.get("vertical", 180)
        return (
            char_cx - self._ar.get("left",  300),
            cy - v,
            char_cx + self._ar.get("right", 300),
            cy + v,
        )

    @staticmethod
    def _monster_center(m: dict) -> tuple[int, int]:
        x1, y1, x2, y2 = m["box"]
        return (x1 + x2) // 2, (y1 + y2) // 2

    def calculate(
        self,
        character_center: tuple[int, int],
        monsters: list[dict],
    ) -> dict:
        """
        반환: {"direction": "left"|"right"|None, "can_attack": bool}
        """
        if not monsters:
            return {"direction": None, "can_attack": False}

        cx, cy = character_center
        ax1, ay1, ax2, ay2 = self._attack_box(cx, cy)

        # 공격 범위 내 몬스터 필터
        in_range = [
            m for m in monsters
            if ax1 <= self._monster_center(m)[0] <= ax2
            and ay1 <= self._monster_center(m)[1] <= ay2
        ]
        can_attack = len(in_range) > 0

        # 우선순위 1: 공격 범위 내 몬스터 있으면 제자리
        if can_attack:
            return {"direction": None, "can_attack": True}

        # 좌/우 분류
        left_monsters  = [m for m in monsters if self._monster_center(m)[0] < cx]
        right_monsters = [m for m in monsters if self._monster_center(m)[0] >= cx]

        # 우선순위 2: 수 비교
        if len(left_monsters) > len(right_monsters):
            return {"direction": "left", "can_attack": False}
        if len(right_monsters) > len(left_monsters):
            return {"direction": "right", "can_attack": False}

        # 우선순위 3: 동수 — 더 가까운 몬스터가 있는 쪽
        def _closest_dist(ms):
            if not ms:
                return float("inf")
            return min(abs(self._monster_center(m)[0] - cx) for m in ms)

        dl = _closest_dist(left_monsters)
        dr = _closest_dist(right_monsters)
        if dl < dr:
            return {"direction": "left",  "can_attack": False}
        if dr < dl:
            return {"direction": "right", "can_attack": False}

        # 우선순위 4: 완전 동일 → None
        return {"direction": None, "can_attack": False}
```

- [ ] **Step 2: 동작 확인**

```python
from core.attack_decision import AttackDecision

ar = {"left": 300, "right": 300, "vertical": 180, "y_offset": -40}
ad = AttackDecision(ar)

char = (960, 540)

# 케이스 1: 공격 범위 내 몬스터
m_in = {"box": [800, 400, 900, 500]}
print(ad.calculate(char, [m_in]))
# 예상: {"direction": None, "can_attack": True}

# 케이스 2: 왼쪽 2개, 오른쪽 1개
m_l1 = {"box": [400, 400, 450, 500]}
m_l2 = {"box": [500, 400, 550, 500]}
m_r1 = {"box": [1300, 400, 1350, 500]}
print(ad.calculate(char, [m_l1, m_l2, m_r1]))
# 예상: {"direction": "left", "can_attack": False}

# 케이스 3: 몬스터 없음
print(ad.calculate(char, []))
# 예상: {"direction": None, "can_attack": False}
```

Expected: 각 케이스 주석과 일치.

- [ ] **Step 3: 커밋**

```bash
git add maple_bot/core/attack_decision.py
git commit -m "feat: AttackDecision — 우선순위 기반 방향 판단 및 공격 범위 계산"
```

---

## Task 5: Config에 yolo 섹션 추가

**Files:**
- Modify: `maple_bot/core/config_manager.py`

- [ ] **Step 1: `DEFAULT_CONFIG`에 yolo 섹션 추가**

`core/config_manager.py`의 `DEFAULT_CONFIG` 딕셔너리 마지막 항목 뒤에 추가:

```python
    "yolo": {
        "enabled":              False,
        "model_path":           "",
        "confidence":           0.5,
        "iou":                  0.45,
        "max_det":              20,
        "every_n_frame":        1,
        "dev_mode":             False,
        "detection_roi_ratio":  [0.22, 0.18, 0.78, 0.72],
        "central_area_ratio":   [0.20, 0.10, 0.80, 0.85],
        "attack_range": {
            "left":     300,
            "right":    300,
            "vertical": 180,
            "y_offset": -40,
        },
    },
```

- [ ] **Step 2: 확인**

```python
from core.config_manager import ConfigManager
cfg = ConfigManager()
print(cfg.get("yolo", "enabled"))       # False
print(cfg.get("yolo", "confidence"))    # 0.5
print(cfg.get("yolo", "attack_range"))  # {"left":300, ...}
```

Expected: 위 값들이 출력되면 OK.

- [ ] **Step 3: 커밋**

```bash
git add maple_bot/core/config_manager.py
git commit -m "feat: config — yolo 설정 섹션 추가 (DEFAULT_CONFIG)"
```

---

## Task 6: bot_loop에 YOLO 파이프라인 통합

**Files:**
- Modify: `maple_bot/core/bot_loop.py`

> 기존 `self._detector` (템플릿 매칭)는 유지. YOLO는 별도 파이프라인으로 실행.

- [ ] **Step 1: `__init__`에 YOLO 관련 필드 추가**

`bot_loop.py`의 `BotLoop.__init__` 마지막 부분에 추가:

```python
        # YOLO 파이프라인 (enabled+모델 있을 때만 초기화)
        self._yolo_detector:      "YoloDetector | None"   = None
        self._char_tracker:       "CharacterTracker | None" = None
        self._attack_decision:    "AttackDecision | None"  = None
        self._roi_manager:        "ROIManager | None"      = None
        self._yolo_frame_counter: int   = 0
        self._yolo_last_result:   dict  = {"monsters": [], "character": None, "detections": []}
        self._yolo_char_center:   "tuple[int,int] | None" = None
        self._yolo_active:        bool  = False   # YOLO 실제 작동 여부
```

- [ ] **Step 2: `_init_yolo()` 메서드 추가**

`BotLoop` 클래스 내부 `_game_window_title` 메서드 바로 위에 추가:

```python
    def _init_yolo(self) -> None:
        """YOLO 파이프라인 초기화. 모델 없거나 disabled면 self._yolo_active=False."""
        from core.yolo_detector   import YoloDetector
        from core.character_tracker import CharacterTracker
        from core.attack_decision  import AttackDecision
        from core.roi_manager      import ROIManager

        yolo_cfg = self._config.get("yolo") or {}
        if not yolo_cfg.get("enabled", False):
            self._status("YOLO 비활성화 — 템플릿 매칭 사용")
            return

        model_path = yolo_cfg.get("model_path", "").strip()
        if not model_path:
            self._status("YOLO 모델 경로 미설정 — 템플릿 매칭 폴백")
            return

        yd = YoloDetector(
            model_path  = model_path,
            confidence  = float(yolo_cfg.get("confidence", 0.5)),
            iou         = float(yolo_cfg.get("iou", 0.45)),
            max_det     = int(yolo_cfg.get("max_det", 20)),
        )
        if not yd.is_loaded:
            self._status("YOLO 모델 로드 실패 — 템플릿 매칭 폴백")
            return

        ar = yolo_cfg.get("attack_range", {
            "left": 300, "right": 300, "vertical": 180, "y_offset": -40
        })
        self._yolo_detector   = yd
        self._char_tracker    = CharacterTracker()
        self._attack_decision = AttackDecision(ar)
        self._roi_manager     = ROIManager()
        self._roi_manager.find_game_window(
            self._config.get("settings2", "game_window_title") or "MapleStory"
        )
        self._yolo_active = True
        self._status("✅ YOLO 파이프라인 초기화 완료")
```

- [ ] **Step 3: `start()` 메서드에서 `_init_yolo()` 호출**

`bot_loop.py`의 `start()` 메서드에서 스레드 시작 직전에 추가:

```python
        self._init_yolo()
```

기존 `start()` 구조:
```python
    def start(self) -> None:
        self._stop_event.clear()
        self._init_yolo()          # ← 이 줄 추가
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        ...
```

- [ ] **Step 4: 메인 루프에 YOLO 파이프라인 블록 추가**

`bot_loop.py`의 `_run()` 메인 루프 안, 이동+스킬 실행 블록(`_on_transit` 계산) 직전에 추가:

```python
                    # ── YOLO 파이프라인 ────────────────────────────────
                    if self._yolo_active:
                        yolo_cfg = self._config.get("yolo") or {}
                        every_n  = int(yolo_cfg.get("every_n_frame", 1))
                        self._yolo_frame_counter += 1
                        if self._yolo_frame_counter >= every_n:
                            self._yolo_frame_counter = 0
                            det_ratio = yolo_cfg.get(
                                "detection_roi_ratio", [0.22, 0.18, 0.78, 0.72]
                            )
                            roi = self._roi_manager.get_absolute_roi(
                                screenshot.shape, det_ratio
                            )
                            self._yolo_last_result = self._yolo_detector.detect(
                                screenshot, roi
                            )

                        raw_char = self._yolo_last_result.get("character")
                        char_center_raw = raw_char["center"] if raw_char else None
                        self._yolo_char_center = self._char_tracker.update(char_center_raw)

                        monsters = self._yolo_last_result.get("monsters", [])
                        decision = self._attack_decision.calculate(
                            self._yolo_char_center, monsters
                        )

                        # 방향 보정 (공격 범위 밖에 몬스터 있을 때만)
                        if decision["direction"] == "left":
                            self._map_navigator.force_direction("left")
                        elif decision["direction"] == "right":
                            self._map_navigator.force_direction("right")

                        # 공격 범위 내 몬스터 → 공격키 (이동 중단 없이)
                        if decision["can_attack"] and self._enable_attack:
                            attack_key = (
                                self._config.get("attack", "key") or "ctrl"
                            )
                            self._input.press_key(attack_key, hold_sec=0.05)
                        continue   # 이동+스킬 일반 루프 스킵
```

- [ ] **Step 5: 커밋**

```bash
git add maple_bot/core/bot_loop.py
git commit -m "feat: bot_loop — YOLO 파이프라인 통합 (every_n_frame, 폴백 포함)"
```

---

## Task 7: UI — YOLO 설정 섹션 추가 (tab_settings1)

**Files:**
- Modify: `maple_bot/ui/tab_settings1.py`

- [ ] **Step 1: tab_settings1.py import 블록에 추가**

기존 import 블록 안에 추가:
```python
from PyQt6.QtWidgets import QFileDialog, QDoubleSpinBox, QSlider
from PyQt6.QtCore    import Qt
```

- [ ] **Step 2: `__init__` 내 `layout.addStretch()` 직전에 YOLO 그룹 추가 호출**

```python
        layout.addWidget(self._build_yolo_group())
        layout.addStretch()
```

- [ ] **Step 3: `_build_yolo_group()` 메서드 추가**

```python
    def _build_yolo_group(self) -> QGroupBox:
        """YOLO 설정 그룹 — dev_mode=True일 때만 고급 설정 노출."""
        from PyQt6.QtWidgets import QFileDialog, QDoubleSpinBox
        yolo_cfg = self.config.get("yolo") or {}
        dev_mode  = bool(yolo_cfg.get("dev_mode", False))

        box = QGroupBox("🤖 YOLO 몬스터 감지")
        layout = QVBoxLayout(box)
        layout.setSpacing(6)

        # ── 활성화 ──────────────────────────────────────────────────
        self.chk_yolo_enabled = QCheckBox("YOLO 감지 활성화 (모델 파일 필요)")
        self.chk_yolo_enabled.setChecked(bool(yolo_cfg.get("enabled", False)))
        self.chk_yolo_enabled.stateChanged.connect(self._save_yolo)
        layout.addWidget(self.chk_yolo_enabled)

        # ── 모델 경로 ────────────────────────────────────────────────
        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("모델 (.pt)"))
        self.lbl_yolo_model = QLabel(yolo_cfg.get("model_path", "") or "미설정")
        self.lbl_yolo_model.setStyleSheet("color: gray; font-size: 10px;")
        self.lbl_yolo_model.setWordWrap(True)
        btn_model = QPushButton("📂 선택")
        btn_model.setFixedWidth(60)
        btn_model.clicked.connect(self._select_yolo_model)
        path_row.addWidget(self.lbl_yolo_model, 1)
        path_row.addWidget(btn_model)
        layout.addLayout(path_row)

        # ── Confidence / IoU ─────────────────────────────────────────
        conf_row = QHBoxLayout()
        conf_row.addWidget(QLabel("Confidence"))
        self.spin_yolo_conf = QDoubleSpinBox()
        self.spin_yolo_conf.setRange(0.1, 1.0)
        self.spin_yolo_conf.setSingleStep(0.05)
        self.spin_yolo_conf.setValue(float(yolo_cfg.get("confidence", 0.5)))
        self.spin_yolo_conf.setFixedWidth(70)
        self.spin_yolo_conf.valueChanged.connect(self._save_yolo)
        conf_row.addWidget(self.spin_yolo_conf)
        conf_row.addSpacing(12)
        conf_row.addWidget(QLabel("IoU"))
        self.spin_yolo_iou = QDoubleSpinBox()
        self.spin_yolo_iou.setRange(0.1, 1.0)
        self.spin_yolo_iou.setSingleStep(0.05)
        self.spin_yolo_iou.setValue(float(yolo_cfg.get("iou", 0.45)))
        self.spin_yolo_iou.setFixedWidth(70)
        self.spin_yolo_iou.valueChanged.connect(self._save_yolo)
        conf_row.addWidget(self.spin_yolo_iou)
        conf_row.addStretch()
        layout.addLayout(conf_row)

        # ── DEV MODE 전용 고급 설정 ──────────────────────────────────
        self._yolo_dev_widget = QWidget()
        dev_layout = QVBoxLayout(self._yolo_dev_widget)
        dev_layout.setContentsMargins(0, 0, 0, 0)
        dev_layout.setSpacing(4)

        # every_n_frame / max_det
        perf_row = QHBoxLayout()
        perf_row.addWidget(QLabel("추론 주기 (프레임)"))
        self.spin_yolo_every_n = QSpinBox()
        self.spin_yolo_every_n.setRange(1, 10)
        self.spin_yolo_every_n.setValue(int(yolo_cfg.get("every_n_frame", 1)))
        self.spin_yolo_every_n.setFixedWidth(55)
        self.spin_yolo_every_n.valueChanged.connect(self._save_yolo)
        perf_row.addWidget(self.spin_yolo_every_n)
        perf_row.addSpacing(12)
        perf_row.addWidget(QLabel("최대 감지 수"))
        self.spin_yolo_max_det = QSpinBox()
        self.spin_yolo_max_det.setRange(1, 100)
        self.spin_yolo_max_det.setValue(int(yolo_cfg.get("max_det", 20)))
        self.spin_yolo_max_det.setFixedWidth(55)
        self.spin_yolo_max_det.valueChanged.connect(self._save_yolo)
        perf_row.addWidget(self.spin_yolo_max_det)
        perf_row.addStretch()
        dev_layout.addLayout(perf_row)

        # detection_roi_ratio
        ar = yolo_cfg.get("attack_range", {})
        roi_note = QLabel(
            f"감지 ROI 비율: {yolo_cfg.get('detection_roi_ratio', [0.22,0.18,0.78,0.72])}\n"
            f"공격 범위: 좌{ar.get('left',300)} 우{ar.get('right',300)} "
            f"상하{ar.get('vertical',180)} Y오프셋{ar.get('y_offset',-40)}"
        )
        roi_note.setStyleSheet("color: #888; font-size: 10px;")
        roi_note.setWordWrap(True)
        dev_layout.addWidget(roi_note)

        self._yolo_dev_widget.setVisible(dev_mode)
        layout.addWidget(self._yolo_dev_widget)

        # DEV MODE 토글 (항상 보임)
        chk_dev = QCheckBox("🛠 개발 모드 (고급 설정 표시)")
        chk_dev.setChecked(dev_mode)
        chk_dev.setStyleSheet("color: gray; font-size: 10px;")
        chk_dev.stateChanged.connect(lambda v: (
            self._yolo_dev_widget.setVisible(bool(v)),
            self.config.set("yolo", "dev_mode", bool(v)),
            self.config.save(),
        ))
        layout.addWidget(chk_dev)

        return box

    def _select_yolo_model(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "YOLO 모델 선택", "", "PyTorch Model (*.pt)"
        )
        if path:
            self.config.set("yolo", "model_path", path)
            self.config.save()
            self.lbl_yolo_model.setText(path)
            self.lbl_yolo_model.setStyleSheet("color: green; font-size: 10px;")

    def _save_yolo(self) -> None:
        self.config.set("yolo", "enabled",      self.chk_yolo_enabled.isChecked())
        self.config.set("yolo", "confidence",   self.spin_yolo_conf.value())
        self.config.set("yolo", "iou",          self.spin_yolo_iou.value())
        self.config.set("yolo", "every_n_frame", self.spin_yolo_every_n.value())
        self.config.set("yolo", "max_det",       self.spin_yolo_max_det.value())
        self.config.save()
```

- [ ] **Step 4: `load_from_config()` 메서드에 YOLO 값 로드 추가**

`tab_settings1.py`의 `load_from_config()` 마지막에 추가:

```python
        # YOLO 설정 로드
        yolo = self.config.get("yolo") or {}
        self.chk_yolo_enabled.setChecked(bool(yolo.get("enabled", False)))
        self.spin_yolo_conf.setValue(float(yolo.get("confidence", 0.5)))
        self.spin_yolo_iou.setValue(float(yolo.get("iou", 0.45)))
        self.spin_yolo_every_n.setValue(int(yolo.get("every_n_frame", 1)))
        self.spin_yolo_max_det.setValue(int(yolo.get("max_det", 20)))
        model_path = yolo.get("model_path", "")
        if model_path:
            self.lbl_yolo_model.setText(model_path)
            self.lbl_yolo_model.setStyleSheet("color: green; font-size: 10px;")
```

- [ ] **Step 5: 앱 실행 후 UI 확인**

```bash
cd C:\Users\PC\Desktop\02_work\05_AI\maple_bot
python main.py
```

설정1 탭 하단에 "🤖 YOLO 몬스터 감지" 그룹이 보이는지 확인.
"🛠 개발 모드" 체크박스를 켜면 고급 설정이 나타나는지 확인.

- [ ] **Step 6: 커밋**

```bash
git add maple_bot/ui/tab_settings1.py
git commit -m "feat: tab_settings1 — YOLO 설정 UI 추가 (dev_mode 토글)"
```

---

## Task 8: 전체 통합 확인 및 마무리

- [ ] **Step 1: 앱 실행 후 YOLO 비활성화 상태 동작 확인**

```bash
python main.py
```

1. 설정1 탭 → YOLO 비활성화 상태
2. 봇 시작 → 상태 로그에 "YOLO 비활성화 — 템플릿 매칭 사용" 출력 확인
3. 기존 템플릿 매칭 방식으로 정상 사냥 확인

- [ ] **Step 2: YOLO 활성화 + 모델 파일 없는 상태 폴백 확인**

1. 설정1 탭 → YOLO 활성화 체크
2. 모델 경로 미설정 상태로 봇 시작
3. 상태 로그에 "YOLO 모델 경로 미설정 — 템플릿 매칭 폴백" 출력 확인
4. 기존 방식으로 정상 동작 확인

- [ ] **Step 3: YOLO 활성화 + 실제 모델 파일로 동작 확인 (모델 있을 때)**

1. 설정1 탭 → 모델 파일 선택 (.pt)
2. 봇 시작 → "✅ YOLO 파이프라인 초기화 완료" 로그 확인
3. 캐릭터 감지되면 방향 전환 동작 확인
4. 몬스터 공격 범위 진입 시 공격키 입력 확인

- [ ] **Step 4: 최종 커밋**

```bash
git add -A
git commit -m "feat: YOLO11 몬스터 감지 파이프라인 완성 (ROIManager, CharacterTracker, YoloDetector, AttackDecision, UI)"
git push
```
