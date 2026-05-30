# 투명 도형 추적기 재설계 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 투명 도형 찾기 추적기가 흰→투명 전환을 끝까지 추종하고, 분홍 마우스 커서를 추적 대상으로 오인하지 않게 만든다.

**Architecture:** base OpenCV `cv2.matchTemplate` 기반 경량 상관 추적기(A′). 입력 단계에서 분홍 커서를 HSV 마스킹+inpaint로 제거하고, 예측 위치 주변 로컬 윈도우에서 템플릿을 매칭하며, 템플릿을 느리게 갱신해 외형 변화에 적응한다. 종료는 SUCCESS 화면 감지 / 35초 타임아웃 / F10.

**Tech Stack:** Python 3.14, OpenCV 4.13 (headless, base만), NumPy, mss, win32api, PyQt6. 테스트는 pytest 없이 독립 실행 `assert` 스크립트(`test_yolo_detect.py`와 동일 패턴).

---

## File Structure

| 파일 | 책임 | 변경 |
|---|---|---|
| `transparent_shape_standalone.py` | GUI + 추적 전체 | 수정 (파라미터·검출함수·ShapeTracker) |
| `test_transparent_tracker.py` | 순수 함수 단위 검증 | 신규 생성 (루트) |

수정은 추적 로직에 한정. UI/단축키/ROI 시스템(`HotkeyPoller`, `KeyCaptureButton`, `RoiOverlay`, `MainWindow`, 다크 스타일, config 저장/로드)은 건드리지 않는다.

순수 함수 4개를 새로 분리해 테스트 가능하게 한다.
- `mask_cursor(img)` → 분홍 커서 제거된 BGR 이미지
- `match_template_local(img, tmpl, pred, margin)` → `(cx, cy, score)` 또는 `None`
- `detect_end_screen(img)` → bool (SUCCESS/종료 화면)
- 기존 `find_white(img)` → 초기 템플릿 시드용으로 재사용 (변경 없음)

`find_diff()`는 커서 오인의 직접 원인이므로 **제거**한다.

---

## Task 1: 신규 파라미터 상수 추가

**Files:**
- Modify: `transparent_shape_standalone.py:36-37` (DIFF_* 상수 블록)

- [ ] **Step 1: DIFF 상수를 신규 추적 상수로 교체**

`transparent_shape_standalone.py`의 아래 두 줄을 찾는다:

```python
DIFF_THRESH    = 20
DIFF_MIN_AREA  = 400
```

다음으로 교체한다:

```python
# 로컬 템플릿 추적기
MATCH_THRESH   = 0.45    # NCC 매칭 채택 임계
TMPL_SIZE      = 64      # 초기 템플릿 한 변(px)
SEARCH_MARGIN  = 40      # 예측위치 ± 검색 윈도우 여유(px)
TMPL_UPDATE    = 0.10    # 템플릿 갱신 비율(이전 1-값 유지)
LOST_MAX       = 15      # 연속 미검출 허용 프레임
VEL_ALPHA      = 0.5     # velocity EMA
HARD_TIMEOUT   = 35.0    # 하드 타임아웃(초)

# 분홍 커서 HSV 범위 (OpenCV H 0~179)
CURSOR_HUE     = (140, 175)
CURSOR_SAT_MIN = 80
CURSOR_VAL_MIN = 80

# 종료 화면 감지 (밝은 노란 SUCCESS 글자 비율)
END_YELLOW_HUE = (20, 35)
END_SAT_MIN    = 120
END_VAL_MIN    = 180
END_RATIO_MIN  = 0.02    # 노란 픽셀 비율 임계
```

- [ ] **Step 2: 구문 검증**

Run: `py -c "import ast; ast.parse(open('transparent_shape_standalone.py', encoding='utf-8').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add transparent_shape_standalone.py
git commit -m "feat: 로컬 템플릿 추적기 파라미터 상수 추가"
```

---

## Task 2: `mask_cursor` — 분홍 커서 마스킹

**Files:**
- Modify: `transparent_shape_standalone.py` (감지 함수 블록, `find_white` 위)
- Test: `test_transparent_tracker.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`test_transparent_tracker.py`를 생성한다(파일 첫 줄 한국어 헤더 포함):

```python
# 투명 도형 추적기 순수 함수 단위 테스트 (pytest 불필요, 직접 실행)
import numpy as np
import cv2
import importlib.util, os

spec = importlib.util.spec_from_file_location(
    "tst", os.path.join(os.path.dirname(__file__), "transparent_shape_standalone.py"))
tst = importlib.util.module_from_spec(spec)
# PyQt6 import 부작용 없이 함수만 쓰기 위해 모듈 로드
spec.loader.exec_module(tst)


def test_mask_cursor_removes_pink():
    # 회색 배경에 분홍 커서 블록을 그림
    img = np.full((100, 100, 3), 120, np.uint8)            # BGR 회색
    cv2.circle(img, (50, 50), 12, (200, 0, 200), -1)        # 분홍(자홍) 원
    out = tst.mask_cursor(img)
    # 커서 중심부가 더 이상 고채도 분홍이 아니어야 함
    hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[50, 50]
    assert s < tst.CURSOR_SAT_MIN, f"분홍 채도 남음 s={s}"
    print("test_mask_cursor_removes_pink: PASS")


if __name__ == "__main__":
    test_mask_cursor_removes_pink()
    print("ALL PASS")
```

- [ ] **Step 2: 실패 확인**

Run: `py test_transparent_tracker.py`
Expected: FAIL — `AttributeError: module ... has no attribute 'mask_cursor'`

- [ ] **Step 3: 최소 구현 작성**

`transparent_shape_standalone.py`에서 `def find_white(img):` 바로 **위**에 추가한다:

```python
def mask_cursor(img):
    """분홍 마우스 커서를 HSV로 검출해 주변 픽셀로 inpaint 제거한다."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lo = np.array([CURSOR_HUE[0], CURSOR_SAT_MIN, CURSOR_VAL_MIN], np.uint8)
    hi = np.array([CURSOR_HUE[1], 255, 255], np.uint8)
    mask = cv2.inRange(hsv, lo, hi)
    if cv2.countNonZero(mask) == 0:
        return img
    mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)))
    return cv2.inpaint(img, mask, 3, cv2.INPAINT_TELEA)
```

- [ ] **Step 4: 통과 확인**

Run: `py test_transparent_tracker.py`
Expected: `test_mask_cursor_removes_pink: PASS` / `ALL PASS`

- [ ] **Step 5: Commit**

```bash
git add transparent_shape_standalone.py test_transparent_tracker.py
git commit -m "feat: 분홍 커서 HSV 마스킹 mask_cursor 추가"
```

---

## Task 3: `match_template_local` — 로컬 NCC 매칭

**Files:**
- Modify: `transparent_shape_standalone.py` (`find_white` 아래)
- Test: `test_transparent_tracker.py`

- [ ] **Step 1: 실패하는 테스트 추가**

`test_transparent_tracker.py`에 함수와 main 호출을 추가한다:

```python
def test_match_template_local_finds_patch():
    # 200x200 배경에 64x64 밝은 패치를 (120,80) 중심에 배치
    img = np.full((200, 200, 3), 90, np.uint8)
    patch = np.full((64, 64, 3), 230, np.uint8)
    cx, cy = 120, 80
    img[cy-32:cy+32, cx-32:cx+32] = patch
    # 예측 위치를 약간 어긋나게 줘도 윈도우 안에서 찾아야 함
    res = tst.match_template_local(img, patch, (110, 70), tst.SEARCH_MARGIN)
    assert res is not None, "매칭 실패"
    fx, fy, score = res
    assert abs(fx - cx) <= 3 and abs(fy - cy) <= 3, f"위치 오차 ({fx},{fy})"
    assert score >= tst.MATCH_THRESH, f"점수 낮음 {score}"
    print("test_match_template_local_finds_patch: PASS")


def test_match_template_local_rejects_noise():
    img = np.random.randint(0, 60, (200, 200, 3), np.uint8)  # 어두운 노이즈
    patch = np.full((64, 64, 3), 240, np.uint8)              # 밝은 패치(부재)
    res = tst.match_template_local(img, patch, (100, 100), tst.SEARCH_MARGIN)
    assert res is None or res[2] < tst.MATCH_THRESH, "노이즈 오검출"
    print("test_match_template_local_rejects_noise: PASS")
```

그리고 `if __name__ == "__main__":` 블록을 다음으로 교체한다:

```python
if __name__ == "__main__":
    test_mask_cursor_removes_pink()
    test_match_template_local_finds_patch()
    test_match_template_local_rejects_noise()
    print("ALL PASS")
```

- [ ] **Step 2: 실패 확인**

Run: `py test_transparent_tracker.py`
Expected: FAIL — `has no attribute 'match_template_local'`

- [ ] **Step 3: 최소 구현 작성**

`transparent_shape_standalone.py`에서 `find_white` 정의 **아래**(기존 `find_diff` 자리)에 추가한다:

```python
def match_template_local(img, tmpl, pred, margin):
    """예측 위치 pred 주변 윈도우에서 tmpl을 NCC 매칭. (cx, cy, score) | None."""
    th, tw = tmpl.shape[:2]
    H, W = img.shape[:2]
    px, py = int(pred[0]), int(pred[1])
    # 검색 윈도우 (템플릿 절반 + margin 여유)
    half_w, half_h = tw // 2 + margin, th // 2 + margin
    x0 = max(0, px - half_w); y0 = max(0, py - half_h)
    x1 = min(W, px + half_w); y1 = min(H, py + half_h)
    win = img[y0:y1, x0:x1]
    if win.shape[0] < th or win.shape[1] < tw:
        return None
    res = cv2.matchTemplate(win, tmpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    cx = x0 + max_loc[0] + tw // 2
    cy = y0 + max_loc[1] + th // 2
    return (cx, cy, float(max_val))
```

- [ ] **Step 4: 통과 확인**

Run: `py test_transparent_tracker.py`
Expected: 세 테스트 모두 PASS / `ALL PASS`

- [ ] **Step 5: Commit**

```bash
git add transparent_shape_standalone.py test_transparent_tracker.py
git commit -m "feat: 로컬 윈도우 NCC 매칭 match_template_local 추가"
```

---

## Task 4: `detect_end_screen` — SUCCESS/종료 감지

**Files:**
- Modify: `transparent_shape_standalone.py` (`match_template_local` 아래)
- Test: `test_transparent_tracker.py`

- [ ] **Step 1: 실패하는 테스트 추가**

`test_transparent_tracker.py`에 추가한다:

```python
def test_detect_end_screen_true_on_yellow():
    img = np.full((200, 300, 3), 80, np.uint8)
    # 밝은 노란 SUCCESS 글자 영역 (BGR에서 노랑 = (0,230,230))
    cv2.rectangle(img, (40, 80), (260, 130), (0, 230, 230), -1)
    assert tst.detect_end_screen(img) is True
    print("test_detect_end_screen_true_on_yellow: PASS")


def test_detect_end_screen_false_on_board():
    img = np.random.randint(60, 110, (200, 300, 3), np.uint8)  # 갈색 보드 근사
    assert tst.detect_end_screen(img) is False
    print("test_detect_end_screen_false_on_board: PASS")
```

`__main__` 블록에 두 호출을 `print("ALL PASS")` 위에 추가한다:

```python
    test_detect_end_screen_true_on_yellow()
    test_detect_end_screen_false_on_board()
```

- [ ] **Step 2: 실패 확인**

Run: `py test_transparent_tracker.py`
Expected: FAIL — `has no attribute 'detect_end_screen'`

- [ ] **Step 3: 최소 구현 작성**

`match_template_local` 아래에 추가한다:

```python
def detect_end_screen(img):
    """SUCCESS/종료 화면의 밝은 노란 글자 비율로 게임 종료를 감지한다."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lo = np.array([END_YELLOW_HUE[0], END_SAT_MIN, END_VAL_MIN], np.uint8)
    hi = np.array([END_YELLOW_HUE[1], 255, 255], np.uint8)
    mask = cv2.inRange(hsv, lo, hi)
    ratio = cv2.countNonZero(mask) / float(mask.size)
    return ratio >= END_RATIO_MIN
```

- [ ] **Step 4: 통과 확인**

Run: `py test_transparent_tracker.py`
Expected: 모든 테스트 PASS / `ALL PASS`

- [ ] **Step 5: Commit**

```bash
git add transparent_shape_standalone.py test_transparent_tracker.py
git commit -m "feat: SUCCESS 종료 화면 감지 detect_end_screen 추가"
```

---

## Task 5: `ShapeTracker` 상태 + 추적 루프 재작성

**Files:**
- Modify: `transparent_shape_standalone.py:363-430` (ShapeTracker 클래스 전체)

이 태스크는 GUI/스레드/캡처가 얽혀 단위 테스트가 어렵다. 순수 함수(Task 2~4)는 이미 검증됐으므로, 여기서는 **구문 검증 + import 검증**으로 확인하고 실게임은 수동 검증한다.

- [ ] **Step 1: `find_diff` 제거 확인**

Task 3에서 `find_diff`를 `match_template_local`로 교체했다면 이미 제거됨. 남아 있으면 `def find_diff(...)` 함수 전체를 삭제한다. (Grep으로 `find_diff` 잔존 참조가 없는지 확인.)

- [ ] **Step 2: ShapeTracker `__init__` 상태 추가**

기존 `__init__`(363~370행 근처)을 다음으로 교체한다:

```python
class ShapeTracker:
    def __init__(self, roi, emitter: _Emitter):
        self.roi = roi
        self._emitter = emitter
        self._ema_x = None
        self._ema_y = None
        self._stop  = threading.Event()
        # 추적 상태
        self._tmpl   = None          # 현재 템플릿 (BGR)
        self._pos    = None          # 마지막 도형 위치 (board 상대 px)
        self._vel    = (0.0, 0.0)    # 속도(px/frame)
        self._lost   = 0
```

- [ ] **Step 3: `run()` 전체 재작성**

기존 `run()` 메서드 전체를 다음으로 교체한다:

```python
    def _init_template(self, board):
        """가운데 흰 도형을 찾아 첫 템플릿으로 시드한다. 실패 시 None."""
        rel = find_white(board)
        H, W = board.shape[:2]
        if rel is None:
            return None
        half = TMPL_SIZE // 2
        cx, cy = rel
        x0 = max(0, cx - half); y0 = max(0, cy - half)
        x1 = min(W, cx + half); y1 = min(H, cy + half)
        patch = board[y0:y1, x0:x1].copy()
        if patch.shape[0] < 8 or patch.shape[1] < 8:
            return None
        self._tmpl = patch
        self._pos  = (cx, cy)
        return rel

    def run(self):
        x, y, w, h = self.roi["x"], self.roi["y"], self.roi["w"], self.roi["h"]
        region = {"left": x, "top": y, "width": w, "height": h}
        self._ema_x = x + w / 2.0
        self._ema_y = y + h / 2.0
        self._emitter.log.emit(f"[추적 시작] {w}×{h} @ ({x},{y})")

        start_t = time.time()
        with mss.MSS() as sct:
            # ── 초기화: 가운데 흰 도형으로 템플릿 시드 ──
            init_deadline = start_t + 3.0
            while not self._stop.is_set():
                raw = sct.grab(region)
                board = cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)
                board = mask_cursor(board)
                if self._init_template(board) is not None:
                    self._emitter.log.emit("[초기화] 흰 도형 템플릿 확보")
                    break
                if time.time() > init_deadline:
                    self._pos = (w // 2, h // 2)
                    self._emitter.log.emit("[초기화] 흰 도형 미발견 → 중심에서 시작")
                    break
                time.sleep(FRAME_INTERVAL)

            # ── 추적 루프 ──
            while not self._stop.is_set():
                t0 = time.time()

                if t0 - start_t >= HARD_TIMEOUT:
                    self._emitter.log.emit("[종료] 타임아웃")
                    break

                raw = sct.grab(region)
                board = cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)
                board = mask_cursor(board)

                if detect_end_screen(board):
                    self._emitter.log.emit("[종료] SUCCESS 화면 감지")
                    break

                pred = (self._pos[0] + self._vel[0], self._pos[1] + self._vel[1])
                res = None
                if self._tmpl is not None:
                    res = match_template_local(board, self._tmpl, pred, SEARCH_MARGIN)

                if res is not None and res[2] >= MATCH_THRESH:
                    nx, ny, score = res
                    self._vel = (
                        VEL_ALPHA * (nx - self._pos[0]) + (1 - VEL_ALPHA) * self._vel[0],
                        VEL_ALPHA * (ny - self._pos[1]) + (1 - VEL_ALPHA) * self._vel[1],
                    )
                    self._pos = (nx, ny)
                    self._lost = 0
                    self._update_template(board, nx, ny)
                else:
                    # 미검출: 예측 위치로 직진 추종
                    self._lost += 1
                    self._pos = (
                        max(0, min(w - 1, pred[0])),
                        max(0, min(h - 1, pred[1])),
                    )
                    if self._lost > LOST_MAX:
                        self._vel = (0.0, 0.0)

                sx, sy = self._ema(x + self._pos[0], y + self._pos[1])
                self._move(sx, sy)

                rem = FRAME_INTERVAL - (time.time() - t0)
                if rem > 0:
                    time.sleep(rem)

        self._emitter.log.emit("[추적 정지]")
        self._emitter.stopped.emit()

    def _update_template(self, board, cx, cy):
        """매칭 위치 패치로 템플릿을 느리게 갱신해 흰→투명 변화에 적응한다."""
        if self._tmpl is None:
            return
        th, tw = self._tmpl.shape[:2]
        H, W = board.shape[:2]
        x0 = cx - tw // 2; y0 = cy - th // 2
        if x0 < 0 or y0 < 0 or x0 + tw > W or y0 + th > H:
            return
        patch = board[y0:y0 + th, x0:x0 + tw].astype(np.float32)
        cur   = self._tmpl.astype(np.float32)
        blended = (1 - TMPL_UPDATE) * cur + TMPL_UPDATE * patch
        self._tmpl = blended.astype(np.uint8)
```

기존 `_ema()`와 `_move()` 메서드는 그대로 둔다.

- [ ] **Step 4: 구문 + import 검증**

Run: `py -c "import ast; ast.parse(open('transparent_shape_standalone.py', encoding='utf-8').read()); print('SYNTAX OK')"`
Expected: `SYNTAX OK`

Run: `py test_transparent_tracker.py`
Expected: `ALL PASS` (순수 함수 회귀 확인)

- [ ] **Step 5: `find_diff` 잔존 참조 없음 확인**

Run(Grep 도구 사용): 패턴 `find_diff`
Expected: 매치 0건

- [ ] **Step 6: Commit**

```bash
git add transparent_shape_standalone.py
git commit -m "feat: ShapeTracker를 템플릿 추적+커서마스킹+예측+종료감지로 재작성"
```

---

## Task 6: 실게임 수동 검증

**Files:** 없음 (런타임 검증)

- [ ] **Step 1: GUI 실행**

Run: `py transparent_shape_standalone.py`
Expected: 다크 테마 창이 뜨고, ROI/단축키/제어/로그 그룹이 보임.

- [ ] **Step 2: 게임판 ROI 선택 후 미니게임에서 시작**

미니게임 팝업 상태에서 "영역 선택"으로 갈색 게임판을 드래그 → F9(또는 시작 버튼).

검증 체크리스트:
- [ ] 가운데 흰 도형을 즉시 잡고 따라간다.
- [ ] 흰색이 투명해져도 계속 추종한다(끊겨서 멈추지 않음).
- [ ] 분홍 커서를 추적 대상으로 오인해 점프하지 않는다.
- [ ] SUCCESS 화면에서 자동 정지(또는 35초 타임아웃)한다.

- [ ] **Step 3: 튜닝(필요 시)**

- 추적이 자주 끊기면: `MATCH_THRESH` 0.45 → 0.35로 낮춤.
- 배경으로 드리프트하면: `TMPL_UPDATE` 0.10 → 0.05로 낮추고 `MATCH_THRESH` 올림.
- 커서가 여전히 잡히면: `CURSOR_HUE`/`CURSOR_SAT_MIN`을 실제 커서 색으로 조정.
- 이동을 못 따라가면: `SEARCH_MARGIN` 40 → 60으로 키움.

- [ ] **Step 4: 최종 커밋(튜닝값 반영 시)**

```bash
git add transparent_shape_standalone.py
git commit -m "tune: 실게임 검증 후 추적 파라미터 조정"
```

---

## Self-Review 결과

- **스펙 커버리지:** 커서 마스킹(Task 2), 흰→투명 적응(Task 5 `_update_template`), 연속이동 예측(Task 5 velocity), 종료 감지(Task 4), 타임아웃/F10(Task 5 + 기존 단축키) — 스펙 항목 모두 태스크 존재.
- **플레이스홀더:** 없음. 모든 코드 스텝에 실제 코드 포함.
- **타입 일관성:** `mask_cursor(img)→img`, `match_template_local(...)→(cx,cy,score)|None`, `detect_end_screen(img)→bool`, `_pos`는 board 상대 `(x,y)`, `_vel`은 `(vx,vy)` — 태스크 간 일치.
