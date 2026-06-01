# 실시간 미니맵 캔버스 + 캐릭터 투영 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 인게임 미니맵을 실시간으로 캡처해 캔버스 배경으로 깔고, 캐릭터(노란 점)·공격/사냥 범위를 그 위에 줌 비례로 투영하는 보기 전용 위젯을 만든다.

**Architecture:** 좌표 변환은 위젯과 분리한 순수 함수 모듈(`minimap_geom.py`)에 두고, `MinimapCanvas(QWidget)`가 `QTimer`로 미니맵을 캡처→`find_char_in_hsv`로 캐릭터를 찾고→`paintEvent`에서 배경·점·범위를 그린다. 모든 좌표는 미니맵 픽셀 기준이며 화면에 그릴 때 줌 배율을 곱한다.

**Tech Stack:** PyQt6(QWidget/QTimer/QPainter/QImage), numpy, 기존 `core/sensing/char_scanner.find_char_in_hsv`, `core/screen_reader.ScreenReader`.

**참고 규칙(이 저장소):** 모든 신규 소스 첫 줄에 역할을 적은 한국어 주석 1줄. 테스트는 `QT_QPA_PLATFORM=offscreen`. 명령은 `py -3.14 -m pytest`.

---

## 파일 구조

| 파일 | 책임 |
|------|------|
| `core_ui/minimap_geom.py` (생성) | 미니맵↔캔버스 좌표 변환 + 화면px→미니맵px 범위 환산 (순수 함수) |
| `core_ui/minimap_canvas.py` (생성) | 실시간 캡처·캐릭터 투영·범위·줌 캔버스 위젯 |
| `core_ui/pages.py` (수정) | "동선·이동" 페이지 상단에 `MinimapCanvas` 추가 |
| `tests/test_minimap_geom.py` (생성) | 순수 함수 단위 테스트 |
| `tests/test_minimap_canvas.py` (생성) | 위젯 offscreen 스모크 테스트 |

---

### Task 1: 좌표 변환 순수 함수

**Files:**
- Create: `core_ui/minimap_geom.py`
- Test: `tests/test_minimap_geom.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_minimap_geom.py`:
```python
# 미니맵↔캔버스 좌표 변환 + 범위 환산 순수 함수 검증
from core_ui.minimap_geom import minimap_to_canvas, screen_px_to_minimap_px


def test_minimap_to_canvas_zoom_and_pan():
    assert minimap_to_canvas(10, 20, 1.0) == (10, 20)
    assert minimap_to_canvas(10, 20, 2.0) == (20, 40)
    assert minimap_to_canvas(10, 20, 2.0, pan=(5, -3)) == (25, 37)


def test_screen_px_to_minimap_px_proportional():
    # factor = camera_w_ratio*minimap_w/screen_w = 0.5*200/1000 = 0.1
    assert screen_px_to_minimap_px(35, 200, 1000, 0.5) == 3.5
    assert screen_px_to_minimap_px(70, 200, 1000, 0.5) == 7.0   # 2배 입력→2배 출력


def test_screen_px_to_minimap_px_guards_zero_screen():
    assert screen_px_to_minimap_px(35, 200, 0, 0.5) == 0.0
```

- [ ] **Step 2: 실패 확인**

Run: `cd /c/Users/PC/Desktop/02_work/05_AI/maple_bot && QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_minimap_geom.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'core_ui.minimap_geom'`

- [ ] **Step 3: 구현**

`core_ui/minimap_geom.py`:
```python
# 미니맵↔캔버스 좌표 변환 + 화면px→미니맵px 범위 환산 (위젯 의존 없는 순수 함수)
from __future__ import annotations


def minimap_to_canvas(cx: int, cy: int, zoom: float,
                      pan: tuple[int, int] = (0, 0)) -> tuple[int, int]:
    """미니맵 픽셀(cx,cy)을 줌·팬 적용한 캔버스 픽셀로 변환."""
    return (round(cx * zoom + pan[0]), round(cy * zoom + pan[1]))


def screen_px_to_minimap_px(screen_px: float, minimap_w: int,
                            screen_w: int, camera_w_ratio: float) -> float:
    """화면 픽셀 거리를 미니맵 픽셀 거리로 환산.

    미니맵 폭 중 카메라 가시 폭 = camera_w_ratio*minimap_w 이고, 화면 폭(screen_w)이
    그 폭에 대응하므로 비례 환산한다. screen_w<=0이면 0.0(방어).
    """
    if screen_w <= 0:
        return 0.0
    return screen_px * (camera_w_ratio * minimap_w) / screen_w
```

- [ ] **Step 4: 통과 확인**

Run: `cd /c/Users/PC/Desktop/02_work/05_AI/maple_bot && QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_minimap_geom.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add core_ui/minimap_geom.py tests/test_minimap_geom.py
git commit -m "feat(minimap): 좌표 변환·범위 환산 순수 함수"
```

---

### Task 2: MinimapCanvas 위젯 (캡처·투영·범위·에러표시)

**Files:**
- Create: `core_ui/minimap_canvas.py`
- Test: `tests/test_minimap_canvas.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_minimap_canvas.py`:
```python
# MinimapCanvas — 실시간 캡처·캐릭터 투영·에러표시 offscreen 스모크
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication
from core_ui.minimap_canvas import MinimapCanvas


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class FakeConfig:
    def __init__(self, data=None): self._d = data or {}
    def get(self, *keys, default=None):
        node = self._d
        for k in keys:
            if not isinstance(node, dict) or k not in node:
                return default
            node = node[k]
        return node


def _region_cfg():
    return FakeConfig({"minimap": {"region_x": 0, "region_y": 0,
                                   "width": 200, "height": 120}})


def test_tick_detects_char_and_paints(app):
    cfg = _region_cfg()
    shot = np.zeros((120, 200, 3), dtype=np.uint8)
    cv = MinimapCanvas(cfg, screen_capture=lambda r: shot,
                       char_finder=lambda *a, **k: (50, 60), interval_ms=99999)
    cv.resize(300, 200)
    cv._tick()
    assert cv._last_char == (50, 60)
    cv.grab()                       # paintEvent 예외 없이 도는지


def test_region_unset_shows_hint_no_crash(app):
    cfg = FakeConfig({"minimap": {"width": 0}})
    cv = MinimapCanvas(cfg, screen_capture=lambda r: None,
                       char_finder=lambda *a, **k: (1, 1), interval_ms=99999)
    cv._tick()
    assert cv._last_char is None
    cv.grab()


def test_char_not_found_keeps_last(app):
    cfg = _region_cfg()
    shot = np.zeros((120, 200, 3), dtype=np.uint8)
    seq = [(10, 20), None]
    cv = MinimapCanvas(cfg, screen_capture=lambda r: shot,
                       char_finder=lambda *a, **k: seq.pop(0), interval_ms=99999)
    cv._tick()                      # (10,20)
    cv._tick()                      # None → 직전 유지
    assert cv._last_char == (10, 20)
```

- [ ] **Step 2: 실패 확인**

Run: `cd /c/Users/PC/Desktop/02_work/05_AI/maple_bot && QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_minimap_canvas.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'core_ui.minimap_canvas'`

- [ ] **Step 3: 구현**

`core_ui/minimap_canvas.py`:
```python
# 미니맵을 실시간 캡처해 배경으로 깔고 캐릭터·공격/사냥 범위를 투영하는 캔버스 위젯
from __future__ import annotations

import numpy as np
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import QTimer, Qt, QRectF
from PyQt6.QtGui import QImage, QPainter, QPen, QColor

from core.sensing.char_scanner import find_char_in_hsv
from core_ui.minimap_geom import minimap_to_canvas, screen_px_to_minimap_px


class MinimapCanvas(QWidget):
    """미니맵 영역을 주기 캡처해 배경(흐리게)·캐릭터(노란 점)·공격/사냥 범위를 그린다.
    좌표는 미니맵 픽셀 기준, 화면 표시 시 줌 배율을 곱한다(범위도 줌 비례)."""

    def __init__(self, config, screen_capture, char_finder=find_char_in_hsv,
                 interval_ms: int = 80, screen_w: int = 1920):
        super().__init__()
        self._cfg = config
        self._capture = screen_capture
        self._find = char_finder
        self._screen_w = screen_w
        self._zoom = 1.0
        self._last_char: tuple[int, int] | None = None
        self._shot: QImage | None = None
        self._mm_size = (0, 0)        # (W_mm, H_mm)
        self.setMinimumHeight(220)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(interval_ms)

    def _region(self) -> dict:
        c = self._cfg
        return {"left": int(c.get("minimap", "region_x", default=0)),
                "top": int(c.get("minimap", "region_y", default=0)),
                "width": int(c.get("minimap", "width", default=0)),
                "height": int(c.get("minimap", "height", default=0))}

    def _tick(self) -> None:
        r = self._region()
        if r["width"] <= 0:
            self._shot = None
            self.update()
            return
        try:
            bgr = self._capture(r)
        except Exception:
            return
        if bgr is None:
            return
        pos = self._find(bgr, (20, 100, 200), (40, 255, 255), 6, 4000)
        if pos is not None:
            self._last_char = pos
        h, w = bgr.shape[:2]
        self._mm_size = (w, h)
        rgb = np.ascontiguousarray(bgr[:, :, ::-1])
        self._shot = QImage(rgb.data, w, h, 3 * w,
                            QImage.Format.Format_RGB888).copy()
        self.update()

    def paintEvent(self, ev) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#0d0e10"))
        if self._shot is None:
            self._hint(p, "연결·인식에서 미니맵 영역을 먼저 지정하세요")
            return
        W, H = self._mm_size
        p.setOpacity(0.30)
        p.drawImage(QRectF(0, 0, W * self._zoom, H * self._zoom), self._shot)
        p.setOpacity(1.0)
        if self._last_char is None:
            self._hint(p, "캐릭터 미검출")
            return
        cx, cy = minimap_to_canvas(self._last_char[0], self._last_char[1], self._zoom)
        self._draw_ranges(p, cx, cy)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#ffd33d"))
        p.drawEllipse(cx - 7, cy - 7, 14, 14)

    def _draw_ranges(self, p: QPainter, cx: int, cy: int) -> None:
        c = self._cfg
        W = self._mm_size[0]
        ratio = float(c.get("attack", "camera_w_ratio", default=0.5))
        z = self._zoom

        def conv(key, dft):
            v = abs(int(c.get("attack", key, default=dft)))
            return screen_px_to_minimap_px(v, W, self._screen_w, ratio) * z

        axw = max(3.0, conv("atk_x_max", 35))
        ayh = max(3.0, conv("atk_y_max", 70))
        hxw = max(4.0, conv("monster_range_px", 600))
        hyh = max(4.0, conv("monster_range_h", 120))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor("#4d7cff"), 1.4, Qt.PenStyle.DashLine))   # 사냥
        p.drawRect(int(cx - hxw), int(cy - hyh), int(hxw * 2), int(hyh * 2))
        p.setPen(QPen(QColor("#f04452"), 1.4, Qt.PenStyle.DashLine))   # 공격
        p.drawRect(int(cx - axw), int(cy - ayh), int(axw * 2), int(ayh * 2))

    def _hint(self, p: QPainter, text: str) -> None:
        p.setPen(QColor("#8a8f98"))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)
```

- [ ] **Step 4: 통과 확인**

Run: `cd /c/Users/PC/Desktop/02_work/05_AI/maple_bot && QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_minimap_canvas.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add core_ui/minimap_canvas.py tests/test_minimap_canvas.py
git commit -m "feat(minimap): 실시간 캡처·캐릭터 투영·범위 캔버스 위젯"
```

---

### Task 3: 줌(휠) + 맞춤(fit)

**Files:**
- Modify: `core_ui/minimap_canvas.py` (메서드 추가)
- Test: `tests/test_minimap_canvas.py` (테스트 추가)

- [ ] **Step 1: 실패 테스트 추가**

`tests/test_minimap_canvas.py` 끝에 추가:
```python
def test_fit_sets_zoom_to_show_whole_minimap(app):
    cfg = _region_cfg()
    shot = np.zeros((120, 200, 3), dtype=np.uint8)
    cv = MinimapCanvas(cfg, screen_capture=lambda r: shot,
                       char_finder=lambda *a, **k: (50, 60), interval_ms=99999)
    cv.resize(400, 240)
    cv._tick()                      # _mm_size=(200,120)
    cv.fit()
    # min(400/200, 240/120) = min(2.0, 2.0) = 2.0
    assert abs(cv._zoom - 2.0) < 1e-6


def test_zoom_clamped(app):
    cfg = _region_cfg()
    cv = MinimapCanvas(cfg, screen_capture=lambda r: None,
                       char_finder=lambda *a, **k: None, interval_ms=99999)
    cv.set_zoom(99)
    assert cv._zoom == 4.0          # 상한
    cv.set_zoom(0.01)
    assert cv._zoom == 0.5          # 하한
```

- [ ] **Step 2: 실패 확인**

Run: `cd /c/Users/PC/Desktop/02_work/05_AI/maple_bot && QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_minimap_canvas.py -q`
Expected: FAIL — `AttributeError: 'MinimapCanvas' object has no attribute 'fit'`

- [ ] **Step 3: 구현 (메서드 추가)**

`core_ui/minimap_canvas.py` 의 `_hint` 메서드 아래에 추가:
```python
    def set_zoom(self, zoom: float) -> None:
        """줌 배율 설정(0.5~4.0 클램프)."""
        self._zoom = max(0.5, min(4.0, zoom))
        self.update()

    def fit(self) -> None:
        """미니맵 전체가 캔버스에 들어오도록 줌 맞춤."""
        W, H = self._mm_size
        if W > 0 and H > 0 and self.width() > 0 and self.height() > 0:
            self.set_zoom(min(self.width() / W, self.height() / H))

    def wheelEvent(self, ev) -> None:
        step = 1.1 if ev.angleDelta().y() > 0 else 0.9
        self.set_zoom(self._zoom * step)
```

- [ ] **Step 4: 통과 확인**

Run: `cd /c/Users/PC/Desktop/02_work/05_AI/maple_bot && QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_minimap_canvas.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: 커밋**

```bash
git add core_ui/minimap_canvas.py tests/test_minimap_canvas.py
git commit -m "feat(minimap): 줌(휠)·맞춤(fit) + 클램프"
```

---

### Task 4: "동선·이동" 페이지에 캔버스 통합

**Files:**
- Modify: `core_ui/pages.py` (page 2 빌더)

- [ ] **Step 1: 통합 코드 작성**

`core_ui/pages.py` 의 page 2(동선·이동) 빌더에서, `block_editor = BlockEditor(...)` 줄 다음에 캔버스 생성 블록을 추가하고 `extras` 를 교체한다.

기존:
```python
    block_editor = BlockEditor(c, ("floor_hunt", "route"))
    pages.append(_page("동선·이동", "구역·사다리·다운점프·텔포·포탈·블록빌더·녹화·프리셋", [
        CheckField("층별 사냥 사용", c, ("floor_hunt", "enabled")),
        CheckField("커스텀 루트 모드", c, ("floor_hunt", "route_mode")),
        TextField("현재 사냥터", c, ("hunt_grounds", "active")),
        ComboField("좌표 기준", c, ("coord_mode",), ["relative", "absolute"], default="relative"),
    ], extras=[route_lbl, block_editor]))
```

교체:
```python
    block_editor = BlockEditor(c, ("floor_hunt", "route"))
    # 실시간 미니맵 캔버스(보기 전용). 캡처/모니터 폭 획득 실패 시 생략
    nav_extras = []
    try:
        import mss as _mss
        from core.screen_reader import ScreenReader
        from core_ui.minimap_canvas import MinimapCanvas
        with _mss.mss() as _s:
            _sw = int(_s.monitors[1]["width"])
        nav_extras.append(MinimapCanvas(c, ScreenReader().capture, screen_w=_sw))
    except Exception:
        pass
    nav_extras += [route_lbl, block_editor]
    pages.append(_page("동선·이동", "구역·사다리·다운점프·텔포·포탈·블록빌더·녹화·프리셋", [
        CheckField("층별 사냥 사용", c, ("floor_hunt", "enabled")),
        CheckField("커스텀 루트 모드", c, ("floor_hunt", "route_mode")),
        TextField("현재 사냥터", c, ("hunt_grounds", "active")),
        ComboField("좌표 기준", c, ("coord_mode",), ["relative", "absolute"], default="relative"),
    ], extras=nav_extras))
```

- [ ] **Step 2: 전체 회귀 + 셸 렌더 스모크**

Run:
```bash
cd /c/Users/PC/Desktop/02_work/05_AI/maple_bot && QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/ -q
```
Expected: PASS (기존 210 + 신규 8 = 218 passed)

Run (셸 렌더 — 예외 없이 동선 페이지가 뜨는지):
```bash
cd /c/Users/PC/Desktop/02_work/05_AI/maple_bot && QT_QPA_PLATFORM=offscreen py -3.14 -c "import os; os.environ['QT_QPA_PLATFORM']='offscreen'; from PyQt6.QtWidgets import QApplication; from core_ui.shell import MainShell; from core_ui.theme import apply_font; from core.config_manager import ConfigManager; a=QApplication([]); apply_font(a); w=MainShell(ConfigManager()); w.resize(1180,720); w.show(); a.processEvents(); w.stack.setCurrentIndex(1); a.processEvents(); print('동선 페이지 렌더 OK', w.stack.count())"
```
Expected: `동선 페이지 렌더 OK 6`

- [ ] **Step 3: 커밋**

```bash
git add core_ui/pages.py
git commit -m "feat(minimap): 동선·이동 페이지에 실시간 미니맵 캔버스 통합"
```

---

## Self-Review (작성자 확인)

**Spec coverage:** 미니맵 배경(Task2 paintEvent)·캐릭터 투영(Task1+2)·공격/사냥 범위 줌비례(Task1 conv+Task2 _draw_ranges)·줌/맞춤(Task3)·미설정/미검출 에러(Task2 _hint, char_not_found 테스트)·통합(Task4)·순수함수 테스트(Task1)·offscreen 스모크(Task2)= 스펙 항목 전부 매핑됨. 팬(pan)은 스펙에서 #1 범위 외로 명시(미니맵 전부 보임 가정) — minimap_to_canvas는 pan 인자만 보유(미사용, #4 대비).

**Placeholder scan:** TBD/TODO/"적절히" 없음. 모든 코드 스텝에 완성 코드 포함.

**Type consistency:** `minimap_to_canvas(cx,cy,zoom,pan)`·`screen_px_to_minimap_px(screen_px,minimap_w,screen_w,camera_w_ratio)`·`MinimapCanvas(config,screen_capture,char_finder,interval_ms,screen_w)`·`set_zoom/fit/wheelEvent`·`_last_char/_mm_size/_zoom/_shot` 명칭이 Task 전반에서 일치. `char_finder` 호출 시그니처 `(bgr, lo, hi, min_area, max_area)`는 기존 `find_char_in_hsv`와 일치, 테스트 가짜는 `*a,**k`로 수용.
