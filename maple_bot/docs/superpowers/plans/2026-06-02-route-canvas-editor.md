# 캔버스 블록 시각 편집기 Implementation Plan (하위 프로젝트 #2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** #1의 미니맵 캔버스 위에서 클릭으로 블록을 배치하고 드래그로 옮겨 동선을 그리며, 기존 리스트형 `BlockEditor`와 콜백으로 양방향 동기화한다.

**Architecture:** 새 파일을 만들지 않는다. 좌표·공간 순수 로직은 기존 `core_ui/minimap_geom.py`에, 편집 위젯 `RouteCanvas(MinimapCanvas)`는 기존 `core_ui/minimap_canvas.py`에 추가(같은 파일 상속→순환참조 없음). 동기화는 타이머 폴링이 아니라 콜백 이벤트(`on_route_changed`/`on_change`).

**Tech Stack:** PyQt6(상속·마우스이벤트·QPainter), `core/navigation/block.Block`, 기존 `core_ui/minimap_geom`·`minimap_canvas`·`block_editor`.

**저장소 규칙:** 신규/수정 소스 첫 줄 한국어 역할 주석 유지. 테스트 `QT_QPA_PLATFORM=offscreen`. 명령 `py -3.14 -m pytest`. 작업 디렉토리 `/c/Users/PC/Desktop/02_work/05_AI/maple_bot`. 커밋 본문 끝에 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. 브랜치는 새로 만들지 말고 현재 브랜치에서 작업. `config.json`은 절대 stage 금지.

---

## 파일 구조
| 파일 | 변경 | 책임 |
|------|------|------|
| `core/navigation/block.py` | 수정 | `pos_x/pos_y=-1`(캔버스 앵커) 필드 |
| `core_ui/minimap_geom.py` | 수정 | `canvas_to_minimap`·`BLOCK_COLORS`·`block_color`·`block_anchor`·`hit_test`·`seed_block_at`·`translate_block` |
| `core_ui/block_editor.py` | 수정 | `on_change` 콜백 + `reload()` |
| `core_ui/minimap_canvas.py` | 수정 | `minimap_size()` getter + `RouteCanvas` 클래스 |
| `core_ui/pages.py` | 수정 | 동선 페이지에 블록툴바 + RouteCanvas + 양방향 결선 |

---

### Task 1: Block에 캔버스 앵커 좌표(pos_x/pos_y=-1)

**Files:** Modify `core/navigation/block.py`; Test `tests/test_block.py`

- [ ] **Step 1: 실패 테스트 추가** — `tests/test_block.py` 끝에 추가:
```python
def test_block_has_canvas_anchor_default_unplaced():
    from core.navigation.block import Block
    b = Block(type="attack")
    assert b.pos_x == -1 and b.pos_y == -1        # 기본 미배치


def test_block_from_dict_preserves_pos():
    from core.navigation.block import Block
    b = Block.from_dict({"type": "attack", "pos_x": 30, "pos_y": 40})
    assert (b.pos_x, b.pos_y) == (30, 40)
```

- [ ] **Step 2: 실패 확인** — Run: `cd /c/Users/PC/Desktop/02_work/05_AI/maple_bot && QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_block.py -q`
Expected: FAIL (`AttributeError: ... 'pos_x'`).

- [ ] **Step 3: 구현** — `core/navigation/block.py`의 `grab_side: str = "auto"` 필드 줄 **바로 다음**에 추가:
```python
    pos_x: int = -1              # 캔버스 앵커 X (미니맵 픽셀). -1=미배치(캔버스에 안 그림)
    pos_y: int = -1              # 캔버스 앵커 Y (미니맵 픽셀). -1=미배치
```

- [ ] **Step 4: 통과 확인** — Run: `cd /c/Users/PC/Desktop/02_work/05_AI/maple_bot && QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_block.py -q`
Expected: PASS.

- [ ] **Step 5: 커밋**
```bash
git add core/navigation/block.py tests/test_block.py
git commit -m "feat(block): 캔버스 앵커 좌표 pos_x/pos_y(-1=미배치) 추가"
```

---

### Task 2: minimap_geom 순수 함수 추가 (좌표 역변환·색·앵커·히트·시드·평행이동)

**Files:** Modify `core_ui/minimap_geom.py`; Test `tests/test_minimap_geom.py`

- [ ] **Step 1: 실패 테스트 추가** — `tests/test_minimap_geom.py` 끝에 추가:
```python
def test_canvas_to_minimap_roundtrip():
    from core_ui.minimap_geom import minimap_to_canvas, canvas_to_minimap
    cx, cy = minimap_to_canvas(37, 21, 2.0, pan=(5, -3))
    assert canvas_to_minimap(cx, cy, 2.0, pan=(5, -3)) == (37, 21)


def test_block_color_move_vs_teleport():
    from core_ui.minimap_geom import block_color, BLOCK_COLORS
    assert block_color({"type": "move"}) == BLOCK_COLORS["move"]
    assert block_color({"type": "move", "move_type": "teleport"}) == BLOCK_COLORS["teleport"]
    assert block_color({"type": "attack"}) == BLOCK_COLORS["attack"]


def test_block_anchor_by_type_and_unplaced():
    from core_ui.minimap_geom import block_anchor
    assert block_anchor({"type": "attack", "pos_x": 30, "pos_y": 40}) == (30, 40)
    assert block_anchor({"type": "attack", "pos_x": -1, "pos_y": -1}) is None
    assert block_anchor({"type": "ladder", "ladder_x": 450, "y_bot": 180}) == (450, 180)
    assert block_anchor({"type": "ladder", "ladder_x": 0, "y_bot": 0}) is None


def test_hit_test_nearest_and_skips_unplaced():
    from core_ui.minimap_geom import hit_test
    blocks = [
        {"type": "attack", "pos_x": 100, "pos_y": 100},
        {"type": "attack", "pos_x": -1, "pos_y": -1},      # 미배치 → 제외
        {"type": "attack", "pos_x": 105, "pos_y": 102},
    ]
    assert hit_test(blocks, 104, 101, radius=10) == 2       # 가장 가까운 것
    assert hit_test(blocks, 300, 300, radius=10) is None    # 반경 밖


def test_seed_block_at_seeds_type_fields():
    from core_ui.minimap_geom import seed_block_at
    m = seed_block_at("move", 70, 40)
    assert m["type"] == "move" and m["pos_x"] == 70 and m["pos_y"] == 40
    assert m["start_x"] == 70 and m["end_x"] == 70
    la = seed_block_at("ladder", 55, 88)
    assert la["type"] == "ladder" and la["ladder_x"] == 55 and la["y_bot"] == 88
    tp = seed_block_at("teleport", 12, 13)
    assert tp["type"] == "move" and tp["move_type"] == "teleport" and tp["pos_x"] == 12


def test_translate_block_moves_pos_and_type_fields_immutable():
    from core_ui.minimap_geom import translate_block
    src = {"type": "move", "pos_x": 10, "pos_y": 20, "start_x": 10, "end_x": 90}
    out = translate_block(src, 5, 3)
    assert out["pos_x"] == 15 and out["pos_y"] == 23
    assert out["start_x"] == 15 and out["end_x"] == 95
    assert src["pos_x"] == 10                                # 원본 불변
    lad = translate_block({"type": "ladder", "pos_x": -1, "pos_y": -1,
                           "ladder_x": 100, "y_top": 10, "y_bot": 50}, 5, 3)
    assert lad["ladder_x"] == 105 and lad["y_top"] == 13 and lad["y_bot"] == 53
    assert lad["pos_x"] == -1                                # 미배치 pos는 그대로
```

- [ ] **Step 2: 실패 확인** — Run: `cd /c/Users/PC/Desktop/02_work/05_AI/maple_bot && QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_minimap_geom.py -q`
Expected: FAIL (`ImportError: cannot import name 'canvas_to_minimap'`).

- [ ] **Step 3: 구현** — `core_ui/minimap_geom.py` 끝에 추가:
```python
# 블록 타입 색 (단일 출처) — 캔버스가 참조
BLOCK_COLORS = {
    "move": "#3a8f5a", "attack": "#c0556a", "ladder": "#b07a30",
    "jump": "#5aa0c0", "teleport": "#7a5ad2",
}


def canvas_to_minimap(px: float, py: float, zoom: float,
                      pan: tuple[int, int] = (0, 0)) -> tuple[int, int]:
    """캔버스 픽셀 → 미니맵 픽셀 (minimap_to_canvas의 역변환). zoom=0이면 (0,0)."""
    if zoom == 0:
        return (0, 0)
    return (round((px - pan[0]) / zoom), round((py - pan[1]) / zoom))


def block_color(block: dict) -> str:
    """블록 표시색. move + move_type=teleport면 텔포색, 그 외 타입색."""
    t = block.get("type", "move")
    if t == "move" and block.get("move_type") == "teleport":
        return BLOCK_COLORS["teleport"]
    return BLOCK_COLORS.get(t, "#888888")


def block_anchor(block: dict) -> tuple[int, int] | None:
    """블록의 캔버스 앵커(미니맵 픽셀). ladder는 (ladder_x,y_bot), 그 외는 (pos_x,pos_y).
    미배치(ladder 좌표 0이거나 pos<0)면 None."""
    if block.get("type") == "ladder":
        lx, yb = int(block.get("ladder_x", 0)), int(block.get("y_bot", 0))
        if lx <= 0 and yb <= 0:
            return None
        return (lx, yb)
    px, py = int(block.get("pos_x", -1)), int(block.get("pos_y", -1))
    if px < 0 or py < 0:
        return None
    return (px, py)


def hit_test(blocks: list[dict], mx: int, my: int, radius: int = 10) -> int | None:
    """(mx,my)에서 radius 내 가장 가까운 블록 인덱스. 미배치(anchor None)는 제외, 없으면 None."""
    best_i, best_d = None, None
    for i, b in enumerate(blocks):
        a = block_anchor(b)
        if a is None:
            continue
        d = (a[0] - mx) ** 2 + (a[1] - my) ** 2
        if d <= radius * radius and (best_d is None or d < best_d):
            best_i, best_d = i, d
    return best_i


def seed_block_at(block_type: str, mx: int, my: int) -> dict:
    """클릭 좌표에 놓을 새 블록 dict. block_editor._DEFAULTS 재사용(지연 임포트).
    'teleport'는 move + move_type=teleport. 타입필드도 좌표로 시드."""
    from core_ui.block_editor import _DEFAULTS
    base = "move" if block_type == "teleport" else block_type
    blk = dict(_DEFAULTS[base])
    blk["pos_x"], blk["pos_y"] = mx, my
    if base == "move":
        blk["start_x"] = blk["end_x"] = mx
        if block_type == "teleport":
            blk["move_type"] = "teleport"
    elif base == "ladder":
        blk["ladder_x"] = mx
        blk["y_bot"] = my
    return blk


def translate_block(block: dict, dx: int, dy: int) -> dict:
    """블록을 (dx,dy)만큼 평행이동한 새 dict. 캔버스가 블록 내부필드를 몰라도 되게 한다.
    배치된 pos_x/y는 이동, move면 start_x/end_x, ladder면 ladder_x/y_top/y_bot도 함께."""
    b = dict(block)
    if int(b.get("pos_x", -1)) >= 0:
        b["pos_x"] = int(b["pos_x"]) + dx
    if int(b.get("pos_y", -1)) >= 0:
        b["pos_y"] = int(b["pos_y"]) + dy
    t = b.get("type")
    if t == "move":
        b["start_x"] = int(b.get("start_x", 0)) + dx
        b["end_x"] = int(b.get("end_x", 0)) + dx
    elif t == "ladder":
        b["ladder_x"] = int(b.get("ladder_x", 0)) + dx
        b["y_top"] = int(b.get("y_top", 0)) + dy
        b["y_bot"] = int(b.get("y_bot", 0)) + dy
    return b
```

- [ ] **Step 4: 통과 확인** — Run: `cd /c/Users/PC/Desktop/02_work/05_AI/maple_bot && QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_minimap_geom.py -q`
Expected: PASS (기존 5 + 신규 6 = 11 passed).

- [ ] **Step 5: 커밋**
```bash
git add core_ui/minimap_geom.py tests/test_minimap_geom.py
git commit -m "feat(minimap): 캔버스 편집 순수함수(역변환·색·앵커·히트·시드·평행이동)"
```

---

### Task 3: BlockEditor 콜백(on_change) + reload()

**Files:** Modify `core_ui/block_editor.py`; Test `tests/test_block_editor.py`

- [ ] **Step 1: 실패 테스트 추가** — `tests/test_block_editor.py` 끝에 추가:
```python
def test_on_change_called_when_saved(app):
    cfg = FakeConfig()
    calls = {"n": 0}
    ed = BlockEditor(cfg, ("floor_hunt", "route"), on_change=lambda: calls.__setitem__("n", calls["n"] + 1))
    ed.add_block("move")            # _save 발생
    assert calls["n"] >= 1


def test_reload_reads_config(app):
    cfg = FakeConfig({"floor_hunt": {"route": [{"type": "attack", "skill_key": "a"}]}})
    ed = BlockEditor(cfg, ("floor_hunt", "route"))
    assert ed.row_count() == 1
    cfg.set("floor_hunt", "route", [{"type": "attack"}, {"type": "jump"}])
    ed.reload()
    assert ed.row_count() == 2
```

- [ ] **Step 2: 실패 확인** — Run: `cd /c/Users/PC/Desktop/02_work/05_AI/maple_bot && QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_block_editor.py -q`
Expected: FAIL (`TypeError: ... unexpected keyword 'on_change'` 또는 `reload` 없음).

- [ ] **Step 3: 구현** — `core_ui/block_editor.py`:

(a) `__init__` 시그니처와 본문 시작을 수정:
```python
    def __init__(self, config, keys: tuple, on_change=None):
        super().__init__()
        self._cfg = config
        self._keys = keys
        self._on_change = on_change or (lambda: None)
        self._route: list[dict] = list(config.get(*keys, default=[]) or [])
        self._reordering = False
```

(b) `_save` 끝(`self._cfg.save()` 다음 줄)에 콜백 호출 추가:
```python
        self._cfg.set(*self._keys, valid)
        self._cfg.save()
        self._on_change()
```

(c) 공개 `reload()` 추가 — `_save_render` 메서드 **바로 위**에:
```python
    def reload(self) -> None:
        """config에서 route를 다시 읽어 화면 갱신(외부 변경 반영)."""
        self._route = list(self._cfg.get(*self._keys, default=[]) or [])
        self._render()
```

- [ ] **Step 4: 통과 확인** — Run: `cd /c/Users/PC/Desktop/02_work/05_AI/maple_bot && QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_block_editor.py -q`
Expected: PASS (기존 + 신규 2).

- [ ] **Step 5: 커밋**
```bash
git add core_ui/block_editor.py tests/test_block_editor.py
git commit -m "feat(block-editor): on_change 콜백 + reload() (캔버스 동기화용)"
```

---

### Task 4: MinimapCanvas.minimap_size() getter

**Files:** Modify `core_ui/minimap_canvas.py`; Test `tests/test_minimap_canvas.py`

- [ ] **Step 1: 실패 테스트 추가** — `tests/test_minimap_canvas.py` 끝에 추가:
```python
def test_minimap_size_from_region_without_tick(app):
    cfg = _region_cfg()
    cv = MinimapCanvas(cfg, screen_capture=lambda r: None,
                       char_finder=lambda *a, **k: None, interval_ms=99999)
    assert cv.minimap_size() == (200, 120)   # 타이머 안 돌아도 _region 기반
```

- [ ] **Step 2: 실패 확인** — Run: `cd /c/Users/PC/Desktop/02_work/05_AI/maple_bot && QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_minimap_canvas.py -q`
Expected: FAIL (`AttributeError: ... 'minimap_size'`).

- [ ] **Step 3: 구현** — `core_ui/minimap_canvas.py`의 `_region` 메서드 **바로 다음**에 추가:
```python
    def minimap_size(self) -> tuple[int, int]:
        """미니맵 (W,H) — _region 기반이라 타이머 틱 전에도 유효(클램프용)."""
        r = self._region()
        return (r["width"], r["height"])
```

- [ ] **Step 4: 통과 확인** — Run: `cd /c/Users/PC/Desktop/02_work/05_AI/maple_bot && QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_minimap_canvas.py -q`
Expected: PASS (기존 7 + 1 = 8 passed).

- [ ] **Step 5: 커밋**
```bash
git add core_ui/minimap_canvas.py tests/test_minimap_canvas.py
git commit -m "feat(minimap): minimap_size() getter (_region 기반, 타이머 비의존)"
```

---

### Task 5: RouteCanvas — 클릭 배치·드래그 이동·블록/경로 렌더

**Files:** Modify `core_ui/minimap_canvas.py`; Test `tests/test_route_canvas.py`

- [ ] **Step 1: 실패 테스트 작성** — 새 파일 `tests/test_route_canvas.py`:
```python
# RouteCanvas — 클릭 배치·드래그 이동·동기화 offscreen 스모크
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication
from core_ui.minimap_canvas import RouteCanvas


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class FakeConfig:
    def __init__(self, data=None): self._d = data or {}; self.saved = 0
    def get(self, *keys, default=None):
        node = self._d
        for k in keys:
            if not isinstance(node, dict) or k not in node:
                return default
            node = node[k]
        return node
    def set(self, *args):
        *keys, val = args; node = self._d
        for k in keys[:-1]:
            node = node.setdefault(k, {})
        node[keys[-1]] = val
    def save(self): self.saved += 1


def _cfg():
    return FakeConfig({"minimap": {"region_x": 0, "region_y": 0, "width": 200, "height": 120}})


def _canvas(cfg, on_changed=None):
    cv = RouteCanvas(cfg, screen_capture=lambda r: np.zeros((120, 200, 3), dtype=np.uint8),
                     char_finder=lambda *a, **k: None, interval_ms=99999,
                     on_route_changed=on_changed)
    cv.resize(400, 240)
    return cv


def test_empty_click_with_active_type_adds_block_and_resets(app):
    cfg = _cfg()
    fired = {"n": 0}
    cv = _canvas(cfg, on_changed=lambda: fired.__setitem__("n", fired["n"] + 1))
    cv.set_active_type("move")
    cv._place_or_select(70, 40)
    route = cfg.get("floor_hunt", "route")
    assert len(route) == 1 and route[0]["type"] == "move"
    assert route[0]["pos_x"] == 70 and route[0]["pos_y"] == 40
    assert cv._active_type is None          # 자동 리셋
    assert fired["n"] >= 1                   # on_route_changed 발화


def test_click_on_block_starts_drag(app):
    cfg = _cfg()
    cfg.set("floor_hunt", "route", [{"type": "attack", "pos_x": 100, "pos_y": 100}])
    cv = _canvas(cfg)
    cv._place_or_select(102, 101)            # 블록 근처 클릭
    assert cv._dragging == 0


def test_drag_translates_block(app):
    cfg = _cfg()
    cfg.set("floor_hunt", "route", [{"type": "attack", "pos_x": 100, "pos_y": 100}])
    cv = _canvas(cfg)
    cv._place_or_select(100, 100)            # 선택
    cv._drag_to(110, 108)                    # +10,+8
    cv._end_drag()
    route = cfg.get("floor_hunt", "route")
    assert (route[0]["pos_x"], route[0]["pos_y"]) == (110, 108)
    assert cv._dragging is None


def test_empty_click_without_active_type_does_nothing(app):
    cfg = _cfg()
    cv = _canvas(cfg)                        # _active_type None
    cv._place_or_select(50, 50)
    assert cfg.get("floor_hunt", "route", default=None) in (None, [])


def test_paint_does_not_crash_with_blocks(app):
    cfg = _cfg()
    cfg.set("floor_hunt", "route", [
        {"type": "attack", "pos_x": 30, "pos_y": 40},
        {"type": "attack", "pos_x": -1, "pos_y": -1},     # 미배치 — 안 그려짐
        {"type": "ladder", "ladder_x": 120, "y_top": 20, "y_bot": 90},
    ])
    cv = _canvas(cfg)
    cv._tick()                               # _shot 세팅
    cv.grab()                                # paintEvent 예외 없이
```

- [ ] **Step 2: 실패 확인** — Run: `cd /c/Users/PC/Desktop/02_work/05_AI/maple_bot && QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_route_canvas.py -q`
Expected: FAIL (`ImportError: cannot import name 'RouteCanvas'`).

- [ ] **Step 3: 구현** — `core_ui/minimap_canvas.py`의 `MinimapCanvas` 클래스 정의 **전체가 끝난 뒤**(파일 맨 끝)에 새 클래스 추가:
```python
class RouteCanvas(MinimapCanvas):
    """미니맵 캔버스 위에 동선 블록을 클릭 배치·드래그 이동하는 편집 캔버스.
    config의 route(같은 키)를 편집하고 on_route_changed로 리스트와 동기화한다."""

    def __init__(self, config, screen_capture,
                 route_keys=("floor_hunt", "route"), on_route_changed=None, **kw):
        super().__init__(config, screen_capture, **kw)
        self._route_keys = route_keys
        self._on_changed = on_route_changed or (lambda: None)
        self._active_type: str | None = None
        self._dragging: int | None = None
        self._drag_last: tuple[int, int] | None = None

    def set_active_type(self, t: str | None) -> None:
        self._active_type = t

    # ── route 입출력 ──────────────────────────────────────────────────
    def _route(self) -> list[dict]:
        return list(self._cfg.get(*self._route_keys, default=[]) or [])

    def _save_route(self, route: list[dict]) -> None:
        from core.navigation.block import Block
        valid = []
        for b in route:
            try:
                Block.from_dict(b); valid.append(b)
            except Exception:
                pass
        self._cfg.set(*self._route_keys, valid)
        self._cfg.save()
        self._on_changed()

    # ── 마우스 로직(테스트 가능한 좌표 단위로 분리) ───────────────────
    def _place_or_select(self, mx: int, my: int) -> None:
        from core_ui.minimap_geom import hit_test, seed_block_at
        W, H = self.minimap_size()
        if W > 0:
            mx = max(0, min(W - 1, mx))
        if H > 0:
            my = max(0, min(H - 1, my))
        route = self._route()
        idx = hit_test(route, mx, my)
        if idx is not None:
            self._dragging = idx
            self._drag_last = (mx, my)
        elif self._active_type is not None:
            route.append(seed_block_at(self._active_type, mx, my))
            self._save_route(route)
            self._active_type = None
        self.update()

    def _drag_to(self, mx: int, my: int) -> None:
        from core_ui.minimap_geom import translate_block
        if self._dragging is None or self._drag_last is None:
            return
        dx = mx - self._drag_last[0]
        dy = my - self._drag_last[1]
        route = self._route()
        route[self._dragging] = translate_block(route[self._dragging], dx, dy)
        self._cfg.set(*self._route_keys, route)   # 드래그 중엔 메모리만(저장 스팸 방지)
        self._drag_last = (mx, my)
        self.update()

    def _end_drag(self) -> None:
        if self._dragging is not None:
            self._save_route(self._route())
            self._dragging = None
            self._drag_last = None
        self.update()

    def mousePressEvent(self, ev) -> None:
        from core_ui.minimap_geom import canvas_to_minimap
        mx, my = canvas_to_minimap(ev.position().x(), ev.position().y(), self._zoom)
        self._place_or_select(mx, my)

    def mouseMoveEvent(self, ev) -> None:
        if self._dragging is None:
            return
        from core_ui.minimap_geom import canvas_to_minimap
        mx, my = canvas_to_minimap(ev.position().x(), ev.position().y(), self._zoom)
        self._drag_to(mx, my)

    def mouseReleaseEvent(self, ev) -> None:
        self._end_drag()

    # ── 렌더 ──────────────────────────────────────────────────────────
    def paintEvent(self, ev) -> None:
        super().paintEvent(ev)        # 배경+노란점+범위
        if self._shot is None:
            return
        from core_ui.minimap_geom import block_anchor, minimap_to_canvas, block_color
        route = self._route()
        p = QPainter(self)
        pts = []
        for b in route:
            a = block_anchor(b)
            if a is not None:
                pts.append(minimap_to_canvas(a[0], a[1], self._zoom))
        if len(pts) >= 2:
            p.setPen(QPen(QColor("#5e6ad2"), 1.5, Qt.PenStyle.DashLine))
            for i in range(len(pts) - 1):
                p.drawLine(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
        for i, b in enumerate(route):
            a = block_anchor(b)
            if a is None:
                continue
            cx, cy = minimap_to_canvas(a[0], a[1], self._zoom)
            if i == self._dragging:
                p.setPen(QPen(QColor("#ffffff"), 2))
            else:
                p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(block_color(b)))
            p.drawEllipse(cx - 6, cy - 6, 12, 12)
```

- [ ] **Step 4: 통과 확인** — Run: `cd /c/Users/PC/Desktop/02_work/05_AI/maple_bot && QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_route_canvas.py -q`
Expected: PASS (5 passed). 실패 시 실제 에러를 읽고 원인을 고친다(테스트 약화 금지).

- [ ] **Step 5: 커밋**
```bash
git add core_ui/minimap_canvas.py tests/test_route_canvas.py
git commit -m "feat(minimap): RouteCanvas — 클릭 배치·드래그 이동·블록/경로 렌더"
```

---

### Task 6: 동선·이동 페이지 통합 (블록툴바 + RouteCanvas + 양방향 결선)

**Files:** Modify `core_ui/pages.py`

- [ ] **Step 1: 통합 코드 작성** — `core_ui/pages.py`의 page2(동선·이동) 빌더에서, Task #1 통합으로 들어간 캔버스 블록을 찾아 교체한다.

찾을 블록(현재 코드):
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
```

교체:
```python
    block_editor = BlockEditor(c, ("floor_hunt", "route"))
    # 미니맵 편집 캔버스(RouteCanvas) + 블록타입 툴바. 캡처/모니터 폭 실패 시 캔버스 생략
    nav_extras = []
    try:
        import mss as _mss
        from PyQt6.QtWidgets import QWidget as _QWidget, QHBoxLayout as _QHBox, \
            QPushButton as _QBtn, QButtonGroup as _QBtnGroup
        from core.screen_reader import ScreenReader
        from core_ui.minimap_canvas import RouteCanvas
        with _mss.mss() as _s:
            _sw = int(_s.monitors[1]["width"])
        route_canvas = RouteCanvas(c, ScreenReader().capture, screen_w=_sw,
                                   on_route_changed=block_editor.reload)
        block_editor._on_change = route_canvas.update   # 리스트→캔버스 이벤트
        # 블록타입 툴바 (선택 안 함 기본)
        bar = _QWidget(); bl = _QHBox(bar)
        bl.setContentsMargins(0, 0, 0, 0)
        grp = _QBtnGroup(bar); grp.setExclusive(True)
        for label, typ in [("선택 안 함", None), ("이동", "move"), ("공격", "attack"),
                           ("사다리", "ladder"), ("점프", "jump"), ("텔포", "teleport")]:
            btn = _QBtn(label); btn.setCheckable(True)
            btn.clicked.connect(lambda _=False, t=typ: route_canvas.set_active_type(t))
            grp.addButton(btn); bl.addWidget(btn)
            if typ is None:
                btn.setChecked(True)
        bl.addStretch()
        nav_extras += [bar, route_canvas]
    except Exception:
        pass
    nav_extras += [route_lbl, block_editor]
```

- [ ] **Step 2: 전체 회귀 + 셸 렌더 스모크**

Run: `cd /c/Users/PC/Desktop/02_work/05_AI/maple_bot && QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/ -q`
Expected: PASS (이전 222 + 신규: block 2 + geom 6 + block_editor 2 + canvas 1 + route_canvas 5 = 16 → 238 passed).

Run (동선 페이지가 예외 없이 렌더):
```bash
cd /c/Users/PC/Desktop/02_work/05_AI/maple_bot && QT_QPA_PLATFORM=offscreen py -3.14 -c "import os; os.environ['QT_QPA_PLATFORM']='offscreen'; from PyQt6.QtWidgets import QApplication; from core_ui.shell import MainShell; from core_ui.theme import apply_font; from core.config_manager import ConfigManager; a=QApplication([]); apply_font(a); w=MainShell(ConfigManager()); w.resize(1180,720); w.show(); a.processEvents(); w.stack.setCurrentIndex(1); a.processEvents(); print('동선 페이지 렌더 OK', w.stack.count())"
```
Expected: `동선 페이지 렌더 OK 6`

- [ ] **Step 3: 커밋**
```bash
git add core_ui/pages.py
git commit -m "feat(minimap): 동선 페이지에 RouteCanvas+블록툴바 통합, 리스트 양방향 결선"
```

---

## Self-Review (작성자 확인)

**Spec coverage:** Block pos(-1)=Task1 · 순수함수(canvas_to_minimap/block_anchor/hit_test/seed_block_at/translate_block/BLOCK_COLORS/block_color)=Task2 · 콜백 양방향(on_change/reload)=Task3+Task6 · minimap_size getter=Task4 · RouteCanvas 배치/드래그/렌더+active리셋+미배치제외=Task5 · 툴바 QButtonGroup+선택안함+통합=Task6. 스펙 항목 전부 매핑.

**Placeholder scan:** TBD/"적절히" 없음. 모든 코드 스텝 완성 코드.

**Type consistency:** `canvas_to_minimap(px,py,zoom,pan)`·`block_anchor(block)->tuple|None`·`hit_test(blocks,mx,my,radius)`·`seed_block_at(type,mx,my)`·`translate_block(block,dx,dy)`·`RouteCanvas(config,screen_capture,route_keys,on_route_changed,**kw)`·`set_active_type/_place_or_select/_drag_to/_end_drag/minimap_size` 명칭이 Task 전반에서 일치. `seed_block_at`은 `_DEFAULTS`에 없는 'teleport'를 move로 매핑(Task2 구현+테스트 일치).

**알려진 주의:** Task6에서 `block_editor._on_change`를 직접 설정(Task3가 `_on_change` 속성을 만들기 때문). 더 깔끔히 하려면 BlockEditor에 `set_on_change()`를 둘 수 있으나 YAGNI로 직접 대입. 툴바 '선택 안 함' 재동기화는 캔버스가 `_active_type=None`으로만 처리(버튼 시각 체크 복원은 후속 폴리시 — 기능엔 영향 없음).
