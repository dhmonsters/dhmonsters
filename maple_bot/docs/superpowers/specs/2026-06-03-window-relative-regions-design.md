# 게임창 상대좌표로 영역 추적 설계

**작성일:** 2026-06-03
**상태:** 승인됨(설계) → 구현 계획 단계

## 배경 / 문제

통합 앱에서 영역(미니맵·사냥영역·맵이탈)이 **절대 화면좌표**로 저장·사용된다.
"좌표 기준"(`coord_mode`) 설정이 UI엔 있으나(`pages.py:283`, 기본 relative) `core/runtime.py`·
`config_adapter.py`·`minimap_canvas.py` 어디에서도 읽지 않는다. 게임창이 움직이면
(창모드 최소화/복원, 게임/프로그램 재실행 시 위치 변동) 고정 절대영역이 화면의 엉뚱한
곳을 캡처해, 크기는 그대로지만 "크기가 바뀐 것처럼" 보인다. 공격범위 표시도 캐릭터
검출이 불안정해져 같이 튄다.

옛 코드엔 창상대 해석(`get_game_window_rect`, `resolve_region_coords`,
`get_minimap_region`)이 있으나 통합 경로엔 연결돼 있지 않다.

## 목표

영역을 게임창 클라이언트 좌상단 기준 **상대 픽셀**로 저장하고, 캡처 시점마다 현재 창
원점을 더해 해석한다. 창을 옮겨도 영역이 따라간다(크기는 고정).

## 핵심 결정 (승인됨)

- 좌표 모델: **창 상대 픽셀**(오프셋+고정 w/h). 창 못 찾으면 절대로 폴백.
- 적용 범위: **전 영역 일괄**(미니맵·사냥영역·맵이탈).
- 마이그레이션: 기존 절대값은 상대 해석으로 1회 어긋남 → **업데이트 후 영역 1회 재지정**(사용자 동의함).
- 템플릿 캡처(닉네임/몬스터)·공격박스 오프셋은 위치 독립이라 변경 없음.

## 설계

### 1. 핵심 헬퍼 (config_manager.py) — 명시 인자형

ConfigManager/RuntimeConfig 양쪽에서 쓰도록 config 객체가 아니라 **명시 인자**를 받는다.

```python
def cached_window_origin(window_title: str, ttl: float = 0.2,
                         _now=time.monotonic) -> tuple[int, int, int, int]:
    """게임창 클라이언트 (ox,oy,cw,ch). win32 조회를 ttl초 캐시(매 캡처 폭주 방지).
    창 못 찾으면 (0,0,0,0). win32 미가용/예외도 (0,0,0,0)."""

def resolve_window_region(coord_mode: str, window_title: str,
                          left: int, top: int, w: int, h: int) -> tuple[int, int, int, int]:
    """창 상대 픽셀(left,top)+w,h → 절대 화면 (x,y,w,h).
    coord_mode != 'relative'거나 창 못 찾으면 (left,top,w,h) 그대로(절대 폴백)."""
```

- `resolve_window_region` 로직: coord_mode != "relative" → 그대로. relative면
  `ox,oy,cw,ch = cached_window_origin(window_title)`; cw>0 → `(ox+left, oy+top, w, h)`; cw==0 → 그대로.
- 캐시: 모듈 레벨 `(title, ts, rect)` 1-슬롯 캐시. ttl 내 같은 title이면 win32 재조회 안 함.
- win32 조회는 기존 `get_game_window_rect`의 FindWindow/ClientToScreen/GetClientRect 로직 재사용
  (단, 여기선 coord_mode 게이팅 없이 title만으로 조회 — 게이팅은 `resolve_window_region`이 담당).

### 2. 저장 측 (pages.py 영역 픽커 3개)

`_make_region_picker`의 `apply(x,y,w,h)`에서 저장 직전, relative+창 찾음이면 원점 차감:

```python
ox, oy, cw, ch = get_game_window_rect(config)
if (config.get("coord_mode") or "relative") == "relative" and cw > 0:
    x, y = x - ox, y - oy          # 클라이언트 상대 픽셀로 저장
# w, h 그대로
```

- 대상: 미니맵(`minimap.region_x/y/width/height`), 사냥영역(`attack.hunt_area.x/y/w/h`),
  맵이탈(`map_exit.region_x/y/width/height`).
- `_make_template_capture`(닉네임/몬스터 png)·`_make_attack_box_picker`(닉네임 기준 오프셋)는 변경 없음.

### 3. 캡처 측 (현재 창 원점으로 해석)

- `MinimapCanvas`(ConfigManager 보유): `_region()`에서 `coord_mode = self._cfg.get("coord_mode")`,
  `title = self._cfg.get("settings2","game_window_title")`를 읽어 `resolve_window_region(...)`로 해석한 값 반환.
- `runtime`: `RuntimeConfig`에 `coord_mode: str = "absolute"`, `game_window_title: str = ""` 추가.
  영역 dict(minimap_region/hunt_area_region/map_exit)는 **상대값 그대로** 보관(어댑터에서 원점 안 더함).
  `_monster_in_range`·맵이탈 캡처에서 캡처 직전 `resolve_window_region(self._cfg.coord_mode,
  self._cfg.game_window_title, left, top, w, h)`로 해석해 mss에 넘김.
- `config_adapter.py`: `coord_mode`(d.coord_mode), `game_window_title`(settings2.game_window_title) 매핑 추가.
  영역은 상대값 그대로 전달.

### 4. 공격범위 표시(_draw_ranges) — 변경 없음

캐릭터(cx,cy) 중심·고정 오프셋·줌 비례로 그리는 현 동작 유지. 좌표 안정화로 캐릭 검출이
안정되면 박스 흔들림도 자연 해소. (줌 비례 크기 변화는 의도된 동작.)

## 테스트

- `test_resolve_window_region`: absolute 모드→그대로 / relative+창있음→원점 더함 / relative+창없음→폴백.
- `cached_game_window_rect`: ttl 내 1회만 조회(호출 카운트 fake)·만료 후 재조회.
- 픽커 저장: relative+창있음이면 (x-ox, y-oy) 저장, absolute면 그대로(헬퍼 단위 테스트로 검증).
- 회귀: 기존 전체 통과 유지.

## 비범위(YAGNI)

- 비율(ratio) 기반 좌표, 창 크기 변화 추적, 공격범위 고정크기 표시 옵션, 자동 재정렬 버튼.

## 트레이드오프

매 캡처 win32 창조회는 200ms 캐시로 완화. 창을 못 찾으면 절대 폴백이라 기존 동작과
동일(안전). 마이그레이션은 1회 재지정으로 처리(사용자 동의).
