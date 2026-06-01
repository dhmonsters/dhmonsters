# 캔버스 블록 시각 편집기 설계 (하위 프로젝트 #2)

> "실시간 미니맵 동선 에디터"의 두 번째 하위 프로젝트. #1(미니맵 캔버스 + 투영)이 main에 있고 그 위에 얹는다.
> 맵 그래프·층 복귀(#3), 큰맵 파노라마(#4)는 별도 spec.

**목표:** #1의 미니맵 캔버스 위에서 **클릭으로 블록을 배치하고 드래그로 옮겨** 동선을 시각적으로 그린다. 기존 리스트형 `BlockEditor`는 정밀편집·순서변경용으로 **병행 유지**하며, 둘은 같은 `floor_hunt.route`를 편집(동기화)한다.

**아키텍처:** 히트테스트·블록앵커·배치시드 같은 핵심 로직은 위젯과 분리한 **순수 함수**(`core_ui/route_geom.py`)에 두고, `RouteCanvas`(`MinimapCanvas` 상속)가 마우스 이벤트를 그 함수들 + config에 연결한다. 캔버스가 route를 바꾸면 config 저장 후 콜백으로 리스트를 reload하고, 리스트가 바꾸면 캔버스는 타이머 틱마다 config를 다시 읽어 repaint한다.

**Tech Stack:** PyQt6(상속/마우스이벤트/QPainter), 기존 `core_ui/minimap_canvas.MinimapCanvas`, `core_ui/minimap_geom`, `core/navigation/block.Block`, `core_ui/block_editor.BlockEditor`.

---

## 범위 (Scope)

**포함:**
- `Block`에 캔버스 앵커 좌표 `pos_x`, `pos_y`(미니맵 픽셀) 추가 — 공격·점프 등 위치없던 블록도 점으로 표시
- 캔버스 위 블록 렌더(타입별 색) + 실행 순서를 잇는 점선 경로
- 블록타입 툴바(이동/공격/사다리/점프/텔포) → 빈 곳 클릭 시 그 미니맵 좌표에 블록 추가
- 블록 클릭 선택 + 드래그로 이동(좌표 갱신)
- 캔버스 ↔ 리스트 양방향 동기화(같은 route)

**제외(다른 하위 프로젝트/유지):**
- 블록 **옵션 편집**(왕복수·키·mode 등)은 기존 리스트 `BlockEditor`에서 (캔버스는 배치/이동만)
- **순서 재정렬**은 리스트의 드래그(이미 구현)에서
- 밧줄/텔포가 **층을 잇는 간선**이라는 의미·복귀 → #3
- 큰맵 → #4

---

## 데이터 모델 — `Block` 확장 (`core/navigation/block.py`)
필드 2개 추가(전방호환, 기존 route 그대로 로드됨):
```python
pos_x: int = 0     # 캔버스 앵커 X (미니맵 픽셀)
pos_y: int = 0     # 캔버스 앵커 Y (미니맵 픽셀)
```
검증 불필요(좌표값). `Block.from_dict`가 알 수 없는 키를 무시하므로 구버전 config도 안전.

**타입별 캔버스 앵커/렌더 규칙:**
| 타입 | 앵커(hit/라벨) | 렌더 |
|------|----------------|------|
| move | (pos_x, pos_y) | start_x<end_x면 y=pos_y에 가로선(start_x→end_x), 아니면 점 |
| ladder | (ladder_x, y_bot) | x=ladder_x 세로선 (y_top↔y_bot) |
| attack/jump | (pos_x, pos_y) | 점 + 작은 아이콘 |
| (move,teleport) | (pos_x, pos_y) | 점/선 (move의 move_type=teleport는 색만 다름) |

---

## 컴포넌트

### 1. 순수 함수 — `core_ui/route_geom.py` (생성)
헤더: `# 캔버스 블록 편집의 좌표/히트테스트/배치 순수 로직 (위젯 의존 없음)`
```python
def block_anchor(block: dict) -> tuple[int, int]:
    """블록의 캔버스 앵커(미니맵 픽셀). ladder는 (ladder_x,y_bot), 그 외는 (pos_x,pos_y)."""

def hit_test(blocks: list[dict], mx: int, my: int, radius: int = 10) -> int | None:
    """(mx,my) 미니맵 좌표에서 radius 내 가장 가까운 블록 인덱스. 없으면 None."""

def seed_block_at(block_type: str, mx: int, my: int) -> dict:
    """클릭 좌표에 놓을 새 블록 dict. 타입별 기본값 + pos_x/pos_y=(mx,my)와
    타입필드 시드(move: start_x=end_x=mx; ladder: ladder_x=mx, y_bot=my)."""
```
- `seed_block_at`는 기존 `block_editor._DEFAULTS`를 재사용(중복 정의 금지)하고 좌표만 주입.

### 2. `RouteCanvas(MinimapCanvas)` — `core_ui/route_canvas.py` (생성)
헤더: `# 미니맵 캔버스 위에 동선 블록을 클릭 배치·드래그 이동하는 편집 캔버스`
- 생성자: `RouteCanvas(config, screen_capture, route_keys=("floor_hunt","route"), on_route_changed=None, **kw)` — 나머지(`screen_capture/char_finder/screen_w/clock`)는 `MinimapCanvas`로 위임.
- 상태: `_active_type: str|None`(툴바 선택), `_dragging: int|None`(드래그 중 블록 idx).
- `set_active_type(t)`: 다음 빈클릭에 놓을 블록 타입 설정(None이면 선택/드래그만).
- `paintEvent`: `super().paintEvent`(배경+노란점+범위) 후, config의 route를 읽어 각 블록을 `block_anchor`로 `minimap_to_canvas` 변환해 타입색으로 그리고, 실행순서대로 앵커를 잇는 점선 경로를 그린다. 선택/드래그 중 블록은 강조.
- 마우스:
  - `mousePressEvent`: 클릭점을 `canvas_to_minimap`로 미니맵좌표 환산 → `hit_test`로 블록 맞으면 `_dragging=idx`(선택), 아니면 `_active_type`이 있으면 `seed_block_at`로 추가 후 저장.
  - `mouseMoveEvent`(버튼 눌림): `_dragging` 블록을 이동. 앵커 delta(dx,dy)만큼 `pos_x/pos_y` 갱신하고, 타입필드도 함께 평행이동 — ladder면 `ladder_x+=dx`(+y_bot/y_top 함께 dy), move 구간이면 `start_x+=dx`와 `end_x+=dx`(구간 전체가 같이 이동). → repaint.
  - `mouseReleaseEvent`: 드래그 끝 → 저장 + `on_route_changed()` 호출, `_dragging=None`.
- 저장: route(dict 리스트)를 config에 set+save. `Block.from_dict` 검증 통과분만 저장(`block_editor`와 동일 정책).

### 3. 색상 — `block_editor`와 공유
블록 타입색은 `block_editor`에 이미 쓰는 색을 단일 출처로 묶어 `route_geom` 또는 `block_editor`에 `BLOCK_COLORS = {"move":"#3a8f5a","attack":"#c0556a","ladder":"#b07a30","jump":"#5aa0c0","teleport":"#7a5ad2"}` 상수로 두고 양쪽이 참조(중복 정의 금지).

### 4. 통합 — 동선·이동 페이지
- 현재 page2의 `MinimapCanvas` 대신 `RouteCanvas`를 쓰고, 위에 블록타입 툴바(이동/공격/사다리/점프/텔포 토글 버튼) 한 줄을 둔다.
- `BlockEditor`에 공개 메서드 `reload()`(config의 route를 다시 읽어 `self._route` 갱신 후 `_render`)를 추가하고, `on_route_changed = block_editor.reload`로 연결해 캔버스 변경이 리스트에 즉시 반영. 리스트→캔버스는 캔버스 타이머가 config 재로딩으로 자동 반영.

---

## 데이터 흐름
```
[캔버스] 빈클릭+타입 → canvas_to_minimap → seed_block_at → route append → config save → on_route_changed → 리스트 reload
[캔버스] 블록드래그 → hit_test → pos 갱신 → config save → on_route_changed
[리스트] 옵션/순서 변경 → config save → (캔버스 타이머 틱) config 재로딩 → repaint
```

## 에러 처리
- 미니맵 영역 미설정: #1 그대로 "미니맵 영역 먼저 지정" 안내 — 클릭 배치 무시(좌표 환산 불가).
- 빈 곳 클릭인데 `_active_type=None`: 아무 동작 안 함(선택 해제).
- 드래그가 캔버스 밖으로: 좌표를 미니맵 범위(0..W,0..H)로 클램프.
- 잘못된 블록(검증 실패): 저장에서 제외(기존 정책 재사용).

## 테스트
순수 함수 위주(`tests/test_route_geom.py`):
- `block_anchor`: move/attack는 (pos_x,pos_y), ladder는 (ladder_x,y_bot).
- `hit_test`: 반경 내 가장 가까운 블록 선택, 밖이면 None, 여러개면 최근접.
- `seed_block_at`: 타입별 좌표 시드(move start_x=end_x=mx, ladder ladder_x=mx/y_bot=my, attack pos만).
- `minimap_geom.canvas_to_minimap`(추가): `minimap_to_canvas`의 역변환 왕복 일치.

위젯 스모크(`tests/test_route_canvas.py`, offscreen, 가짜 config/capture):
- 빈클릭+active_type="move" → route에 블록 1개 추가, pos 정확.
- 블록 위 클릭 → `_dragging` 설정.
- `paintEvent`(grab) 예외 없이.
- 리스트 동기화 콜백 호출 확인(가짜 콜백).

## 다른 하위 프로젝트로의 연결
- #3은 route의 ladder/teleport 블록을 **간선**으로 읽어 그래프를 만든다(이 spec은 그리기/배치만, 의미부여 없음).
- #4는 캔버스 배경(_shot)을 파노라마로 교체 — `RouteCanvas`는 미니맵 픽셀 좌표만 쓰므로 인터페이스 불변.
