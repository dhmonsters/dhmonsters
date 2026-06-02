# 캔버스 블록 시각 편집기 설계 (하위 프로젝트 #2)

> "실시간 미니맵 동선 에디터"의 두 번째 하위 프로젝트. #1(미니맵 캔버스 + 투영)이 main에 있고 그 위에 얹는다.
> 맵 그래프·층 복귀(#3), 큰맵 파노라마(#4)는 별도 spec.

**목표:** #1의 미니맵 캔버스 위에서 **클릭으로 블록을 배치하고 드래그로 옮겨** 동선을 시각적으로 그린다. 기존 리스트형 `BlockEditor`는 정밀편집·순서변경용으로 **병행 유지**하며, 둘은 같은 `floor_hunt.route`를 편집(동기화)한다.

**아키텍처:** 새 파일을 만들지 않는다. 좌표·공간 연산이라는 하나의 책임을 가진 **기존 `core_ui/minimap_geom.py`** 에 순수 함수(`block_anchor/hit_test/seed_block_at/translate_block`)를 추가하고, **기존 `core_ui/minimap_canvas.py`** 에 `RouteCanvas(MinimapCanvas)` 클래스를 추가한다(같은 파일 상속 → 순환참조 없음). 동기화는 타이머 폴링이 아니라 **콜백 이벤트**다 — 캔버스 변경→config 저장→`on_route_changed()`→`BlockEditor.reload()`, 리스트 변경→config 저장→주입된 콜백→`RouteCanvas` repaint. (도면 5-4: 모든 변경은 이벤트로 전파, 폴링 금지.)

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
pos_x: int = -1    # 캔버스 앵커 X (미니맵 픽셀). -1 = 미배치(렌더 안 함)
pos_y: int = -1    # 캔버스 앵커 Y (미니맵 픽셀). -1 = 미배치
```
검증 불필요(좌표값). 기본값 **-1 = 미배치** — 리스트에서만 추가한 블록이 (0,0)에 모여 보이는 혼란을 막는다. 캔버스에 **처음 배치할 때만** 좌표가 설정되고, `pos_x<0` 또는 `pos_y<0`이면 캔버스에서 그리지 않는다(단 ladder는 자체 좌표 `ladder_x/y_bot`가 있으면 그것으로 그림). `Block.from_dict`가 알 수 없는 키를 무시하므로 구버전 config도 안전.

**타입별 캔버스 앵커/렌더 규칙:**
| 타입 | 앵커(hit/라벨) | 렌더 |
|------|----------------|------|
| move | (pos_x, pos_y) | start_x<end_x면 y=pos_y에 가로선(start_x→end_x), 아니면 점 |
| ladder | (ladder_x, y_bot) | x=ladder_x 세로선 (y_top↔y_bot) |
| attack/jump | (pos_x, pos_y) | 점 + 작은 아이콘 |
| (move,teleport) | (pos_x, pos_y) | 점/선 (move의 move_type=teleport는 색만 다름) |

---

## 컴포넌트

### 1. 순수 함수 — **기존 `core_ui/minimap_geom.py`에 추가** (새 파일 X)
`minimap_geom`은 "좌표 변환·공간 연산"이라는 단일 책임이라 route 관련 순수 로직도 여기 둔다.
```python
def block_anchor(block: dict) -> tuple[int, int] | None:
    """블록의 캔버스 앵커(미니맵 픽셀). ladder는 (ladder_x,y_bot),
    그 외는 (pos_x,pos_y). 미배치(pos<0이고 ladder좌표도 없음)면 None."""

def hit_test(blocks: list[dict], mx: int, my: int, radius: int = 10) -> int | None:
    """(mx,my) 미니맵 좌표에서 radius 내 가장 가까운 블록 인덱스. 미배치(anchor None)는 제외, 없으면 None."""

def seed_block_at(block_type: str, mx: int, my: int) -> dict:
    """클릭 좌표에 놓을 새 블록 dict. 타입별 기본값 + pos_x/pos_y=(mx,my)와
    타입필드 시드(move: start_x=end_x=mx; ladder: ladder_x=mx, y_bot=my)."""

def translate_block(block: dict, dx: int, dy: int) -> dict:
    """블록을 미니맵 픽셀(dx,dy)만큼 평행이동한 새 dict 반환. 캔버스는 블록 내부
    구조를 몰라도 되도록 이 함수만 호출한다(타입 추가돼도 캔버스 코드 불변).
    pos_x/y는 항상 이동. move면 start_x/end_x, ladder면 ladder_x/y_top/y_bot도 함께."""
```
- `seed_block_at`는 기존 `block_editor._DEFAULTS`를 재사용(중복 정의 금지)하고 좌표만 주입.

### 2. `RouteCanvas(MinimapCanvas)` — **기존 `core_ui/minimap_canvas.py`에 추가** (새 파일 X)
같은 파일에서 `MinimapCanvas`를 상속해 순환참조를 피한다.
- 생성자: `RouteCanvas(config, screen_capture, route_keys=("floor_hunt","route"), on_route_changed=None, **kw)` — 나머지(`screen_capture/char_finder/screen_w/clock`)는 `MinimapCanvas`로 위임.
- 상태: `_active_type: str|None`(툴바 선택, 기본 None), `_dragging: int|None`(드래그 중 블록 idx), `_drag_last: tuple|None`(직전 미니맵좌표).
- `set_active_type(t)`: 다음 빈클릭에 놓을 블록 타입 설정(None이면 선택/드래그만).
- **미니맵 크기**(클램프용): `_tick` 폴링 결과 `_mm_size`에 의존하지 않고, `MinimapCanvas`에 추가할 `minimap_size()` getter(=`_region()`의 width/height 반환)를 써서 타이머가 안 돌았어도 즉시 안다.
- `paintEvent`: `super().paintEvent`(배경+노란점+범위) 후, config의 route를 읽어 각 블록을 `block_anchor`(None이면 건너뜀)로 `minimap_to_canvas` 변환해 타입색으로 그리고, 실행순서대로 배치된 앵커를 잇는 점선 경로를 그린다. 선택/드래그 중 블록은 강조.
- 마우스:
  - `mousePressEvent`: 클릭점을 `canvas_to_minimap`로 미니맵좌표 환산(+`minimap_size()`로 0..W,0..H 클램프) → `hit_test`로 블록 맞으면 `_dragging=idx`(선택), 아니면 `_active_type`이 있으면 `seed_block_at`로 추가·저장하고 **`_active_type=None`으로 자동 복귀**(연속 배치 방지).
  - `mouseMoveEvent`(버튼 눌림): `_dragging` 블록을 `translate_block(block, dx, dy)`로 이동(캔버스는 블록 내부필드를 모름). dx,dy는 현재-직전 미니맵좌표 차. → repaint.
  - `mouseReleaseEvent`: 드래그 끝 → 저장 + `on_route_changed()` 호출, `_dragging=None`.
- 저장: route(dict 리스트)를 config에 set+save → `on_route_changed()`. `Block.from_dict` 검증 통과분만 저장(`block_editor`와 동일 정책).

### 3. 색상 — 단일 출처 상수
블록 타입색을 `minimap_geom.BLOCK_COLORS = {"move":"#3a8f5a","attack":"#c0556a","ladder":"#b07a30","jump":"#5aa0c0","teleport":"#7a5ad2"}` 한 곳에 두고 캔버스가 참조(중복 정의 금지).

### 4. 리스트 동기화 — `BlockEditor`에 콜백 추가
- `BlockEditor`에 공개 `reload()`(config route 재로딩 후 `_render`)를 추가하고, **생성자에 `on_change=None` 콜백을 받아** 저장(`_save`)할 때마다 호출하게 한다. 캔버스는 `on_change=route_canvas.update`(repaint)로 연결 → 리스트 변경이 캔버스에 **이벤트로** 전파(타이머 폴링 아님).

### 5. 통합 — 동선·이동 페이지
- page2의 `MinimapCanvas` 자리에 `RouteCanvas`를 쓰고, 그 위에 **블록타입 툴바** 한 줄을 둔다.
- 툴바 = `QButtonGroup`(exclusive) 6버튼: **선택 안 함**(기본 체크) / 이동 / 공격 / 사다리 / 점프 / 텔포. 버튼 클릭 → `route_canvas.set_active_type(타입 or None)`. 캔버스에 블록을 놓으면 캔버스가 `_active_type=None`으로 돌아가므로 툴바도 "선택 안 함"으로 리셋(시그널로 동기화).
- 양방향 결선: `route_canvas`는 `on_route_changed=block_editor.reload`, `block_editor`는 `on_change=route_canvas.update`.

---

## 데이터 흐름 (전부 이벤트, 폴링 없음)
```
[캔버스] 빈클릭+타입 → canvas_to_minimap(+클램프) → seed_block_at → route append
                    → config save → on_route_changed() → BlockEditor.reload() ; _active_type=None(툴바 리셋)
[캔버스] 블록드래그 → hit_test → translate_block(block,dx,dy)
                    → (release 시) config save → on_route_changed()
[리스트] 옵션/순서 변경 → config save → on_change() → RouteCanvas.update()(repaint)
```

## 에러 처리
- 미니맵 영역 미설정: #1 그대로 "미니맵 영역 먼저 지정" 안내 — 클릭 배치 무시(좌표 환산 불가).
- 빈 곳 클릭인데 `_active_type=None`: 아무 동작 안 함(선택 해제).
- 드래그가 캔버스 밖으로: 좌표를 미니맵 범위(0..W,0..H)로 클램프.
- 잘못된 블록(검증 실패): 저장에서 제외(기존 정책 재사용).

## 테스트
순수 함수 — 기존 `tests/test_minimap_geom.py`에 추가:
- `canvas_to_minimap`: `minimap_to_canvas`의 역변환, 왕복 일치(zoom/pan 포함).
- `block_anchor`: move/attack는 (pos_x,pos_y), ladder는 (ladder_x,y_bot), 미배치(pos=-1, ladder좌표 없음)는 None.
- `hit_test`: 반경 내 최근접 선택, 밖이면 None, 미배치 블록 제외.
- `seed_block_at`: 타입별 좌표 시드(move start_x=end_x=mx, ladder ladder_x=mx/y_bot=my, attack pos만).
- `translate_block`: pos_x/y 평행이동 + move의 start_x/end_x, ladder의 ladder_x/y_top/y_bot 함께 이동, 원본 불변(새 dict 반환).

위젯 스모크 — 신규 `tests/test_route_canvas.py`(offscreen, 가짜 config/capture):
- 빈클릭+active_type="move" → route에 블록 1개 추가, pos 정확, **active_type이 None으로 리셋**, `on_route_changed` 호출됨.
- 블록 위 클릭 → `_dragging` 설정, 드래그 후 좌표가 `translate_block` 결과와 일치.
- `_active_type=None`에서 빈클릭 → 아무 블록도 안 생김.
- 미배치(-1) 블록은 `paintEvent`에서 그려지지 않고 `hit_test`에 안 잡힘.
- `paintEvent`(grab) 예외 없이.

`Block` 확장 — `tests/test_block.py`에 추가: `pos_x/pos_y` 기본값 -1, `from_dict`로 좌표 보존.

## 다른 하위 프로젝트로의 연결
- #3은 route의 ladder/teleport 블록을 **간선**으로 읽어 그래프를 만든다(이 spec은 그리기/배치만, 의미부여 없음).
- #4는 캔버스 배경(_shot)을 파노라마로 교체 — `RouteCanvas`는 미니맵 픽셀 좌표만 쓰므로 인터페이스 불변.
