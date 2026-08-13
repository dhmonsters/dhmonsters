# 단일 캐릭터 기준색 캡처 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 드래그 영역의 평균 RGB 한 값을 영구 저장하고, 해제 이벤트가 누락돼도 선택을 완료하며, 자동 계산된 HSV 범위로 캐릭터를 검출한다.

**Architecture:** 설정에는 `minimap.reference_color_rgb` 한 항목만 새 기준색으로 저장한다. UI는 색상 견본 하나와 점 크기 설정만 표시하며, 런타임은 대표 RGB에서 HSV 허용 범위를 자동 계산한다. 영역 선택기는 정상 해제 이벤트와 버튼 상태 감시를 하나의 완료 함수로 합쳐 중복 없이 확정한다.

**Tech Stack:** Python 3.14, PyQt6, OpenCV, NumPy, pytest.

**Spec:** `03_output/2026-08-13_single-reference-color-capture-design_v1.md`.

## Global Constraints

- 실제 실행 진입점은 `run_integrated.py`다.
- 활성 UI는 `core_ui`이며 구형 UI를 연결하지 않는다.
- 대표 색상은 드래그 영역 전체 BGR 픽셀의 채널별 산술 평균을 RGB `[R, G, B]`로 저장한다.
- 새 기준색이 있으면 기존 HSV 네 설정은 검출에 사용하지 않는다.
- 점 크기 최소·최대와 `player/y_p.png` 단일 덮어쓰기 동작은 유지한다.
- UTF-8을 유지하고 관련 없는 작업 트리 변경을 수정하거나 커밋하지 않는다.
- EXE 빌드, 설치본 생성, 배포는 수행하지 않는다.

---

### Task 1: 누락된 마우스 해제 확정

**Files:**
- Modify: `core_ui/shot_selector.py:179-360`
- Test: `tests/test_shot_selector.py`

**Interfaces:**
- Consumes: `_Canvas.start`, `_Canvas.cur`, `_Canvas._dragging`, `ScreenshotRegionSelector._on_release(QRect)`.
- Produces: `_Canvas._finish_drag(QPoint | None) -> None`, `_Canvas._check_button_release() -> None`.

- [ ] **Step 1: 해제 이벤트 누락 실패 테스트 작성**

```python
def test_region_selector_finishes_when_button_poll_detects_release(app, monkeypatch):
    selector = ScreenshotRegionSelector(np.zeros((100, 100, 3), np.uint8), max_display=100)
    selected = []
    selector.region_selected.connect(lambda *rect: selected.append(rect))
    monkeypatch.setattr(selector._canvas, "releaseMouse", lambda: None)
    selector._canvas.start = QPoint(10, 10)
    selector._canvas.cur = QPoint(30, 25)
    selector._canvas._dragging = True
    monkeypatch.setattr(QApplication, "mouseButtons", lambda: Qt.MouseButton.NoButton)

    selector._canvas._check_button_release()

    assert selected == [(10, 10, 21, 16)]
    assert selector.result() == QDialog.DialogCode.Accepted
```

정상 해제 뒤 감시 함수가 다시 실행돼도 신호가 한 번만 발생하는 테스트도 같은 파일에 추가한다.

원본 기준 2×2 미만 영역은 다이얼로그를 닫지 않고 창 제목 또는 안내 문구에 `영역이 너무 작습니다`를 표시하며 같은 창에서 다시 드래그할 수 있는 테스트도 추가한다.

- [ ] **Step 2: 현재 코드에서 실패 확인**

Run: `python -m pytest -p no:cacheprovider tests/test_shot_selector.py -q`.

Expected: `_check_button_release`가 없어 실패한다.

- [ ] **Step 3: 단일 완료 함수와 버튼 상태 감시 구현**

`_Canvas`에 16ms `QTimer`를 두고 드래그 중에만 실행한다. `mouseReleaseEvent`와 타이머는 아래 형태의 동일 함수로 연결한다.

```python
def _finish_drag(self, release_point: QPoint | None = None) -> None:
    if not self._dragging or self.start is None or self.cur is None:
        return
    if release_point is not None and self.cur == self.start:
        self.cur = self._clamp(release_point)
    rect = QRect(self.start, self.cur).normalized()
    self._dragging = False
    self._release_timer.stop()
    self.releaseMouse()
    self.start = None
    self.cur = None
    self.update()
    self._on_release(rect)

def _check_button_release(self) -> None:
    if self._dragging and not (QApplication.mouseButtons() & Qt.MouseButton.LeftButton):
        self._finish_drag()
```

`mousePressEvent`에서 타이머를 시작하고 `mouseReleaseEvent`에서는 `_finish_drag(e.position().toPoint())`만 호출한다.

- [ ] **Step 4: 선택기 테스트 통과 확인**

Run: `python -m pytest -p no:cacheprovider tests/test_shot_selector.py -q`.

Expected: 모든 테스트 통과, 선택 신호 중복 없음.

- [ ] **Step 5: 의미 단위 커밋**

Stage only `core_ui/shot_selector.py` and `tests/test_shot_selector.py` using the task-specific alternate index, then commit with `fix: 마우스 해제 누락에서도 캡처 영역 확정`.

---

### Task 2: 대표 RGB 설정과 자동 HSV 범위

**Files:**
- Modify: `core/config_manager.py:176-182`
- Modify: `core/config_adapter.py:515-549, 671-683`
- Modify: `core/sensing/char_scanner.py:17-23`
- Modify: `core/runtime.py:512-546`
- Test: `tests/test_config_adapter.py`
- Test: `tests/test_char_color.py`
- Test: `tests/test_char_scanner_template_reload.py`

**Interfaces:**
- Produces: `minimap.reference_color_rgb: list[int]`.
- Produces: `auto_hsv_range_from_rgb(r: int, g: int, b: int, h_tol: int = 10, sv_margin: int = 40) -> tuple[tuple[int, int, int], tuple[int, int, int]]`.
- Consumes: `RuntimeConfig.char_rgb` and `CharScanner.set_filters(lower, upper, min_area, max_area)`.

- [ ] **Step 1: 설정 우선순위와 자동 범위 실패 테스트 작성**

```python
def test_reference_color_rgb_overrides_legacy_hsv_fields():
    data = deepcopy(DEFAULT_CONFIG)
    data["minimap"].update({
        "reference_color_rgb": [220, 210, 20],
        "hsv_h_low": 1,
        "hsv_h_high": 2,
    })
    result = to_runtime_config(data)
    assert result.char_rgb == (220, 210, 20)
    assert result.char_h_low is None
    assert result.char_h_high is None
```

```python
def test_auto_hsv_range_uses_reference_s_and_v_minus_forty():
    lo, hi = auto_hsv_range_from_rgb(220, 210, 20)
    hsv = cv2.cvtColor(np.uint8([[[20, 210, 220]]]), cv2.COLOR_BGR2HSV)[0, 0]
    assert lo == (max(0, int(hsv[0]) - 10), max(0, int(hsv[1]) - 40), max(0, int(hsv[2]) - 40))
    assert hi == (min(179, int(hsv[0]) + 10), 255, 255)
```

- [ ] **Step 2: 현재 코드에서 실패 확인**

Run: `python -m pytest -p no:cacheprovider tests/test_config_adapter.py tests/test_char_color.py -q`.

Expected: 새 설정 키와 자동 범위 함수가 없어 실패한다.

- [ ] **Step 3: 설정 기본값·어댑터·자동 범위 구현**

`DEFAULT_CONFIG["minimap"]`에 `"reference_color_rgb": None`을 추가한다. 어댑터는 유효한 길이 3 목록을 0~255 정수 튜플로 정규화하고, 새 값이 있으면 `char_h_low`와 `char_h_high`를 `None`으로 만든다. 새 값이 없으면 기존 `char_r/g/b` 호환을 유지한다.

`core/sensing/char_scanner.py`에 `auto_hsv_range_from_rgb`를 추가하고, `BotRuntime.reload_character_filter`의 RGB 경로에서 기존 고정 S/V 하한 대신 이 함수를 사용한다.

- [ ] **Step 4: 설정과 런타임 테스트 통과 확인**

Run: `python -m pytest -p no:cacheprovider tests/test_config_adapter.py tests/test_char_color.py tests/test_char_scanner_template_reload.py -q`.

Expected: 새 대표 RGB 우선순위, 기존 RGB 호환, 자동 HSV 범위가 모두 통과한다.

- [ ] **Step 5: 의미 단위 커밋**

Stage only the files in Task 2 using the alternate index, then commit with `feat: 단일 기준색 자동 검출 범위 적용`.

---

### Task 3: 단일 기준색 UI와 평균 저장

**Files:**
- Modify: `core_ui/pages.py:430-585`
- Test: `tests/test_pages.py`

**Interfaces:**
- Produces: `_mean_rgb_from_bgr(crop: np.ndarray) -> tuple[int, int, int]`.
- Consumes: `minimap.reference_color_rgb` and `ConfigManager.save()`.

- [ ] **Step 1: 평균값과 UI 실패 테스트 작성**

```python
def test_mean_rgb_from_bgr_uses_all_selected_pixels():
    crop = np.array([[[10, 20, 30], [30, 40, 50]]], dtype=np.uint8)
    assert pages_module._mean_rgb_from_bgr(crop) == (40, 30, 20)
```

```python
def test_character_color_controls_show_one_reference_color_without_hsv_sliders(app):
    cfg = FakeConfig()
    cfg.set("minimap", "reference_color_rgb", [225, 220, 10])
    controls = pages_module._make_character_color_controls(cfg)
    text = " ".join(label.text() for label in controls.findChildren(QLabel))
    assert "#E1DC0A" in text
    assert "색상 시작 H" not in text
    assert "색상 끝 H" not in text
    assert "채도 최소 S" not in text
    assert "밝기 최소 V" not in text
    assert "점 크기 최소" in text
    assert "점 크기 최대" in text
```

캡처 버튼 테스트는 선택 영역의 평균 RGB가 `reference_color_rgb`에 저장되고 `cfg.saved`가 증가하는지 검증한다.

`config.save()`가 예외를 발생시키면 이전 `reference_color_rgb`를 복원하고 성공 문구 대신 저장 실패 문구를 표시하는 테스트도 추가한다.

- [ ] **Step 2: 현재 코드에서 실패 확인**

Run: `python -m pytest -p no:cacheprovider tests/test_pages.py -q`.

Expected: 평균 함수와 단일 색상 UI가 없어 실패한다.

- [ ] **Step 3: UI와 평균 저장 구현**

HSV 네 `SliderField` 생성을 제거한다. `_mean_rgb_from_bgr`는 NumPy 평균과 반올림을 사용한다.

```python
def _mean_rgb_from_bgr(crop):
    b, g, r = np.rint(crop[:, :, :3].reshape(-1, 3).mean(axis=0)).astype(int)
    return int(r), int(g), int(b)
```

캡처 성공 시 기존 값을 보관한 뒤 `config.set("minimap", "reference_color_rgb", [r, g, b])`와 `config.save()`를 한 번 실행한다. 저장 성공 후에만 색상 견본 스타일과 `#RRGGBB · RGB(R, G, B)` 텍스트를 갱신한다. 저장 예외가 나면 기존 값을 다시 설정하고 실패 문구를 표시한다. 취소 시 기존 색상과 설정을 변경하지 않는다.

- [ ] **Step 4: 페이지와 캡처 테스트 통과 확인**

Run: `python -m pytest -p no:cacheprovider tests/test_pages.py tests/test_shot_selector.py -q`.

Expected: 단일 기준색 UI, 평균 저장, 취소 보존, 템플릿 덮어쓰기 테스트가 모두 통과한다.

- [ ] **Step 5: 의미 단위 커밋**

Stage only `core_ui/pages.py` and `tests/test_pages.py` using the alternate index, then commit with `feat: 드래그 평균 기준색 하나로 UI 단순화`.

---

### Task 4: 통합 검증과 기록

**Files:**
- Modify: `03_output/2026-08-13_single-reference-color-capture_checklist_v1.md`
- Modify: `03_output/2026-08-13_single-reference-color-capture_context-notes_v1.md`

**Interfaces:**
- Consumes: Task 1~3의 테스트와 커밋.
- Produces: 최종 검증 근거와 배포 제외 기록.

- [ ] **Step 1: 관련 전체 테스트 실행**

Run: `python -m pytest -p no:cacheprovider tests/test_shot_selector.py tests/test_pages.py tests/test_char_color.py tests/test_char_scanner.py tests/test_char_scanner_template_reload.py tests/test_config_adapter.py -q`.

Expected: 모든 관련 테스트 통과. 기존 `mss.mss` 폐기 예정 경고 외 새 경고 없음.

- [ ] **Step 2: 문법과 인코딩 검증**

Run: `python -m compileall -q core_ui/shot_selector.py core_ui/pages.py core/config_adapter.py core/config_manager.py core/sensing/char_scanner.py core/runtime.py`.

PowerShell의 strict UTF-8 디코더로 수정 파일을 모두 읽고 `git diff --check`를 실행한다.

- [ ] **Step 3: 범위 검토**

각 변경 줄을 단일 기준색, 드래그 확정, 호환, 테스트 중 하나에 연결한다. 구형 UI 연결, EXE 빌드, 설치본 생성, 배포가 없음을 기록한다. 기존 `tests/test_runtime.py`의 Humanizer·공격·픽업 구조 불일치는 이번 범위에서 수정하지 않는다.

- [ ] **Step 4: 기록 커밋**

Stage only the two Task 4 records using the alternate index, then commit with `docs: 단일 기준색 캡처 구현 검증 기록`.
