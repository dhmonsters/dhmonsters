# 빨코2 좌표 설정 UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 빨코2 이동·회수 X 좌표 15개를 동선·이동 탭에서 안전하게 편집하고 다음 F1 시작부터 적용한다.

**Architecture:** `core/config_adapter.py`가 검증된 기본값, 허용 키, 순수 검증·병합 함수를 제공하고 런타임 프로필을 만든다. 새 `Rednose2CoordinateWidget`은 숫자 입력, 전체 검증, 한 번의 저장, 기본값 복원만 담당하며 `pages.py`는 카드를 배치한다. 빨코2 러너의 동작 로직은 변경하지 않는다.

**Tech Stack:** Python 3.14, PyQt6, pytest, 기존 `ConfigManager`, 기존 `RuntimeConfig` 변환 경로.

## Global Constraints

- 프로젝트 경로는 `C:\Users\PC\Desktop\02_work\05_AI\maple_bot`이다.
- 실제 실행 진입점은 `run_integrated.py`이고 활성 UI는 `core_ui`다.
- 구형 UI와 구형 `main.py` 코드를 연결하지 않는다.
- 빨코2만 수정하고 빨코3는 변경하지 않는다.
- 기준 미니맵 너비는 172이며 UI X 입력 범위는 0부터 171까지다.
- Y 판정값, 입력 시간, 공격 횟수, 시도 횟수, 자동판매 좌표는 수정하지 않는다.
- 저장값은 실행 중인 러너에 즉시 반영하지 않고 다음 F1 시작부터 적용한다.
- `빨코2 기본값 복원`은 입력칸만 바꾸며 `저장` 전에는 설정 파일을 변경하지 않는다.
- 새 Python 파일의 첫 줄에는 역할을 설명하는 한글 주석을 넣고 모든 파일은 UTF-8을 유지한다.
- EXE 빌드와 배포는 이번 구현 범위에 포함하지 않는다.

## File Structure

- Create `core_ui/rednose2_coordinate_widget.py`. 빨코2 좌표 카드의 입력, 검증, 저장, 복원을 담당한다.
- Create `tests/test_rednose2_coordinate_widget.py`. 위젯의 저장 원자성, 복원, 오류 표시를 검증한다.
- Modify `core/config_adapter.py:240-329`. 빨코2 X 기본값과 허용 병합 함수를 추가하고 비율 생성 전에 적용한다.
- Modify `tests/test_config_adapter.py`. 저장 좌표의 런타임 반영, 비율, 손상 설정 폴백, 빨코3 비회귀를 검증한다.
- Modify `core_ui/pages.py:617-621`. 전용 카드를 사냥터 프리셋 카드 바로 아래에 배치한다.
- Modify `tests/test_pages.py:38-50`. 동선·이동 페이지에 카드가 존재하는지 검증한다.
- Modify `03_output/2026-08-10_rednose2-coordinate-ui-checklist_v1.md`. 구현·검증 완료 상태를 기록한다.
- Modify `03_output/2026-08-10_rednose2-coordinate-ui-context-notes_v1.md`. 실제 변경과 테스트 결과를 기록한다.

---

### Task 1: 빨코2 X 좌표의 검증·런타임 병합

**Files:**
- Modify: `core/config_adapter.py:240-329`
- Modify: `tests/test_config_adapter.py`

**Interfaces:**
- Consumes: `dict` 형식의 `rednose2_v5` 사용자 설정과 기존 `_with_minimap_ratios()`.
- Produces: `REDNOSE2_X_DEFAULTS: dict[str, int]`, `rednose2_x_validation_error(values: dict) -> str | None`, `_merge_rednose2_x_settings(raw: dict | None) -> dict[str, int]`.

- [ ] **Step 1: 유효한 사용자 좌표와 비율 반영 실패 테스트 작성**

`tests/test_config_adapter.py`에 다음 테스트를 추가한다.

```python
def test_rednose2_user_x_settings_override_defaults_and_rebuild_ratios():
    data = _sample_config()
    data["hunt_grounds"] = {"active": "빨코2"}
    data["rednose2_v5"] = {
        "floor2_left_x": 58,
        "floor2_right_x": 121,
        "floor2_right_safe_x": 120,
        "stair7_x": 42,
        "stair7_x_min": 39,
        "stair7_x_max": 45,
        "platform24_approach_x": 44,
        "platform24_x": 31,
        "platform1415_16_approach_x": 97,
        "platform1415_x_min": 96,
        "platform1415_x_max": 98,
        "platform27_approach_x": 92,
        "platform27_bypass_approach_x": 81,
        "platform27_bypass_x_min": 73,
        "platform27_bypass_x_max": 90,
    }

    profile = to_runtime_config(data).rednose2_v5

    assert profile["floor2_left_x"] == 58
    assert profile["stair7_x"] == 42
    assert profile["platform1415_16_approach_x"] == 97
    assert profile["platform27_bypass_x_max"] == 90
    assert profile["floor2_left_x_ratio"] == pytest.approx(58 / 172)
    assert profile["platform27_bypass_x_max_ratio"] == pytest.approx(90 / 172)
```

- [ ] **Step 2: 테스트를 실행해 현재 고정값 때문에 실패함을 확인**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest tests/test_config_adapter.py::test_rednose2_user_x_settings_override_defaults_and_rebuild_ratios -q`

Expected: `floor2_left_x`가 55로 남아 assertion이 실패한다.

- [ ] **Step 3: 기본값·허용 키·검증 함수의 최소 구현 추가**

`core/config_adapter.py`의 빨코2 프로필 함수 바로 위에 다음 인터페이스를 추가한다. 관계 검증 문구는 UI에서 그대로 표시하므로 한글로 고정한다.

```python
REDNOSE2_X_DEFAULTS = {
    "floor2_left_x": 55,
    "floor2_right_x": 124,
    "floor2_right_safe_x": 124,
    "stair7_x": 41,
    "stair7_x_min": 38,
    "stair7_x_max": 44,
    "platform24_approach_x": 43,
    "platform24_x": 30,
    "platform1415_16_approach_x": 95,
    "platform1415_x_min": 94,
    "platform1415_x_max": 96,
    "platform27_approach_x": 91,
    "platform27_bypass_approach_x": 80,
    "platform27_bypass_x_min": 72,
    "platform27_bypass_x_max": 89,
}


def rednose2_x_validation_error(values: dict) -> str | None:
    for key in REDNOSE2_X_DEFAULTS:
        value = values.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 171:
            return "모든 X 좌표는 0~171 사이의 정수여야 합니다."
    if values["floor2_left_x"] > values["floor2_right_x"]:
        return "2층 사냥 범위의 왼쪽 X는 오른쪽 X보다 클 수 없습니다."
    if not values["stair7_x_min"] <= values["stair7_x"] <= values["stair7_x_max"]:
        return "7번 계단 목표 X는 허용 범위 안에 있어야 합니다."
    if not values["platform1415_x_min"] <= values["platform1415_16_approach_x"] <= values["platform1415_x_max"]:
        return "14/15번·16번 공통 접근 X는 14/15 허용 범위 안에 있어야 합니다."
    if not values["platform27_bypass_x_min"] <= values["platform27_bypass_approach_x"] <= values["platform27_bypass_x_max"]:
        return "27번 우회 접근 X는 우회 허용 범위 안에 있어야 합니다."
    return None
```

`_merge_rednose2_x_settings()`는 기본값 복사본에서 시작한다. 단일 키 4개는 각각 유효한 경우만 덮어쓰고, 관계 그룹은 후보 그룹 전체가 유효할 때만 함께 덮어쓴다.

```python
def _valid_rednose2_x(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 171


def _rednose2_group_is_valid(keys: tuple[str, ...], values: dict) -> bool:
    if not all(_valid_rednose2_x(values[key]) for key in keys):
        return False
    if keys == ("floor2_left_x", "floor2_right_x"):
        return values["floor2_left_x"] <= values["floor2_right_x"]
    if keys == ("stair7_x_min", "stair7_x", "stair7_x_max"):
        return values["stair7_x_min"] <= values["stair7_x"] <= values["stair7_x_max"]
    if keys == ("platform1415_x_min", "platform1415_16_approach_x", "platform1415_x_max"):
        return values["platform1415_x_min"] <= values["platform1415_16_approach_x"] <= values["platform1415_x_max"]
    if keys == ("platform27_bypass_x_min", "platform27_bypass_approach_x", "platform27_bypass_x_max"):
        return values["platform27_bypass_x_min"] <= values["platform27_bypass_approach_x"] <= values["platform27_bypass_x_max"]
    return False


def _merge_rednose2_x_settings(raw: dict | None) -> dict[str, int]:
    raw = raw if isinstance(raw, dict) else {}
    merged = dict(REDNOSE2_X_DEFAULTS)
    simple_keys = (
        "floor2_right_safe_x",
        "platform24_approach_x",
        "platform24_x",
        "platform27_approach_x",
    )
    for key in simple_keys:
        if _valid_rednose2_x(raw.get(key)):
            merged[key] = int(raw[key])

    groups = (
        ("floor2_left_x", "floor2_right_x"),
        ("stair7_x_min", "stair7_x", "stair7_x_max"),
        ("platform1415_x_min", "platform1415_16_approach_x", "platform1415_x_max"),
        ("platform27_bypass_x_min", "platform27_bypass_approach_x", "platform27_bypass_x_max"),
    )
    for keys in groups:
        candidate = dict(merged)
        for key in keys:
            if key in raw:
                candidate[key] = raw[key]
        if _rednose2_group_is_valid(keys, candidate):
            merged.update({key: int(candidate[key]) for key in keys})
    return merged
```

관계 그룹 하나의 오류는 다른 그룹 적용을 막지 않는다. 최종 반환값 전체에는 `rednose2_x_validation_error(merged) is None`이 성립해야 한다.

- [ ] **Step 4: 빨코2 프로필에 병합값을 적용한 뒤 비율 생성**

`_rednose2_v5_profile()`에서 표의 15개 X 리터럴을 `REDNOSE2_X_DEFAULTS`로부터 구성하고, `return _with_minimap_ratios(...)` 직전에 다음을 실행한다.

```python
    forced.update(_merge_rednose2_x_settings(d.get("rednose2_v5")))
```

기존 `x_keys` 튜플은 유지해 사용자 값으로 비율이 다시 만들어지게 한다. `stair7_right_bias_x`와 자동판매 X 값은 허용 목록에 넣지 않는다.

- [ ] **Step 5: 유효 좌표 테스트를 실행해 통과 확인**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest tests/test_config_adapter.py::test_rednose2_user_x_settings_override_defaults_and_rebuild_ratios -q`

Expected: PASS.

- [ ] **Step 6: 손상 그룹 폴백과 빨코3 비회귀 테스트 작성**

```python
def test_rednose2_invalid_external_ranges_fall_back_by_group():
    data = _sample_config()
    data["rednose2_v5"] = {
        "floor2_left_x": 130,
        "floor2_right_x": 120,
        "platform24_approach_x": 46,
        "stair7_x_min": 44,
        "stair7_x": 40,
        "stair7_x_max": 42,
    }

    profile = to_runtime_config(data).rednose2_v5

    assert profile["floor2_left_x"] == 55
    assert profile["floor2_right_x"] == 124
    assert profile["stair7_x_min"] == 38
    assert profile["stair7_x"] == 41
    assert profile["stair7_x_max"] == 44
    assert profile["platform24_approach_x"] == 46


def test_rednose2_x_overrides_do_not_change_rednose3_profile():
    baseline = to_runtime_config(_sample_config()).rednose3
    data = _sample_config()
    data["rednose2_v5"] = {"floor2_left_x": 58, "floor2_right_x": 121}

    assert to_runtime_config(data).rednose3 == baseline
```

- [ ] **Step 7: 어댑터 테스트 전체 실행**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest tests/test_config_adapter.py -q`

Expected: 모든 테스트 PASS.

- [ ] **Step 8: 어댑터 변경 커밋**

```powershell
git add maple_bot/core/config_adapter.py maple_bot/tests/test_config_adapter.py
git commit -m "Apply editable RedNose2 X coordinates"
```

---

### Task 2: 빨코2 좌표 전용 카드

**Files:**
- Create: `core_ui/rednose2_coordinate_widget.py`
- Create: `tests/test_rednose2_coordinate_widget.py`

**Interfaces:**
- Consumes: `REDNOSE2_X_DEFAULTS`, `rednose2_x_validation_error()`, `config.get()`, `config.set()`, `config.save()`.
- Produces: `Rednose2CoordinateWidget(config, parent=None)`, `inputs: dict[str, QSpinBox]`, `save_values()`, `restore_defaults()`.

- [ ] **Step 1: 저장·복원·검증 실패 테스트 작성**

새 테스트 파일 첫 줄은 `# 빨코2 좌표 설정 카드의 저장·검증·기본값 복원을 검증한다.`로 시작한다.

```python
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from core.config_adapter import REDNOSE2_X_DEFAULTS
from core_ui.rednose2_coordinate_widget import Rednose2CoordinateWidget


class FakeConfig:
    def __init__(self, profile=None):
        self._data = {"rednose2_v5": dict(profile or {})}
        self.saved = 0

    def get(self, *keys, default=None):
        node = self._data
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    def set(self, *args):
        *keys, value = args
        node = self._data
        for key in keys[:-1]:
            node = node.setdefault(key, {})
        node[keys[-1]] = value

    def save(self):
        self.saved += 1


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_loads_saved_values_and_defaults_for_missing_values(app):
    widget = Rednose2CoordinateWidget(FakeConfig({"stair7_x": 42}))
    assert widget.inputs["stair7_x"].value() == 42
    assert widget.inputs["platform24_x"].value() == REDNOSE2_X_DEFAULTS["platform24_x"]


def test_restore_defaults_changes_fields_without_saving(app):
    config = FakeConfig({"stair7_x": 42})
    widget = Rednose2CoordinateWidget(config)
    widget.restore_defaults()
    assert widget.inputs["stair7_x"].value() == 41
    assert config.get("rednose2_v5", "stair7_x") == 42
    assert config.saved == 0


def test_valid_save_replaces_only_allowed_keys_and_saves_once(app):
    config = FakeConfig({"teleport_hold_sec": 0.3, "stair7_x": 41})
    widget = Rednose2CoordinateWidget(config)
    widget.inputs["stair7_x"].setValue(42)
    widget.inputs["stair7_x_min"].setValue(39)
    widget.inputs["stair7_x_max"].setValue(45)
    widget.save_values()
    assert config.get("rednose2_v5", "stair7_x") == 42
    assert config.get("rednose2_v5", "teleport_hold_sec") == 0.3
    assert config.saved == 1
    assert "다음 F1" in widget.status.text()


def test_invalid_range_does_not_mutate_or_save(app):
    config = FakeConfig({"stair7_x": 41})
    before = dict(config.get("rednose2_v5"))
    widget = Rednose2CoordinateWidget(config)
    widget.inputs["stair7_x_min"].setValue(45)
    widget.inputs["stair7_x"].setValue(42)
    widget.inputs["stair7_x_max"].setValue(44)
    widget.save_values()
    assert config.get("rednose2_v5") == before
    assert config.saved == 0
    assert "7번 계단" in widget.status.text()
```

- [ ] **Step 2: 테스트를 실행해 모듈 부재 실패 확인**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest tests/test_rednose2_coordinate_widget.py -q`

Expected: `ModuleNotFoundError: core_ui.rednose2_coordinate_widget`.

- [ ] **Step 3: 전용 카드의 최소 구현 작성**

새 파일의 첫 줄은 `# 빨코2 이동·회수 X 좌표를 편집하고 안전하게 저장하는 전용 카드 위젯`으로 한다. `QFrame` 기반으로 구현하고 `setObjectName("rednose2CoordinateCard")`를 지정한다.

```python
class Rednose2CoordinateWidget(QFrame):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self.inputs: dict[str, QSpinBox] = {}
        self.setObjectName("rednose2CoordinateCard")
        self._build_ui()
        self._load()

    def _current_values(self) -> dict[str, int]:
        return {key: spin.value() for key, spin in self.inputs.items()}

    def _load(self) -> None:
        saved = self._config.get("rednose2_v5", default={}) or {}
        for key, default in REDNOSE2_X_DEFAULTS.items():
            value = saved.get(key, default) if isinstance(saved, dict) else default
            self.inputs[key].setValue(value if isinstance(value, int) else default)

    def restore_defaults(self) -> None:
        for key, value in REDNOSE2_X_DEFAULTS.items():
            self.inputs[key].setValue(value)
        self.status.setText("기본값을 불러왔습니다. 저장을 눌러야 반영됩니다.")

    def save_values(self) -> None:
        values = self._current_values()
        error = rednose2_x_validation_error(values)
        if error:
            self.status.setText(error)
            return
        current = self._config.get("rednose2_v5", default={}) or {}
        merged = dict(current) if isinstance(current, dict) else {}
        merged.update(values)
        self._config.set("rednose2_v5", merged)
        self._config.save()
        self.status.setText("저장 완료 · 다음 F1 시작부터 적용됩니다.")
```

`_build_ui()`는 설계 문서의 7개 그룹 순서대로 라벨과 `QSpinBox`를 만들고 각 스핀박스에 `setRange(0, 171)`을 적용한다. 버튼은 `저장`을 `save_values()`, `빨코2 기본값 복원`을 `restore_defaults()`에 연결한다. 값 변경 신호는 설정 저장에 직접 연결하지 않는다.

- [ ] **Step 4: 위젯 테스트 실행**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest tests/test_rednose2_coordinate_widget.py -q`

Expected: 모든 테스트 PASS.

- [ ] **Step 5: 위젯 변경 커밋**

```powershell
git add maple_bot/core_ui/rednose2_coordinate_widget.py maple_bot/tests/test_rednose2_coordinate_widget.py
git commit -m "Add RedNose2 coordinate settings card"
```

---

### Task 3: 동선·이동 페이지 연결

**Files:**
- Modify: `core_ui/pages.py:617-621`
- Modify: `tests/test_pages.py:38-50`

**Interfaces:**
- Consumes: `Rednose2CoordinateWidget(config)`.
- Produces: 동선·이동 페이지 내부의 `rednose2CoordinateCard` 객체.

- [ ] **Step 1: 페이지 배치 실패 테스트 작성**

```python
def test_movement_page_has_rednose2_coordinate_card(app):
    from PyQt6.QtWidgets import QWidget

    pages = build_pages(FakeConfig())

    assert pages[1].findChild(QWidget, "rednose2CoordinateCard") is not None
```

- [ ] **Step 2: 테스트를 실행해 카드 부재 실패 확인**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest tests/test_pages.py::test_movement_page_has_rednose2_coordinate_card -q`

Expected: assertion이 실패한다.

- [ ] **Step 3: 사냥터 프리셋 바로 아래에 카드 배치**

`core_ui/pages.py`의 `nav_extras` 구성부를 다음 순서로 유지한다.

```python
    from core_ui.hunt_ground_preset_widget import HuntGroundPresetWidget
    from core_ui.rednose2_coordinate_widget import Rednose2CoordinateWidget
    nav_extras.append(HuntGroundPresetWidget(c, name_field=hunt_name_field))
    nav_extras.append(Rednose2CoordinateWidget(c))
```

연결·인식 탭, 빨코3, 기존 블록 편집기 순서는 변경하지 않는다.

- [ ] **Step 4: 페이지와 위젯 테스트 실행**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest tests/test_pages.py tests/test_rednose2_coordinate_widget.py -q`

Expected: 모든 테스트 PASS.

- [ ] **Step 5: 페이지 연결 커밋**

```powershell
git add maple_bot/core_ui/pages.py maple_bot/tests/test_pages.py
git commit -m "Show RedNose2 coordinate card in movement page"
```

---

### Task 4: 통합 검증과 작업 기록

**Files:**
- Modify: `03_output/2026-08-10_rednose2-coordinate-ui-checklist_v1.md`
- Modify: `03_output/2026-08-10_rednose2-coordinate-ui-context-notes_v1.md`

**Interfaces:**
- Consumes: Task 1부터 3까지의 코드와 테스트.
- Produces: 검증 결과가 기록된 완료 체크리스트와 인계 문서.

- [ ] **Step 1: 관련 테스트 전체 실행**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest tests/test_config_adapter.py tests/test_rednose2_coordinate_widget.py tests/test_pages.py tests/test_rednose2_collection_stage.py tests/test_position_freshness.py -q`

Expected: 모든 테스트 PASS. 기존 `mss.mss` 사용 중단 예정 경고는 실패로 취급하지 않는다.

- [ ] **Step 2: 문법 검사 실행**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m compileall -q core/config_adapter.py core_ui/rednose2_coordinate_widget.py core_ui/pages.py tests/test_config_adapter.py tests/test_rednose2_coordinate_widget.py tests/test_pages.py`

Expected: 출력 없이 종료 코드 0.

- [ ] **Step 3: UTF-8·변경 범위 검사**

Run: `git diff --check`

Expected: 공백 오류와 인코딩 오류 없음. 줄바꿈 변환 경고만 있으면 기록 후 진행한다.

Run: `git diff --name-only origin/main -- maple_bot`

Expected: 이 계획의 Create/Modify 목록과 설계 기록 파일 외 제품 파일이 나타나지 않는다.

- [ ] **Step 4: 체크리스트와 작업 기록 갱신**

체크리스트에는 구현, 관련 테스트, 문법 검사, UTF-8 확인을 완료 표시한다. 작업 기록에는 실제 테스트 개수, 경고, 기본값 복원 동작, 다음 F1 적용 확인 결과를 구체적으로 추가한다.

- [ ] **Step 5: 최종 검증 커밋**

```powershell
git add maple_bot/03_output/2026-08-10_rednose2-coordinate-ui-checklist_v1.md maple_bot/03_output/2026-08-10_rednose2-coordinate-ui-context-notes_v1.md
git commit -m "Record RedNose2 coordinate UI verification"
```

- [ ] **Step 6: 완료 전 커밋 범위 재검토**

Run: `git log --oneline --decorate origin/main..HEAD`

Expected: 어댑터, 전용 카드, 페이지 연결, 검증 기록의 의미 단위 커밋만 존재한다.

Run: `git diff --stat origin/main...HEAD`

Expected: 빨코2 X 좌표 UI와 관련 테스트·문서만 포함되고 EXE·설치 파일·개인 설정은 포함되지 않는다.
