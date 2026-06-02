# 맵 그래프 + 층 이탈 복귀 Implementation Plan (하위 프로젝트 #3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox(`- [ ]`).

**Goal:** route의 사다리 블록·층 정의로 층 인접그래프를 자동 구성하고, 실행 중 캐릭터가 예상 밖 층에 있으면 최단경로로 복귀 후 동선을 재개한다.

**Architecture:** 그래프/최단경로/기대층은 순수 함수(`core/navigation/map_graph.py`). 복귀는 `BlockRunner`에 `floor_judge`+`recovery_graph`를 주입해 `run_block` 진입 시 처리. 런타임이 그래프를 만들어 주입.

**Tech Stack:** 순수 파이썬(BFS), 기존 `FloorJudge`·`Block`·`BlockRunner`.

**규칙:** 신규 소스 첫 줄 한국어 역할 주석. 테스트 `QT_QPA_PLATFORM=offscreen py -3.14 -m pytest`. 작업 디렉토리 `/c/Users/PC/Desktop/02_work/05_AI/maple_bot`. 커밋 본문 끝 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. 현재 브랜치에서 작업(새 브랜치 X). `config.json` stage 금지.

---

## 파일 구조
| 파일 | 변경 | 책임 |
|------|------|------|
| `core/navigation/map_graph.py` | 생성 | `expected_floor`·`build_graph`·`shortest_path` (순수) |
| `core/navigation/block_runner.py` | 수정 | `floor_judge`/`recovery_graph` 주입 + `run_block` 복귀 |
| `core/runtime.py` | 수정 | 그래프 구성 후 BlockRunner에 주입 |

---

### Task 1: map_graph 순수 함수 (그래프/최단경로/기대층)

**Files:** Create `core/navigation/map_graph.py`; Test `tests/test_map_graph.py`

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_map_graph.py`:
```python
# 맵 그래프 구성·최단경로·기대층 순수 함수 검증
from core.navigation.map_graph import expected_floor, build_graph, shortest_path


class FakeFloor:
    def __init__(self, name): self.name = name


class FakeJudge:
    """y 밴드 → 층. bands=[(name, ymin, ymax)]."""
    def __init__(self, bands): self.bands = bands
    def floor_at(self, y):
        for name, lo, hi in self.bands:
            if lo <= y <= hi:
                return FakeFloor(name)
        return None


def _judge():
    # 1층(아래, y큼) ~ 4층(위, y작음)
    return FakeJudge([("4층", 0, 49), ("3층", 50, 99), ("2층", 100, 149), ("1층", 150, 199)])


def _floors():
    return [FakeFloor("1층"), FakeFloor("2층"), FakeFloor("3층"), FakeFloor("4층")]


def test_expected_floor_from_pos_and_ladder():
    j = _judge()
    assert expected_floor({"type": "attack", "pos_y": 170}, j) == "1층"
    assert expected_floor({"type": "ladder", "y_bot": 170, "y_top": 120}, j) == "1층"  # 아래층 기준
    assert expected_floor({"type": "attack", "pos_y": -1}, j) is None                  # 미배치
    assert expected_floor({"type": "attack", "pos_y": 999}, j) is None                 # 층 밖


def test_build_graph_bidirectional_ladders():
    j = _judge()
    route = [
        {"type": "ladder", "ladder_x": 40, "y_bot": 170, "y_top": 120},   # 1↔2
        {"type": "ladder", "ladder_x": 60, "y_bot": 120, "y_top": 70},    # 2↔3
        {"type": "ladder", "ladder_x": 80, "y_bot": 70, "y_top": 30},     # 3↔4
        {"type": "attack", "pos_y": 170},                                  # 간선 아님
    ]
    g = build_graph(_floors(), route, j)
    assert {e["to"] for e in g["1층"]} == {"2층"}
    assert {e["to"] for e in g["2층"]} == {"1층", "3층"}
    assert {e["to"] for e in g["4층"]} == {"3층"}
    # via는 사다리 블록, 방향 보정됨
    up = [e for e in g["1층"] if e["to"] == "2층"][0]
    assert up["via"]["type"] == "ladder" and up["via"]["ladder_dir"] == "up"
    down = [e for e in g["2층"] if e["to"] == "1층"][0]
    assert down["via"]["ladder_dir"] == "down"


def test_build_graph_skips_out_of_range_and_selfloop():
    j = _judge()
    route = [
        {"type": "ladder", "ladder_x": 1, "y_bot": 999, "y_top": 120},   # 아래층 None → skip
        {"type": "ladder", "ladder_x": 2, "y_bot": 160, "y_top": 170},   # 둘 다 1층 → 자기루프 skip
    ]
    g = build_graph(_floors(), route, j)
    assert all(len(v) == 0 for v in g.values())


def test_shortest_path():
    j = _judge()
    route = [
        {"type": "ladder", "ladder_x": 40, "y_bot": 170, "y_top": 120},   # 1↔2
        {"type": "ladder", "ladder_x": 60, "y_bot": 120, "y_top": 70},    # 2↔3
        {"type": "ladder", "ladder_x": 80, "y_bot": 70, "y_top": 30},     # 3↔4
    ]
    g = build_graph(_floors(), route, j)
    path = shortest_path(g, "1층", "4층")
    assert [e["ladder_x"] for e in path] == [40, 60, 80]   # 1→2→3→4 사다리 순
    assert all(e["ladder_dir"] == "up" for e in path)
    assert shortest_path(g, "2층", "2층") == []             # 같은 층
    assert shortest_path(g, "1층", "없는층") is None         # 경로 없음
```

- [ ] **Step 2: 실패 확인** — Run: `QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_map_graph.py -q`
Expected: FAIL (module not found).

- [ ] **Step 3: 구현** — `core/navigation/map_graph.py`:
```python
# 동선 사다리에서 층 인접그래프 구성 + 최단경로(복귀용). 순수 로직, 런타임 의존 없음
from __future__ import annotations

from collections import deque


def expected_floor(block: dict, judge) -> str | None:
    """블록이 실행돼야 하는 층 이름. ladder는 아래층(y_bot), 그 외는 pos_y로 판정.
    미배치(pos_y<0)나 층 밖이면 None. judge는 floor_at(y)->Floor|None."""
    if block.get("type") == "ladder":
        yb = int(block.get("y_bot", 0))
        f = judge.floor_at(yb) if yb > 0 else None
        return f.name if f is not None else None
    py = int(block.get("pos_y", -1))
    if py < 0:
        return None
    f = judge.floor_at(py)
    return f.name if f is not None else None


def build_graph(floors: list, route: list[dict], judge) -> dict[str, list[dict]]:
    """route의 ladder 블록마다 floor_at(y_bot)=아래층, floor_at(y_top)=위층을 찾아
    양방향 간선 추가. 간선 = {"to": 이웃층, "via": 방향보정된 ladder 블록}.
    층 밖(None)이거나 같은 층(자기루프)이면 건너뜀."""
    graph: dict[str, list[dict]] = {getattr(f, "name", str(f)): [] for f in floors}
    for b in route:
        if b.get("type") != "ladder":
            continue
        yb, yt = int(b.get("y_bot", 0)), int(b.get("y_top", 0))
        fa = judge.floor_at(yb) if yb > 0 else None   # 아래층
        fb = judge.floor_at(yt) if yt > 0 else None   # 위층
        if fa is None or fb is None or fa.name == fb.name:
            continue
        up = dict(b); up["ladder_dir"] = "up"          # 아래→위
        down = dict(b); down["ladder_dir"] = "down"    # 위→아래
        graph.setdefault(fa.name, []).append({"to": fb.name, "via": up})
        graph.setdefault(fb.name, []).append({"to": fa.name, "via": down})
    return graph


def shortest_path(graph: dict, start: str, goal: str) -> list[dict] | None:
    """start→goal 최단경로(간선 수)의 via(ladder 블록) 리스트. 같은 층이면 [],
    경로 없으면 None."""
    if start == goal:
        return []
    q = deque([(start, [])])
    seen = {start}
    while q:
        node, path = q.popleft()
        for edge in graph.get(node, []):
            nxt = edge["to"]
            if nxt in seen:
                continue
            npath = path + [edge["via"]]
            if nxt == goal:
                return npath
            seen.add(nxt)
            q.append((nxt, npath))
    return None
```

- [ ] **Step 4: 통과 확인** — Run: `QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_map_graph.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: 커밋**
```bash
git add core/navigation/map_graph.py tests/test_map_graph.py
git commit -m "feat(nav): 맵 그래프 순수함수(expected_floor·build_graph·shortest_path)"
```

---

### Task 2: BlockRunner 층 이탈 복귀 결선

**Files:** Modify `core/navigation/block_runner.py`; Test `tests/test_block_runner.py`

- [ ] **Step 1: 실패 테스트 추가** — `tests/test_block_runner.py` 끝에 추가:
```python
class FakeFloorObj:
    def __init__(self, name): self.name = name


class BandJudge:
    def __init__(self, bands): self.bands = bands   # [(name,ymin,ymax)]
    def floor_at(self, y):
        for name, lo, hi in self.bands:
            if lo <= y <= hi:
                return FakeFloorObj(name)
        return None


def test_run_block_recovers_when_on_wrong_floor():
    """기대층(블록 pos_y=2층)과 실제층(1층)이 다르면 복귀 사다리를 타고 올라간다."""
    h = FakeHumanizer()
    # 캐릭터 y: 처음 1층(170) → 사다리 등반하면 2층(120)으로 올라간 것으로 흉내
    state = {"y": 170}

    class WorldChar:
        def pos(self): return (40, state["y"])
    judge = BandJudge([("2층", 100, 149), ("1층", 150, 199)])
    graph = {
        "1층": [{"to": "2층", "via": {"type": "ladder", "ladder_x": 40,
                                     "y_bot": 170, "y_top": 120, "ladder_dir": "up"}}],
        "2층": [],
    }

    # _do_ladder를 가로채 '복귀 실행되면 2층으로 이동'으로 흉내
    runner = BlockRunner(humanizer=h, pos_fn=WorldChar().pos,
                         floor_judge=judge, recovery_graph=graph)
    climbed = {"n": 0}
    def fake_climb(block, max_steps=200):
        climbed["n"] += 1; state["y"] = 120   # 2층 도달
        return True
    runner._do_ladder = fake_climb

    # 2층에서 할 공격 블록(pos_y=120) — 현재 1층이라 복귀 후 실행돼야 함
    ok = runner.run_block(Block(type="attack", skill_key="z", pos_y=120), max_steps=5)
    assert climbed["n"] >= 1            # 복귀 사다리 실행됨
    assert ok is True


def test_run_block_no_recovery_when_same_floor():
    h = FakeHumanizer()
    judge = BandJudge([("2층", 100, 149), ("1층", 150, 199)])
    graph = {"1층": [], "2층": []}
    runner = BlockRunner(humanizer=h, pos_fn=lambda: (40, 120),  # 이미 2층
                         floor_judge=judge, recovery_graph=graph)
    called = {"n": 0}
    runner._do_ladder = lambda *a, **k: called.__setitem__("n", called["n"] + 1)
    runner.run_block(Block(type="attack", skill_key="z", pos_y=120), max_steps=5)
    assert called["n"] == 0             # 복귀 없음


def test_run_block_recovery_noop_without_judge():
    """judge/graph 미주입이면 기존 동작 그대로(복귀 비활성)."""
    h = FakeHumanizer()
    char = MovingChar(start_x=20); char.target = 30
    runner = BlockRunner(humanizer=h, pos_fn=char.pos)   # judge 없음
    assert runner.run_block(Block(type="move", target_x=30), max_steps=50) is True
```

- [ ] **Step 2: 실패 확인** — Run: `QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_block_runner.py -q`
Expected: FAIL (`unexpected keyword 'floor_judge'`).

- [ ] **Step 3: 구현** — `core/navigation/block_runner.py`:

(a) `__init__` 시그니처 끝(`poll_sec: float = 0.05):` 줄)을 확장하고 본문에 필드 추가. 기존:
```python
    def __init__(self, humanizer, pos_fn: Callable[[], tuple[int, int]],
                 jump_key: str = "alt", teleport_key: str = "space",
                 sleep_fn: Callable[[float], None] | None = None,
                 stop_fn: Callable[[], bool] | None = None,
                 poll_sec: float = 0.05):
        self._h = humanizer
        self._pos = pos_fn
        self._jump_key = jump_key
        self._tele_key = teleport_key
        self._sleep = sleep_fn or time.sleep
        self._stop = stop_fn or (lambda: False)
        self._poll = poll_sec
```
교체:
```python
    def __init__(self, humanizer, pos_fn: Callable[[], tuple[int, int]],
                 jump_key: str = "alt", teleport_key: str = "space",
                 sleep_fn: Callable[[float], None] | None = None,
                 stop_fn: Callable[[], bool] | None = None,
                 poll_sec: float = 0.05,
                 floor_judge=None, recovery_graph=None, max_recover: int = 3):
        self._h = humanizer
        self._pos = pos_fn
        self._jump_key = jump_key
        self._tele_key = teleport_key
        self._sleep = sleep_fn or time.sleep
        self._stop = stop_fn or (lambda: False)
        self._poll = poll_sec
        self._judge = floor_judge
        self._graph = recovery_graph
        self._max_recover = max_recover
```

(b) `run_block`의 첫 줄(`def run_block(self, block: Block, max_steps: int = 200) -> bool:` 바로 다음)에 복귀 호출 추가:
```python
    def run_block(self, block: Block, max_steps: int = 200) -> bool:
        self._recover_if_needed(block, max_steps)
        if block.type == "move":
```

(c) `_recover_if_needed`를 `run_block` 메서드 **바로 앞**에 추가:
```python
    def _recover_if_needed(self, block: Block, max_steps: int) -> None:
        """현재 층이 블록의 기대 층과 다르면 그래프 최단경로의 사다리를 타고 복귀.
        judge/graph 미주입이거나 기대층 None이면 아무것도 안 함."""
        if self._judge is None or not self._graph:
            return
        from core.navigation.map_graph import expected_floor, shortest_path
        want = expected_floor(block.to_dict(), self._judge)
        if want is None:
            return
        for _ in range(self._max_recover):
            _x, y = self._pos()
            cur = self._judge.floor_at(y)
            if cur is None or cur.name == want:
                return
            path = shortest_path(self._graph, cur.name, want)
            if not path:
                return                       # 복구 불가 → 그냥 진행
            self._do_ladder(Block.from_dict(path[0]), max_steps)
```

- [ ] **Step 4: 통과 확인** — Run: `QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_block_runner.py -q`
Expected: PASS (기존 + 신규 3).

- [ ] **Step 5: 커밋**
```bash
git add core/navigation/block_runner.py tests/test_block_runner.py
git commit -m "feat(nav): BlockRunner 층 이탈 자동 복귀(그래프 최단경로 사다리)"
```

---

### Task 3: 런타임에 그래프 구성·주입

**Files:** Modify `core/runtime.py`; Test `tests/test_runtime.py`

- [ ] **Step 1: 실패 테스트 추가** — `tests/test_runtime.py` 끝에 추가:
```python
def test_runtime_builds_recovery_graph_and_injects():
    """floors+route(사다리)면 BlockRunner에 복귀 그래프가 주입된다."""
    backend = RecordingBackend()
    cfg = RuntimeConfig(
        minimap_region={"left": 0, "top": 0, "width": 200, "height": 120},
        floors=[Floor("2층", 100, 149), Floor("1층", 150, 199)],
        route=[Block(type="ladder", ladder_x=40, y_bot=170, y_top=120)],
    )
    rt = BotRuntime(screen_capture=lambda r=None: _yellow_at(50, 75),
                    input_backend=backend, config=cfg, sidecar_channel=InMemoryChannel())
    assert rt.block_runner._judge is not None
    g = rt.block_runner._graph
    assert g is not None and "1층" in g and "2층" in g
    assert any(e["to"] == "2층" for e in g["1층"])   # 사다리 간선
```

- [ ] **Step 2: 실패 확인** — Run: `QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_runtime.py -q`
Expected: FAIL (`_judge` None 또는 AttributeError).

- [ ] **Step 3: 구현** — `core/runtime.py`의 `self.block_runner = BlockRunner(...)` 생성부를 찾아, `self.floor_judge` 생성 **다음**으로 옮기고 그래프를 주입한다.

현재(대략):
```python
        self.block_runner = BlockRunner(
            humanizer=self.humanizer,
            pos_fn=lambda: self.orchestrator.state.get_position() or (0, 0),
            stop_fn=lambda: not self._route_can_run(),
        )
        self.floor_judge = FloorJudge(config.floors) if config.floors else None
```
교체:
```python
        self.floor_judge = FloorJudge(config.floors) if config.floors else None
        _recovery_graph = None
        if self.floor_judge is not None and config.route:
            from core.navigation.map_graph import build_graph
            _recovery_graph = build_graph(
                config.floors, [b.to_dict() for b in config.route], self.floor_judge)
        self.block_runner = BlockRunner(
            humanizer=self.humanizer,
            pos_fn=lambda: self.orchestrator.state.get_position() or (0, 0),
            stop_fn=lambda: not self._route_can_run(),
            floor_judge=self.floor_judge, recovery_graph=_recovery_graph,
        )
```
주의: `self.floor_judge` 가 원래 `block_runner` 생성 **뒤**에 정의돼 있으면, 위처럼 **앞으로 이동**시켜 순서를 맞춘다. 기존 `self.floor_judge = FloorJudge(...)` 줄이 중복되지 않게 한 곳만 남긴다.

- [ ] **Step 4: 통과 확인 + 전체 회귀**
Run: `QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/ -q`
Expected: PASS (이전 238 + map_graph 4 + block_runner 3 + runtime 1 = 246 passed).

- [ ] **Step 5: 커밋**
```bash
git add core/runtime.py tests/test_runtime.py
git commit -m "feat(runtime): 복귀 그래프 구성 후 BlockRunner 주입"
```

---

## Self-Review (작성자 확인)

**Spec coverage:** expected_floor/build_graph/shortest_path=Task1 · 복귀결선(judge/graph 주입, run_block 복귀, 시도상한, 경로없음 생략)=Task2 · 런타임 그래프구성·주입=Task3. 스펙 항목 전부 매핑.

**Placeholder scan:** TBD/"적절히" 없음, 모든 코드 스텝 완성 코드.

**Type consistency:** `expected_floor(block_dict, judge)->str|None`·`build_graph(floors,route,judge)->dict`·`shortest_path(graph,start,goal)->list|None`·`BlockRunner(...,floor_judge,recovery_graph,max_recover)`·`_recover_if_needed(block,max_steps)`·간선 `{"to","via"}` 명칭이 Task 전반 일치. `via`는 dict(ladder 블록)이며 BlockRunner가 `Block.from_dict(via)`로 실행 — 타입 변환 일관.

**주의:** Task3에서 `self.floor_judge` 정의 위치를 block_runner 생성 앞으로 옮기는 점(중복 라인 제거 필수). 실행기(FloorHuntRunner)는 run_block을 통해 복귀가 자동 작동하므로 추가 결선 불필요.
