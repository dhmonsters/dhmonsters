# Character Capture Release Coordinate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 이동 이벤트가 누락되어도 캐릭터 캡처 드래그가 실제 마우스 해제 좌표로 완료되게 한다.

**Architecture:** 공용 `ScreenshotRegionSelector`의 캔버스가 마우스 해제 이벤트에서 최종 좌표를 직접 읽도록 최소 수정한다. 페이지와 저장 로직은 그대로 두고 실제 위젯 이벤트 테스트로 회귀를 방지한다.

**Tech Stack:** Python 3.14, PyQt6, pytest.

## Global Constraints

- 활성 UI는 `core_ui`만 사용한다.
- 실제 실행 진입점은 `run_integrated.py`이다.
- UTF-8 인코딩을 유지한다.
- EXE 빌드, 설치본 생성, 배포는 수행하지 않는다.

---

### Task 1: 마우스 해제 좌표 회귀 수정

**Files:**
- Modify: `core_ui/shot_selector.py:228-230`
- Test: `tests/test_shot_selector.py`

**Interfaces:**
- Consumes: `QMouseEvent.position()`과 `_Canvas._clamp(QPoint)`.
- Produces: 기존 `_on_release(QRect)` 콜백에 실제 시작점과 해제점으로 만든 정규화 사각형을 전달한다.

- [x] **Step 1: 실패하는 실제 위젯 테스트 작성**

```python
def test_region_selector_uses_release_position_without_move_event(app):
    selector = ScreenshotRegionSelector(np.zeros((100, 100, 3), dtype=np.uint8))
    selected = []
    selector.region_selected.connect(lambda *rect: selected.append(rect))

    QTest.mousePress(selector._canvas, Qt.MouseButton.LeftButton, pos=QPoint(10, 10))
    QTest.mouseRelease(selector._canvas, Qt.MouseButton.LeftButton, pos=QPoint(30, 25))

    assert selected == [(10, 10, 21, 16)]
    assert selector.result() == QDialog.DialogCode.Accepted
```

- [x] **Step 2: 테스트가 원인 때문에 실패하는지 확인**

Run: `python -m pytest tests/test_shot_selector.py::test_region_selector_uses_release_position_without_move_event -q`

Expected: `selected`가 빈 목록이어서 실패한다.

- [x] **Step 3: 최소 구현 적용**

```python
def mouseReleaseEvent(self, e):
    if self.start is not None:
        self.cur = self._clamp(e.position().toPoint())
        self.update()
        self._on_release(QRect(self.start, self.cur).normalized())
```

- [x] **Step 4: 관련 테스트 확인**

Run: `python -m pytest tests/test_shot_selector.py tests/test_pages.py -q`

Expected: 전체 통과.

- [x] **Step 5: 문법과 변경 범위 확인**

Run: `python -m compileall -q core_ui/shot_selector.py tests/test_shot_selector.py`

Run: `git diff --check`

Expected: 모두 종료 코드 0.

- [x] **Step 6: 의미 단위 커밋**

```text
fix: 캡처 선택기의 마우스 해제 좌표 반영
```
