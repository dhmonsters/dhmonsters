# 실시간 미니맵 캔버스 + 캐릭터 투영 설계 (하위 프로젝트 #1)

> 큰 기능("실시간 미니맵 동선 에디터")을 4개 하위 프로젝트로 분해한 것 중 **첫 번째**.
> 이 문서는 **보기 전용 캔버스(HUD)** 만 다룬다. 블록 편집(#2)·맵 그래프/복귀(#3)·큰맵 파노라마(#4)는 별도 spec.

**목표:** 인게임 미니맵을 실시간으로 캔버스에 배경으로 깔고, 캐릭터(노란 점)와 공격/사냥 범위를 그 위에 실시간 투영해 보여준다. 줌으로 크기 조절이 되며 범위는 줌에 비례한다.

**아키텍처:** PyQt6 `QWidget` 한 개(`MinimapCanvas`)가 `QTimer`로 미니맵 영역을 주기 캡처하고, 기존 `char_scanner.find_char_in_hsv`로 캐릭터 위치를 얻어 `paintEvent`에서 배경·점·범위를 그린다. 모든 좌표는 **미니맵 픽셀**을 기준으로 하고 화면에 그릴 때 줌 배율을 곱한다.

**기술 스택:** PyQt6(QWidget/QTimer/QPainter/QImage), 기존 `core/sensing/char_scanner.py`, `mss`(캡처는 주입된 `screen_capture` 콜백 사용), numpy.

---

## 범위 (Scope)

**포함(이 spec):**
- 미니맵 영역 실시간 캡처 → 흐린 배경 렌더
- 캐릭터 노란 점 실시간 투영(미니맵 픽셀 → 캔버스 픽셀)
- 공격 범위·사냥 범위 박스 오버레이(노란 점 기준, 줌 비례)
- 줌 인/아웃 + "맞춤"(캔버스에 꽉 차게)
- 마커 미검출/영역 미설정 등 예외 표시

**제외(다른 하위 프로젝트):**
- 캔버스 위 블록 배치·편집 → #2
- 맵 그래프·층 이탈 복귀 → #3
- 큰맵 파노라마 스캔·라이브 매칭 → #4 (이 spec은 **한 미니맵 영역이 전부 보이는 맵** 기준)
- 봇 실행 동작 변경 없음(이 위젯은 설정/모니터링 화면용)

---

## 컴포넌트

### 1. `MinimapCanvas(QWidget)` — `core_ui/minimap_canvas.py`
한 줄 역할(파일 헤더): `# 미니맵을 실시간 캡처해 배경으로 깔고 캐릭터·공격/사냥 범위를 투영하는 캔버스 위젯`

생성자:
```python
MinimapCanvas(config, screen_capture, char_finder=find_char_in_hsv, interval_ms=80)
```
- `config`: ConfigManager (미니맵 영역·범위 키 읽기)
- `screen_capture`: `callable(region_dict) -> BGR ndarray` (기존 ScreenReader.capture 재사용)
- `char_finder`: 테스트 주입 가능한 캐릭터 검출 함수(기본 `find_char_in_hsv`)
- 내부 상태: `_zoom: float = 1.0`, `_last_char: tuple[int,int] | None`, `_shot: QImage | None`

타이머 루프(`_tick`):
1. config에서 미니맵 영역 읽기 → 미설정(`width<=0`)이면 "미니맵 영역 미설정" 안내만 그리고 종료
2. `screen_capture(region)` → BGR ndarray (`_shot_bgr`)
3. `char_finder(_shot_bgr, hsv_lower, hsv_upper, min_area, max_area)` → `(cx,cy)` 미니맵 픽셀 / `None`
   - `None`이면 `_last_char` 유지(직전 위치), 점을 흐리게(미검출 표시)
   - 검출되면 `_last_char = (cx,cy)`
4. BGR → `QImage`(RGB) 변환해 `_shot` 갱신, `update()` 호출(→ paintEvent)

`paintEvent`:
1. 배경: `_shot`을 캔버스에 `_zoom` 배율로 그림. **은은하게 = QPainter opacity ~0.30** (가우시안 블러 아님, 단순 투명도로 처리)
2. 캐릭터 점: `_last_char`가 있으면 `(cx*_zoom + panX, cy*_zoom + panY)`에 노란 원(반경 7px 고정, 줌 무관). 미검출 상태면 알파 낮춤
3. 범위 박스(아래 #3): 점 중심으로 공격(빨강 점선)·사냥(파랑 점선) 사각형
4. 빈 상태/미검출 안내 텍스트

줌 조작: `wheelEvent`(Ctrl+휠 또는 휠)로 `_zoom` 0.5~4.0 클램프, "맞춤" 버튼은 `_zoom = min(width/W_mm, height/H_mm)`.

### 2. 좌표 투영 — 순수 함수(테스트 대상)
한 파일에 순수 함수로 분리해 위젯 없이 테스트 가능하게 한다 — `core_ui/minimap_geom.py`:
```python
def minimap_to_canvas(cx, cy, zoom, pan=(0,0)) -> tuple[int,int]:
    return (round(cx*zoom + pan[0]), round(cy*zoom + pan[1]))
```

### 3. 범위 환산 — 순수 함수(`minimap_geom.py`)
화면 픽셀 오프셋(공격박스/사냥범위)을 **미니맵 픽셀**로 환산한다. 미니맵 폭은 카메라 가시 폭의 `camera_w_ratio` 배라는 정의를 사용한다.
```python
def screen_px_to_minimap_px(screen_px, minimap_w, screen_w, camera_w_ratio) -> float:
    # 카메라 가시 폭(미니맵 px) = camera_w_ratio * minimap_w
    # 화면 폭(screen_w px)이 그 폭에 대응 → 비례
    if screen_w <= 0:
        return 0.0
    return screen_px * (camera_w_ratio * minimap_w) / screen_w
```
- 공격 박스 반폭 = `atk_x_max`(화면 px) → 미니맵 px → `*zoom` 으로 캔버스 px. 상하는 `atk_y_max`.
- 사냥 범위 반폭 = `monster_range_px`, 높이 = `monster_range_h` 동일 환산.
- `screen_w`는 캡처한 주모니터 폭(런타임에 mss `monitors[1]["width"]`), 테스트엔 인자 주입.
- 환산 결과가 작으면(예: 1px 미만) 최소 표시 크기로 클램프.

### 4. 통합 — 어디에 붙나
- 신규 좌측 내비 항목은 추가하지 않고, **"동선·이동" 페이지 상단에 `MinimapCanvas`를 extras로 추가**(블록 에디터 #2가 이 캔버스 위로 진화할 자리). 현재 BlockEditor는 그 아래 유지.
- 위젯은 설정 화면에서만 도는 가벼운 미리보기. 봇 메인 루프(runtime)와 무관하며 독립 `QTimer`로 캡처한다.

---

## 사용하는 config 키 (실제)
| 용도 | 키 | 비고 |
|------|----|----|
| 미니맵 영역 | `minimap.region_x/region_y/width/height` | 캡처 region |
| 캐릭터 색 | HSV 기본 `(20,100,200)~(40,255,255)` | char_scanner 기본값 |
| 공격 범위 | `attack.atk_x_max`, `attack.atk_y_max` | 화면 px 오프셋(반폭/반높이) |
| 사냥 범위 | `attack.monster_range_px`, `attack.monster_range_h` | 화면 px |
| 화면↔미니맵 비율 | `attack.camera_w_ratio` | 기본 0.5 |

---

## 데이터 흐름
```
QTimer(_tick)
  → config 미니맵 영역 읽기
  → screen_capture(region) → BGR
  → char_finder(BGR) → (cx,cy) 미니맵px | None
  → QImage 변환 + _last_char 갱신
  → update()
paintEvent
  → 배경(_shot × zoom, opacity 0.30)
  → minimap_to_canvas(cx,cy,zoom) → 노란 점
  → screen_px_to_minimap_px(범위) × zoom → 공격/사냥 박스
```

## 에러 처리
- **미니맵 영역 미설정**(`width<=0`): 캡처 시도 없이 "연결·인식에서 미니맵 영역을 먼저 지정하세요" 안내.
- **마커 미검출(추적 상태 머신)**: 마지막 검출 이후 경과시간으로 `tracking`(정상, 실선 점) → `lost`(1~3초, 점이 0.8초 주기로 천천히 깜빡임, 직전 위치 유지) → `stale`(3초+, 점 숨김 + "캐릭터 미검출" 배지)를 구분해 '상황 인지'를 준다. 임계 판정은 순수 함수 `char_track_state(elapsed)`로 분리해 테스트한다.
- **캡처 예외**: try/except로 그 틱 스킵(다음 틱 재시도), 위젯은 죽지 않음.
- **screen_w 미상**: 환산 불가 시 범위 박스는 설정된 미니맵px 기본값으로 폴백(혹은 숨김).

## 테스트
순수 함수 중심으로 위젯 없이 검증(`tests/test_minimap_geom.py`):
- `minimap_to_canvas`: 줌 1.0/2.0, pan 적용 시 좌표 정확.
- `screen_px_to_minimap_px`: camera_w_ratio·minimap_w·screen_w 조합 환산값, screen_w=0 방어, 비례성(2배 입력→2배 출력).
- 위젯 스모크(`tests/test_minimap_canvas.py`, offscreen): 영역 미설정/설정 두 경우 생성·`_tick` 1회·`paintEvent`가 예외 없이 도는지. `screen_capture`·`char_finder`는 가짜 주입(고정 이미지/좌표).

## 다른 하위 프로젝트로의 연결(이 spec 밖)
- #2(블록 편집기)는 이 캔버스의 `minimap_to_canvas` 역변환(`canvas_to_minimap`)으로 클릭→미니맵좌표 블록 배치.
- #4(큰맵)는 `_shot`을 단일 캡처 대신 파노라마+라이브 매칭 결과로 교체(캔버스 인터페이스는 동일 유지).
