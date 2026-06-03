# 블록 루트 기반 층별 사냥 완성 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 커스텀 루트 모드가 이동만 하던 것을 고쳐, 루트를 도는 중 이미지 탐지로 공격하고(사냥 구간 한정), 떨어지면 루트 블록에서 자동 추출한 층 그래프로 복귀하게 만든다.

**Architecture:** 접근 A — 이동은 기존 `BlockRunner`/`FloorHuntRunner` 스레드가, 공격은 메인 루프 `hunting_tick`이 담당한다. BlockRunner가 블록 실행을 `on_segment_enter`/`on_segment_exit`로 감싸(try/finally) "사냥 블록 실행 중"이라는 구간을 런타임에 통지하고, 런타임은 enter에서 `route_hunt_active`를 블록에 따라 세팅·exit에서 항상 False로 정리한다. `hunting_tick`은 그 플래그가 켜져 있을 때만 `_monster_in_range()`→`combat.attack()`을 수행한다(불변식: 사냥 블록을 실제 실행 중일 때만 공격). 복귀용 층은 신규 순수함수 `floors_from_route()`가 move 블록 Y를 클러스터링해 만들고, 간선은 기존 `build_graph()`가 사다리에서 생성한다(책임 분리·DRY).

**Tech Stack:** Python 3.14(`py -3.14`), pytest(`QT_QPA_PLATFORM=offscreen`), 기존 모듈(core/navigation, core/runtime).

---

## File Structure

- `core/navigation/floor_extract.py` (신규) — `floors_from_route(route, band)` 순수함수. move 블록 `pos_y` 클러스터링 → `Floor` 밴드.
- `core/navigation/block_runner.py` (수정) — 생성자 `on_segment_enter`/`on_segment_exit` 콜백 추가, `run_block`을 try/finally로 감싸 진입/이탈 통지.
- `core/runtime.py` (수정) — 자동 층 추출 사용, route_mode 시 템플릿 로드, `route_hunt_active` 플래그 + `_on_route_segment`, `hunting_tick` 루트 분기 공격 게이팅.
- `core_ui/pages.py` (수정) — 죽은 "층별 사냥 사용" 체크박스 제거.
- `tests/test_floor_extract.py` (신규), `tests/test_route_attack.py` (신규).

---

### Task 1: floors_from_route — 루트 블록에서 층 자동 추출

**Files:**
- Create: `core/navigation/floor_extract.py`
- Test: `tests/test_floor_extract.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_floor_extract.py
# move 블록 pos_y 클러스터링 → 층 밴드 생성 검증
from core.navigation.floor_extract import floors_from_route


def test_clusters_move_blocks_into_floors():
    route = [
        {"type": "move", "pos_x": 10, "pos_y": 100, "start_x": 10, "end_x": 50},
        {"type": "move", "pos_x": 20, "pos_y": 103, "start_x": 20, "end_x": 60},  # 100과 같은 층
        {"type": "ladder", "ladder_x": 30, "y_top": 50, "y_bot": 100},
        {"type": "move", "pos_x": 15, "pos_y": 50, "start_x": 15, "end_x": 55},   # 위층
    ]
    floors = floors_from_route(route, band=12)
    assert len(floors) == 2
    # 정렬: Y 작은(위층)이 먼저인지 여부 무관 — 두 밴드가 100대/50대로 분리
    bands = sorted((f.y_min, f.y_max) for f in floors)
    assert bands[0][0] <= 50 <= bands[0][1]
    assert bands[1][0] <= 100 <= bands[1][1]


def test_ignores_unplaced_and_non_move():
    route = [
        {"type": "move", "pos_x": -1, "pos_y": -1, "start_x": 0, "end_x": 0},  # 미배치
        {"type": "attack", "skill_key": "a"},
    ]
    assert floors_from_route(route) == []


def test_names_are_unique():
    route = [
        {"type": "move", "pos_x": 1, "pos_y": 40, "start_x": 1, "end_x": 5},
        {"type": "move", "pos_x": 1, "pos_y": 120, "start_x": 1, "end_x": 5},
    ]
    names = [f.name for f in floors_from_route(route)]
    assert len(names) == len(set(names))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_floor_extract.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.navigation.floor_extract'`

- [ ] **Step 3: Write minimal implementation**

```python
# core/navigation/floor_extract.py
# 루트 블록(move)의 Y를 근접 클러스터링해 층 밴드(Floor)를 자동 추출 — 복귀 그래프용
from __future__ import annotations

from core.navigation.floor_judge import Floor


def floors_from_route(route: list[dict], band: int = 12) -> list[Floor]:
    """move 블록의 pos_y(미니맵 px)를 band 간격으로 클러스터링해 Floor 리스트 생성.

    band: 같은 층으로 묶을 Y 허용 간격(px). 각 층은 [min-band, max+band] 범위로
    여유를 둬 사다리 끝점(y_top/y_bot)이 인접 층에 포함되도록 한다.
    미배치(pos_y<0)·비 move 블록은 무시. 빈 입력이면 []."""
    ys = sorted({int(b["pos_y"]) for b in route
                 if b.get("type") == "move" and int(b.get("pos_y", -1)) >= 0})
    if not ys:
        return []
    clusters: list[list[int]] = [[ys[0]]]
    for y in ys[1:]:
        if y - clusters[-1][-1] <= band:
            clusters[-1].append(y)
        else:
            clusters.append([y])
    floors: list[Floor] = []
    for i, cl in enumerate(clusters):
        floors.append(Floor(name=f"F{i}", y_min=min(cl) - band, y_max=max(cl) + band))
    return floors
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_floor_extract.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add core/navigation/floor_extract.py tests/test_floor_extract.py
git commit -m "feat(nav): 루트 블록 Y에서 층 자동 추출 floors_from_route"
```

---

### Task 2: 런타임에 자동 층 추출 + route_mode 템플릿 로드 배선

**Files:**
- Modify: `core/runtime.py:147-175` (floor_judge/recovery_graph 구성, 템플릿 로드 조건)

복귀가 작동하려면 `config.floors`가 비어도 route에서 층을 만들어 `FloorJudge`/`build_graph`에 넣어야 한다. 또한 루트 공격이 이미지 탐지를 쓰므로, `route_mode`일 때도 닉네임/몬스터 템플릿을 로드해야 한다.

- [ ] **Step 1: 자동 층 추출로 floor_judge/그래프 구성 교체**

`core/runtime.py`에서 기존 블록(147-153행):

```python
        self.floor_judge = FloorJudge(config.floors) if config.floors else None
        # 층 이탈 복귀 그래프 — route의 사다리에서 자동 구성
        _recovery_graph = None
        if self.floor_judge is not None and config.route:
            from core.navigation.map_graph import build_graph
            _recovery_graph = build_graph(
                config.floors, [b.to_dict() for b in config.route], self.floor_judge)
```

를 아래로 교체:

```python
        # 층: 명시적 zones가 있으면 우선, 없으면 루트 블록 Y에서 자동 추출(복귀용)
        _floors = config.floors
        if not _floors and config.route:
            from core.navigation.floor_extract import floors_from_route
            _floors = floors_from_route([b.to_dict() for b in config.route])
        self.floor_judge = FloorJudge(_floors) if _floors else None
        # 층 이탈 복귀 그래프 — route의 사다리에서 자동 구성
        _recovery_graph = None
        if self.floor_judge is not None and config.route:
            from core.navigation.map_graph import build_graph
            _recovery_graph = build_graph(
                _floors, [b.to_dict() for b in config.route], self.floor_judge)
```

- [ ] **Step 2: route_mode일 때도 이미지 템플릿 로드**

`core/runtime.py` 기존 블록(169행 부근):

```python
        if config.hunt_mode == "image":
            if config.name_template:
```

를 아래로 교체(조건만 확장):

```python
        if config.hunt_mode == "image" or config.route_mode:
            if config.name_template:
```

- [ ] **Step 3: 임포트 회귀 확인**

Run: `QT_QPA_PLATFORM=offscreen py -3.14 -c "import core.runtime"`
Expected: 출력 없음(에러 없음).

- [ ] **Step 4: 전체 테스트 회귀**

Run: `QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/ -q`
Expected: 기존과 동일 PASS(254 passed; Task 1의 +3 포함).

- [ ] **Step 5: Commit**

```bash
git add core/runtime.py
git commit -m "feat(runtime): zones 없으면 루트에서 층 자동추출, route_mode 시 템플릿 로드"
```

---

### Task 3: BlockRunner에 on_segment_enter/exit 브래킷 훅 추가

**Files:**
- Modify: `core/navigation/block_runner.py:30-46` (생성자), `:78-98` (run_block을 try/finally로 감쌈)
- Test: `tests/test_block_runner_hooks.py`

이동 모듈을 detector/combat에 의존시키지 않기 위해, BlockRunner는 블록 실행을 enter/exit로 감싸 통지만 한다("사냥" 개념은 모름). exit는 `finally`에서 호출돼 반환/예외와 무관하게 항상 실행된다.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_block_runner_hooks.py
# BlockRunner가 블록 실행을 enter/exit로 감싸 통지하는지(예외에도 exit 보장) 검증
from core.navigation.block import Block
from core.navigation.block_runner import BlockRunner


def _runner(events, fail=False):
    h = type("H", (), {"hold_dir": lambda *a: None, "release_dir": lambda *a: None,
                       "release_all": lambda *a: None, "release": lambda *a, **k: None,
                       "hold": lambda *a, **k: None, "perform": lambda *a, **k: None,
                       "jitter_sec": lambda s, b: 0.0, "random_side": lambda s: "left"})()
    # 도착 즉시(pos가 target과 같다고 보고) 끝나도록 pos_fn 고정
    return BlockRunner(
        humanizer=h, pos_fn=lambda: (0, 0), sleep_fn=lambda s: None,
        on_segment_enter=lambda b: events.append(("enter", b.type, b.mode)),
        on_segment_exit=lambda b: events.append(("exit", b.type, b.mode)))


def test_enter_then_exit_wraps_block():
    events = []
    r = _runner(events)
    r.run_block(Block(type="move", target_x=0, move_type="walk"))  # pos=0=target → 즉시 도착
    assert events[0][0] == "enter"
    assert events[-1][0] == "exit"


def test_exit_called_even_on_exception():
    events = []
    r = _runner(events)
    # _recover_if_needed가 터지게 만들어 예외 경로에서도 exit 보장 확인
    r._recover_if_needed = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    try:
        r.run_block(Block(type="move", target_x=0, move_type="walk"))
    except RuntimeError:
        pass
    assert ("exit", "move", "count") in events
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_block_runner_hooks.py -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'on_segment_enter'`

- [ ] **Step 3: 생성자에 enter/exit 인자 추가**

`core/navigation/block_runner.py` 생성자 시그니처(기존):

```python
                 floor_judge=None, recovery_graph=None, max_recover: int = 3):
```

를:

```python
                 floor_judge=None, recovery_graph=None, max_recover: int = 3,
                 on_segment_enter=None, on_segment_exit=None):
```

생성자 본문 끝(기존 `self._max_recover = max_recover` 다음 줄)에 추가:

```python
        self._on_seg_enter = on_segment_enter   # callable(Block) | None — 블록 진입 통지
        self._on_seg_exit = on_segment_exit     # callable(Block) | None — 블록 이탈 통지(finally)
```

- [ ] **Step 4: run_block을 enter/try/finally(exit)로 감쌈**

`run_block` 전체(기존 78-98행)를 아래로 교체:

```python
    def run_block(self, block: Block, max_steps: int = 200) -> bool:
        if self._on_seg_enter is not None:
            self._on_seg_enter(block)
        try:
            self._recover_if_needed(block, max_steps)
            if block.type == "move":
                # 구간 모드: start_x < end_x 이면 mode(count/infinite/pass)에 따라 왕복/통과
                if block.end_x > block.start_x:
                    if block.mode == "pass":
                        # 통과: 구간을 한 방향으로 1회만 지나감(end_x까지)
                        return self._exec_move(
                            Block(type="move", target_x=block.end_x, move_type=block.move_type),
                            max_steps)
                    infinite = (block.mode == "infinite")
                    sweeps = max(1, block.sweeps)
                    return self.run_sweep(block.start_x, block.end_x, sweeps,
                                          block.move_type, max_steps=max_steps,
                                          infinite=infinite)
                return self._exec_move(block, max_steps)
            if block.type == "ladder":
                return self._do_ladder(block, max_steps)
            if block.type == "jump":
                return self._do_jump(block)
            return True
        finally:
            if self._on_seg_exit is not None:
                self._on_seg_exit(block)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_block_runner_hooks.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: 기존 block_runner 회귀**

Run: `QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_block_runner.py -q`
Expected: 기존 PASS 유지(콜백 기본 None이라 동작 불변).

- [ ] **Step 7: Commit**

```bash
git add core/navigation/block_runner.py tests/test_block_runner_hooks.py
git commit -m "feat(nav): BlockRunner enter/exit 브래킷 훅(try/finally, 블록 실행 구간 통지)"
```

---

### Task 4: route_hunt_active 플래그 + hunting_tick 루트 공격

**Files:**
- Modify: `core/runtime.py:146` (필드), `:154-159` (block_runner에 on_segment 주입), `:256-260` (hunting_tick 루트 분기)
- Test: `tests/test_route_attack.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_route_attack.py
# 루트 모드에서 사냥 구간(pass 아님)일 때만 이미지 탐지→공격이 일어나는지 검증
from core.navigation.block import Block
from core import runtime as rt_mod


def _make_runtime():
    rt = rt_mod.BotRuntime.__new__(rt_mod.BotRuntime)
    rt._route_hunt_active = False
    return rt


def test_segment_enter_sets_flag_for_hunt_and_pass():
    rt = _make_runtime()
    rt._on_route_segment_enter(Block(type="move", start_x=10, end_x=50, mode="infinite"))
    assert rt._route_hunt_active is True
    rt._on_route_segment_enter(Block(type="move", start_x=10, end_x=50, mode="count"))
    assert rt._route_hunt_active is True
    rt._on_route_segment_enter(Block(type="move", start_x=10, end_x=50, mode="pass"))
    assert rt._route_hunt_active is False
    rt._on_route_segment_enter(Block(type="ladder", ladder_x=30, y_top=50, y_bot=100))
    assert rt._route_hunt_active is False


def test_segment_exit_always_clears_flag():
    rt = _make_runtime()
    rt._route_hunt_active = True
    rt._on_route_segment_exit(Block(type="move", start_x=10, end_x=50, mode="infinite"))
    assert rt._route_hunt_active is False


def test_hunting_tick_attacks_only_in_hunt_segment(monkeypatch):
    rt = _make_runtime()
    # 최소 더블: 루트 모드 + 메인 틱이 보는 부속들
    class _FHR: pass
    rt.floor_hunt_runner = _FHR()
    calls = {"attack": 0}

    class _Combat:
        def attack(self, *a, **k): calls["attack"] += 1
    class _Tick:
        def tick(self, now): pass
    class _Orch:
        mode = "hunting"
    class _Cfg:
        attack_key = "ctrl"
    rt.combat = _Combat(); rt.buffs = _Tick(); rt.pet = _Tick(); rt.pickup = _Tick()
    rt.orchestrator = _Orch(); rt._cfg = _Cfg()
    monkeypatch.setattr(rt, "_monster_in_range", lambda: True)

    rt._route_hunt_active = False          # 통과(회수) 구간
    rt.hunting_tick(now=0.0)
    assert calls["attack"] == 0

    rt._route_hunt_active = True           # 사냥 구간 + 몬스터 감지
    rt.hunting_tick(now=0.0)
    assert calls["attack"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_route_attack.py -v`
Expected: FAIL — `AttributeError: 'BotRuntime' object has no attribute '_on_route_segment_enter'`

- [ ] **Step 3: 런타임에 필드·메서드·주입·게이팅 구현**

(a) `core/runtime.py` 기존 146행 다음에 플래그 필드 추가:

```python
        self._bot_running = False    # 컨트롤러 start/stop로 토글 (루트 실행 활성 조건)
        self._route_hunt_active = False   # 현재 루트 블록이 사냥 구간이면 True(공격 게이팅)
```

(b) `BlockRunner(...)` 생성 인자(기존 158행 `floor_judge=..., recovery_graph=...,` 줄)에 추가:

```python
            floor_judge=self.floor_judge, recovery_graph=_recovery_graph,
            on_segment_enter=self._on_route_segment_enter,
            on_segment_exit=self._on_route_segment_exit,
```

(c) `_monster_in_range` 메서드 정의 바로 위에 신규 메서드 2개 추가:

```python
    def _on_route_segment_enter(self, block) -> None:
        """루트 러너가 블록 진입 시 호출 — 사냥 구간(move·pass아님)이면 공격 허용."""
        self._route_hunt_active = (
            getattr(block, "type", None) == "move"
            and getattr(block, "mode", "count") != "pass")

    def _on_route_segment_exit(self, block) -> None:
        """블록 이탈(finally) 시 호출 — 공격 플래그를 항상 끈다(블록 사이 비공격)."""
        self._route_hunt_active = False
```

(d) `hunting_tick`의 루트 분기(기존 256-260행):

```python
        if self.floor_hunt_runner is not None:
            self.buffs.tick(now)
            self.pet.tick(now)
            self.pickup.tick(now)
            return
```

를:

```python
        if self.floor_hunt_runner is not None:
            self.buffs.tick(now)
            self.pet.tick(now)
            self.pickup.tick(now)
            # 사냥 구간이면 이미지 탐지→공격(이동은 루트 스레드 담당)
            if self._route_hunt_active and self._cfg.attack_key and self._monster_in_range():
                self.combat.attack(self._cfg.attack_key, mode="duration")
            return
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_route_attack.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 전체 회귀**

Run: `QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/ -q`
Expected: PASS (258 passed; 251 기존 +3 Task1 +2 Task3 +2 Task4).

- [ ] **Step 6: Commit**

```bash
git add core/runtime.py tests/test_route_attack.py
git commit -m "feat(runtime): 루트 사냥 구간에서 이미지 탐지→공격(접근 A, pass 구간 비공격)"
```

---

### Task 5: 죽은 "층별 사냥 사용" 토글 제거

**Files:**
- Modify: `core_ui/pages.py:278` (CheckField 제거)

- [ ] **Step 1: 체크박스 제거**

`core_ui/pages.py`의 page2 필드 리스트에서 기존 줄:

```python
        CheckField("층별 사냥 사용", c, ("floor_hunt", "enabled")),
        CheckField("커스텀 루트 모드", c, ("floor_hunt", "route_mode")),
```

를(첫 줄 삭제):

```python
        CheckField("커스텀 루트 모드", c, ("floor_hunt", "route_mode")),
```

- [ ] **Step 2: 페이지 빌드 회귀**

Run: `QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/test_pages.py -q`
Expected: PASS (페이지 6개 빌드 유지).

- [ ] **Step 3: Commit**

```bash
git add core_ui/pages.py
git commit -m "refactor(ui): 미연결 '층별 사냥 사용' 토글 제거(커스텀 루트 모드로 일원화)"
```

---

## 완료 후

- 전체 테스트 `QT_QPA_PLATFORM=offscreen py -3.14 -m pytest tests/ -q` PASS 확인.
- superpowers:finishing-a-development-branch로 main 병합.
- 인게임 검증: "커스텀 루트 모드" ON → 로그 `▶ 봇 시작 (층별 루트 실행기)`, 사냥 구간에서 몬스터 들어오면 스킬 사용, pass 구간은 통과만, 떨어지면 사다리로 복귀.
