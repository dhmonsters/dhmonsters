# 맵 그래프 + 층 이탈 복귀 설계 (하위 프로젝트 #3)

> "실시간 미니맵 동선 에디터"의 세 번째 하위 프로젝트. #1(캔버스)·#2(블록 편집기)가 main에 있다.
> 큰맵 파노라마(#4)는 별도.

**목표:** 동선(route)의 사다리 블록과 층(Floor) 정의로부터 **맵 그래프를 자동 구성**하고, 실행 중 캐릭터가 **예상 밖 층에 떨어지면 최단경로로 제 층에 복귀**한 뒤 동선을 재개한다.

**아키텍처:** 그래프 구성·최단경로는 위젯/런타임과 분리한 **순수 함수**(`core/navigation/map_graph.py`)에 둔다. "지금 어느 층"은 기존 `FloorJudge.floor_at(y)`로 안다. "이 블록은 어느 층에서 실행돼야 하나"는 **#2가 추가한 블록 `pos_y`**를 `floor_at`에 넣어 도출한다. 복귀 실행은 `BlockRunner`의 사다리 실행(이미 구현)을 재사용한다.

**Tech Stack:** 순수 파이썬(그래프/BFS), 기존 `core/navigation/floor_judge.FloorJudge`·`block.Block`·`block_runner.BlockRunner`.

---

## 범위 (Scope)

**포함:**
- `build_graph(floors, route)` — route의 ladder 블록을 간선으로 한 층 인접그래프(순수)
- `shortest_path(graph, start, goal)` — BFS 최단경로 = 거쳐야 할 ladder 블록 리스트(순수)
- `expected_floor(block, floors)` — 블록의 기대 층(블록 `pos_y`/ladder y로 `floor_at`)(순수)
- 복귀 계약: BlockRunner가 위치 블록 실행 전 "실제 층 ≠ 기대 층"이면 복귀경로 실행 후 진행

**제외:**
- 그래프 시각화(캔버스에 간선 그리기)는 후속 폴리시(#2 캔버스에 얹을 수 있음, 이 spec 밖)
- 큰맵(#4) — 이 spec은 한 미니맵에 층들이 다 보이는 맵 기준
- 텔포/다운점프 간선: 1차로 **ladder 간선만**. 다운점프 간선은 가능하면 포함하되 핵심은 사다리

---

## 데이터 모델

**Floor**(기존, `floor_judge.py`): `name, y_min, y_max`. 노드 식별자 = `name`.
**그래프 표현:**
```python
Graph = dict[str, list[Edge]]            # floor_name → 이웃 간선들
Edge  = {"to": str, "via": dict}         # to=이웃 층 name, via=실행할 ladder 블록(dict)
```
- ladder 블록은 `ladder_x, y_top, y_bot, ladder_dir`를 가진다. `floor_at(y_bot)`=아래층 A, `floor_at(y_top)`=위층 B.
- 한 ladder는 **양방향 간선** 2개를 만든다: A→B(올라감, dir=up로 실행), B→A(내려감, dir=down로 실행). `via`에는 실행 시 쓸 사다리 블록(필요 시 ladder_dir만 바꾼 사본).

---

## 컴포넌트

### 1. 순수 함수 — `core/navigation/map_graph.py` (생성)
헤더: `# 동선 사다리에서 층 인접그래프 구성 + 최단경로(복귀용). 순수 로직, 런타임 의존 없음`
```python
def expected_floor(block: dict, judge) -> str | None:
    """블록이 실행돼야 하는 층 이름. ladder는 아래층(y_bot), 그 외는 pos_y로 floor_at.
    pos 미배치(-1)나 층 밖이면 None."""

def build_graph(floors: list, route: list[dict], judge) -> dict[str, list[dict]]:
    """route의 ladder 블록마다 floor_at(y_bot)=A, floor_at(y_top)=B를 찾아
    A↔B 양방향 간선 추가. 간선 via=그 방향 실행용 ladder 블록(dir 보정).
    A 또는 B가 None(층 밖)이면 그 ladder는 건너뜀. 반환: {floor_name: [edge,...]}."""

def shortest_path(graph: dict, start: str, goal: str) -> list[dict] | None:
    """start→goal BFS 최단경로의 간선 via(ladder 블록) 리스트. 같은 층이면 [].
    경로 없으면 None. (간선 수 기준 최단)"""
```
- `judge`는 `FloorJudge`(또는 `floor_at(y)->Floor|None`를 가진 객체). 순수성 유지를 위해 인자로 주입(전역참조 X).

### 2. 복귀 결선 — `BlockRunner`에 추가
- `BlockRunner` 생성자에 선택적 `floor_judge`, `recovery_graph`(또는 둘을 합친 `recover_fn`)를 주입.
- `run_block` 진입 시(또는 `run_route` 루프에서) 위치 있는 블록이면:
  1. 현재 위치 `(x,y)=pos_fn()` → `cur = judge.floor_at(y)`
  2. `want = expected_floor(block, judge)`
  3. `cur != want`(둘 다 not None이고 다름)면 **복귀**: `path = shortest_path(graph, cur.name, want)` → path의 각 ladder 블록을 `_do_ladder`로 실행 → 다시 위치 확인. path None이면 복구 불가로 로그 후 해당 블록 skip(또는 정지).
  4. 복귀 끝나면 원래 블록 실행.
- 무한 복귀 방지: 복귀 시도 횟수 상한(예 3) — 초과 시 중단하고 False 반환.

### 3. 런타임 주입 — `runtime.py`
- `BotRuntime`에서 `FloorJudge`(이미 `self.floor_judge`)와 `build_graph(floors, route, judge)`로 만든 그래프를 `BlockRunner`에 주입. route 변경 시 그래프 재구성(설정 reload 시점).

---

## 데이터 흐름
```
[설정] floors + route(ladder들) → build_graph → graph (런타임 보관)
[실행] run_block(positioned) → cur=floor_at(y), want=expected_floor(block)
        cur≠want → shortest_path(graph,cur,want) → 각 ladder _do_ladder 실행 → 재확인
        복귀 완료 → 원래 블록 실행
```

## 에러 처리
- 층 정의 없음(floors 비어있음): 그래프 빈 dict → 복귀 비활성(블록 그대로 실행). 기능 무해 통과.
- ladder가 같은 층 두 점을 가리킴(y_top/y_bot이 같은 층): 자기루프 간선 무시.
- 경로 없음(`shortest_path` None): 로그 후 복귀 생략(블록 실행은 시도). 정지까진 안 함.
- `pos_y` 미배치(-1) 블록: `expected_floor` None → 복귀 판정 생략(그냥 실행).
- 무한 복귀: 시도 상한 초과 시 해당 틱 중단(False).

## 테스트
순수 함수(`tests/test_map_graph.py`) — 가짜 judge(`floor_at(y)` 룩업)로:
- `expected_floor`: pos_y가 2층 범위면 "2층", ladder는 y_bot 기준, 미배치 -1이면 None.
- `build_graph`: 1-2-3-4 사다리 4개 → 인접그래프 양방향, 층 밖 ladder 제외, 자기루프 무시.
- `shortest_path`: 1→4 최단(중간 사다리 거침), 같은 층 [], 단절 None, 최단(간선수) 보장.

런타임 결선(`tests/test_block_runner.py` 또는 `test_runtime.py`) — 가짜 pos/judge/graph로:
- 캐릭터가 기대층과 다른 층 → `run_block`이 복귀 경로의 사다리를 실행(_do_ladder 호출 기록) 후 원블록 실행.
- 같은 층이면 복귀 없이 바로 실행.
- 경로 없음 → 복귀 생략, 무한루프 없음(시도 상한).

## 다른 하위 프로젝트로의 연결
- #4(큰맵): floor_at는 글로벌 좌표(파노라마) 기준이 되며 그래프/복귀 로직은 그대로.
- 캔버스(#2)에 간선을 점선으로 그리는 시각화는 `build_graph` 결과를 재사용하는 후속 폴리시.
