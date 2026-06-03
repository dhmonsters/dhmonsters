# 게임창 상대좌표로 영역 추적 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 설정 영역(미니맵·사냥영역·맵이탈)을 게임창 클라이언트 기준 상대 픽셀로 저장하고 캡처 시점마다 현재 창 원점을 더해 해석해, 창을 옮겨도 영역이 따라가게 한다.

**Architecture:** `config_manager`에 창 원점 캐시 조회 + 상대→절대 해석 헬퍼를 둔다(명시 인자형). 미니맵 스캐너들(CharScanner/AntiMob/User)은 region을 dict 또는 callable로 받아 매 캡처 해석하고, 런타임이 해석 callable을 주입한다. UI 캔버스·사냥영역 캡처도 같은 헬퍼로 해석한다. 영역 픽커는 relative 모드에서 창 원점을 차감해 저장한다.

**Tech Stack:** Python 3.14(`py -3.14`), pytest(`QT_QPA_PLATFORM=offscreen`), win32gui(게임창 위치), mss(캡처).

---

## File Structure

- `core/config_manager.py` (수정) — `_query_window_origin`, `cached_window_origin`, `resolve_window_region` 추가. `import time`.
- `core/sensing/char_scanner.py`, `antimob_scanner.py`, `user_scanner.py` (수정) — `scan_once`에서 region이 callable이면 호출해 해석.
- `core/runtime.py` (수정) — `RuntimeConfig.coord_mode/game_window_title` 추가, `_resolve_region`, 스캐너에 callable region 주입, `_monster_in_range`/`detect_monsters_rel` 해석.
- `core_ui/minimap_canvas.py` (수정) — `_region()`에서 해석.
- `core_ui/pages.py` (수정) — 영역 픽커 3개 저장 시 relative면 원점 차감.
- `core/config_adapter.py` (수정) — `coord_mode`, `game_window_title` 매핑.
- `tests/test_window_region.py` (신규), `tests/test_scanner_callable_region.py` (신규).

---

### Task 1: config_manager 창 원점 해석 헬퍼

**Files:**
- Modify: `core/config_manager.py`
- Test: `tests/test_window_region.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_window_region.py
# 창 원점 캐시 조회 + 상대→절대 영역 해석 검증
import core.config_manager as cm


def _reset():
    cm._origin_cache.update(title=None, ts=0.0, rect=(0, 0, 0, 0))


def test_resolve_absolute_passthrough(monkeypatch):
    _reset()
    monkeypatch.setattr(cm, "_query_window_origin", lambda t: (100, 50, 800, 600))
    # absolute면 창 무시하고 그대로
    assert cm.resolve_window_region("absolute", "X", 13, 136, 256, 104) == (13, 136, 256, 104)


def test_resolve_relative_adds_origin(monkeypatch):
    _reset()
    monkeypatch.setattr(cm, "_query_window_origin", lambda t: (100, 50, 800, 600))
    assert cm.resolve_window_region("relative", "X", 13, 136, 256, 104) == (113, 186, 256, 104)


def test_resolve_relative_no_window_falls_back(monkeypatch):
    _reset()
    monkeypatch.setattr(cm, "_query_window_origin", lambda t: (0, 0, 0, 0))
    assert cm.resolve_window_region("relative", "X", 13, 136, 256, 104) == (13, 136, 256, 104)


def test_cached_within_ttl_queries_once(monkeypatch):
    _reset()
    calls = {"n": 0}
    def q(t):
        calls["n"] += 1
        return (10, 20, 800, 600)
    monkeypatch.setattr(cm, "_query_window_origin", q)
    clock = {"t": 1000.0}
    now = lambda: clock["t"]
    cm.cached_window_origin("X", ttl=0.2, _now=now)
    cm.cached_window_origin("X", ttl=0.2, _now=now)   # ttl 내 → 캐시
    assert calls["n"] == 1
    clock["t"] += 0.5                                  # ttl 경과
    cm.cached_window_origin("X", ttl=0.2, _now=now)
    assert calls["n"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_window_region.py -v`
Expected: FAIL — `AttributeError: module 'core.config_manager' has no attribute '_origin_cache'` (또는 resolve_window_region 없음).

- [ ] **Step 3: Implement in core/config_manager.py**

`import sys` 아래에 `import time` 추가. 그리고 `logical_to_physical_coords` 함수 정의 바로 위(또는 `get_game_window_rect` 근처)에 추가:

```python
def _query_window_origin(window_title: str) -> tuple[int, int, int, int]:
    """win32로 게임창 클라이언트 (ox, oy, cw, ch). 못 찾거나 win32 미가용이면 (0,0,0,0)."""
    try:
        import win32gui
        hwnd = win32gui.FindWindow(None, window_title or "MapleStory")
        if hwnd:
            ox, oy = win32gui.ClientToScreen(hwnd, (0, 0))
            left, top, right, bottom = win32gui.GetClientRect(hwnd)
            if right - left > 0 and bottom - top > 0:
                return (ox, oy, right - left, bottom - top)
    except Exception:
        pass
    return (0, 0, 0, 0)


_origin_cache = {"title": None, "ts": 0.0, "rect": (0, 0, 0, 0)}


def cached_window_origin(window_title: str, ttl: float = 0.2,
                         _now=time.monotonic) -> tuple[int, int, int, int]:
    """게임창 클라이언트 (ox,oy,cw,ch) — win32 조회를 ttl초 캐시(매 캡처 폭주 방지)."""
    c = _origin_cache
    now = _now()
    if c["title"] == window_title and (now - c["ts"]) < ttl:
        return c["rect"]
    rect = _query_window_origin(window_title)
    c.update(title=window_title, ts=now, rect=rect)
    return rect


def resolve_window_region(coord_mode: str, window_title: str,
                          left: int, top: int, w: int, h: int) -> tuple[int, int, int, int]:
    """창 상대 픽셀(left,top)+w,h → 절대 화면 (x,y,w,h).
    coord_mode != 'relative'거나 창 못 찾으면 (left,top,w,h) 그대로(절대 폴백)."""
    if (coord_mode or "absolute") != "relative":
        return (left, top, w, h)
    ox, oy, cw, ch = cached_window_origin(window_title)
    if cw <= 0:
        return (left, top, w, h)
    return (ox + left, oy + top, w, h)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_window_region.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add core/config_manager.py tests/test_window_region.py
git commit -m "feat(config): 게임창 원점 캐시 + 상대→절대 영역 해석 헬퍼

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: 미니맵 스캐너 region을 callable 허용으로

**Files:**
- Modify: `core/sensing/char_scanner.py`, `core/sensing/antimob_scanner.py`, `core/sensing/user_scanner.py`
- Test: `tests/test_scanner_callable_region.py`

런타임이 매 스캔 창상대 해석을 하도록, region이 callable이면 호출해 dict를 얻는다. dict면 기존 동작 유지(테스트/구버전 호환).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_scanner_callable_region.py
# 스캐너가 callable region을 매 스캔 호출해 해석하는지 검증
import numpy as np
from core.sensing.char_scanner import CharScanner


def test_callable_region_is_invoked_each_scan():
    seen = []
    def region_fn():
        r = {"left": 1, "top": 2, "width": 3, "height": 4}
        seen.append(r)
        return r
    def cap(region):
        # callable이 해석한 dict가 넘어와야 함
        assert region == {"left": 1, "top": 2, "width": 3, "height": 4}
        return np.zeros((4, 3, 3), np.uint8)   # 검출 실패해도 됨(호출 여부만 확인)
    sc = CharScanner(cap, region_fn)
    sc.scan_once()
    sc.scan_once()
    assert len(seen) == 2   # 매 스캔마다 해석


def test_dict_region_still_works():
    def cap(region):
        assert region == {"left": 5, "top": 6, "width": 7, "height": 8}
        return None
    sc = CharScanner(cap, {"left": 5, "top": 6, "width": 7, "height": 8})
    sc.scan_once()   # 예외 없이 동작
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_scanner_callable_region.py -v`
Expected: FAIL — `cap`이 callable 객체(region_fn)를 그대로 받아 `region == {...}` assert 실패(TypeError/AssertionError).

- [ ] **Step 3: 세 스캐너 scan_once에서 callable 해석**

`core/sensing/char_scanner.py`의 `scan_once` 첫 줄:

```python
    def scan_once(self) -> Event | None:
        img = self._capture(self._region)
```
를:
```python
    def scan_once(self) -> Event | None:
        region = self._region() if callable(self._region) else self._region
        img = self._capture(region)
```

`core/sensing/antimob_scanner.py`의 `scan_once` 첫 줄:
```python
    def scan_once(self) -> Event | None:
        scene = self._capture(self._region) if self._region else self._capture()
```
를:
```python
    def scan_once(self) -> Event | None:
        region = self._region() if callable(self._region) else self._region
        scene = self._capture(region) if region else self._capture()
```

`core/sensing/user_scanner.py`의 `scan_once` 첫 줄:
```python
    def scan_once(self) -> Event | None:
        img = self._capture(self._region) if self._region else self._capture()
```
를:
```python
    def scan_once(self) -> Event | None:
        region = self._region() if callable(self._region) else self._region
        img = self._capture(region) if region else self._capture()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_scanner_callable_region.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 스캐너 회귀**

Run: `QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/ -q -k "scanner or char or antimob or user"`
Expected: 기존 스캐너 테스트 PASS 유지.

- [ ] **Step 6: Commit**

```bash
git add core/sensing/char_scanner.py core/sensing/antimob_scanner.py core/sensing/user_scanner.py tests/test_scanner_callable_region.py
git commit -m "feat(sensing): 스캐너 region을 callable 허용(매 스캔 창상대 해석용)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: 런타임 — coord_mode/창제목 + 영역 해석 주입

**Files:**
- Modify: `core/runtime.py`
- Test: `tests/test_runtime_resolve_region.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_runtime_resolve_region.py
# 런타임 _resolve_region이 coord_mode/창제목으로 영역을 해석하는지 검증
from core import runtime as rt_mod


def _rt(coord_mode, title):
    rt = rt_mod.BotRuntime.__new__(rt_mod.BotRuntime)
    class _Cfg:
        pass
    rt._cfg = _Cfg()
    rt._cfg.coord_mode = coord_mode
    rt._cfg.game_window_title = title
    return rt


def test_resolve_none_is_none():
    rt = _rt("relative", "X")
    assert rt._resolve_region(None) is None


def test_resolve_absolute_passthrough(monkeypatch):
    import core.config_manager as cm
    cm._origin_cache.update(title=None, ts=0.0, rect=(0, 0, 0, 0))
    monkeypatch.setattr(cm, "_query_window_origin", lambda t: (100, 50, 800, 600))
    rt = _rt("absolute", "X")
    assert rt._resolve_region({"left": 13, "top": 136, "width": 256, "height": 104}) == \
        {"left": 13, "top": 136, "width": 256, "height": 104}


def test_resolve_relative_adds_origin(monkeypatch):
    import core.config_manager as cm
    cm._origin_cache.update(title=None, ts=0.0, rect=(0, 0, 0, 0))
    monkeypatch.setattr(cm, "_query_window_origin", lambda t: (100, 50, 800, 600))
    rt = _rt("relative", "X")
    assert rt._resolve_region({"left": 13, "top": 136, "width": 256, "height": 104}) == \
        {"left": 113, "top": 186, "width": 256, "height": 104}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_runtime_resolve_region.py -v`
Expected: FAIL — `AttributeError: 'BotRuntime' object has no attribute '_resolve_region'`

- [ ] **Step 3: RuntimeConfig 필드 + _resolve_region + 주입/해석**

(a) `RuntimeConfig`(dataclass)에 필드 추가. 기존 `hunt_area_region: dict | None = None` 근처에:
```python
    coord_mode: str = "absolute"
    game_window_title: str = ""
```

(b) `_monster_in_range` 메서드 정의 바로 위에 추가:
```python
    def _resolve_region(self, region: dict | None) -> dict | None:
        """상대 영역 dict를 현재 게임창 원점으로 해석(absolute면 그대로, None이면 None)."""
        if not region:
            return region
        from core.config_manager import resolve_window_region
        x, y, w, h = resolve_window_region(
            self._cfg.coord_mode, self._cfg.game_window_title,
            int(region["left"]), int(region["top"]),
            int(region["width"]), int(region["height"]))
        return {"left": x, "top": y, "width": w, "height": h}
```

(c) 미니맵 스캐너에 해석 callable 주입. 기존:
```python
        self.char_scanner = CharScanner(screen_capture, config.minimap_region)
```
를:
```python
        self.char_scanner = CharScanner(
            screen_capture, lambda: self._resolve_region(config.minimap_region))
```
AntiMobScanner 생성의 `region=config.minimap_region,`을 `region=lambda: self._resolve_region(config.minimap_region),`로,
UserScanner 생성의 `region=config.minimap_region,`을 `region=lambda: self._resolve_region(config.minimap_region),`로 변경.

(d) `_monster_in_range`의 `region = self._cfg.hunt_area_region` 줄을:
```python
        region = self._resolve_region(self._cfg.hunt_area_region)
```
로. `detect_monsters_rel`에도 동일한 `region = self._cfg.hunt_area_region` 줄이 있으면 같게 변경.

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_runtime_resolve_region.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 전체 회귀**

Run: `QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/ -q`
Expected: 전체 PASS(신규 포함).

- [ ] **Step 6: Commit**

```bash
git add core/runtime.py tests/test_runtime_resolve_region.py
git commit -m "feat(runtime): coord_mode/창제목 + 영역 창상대 해석(스캐너·사냥영역 캡처)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: 미니맵 캔버스 영역 해석

**Files:**
- Modify: `core_ui/minimap_canvas.py`

`MinimapCanvas._region()`이 ConfigManager에서 coord_mode/창제목을 읽어 해석한 절대영역을 반환한다.

- [ ] **Step 1: _region 해석 적용**

`core_ui/minimap_canvas.py`의 기존 `_region`:
```python
    def _region(self) -> dict:
        c = self._cfg
        return {"left": int(c.get("minimap", "region_x", default=0)),
                "top": int(c.get("minimap", "region_y", default=0)),
                "width": int(c.get("minimap", "width", default=0)),
                "height": int(c.get("minimap", "height", default=0))}
```
를:
```python
    def _region(self) -> dict:
        c = self._cfg
        left = int(c.get("minimap", "region_x", default=0))
        top = int(c.get("minimap", "region_y", default=0))
        w = int(c.get("minimap", "width", default=0))
        h = int(c.get("minimap", "height", default=0))
        from core.config_manager import resolve_window_region
        coord_mode = c.get("coord_mode") or "absolute"
        title = c.get("settings2", "game_window_title") or ""
        x, y, w, h = resolve_window_region(coord_mode, title, left, top, w, h)
        return {"left": x, "top": y, "width": w, "height": h}
```

주의: `minimap_size()`는 `_region()`을 호출하므로 width/height는 그대로(해석은 좌표만 더함) — 크기 영향 없음.

- [ ] **Step 2: 캔버스 회귀 + 스모크**

Run: `QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_minimap_canvas.py -q`
Expected: 기존 PASS 유지(테스트의 Cfg는 coord_mode 없음 → "absolute" 폴백 → 동작 불변).

- [ ] **Step 3: Commit**

```bash
git add core_ui/minimap_canvas.py
git commit -m "feat(ui): 미니맵 캔버스 영역을 게임창 원점으로 해석

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: config_adapter — coord_mode/창제목 매핑

**Files:**
- Modify: `core/config_adapter.py`

- [ ] **Step 1: RuntimeConfig 인자에 추가**

`to_runtime_config`의 `return RuntimeConfig(` 인자 목록에서 `hunt_area_region=hunt_area_region,` 근처에 추가:
```python
        coord_mode=str(d.get("coord_mode", "relative")),
        game_window_title=str(d.get("settings2", {}).get("game_window_title", "")),
```

- [ ] **Step 2: 어댑터 회귀**

Run: `QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/ -q -k "adapter or runtime or config"`
Expected: PASS 유지.

- [ ] **Step 3: Commit**

```bash
git add core/config_adapter.py
git commit -m "feat(adapter): coord_mode/게임창 제목을 RuntimeConfig로 매핑

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: 영역 픽커 저장 시 창 원점 차감(relative)

**Files:**
- Modify: `core_ui/pages.py`

`_make_region_picker`의 `apply` 콜백에서, relative 모드이고 창을 찾으면 저장 직전에 절대좌표에서 창 원점을 차감해 **클라이언트 상대 픽셀**로 저장한다. 미니맵·사냥영역·맵이탈 픽커가 모두 이 함수를 쓰므로 한 곳만 고치면 일괄 적용된다.

- [ ] **Step 1: apply에서 원점 차감**

`core_ui/pages.py`의 `_make_region_picker` 안 기존 `apply`:
```python
        def apply(x, y, w, h):
            for i, (key, val) in enumerate(zip(keys_xywh, (x, y, w, h))):
                config.set(*key, val)
                if fields_xywh and i < len(fields_xywh) and fields_xywh[i] is not None:
                    fields_xywh[i].widget.setValue(val)
            config.save()
            if on_done:
                on_done()
```
를:
```python
        def apply(x, y, w, h):
            # relative 모드 + 게임창 찾으면 클라이언트 상대 픽셀로 저장(창을 따라가게)
            if (config.get("coord_mode") or "relative") == "relative":
                from core.config_manager import cached_window_origin
                title = config.get("settings2", "game_window_title") or ""
                ox, oy, cw, ch = cached_window_origin(title)
                if cw > 0:
                    x, y = x - ox, y - oy
            for i, (key, val) in enumerate(zip(keys_xywh, (x, y, w, h))):
                config.set(*key, val)
                if fields_xywh and i < len(fields_xywh) and fields_xywh[i] is not None:
                    fields_xywh[i].widget.setValue(val)
            config.save()
            if on_done:
                on_done()
```

- [ ] **Step 2: 페이지 빌드 회귀**

Run: `QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_pages.py -q`
Expected: PASS(6페이지 빌드 유지).

- [ ] **Step 3: 전체 회귀**

Run: `QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/ -q`
Expected: 전체 PASS.

- [ ] **Step 4: Commit**

```bash
git add core_ui/pages.py
git commit -m "feat(ui): 영역 픽커 relative 모드에서 창 원점 차감 저장(미니맵·사냥영역·맵이탈)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## 완료 후

- 전체 테스트 PASS 확인.
- superpowers:finishing-a-development-branch로 main 병합.
- **사용자 안내**: 업데이트 후 미니맵·사냥영역·맵이탈 영역을 **1회 재지정**(기존 절대값→상대 해석 전환). 재지정 후 게임창을 옮겨도 영역이 따라가는지, 공격범위(캐릭 추종)가 안정적인지 확인.
