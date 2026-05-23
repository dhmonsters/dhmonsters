# 아이템 수집 타이머 + 낙사 복귀 버그 수정 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 2분 주기 아이템 수집 루틴을 구현하고, 등록되지 않은 층으로 낙사 시 즉시 복귀하지 못하는 버그를 수정한다.

**Architecture:**
- 낙사 복귀 버그: `bot_loop.py` patrol 상태의 Y 이탈 감지 조건 1줄 수정 (any-zone 체크 추가)
- 아이템 수집 타이머: config 스키마 → UI(tab_coordinate.py) → bot_loop.py 실행 순서로 구현. 기존 to_rope/climbing 상태머신을 그대로 재사용하고, `fh_state == "pickup_nav"` 상태를 추가해 수집 루트를 순회한다.

**Tech Stack:** Python 3.11, PyQt6, 기존 MinimapReader/InputController/MapNavigator

---

## 파일 변경 목록

| 파일 | 변경 내용 |
|------|-----------|
| `core/config_manager.py` | `pickup_timer` 기본값 추가 |
| `ui/tab_coordinate.py` | 아이템 수집 타이머 UI 그룹 추가 |
| `core/bot_loop.py` | 낙사 복귀 버그 수정 + 픽업 타이머 상태머신 추가 |

---

## Task 1: 낙사 복귀 버그 수정

**현상:** 1-2층이 구역 목록에 없을 때 캐릭터가 1층으로 낙사하면, `_zone_by_y()`가 등록된 최근접 층(예: 3층)을 반환하고 `actual_idx == fh_idx`가 되어 복귀 로직이 실행되지 않는다.

**Files:**
- Modify: `core/bot_loop.py` (patrol 상태 Y 이탈 감지 블록, 대략 515~543줄)

- [ ] **Step 1: 버그 재현 조건 확인**

  `bot_loop.py`에서 아래 블록을 찾는다.

  ```python
  if not x_in_zone or not y_in_zone:
      cy_now = pos[1]
      actual_zone = _zone_by_y(cy_now)
      actual_idx  = fh_zones.index(actual_zone)
      reason = ("X범위 이탈" if not x_in_zone else "낙사(Y 이탈)")
      if actual_idx != fh_idx:
          fh_idx        = actual_idx
          ...
  ```

  `if actual_idx != fh_idx:` 조건 때문에 actual_idx == fh_idx이면 아무것도 안 함.

- [ ] **Step 2: 즉시 복귀 조건 추가**

  아래와 같이 수정한다. Y 이탈인데 어떤 구역에도 해당 Y가 없으면 → `fh_half_count`를 강제로 최대치로 올려 다음 틱에 즉시 밧줄 이동을 발동시킨다.

  기존:
  ```python
  if not x_in_zone or not y_in_zone:
      cy_now = pos[1]
      actual_zone = _zone_by_y(cy_now)
      actual_idx  = fh_zones.index(actual_zone)
      reason = ("X범위 이탈" if not x_in_zone else "낙사(Y 이탈)")
      if actual_idx != fh_idx:
          fh_idx        = actual_idx
          fh_half_count = 0
          fh_last_side  = ""
          fh_route_idx  = 0
          fh_arrive_time = time.time()
          self._map_navigator.set_zones([fh_zones[fh_idx]])
          self._status(
              f"[층별] {reason} Y={cy_now} → "
              f"'{fh_zones[fh_idx].name}' 복귀"
          )
          _apply_zone_pattern(fh_zones[fh_idx])
  ```

  변경 후:
  ```python
  if not x_in_zone or not y_in_zone:
      cy_now = pos[1]
      actual_zone = _zone_by_y(cy_now)
      actual_idx  = fh_zones.index(actual_zone)
      reason = ("X범위 이탈" if not x_in_zone else "낙사(Y 이탈)")
      # 어떤 구역에도 현재 Y가 포함되지 않으면 → 미등록 층으로 낙사
      _y_in_any = any(z.y_min - 8 <= cy_now <= z.y_max + 8 for z in fh_zones)
      if actual_idx != fh_idx:
          fh_idx        = actual_idx
          fh_half_count = 0
          fh_last_side  = ""
          fh_route_idx  = 0
          fh_arrive_time = time.time()
          self._map_navigator.set_zones([fh_zones[fh_idx]])
          self._status(
              f"[층별] {reason} Y={cy_now} → "
              f"'{fh_zones[fh_idx].name}' 복귀"
          )
          _apply_zone_pattern(fh_zones[fh_idx])
      elif not _y_in_any and not y_in_zone:
          # 미등록 층 낙사: actual_idx == fh_idx라도 즉시 밧줄로 이동
          fh_half_count = int(fh_zones[fh_idx].sweeps * 2)  # 강제 만료
          fh_last_side  = ""
          self._status(
              f"[층별] 미등록 층 낙사 Y={cy_now} → "
              f"'{fh_zones[fh_idx].name}' 즉시 복귀"
          )
  ```

- [ ] **Step 3: 봇 실행 후 확인**

  1. 좌표 탭에서 3층/4층만 구역 등록 (1-2층은 미등록)
  2. 봇 시작 → 캐릭터를 1층으로 강제 이동(낙사 또는 포탈)
  3. 상태창에 "미등록 층 낙사 Y=… → '3층' 즉시 복귀" 메시지 출력 확인
  4. 봇이 밧줄로 이동해 3층에 도달하는 것 확인

- [ ] **Step 4: 커밋**

  ```
  git add core/bot_loop.py
  git commit -m "fix: 미등록 층 낙사 시 즉시 밧줄 복귀 발동"
  ```

---

## Task 2: Config 스키마 — 아이템 수집 타이머

**Files:**
- Modify: `core/config_manager.py`

- [ ] **Step 1: 기본값 추가**

  `config_manager.py`에서 `DEFAULTS` dict를 찾아 `pickup_timer` 항목을 추가한다.

  ```python
  "pickup_timer": {
      "enabled":      False,
      "interval_sec": 110,      # 수집 주기 (초), 아이템 소멸 2분보다 10초 여유
      "pickup_key":   "z",      # 아이템 줍기 키
      "key_hold_sec": 1.5,      # 각 구역에서 픽업 키 유지 시간
      "route": [],              # [{to_zone: str, rope: str}, ...]
  },
  ```

- [ ] **Step 2: 커밋**

  ```
  git add core/config_manager.py
  git commit -m "feat: pickup_timer config 기본값 추가"
  ```

---

## Task 3: UI — 아이템 수집 타이머

**Files:**
- Modify: `ui/tab_coordinate.py`

수동 루트 그룹 바로 아래에 새 그룹 `_build_pickup_timer_group()`을 추가한다.

- [ ] **Step 1: `_build_pickup_timer_group()` 메서드 작성**

  `tab_coordinate.py`의 `_build_floor_hunt_group()` 메서드 아래에 삽입한다.

  ```python
  def _build_pickup_timer_group(self) -> QGroupBox:
      """아이템 수집 타이머 UI."""
      group = QGroupBox("아이템 수집 타이머")
      layout = QVBoxLayout(group)

      note = QLabel(
          "설정한 주기마다 사냥을 잠시 멈추고 수집 루트를 순회하며 아이템을 줍습니다.\n"
          "수집 루트는 아래에서 직접 지정하세요 (구역 + 밧줄 조합)."
      )
      note.setWordWrap(True)
      note.setStyleSheet("color: gray; font-size: 10px;")
      layout.addWidget(note)

      # 활성화 + 기본 설정
      row0 = QHBoxLayout()
      self.chk_pickup = QCheckBox("타이머 활성화")
      row0.addWidget(self.chk_pickup)
      row0.addStretch()
      layout.addLayout(row0)

      row1 = QHBoxLayout()
      row1.addWidget(QLabel("수집 주기"))
      self.spin_pickup_interval = QSpinBox()
      self.spin_pickup_interval.setRange(10, 600)
      self.spin_pickup_interval.setValue(110)
      self.spin_pickup_interval.setSuffix(" 초")
      self.spin_pickup_interval.setFixedWidth(80)
      row1.addWidget(self.spin_pickup_interval)

      row1.addSpacing(16)
      row1.addWidget(QLabel("픽업 키"))
      self.edit_pickup_key = QLineEdit("z")
      self.edit_pickup_key.setFixedWidth(45)
      row1.addWidget(self.edit_pickup_key)

      row1.addSpacing(16)
      row1.addWidget(QLabel("키 유지"))
      self.dspin_pickup_hold = QDoubleSpinBox()
      self.dspin_pickup_hold.setRange(0.1, 10.0)
      self.dspin_pickup_hold.setSingleStep(0.1)
      self.dspin_pickup_hold.setValue(1.5)
      self.dspin_pickup_hold.setSuffix(" 초")
      self.dspin_pickup_hold.setFixedWidth(75)
      row1.addWidget(self.dspin_pickup_hold)
      row1.addStretch()
      layout.addLayout(row1)

      # 수집 루트 (수동 루트와 동일 형식)
      layout.addWidget(QLabel("수집 루트 (순서대로 방문)"))

      list_row = QHBoxLayout()
      self.lst_pickup_route = QListWidget()
      self.lst_pickup_route.setMaximumHeight(100)
      list_row.addWidget(self.lst_pickup_route)

      btn_col = QVBoxLayout()
      btn_pu = QPushButton("↑"); btn_pu.setFixedSize(28, 32)
      btn_pd = QPushButton("↓"); btn_pd.setFixedSize(28, 32)
      btn_pu.clicked.connect(self._pickup_step_up)
      btn_pd.clicked.connect(self._pickup_step_down)
      btn_col.addWidget(btn_pu); btn_col.addWidget(btn_pd); btn_col.addStretch()
      list_row.addLayout(btn_col)
      layout.addLayout(list_row)

      add_row = QHBoxLayout()
      add_row.addWidget(QLabel("목적지"))
      self.cmb_pickup_zone = QComboBox()
      self.cmb_pickup_zone.setMinimumWidth(80)
      add_row.addWidget(self.cmb_pickup_zone)
      add_row.addWidget(QLabel("밧줄"))
      self.cmb_pickup_rope = QComboBox()
      self.cmb_pickup_rope.setMinimumWidth(80)
      add_row.addWidget(self.cmb_pickup_rope)
      btn_add_pu = QPushButton("+ 추가"); btn_add_pu.setFixedWidth(60)
      btn_del_pu = QPushButton("삭제");   btn_del_pu.setFixedWidth(50)
      btn_add_pu.clicked.connect(self._add_pickup_step)
      btn_del_pu.clicked.connect(self._del_pickup_step)
      add_row.addWidget(btn_add_pu); add_row.addWidget(btn_del_pu)
      add_row.addStretch()
      layout.addLayout(add_row)

      btn_row = QHBoxLayout()
      btn_row.addStretch()
      btn_save_pu = QPushButton("저장")
      btn_save_pu.setFixedWidth(55)
      btn_save_pu.clicked.connect(self._save_pickup_timer)
      btn_row.addWidget(btn_save_pu)
      layout.addLayout(btn_row)

      return group
  ```

- [ ] **Step 2: 수집 루트 조작 메서드 4개 추가**

  `_del_route_step` 메서드 아래에 추가한다.

  ```python
  def _add_pickup_step(self) -> None:
      to_zone = self.cmb_pickup_zone.currentText()
      rope    = self.cmb_pickup_rope.currentText()
      if to_zone and rope:
          self.lst_pickup_route.addItem(f"→ {to_zone}  (밧줄: {rope})")
          item = self.lst_pickup_route.item(self.lst_pickup_route.count() - 1)
          item.setData(Qt.ItemDataRole.UserRole, {"to_zone": to_zone, "rope": rope})

  def _del_pickup_step(self) -> None:
      row = self.lst_pickup_route.currentRow()
      if row >= 0:
          self.lst_pickup_route.takeItem(row)

  def _pickup_step_up(self) -> None:
      row = self.lst_pickup_route.currentRow()
      if row <= 0:
          return
      item = self.lst_pickup_route.takeItem(row)
      self.lst_pickup_route.insertItem(row - 1, item)
      self.lst_pickup_route.setCurrentRow(row - 1)

  def _pickup_step_down(self) -> None:
      row = self.lst_pickup_route.currentRow()
      if row < 0 or row >= self.lst_pickup_route.count() - 1:
          return
      item = self.lst_pickup_route.takeItem(row)
      self.lst_pickup_route.insertItem(row + 1, item)
      self.lst_pickup_route.setCurrentRow(row + 1)
  ```

- [ ] **Step 3: 저장/로드 메서드 추가**

  `_save_floor_hunt` 메서드 아래에 추가한다.

  ```python
  def _save_pickup_timer(self) -> None:
      route = []
      for i in range(self.lst_pickup_route.count()):
          data = self.lst_pickup_route.item(i).data(Qt.ItemDataRole.UserRole)
          if data:
              route.append(data)
      self.config.set("pickup_timer", "enabled",      self.chk_pickup.isChecked())
      self.config.set("pickup_timer", "interval_sec", self.spin_pickup_interval.value())
      self.config.set("pickup_timer", "pickup_key",   self.edit_pickup_key.text().strip() or "z")
      self.config.set("pickup_timer", "key_hold_sec", self.dspin_pickup_hold.value())
      self.config.set("pickup_timer", "route",        route)
      self.config.save()
  ```

- [ ] **Step 4: `_refresh_route_combos()`에 픽업 콤보 갱신 추가**

  기존 `_refresh_route_combos()` 메서드 끝에 두 줄 추가한다.

  ```python
  def _refresh_route_combos(self) -> None:
      """구역/밧줄 목록을 콤보박스에 채운다."""
      zones = self.config.get("zones") or []
      ropes = self.config.get("ropes") or []
      self.cmb_route_zone.clear()
      for z in sorted(zones, key=lambda x: x.get("name", "")):
          self.cmb_route_zone.addItem(z.get("name", ""))
      self.cmb_route_rope.clear()
      for r in ropes:
          self.cmb_route_rope.addItem(r.get("name", ""))
      # 픽업 타이머 콤보도 동일하게 갱신
      self.cmb_pickup_zone.clear()
      for z in sorted(zones, key=lambda x: x.get("name", "")):
          self.cmb_pickup_zone.addItem(z.get("name", ""))
      self.cmb_pickup_rope.clear()
      for r in ropes:
          self.cmb_pickup_rope.addItem(r.get("name", ""))
  ```

- [ ] **Step 5: `load_from_config()`에 픽업 타이머 로드 추가**

  `load_from_config()` 마지막 부분(루트 목록 복원 블록 아래)에 추가한다.

  ```python
  # 픽업 타이머 설정 로드
  pt = self.config.get("pickup_timer") or {}
  self.chk_pickup.setChecked(bool(pt.get("enabled", False)))
  self.spin_pickup_interval.setValue(int(pt.get("interval_sec", 110)))
  self.edit_pickup_key.setText(pt.get("pickup_key", "z"))
  self.dspin_pickup_hold.setValue(float(pt.get("key_hold_sec", 1.5)))
  self.lst_pickup_route.clear()
  for step in pt.get("route", []):
      to_zone = step.get("to_zone", "")
      rope    = step.get("rope", "")
      self.lst_pickup_route.addItem(f"→ {to_zone}  (밧줄: {rope})")
      item = self.lst_pickup_route.item(self.lst_pickup_route.count() - 1)
      item.setData(Qt.ItemDataRole.UserRole, step)
  ```

- [ ] **Step 6: `_build_floor_hunt_group()` 호출 아래에 픽업 그룹 추가**

  `_build_floor_hunt_group()` 빌드 후 `layout.addWidget(...)` 하는 곳(`__init__`의 `layout.addWidget(self._build_floor_hunt_group())`)을 찾아 그 다음 줄에 추가:

  ```python
  layout.addWidget(self._build_floor_hunt_group())
  layout.addWidget(self._build_pickup_timer_group())   # 추가
  ```

- [ ] **Step 7: 커밋**

  ```
  git add ui/tab_coordinate.py
  git commit -m "feat: 아이템 수집 타이머 UI 추가"
  ```

---

## Task 4: bot_loop.py — 픽업 타이머 실행

**Files:**
- Modify: `core/bot_loop.py`

픽업 타이머는 층별 사냥 상태머신에 `"pickup_nav"` 상태를 추가해 구현한다.
기존 `to_rope` / `climbing` 핸들러를 재사용하므로 코드 중복이 없다.

- [ ] **Step 1: 상태 변수 초기화 추가**

  `_run()` 메서드의 상태 변수 선언 블록(fh_state, fh_rope_x 등이 있는 곳)에 아래를 추가한다.

  ```python
  # ── 픽업 타이머 상태 변수 ──────────────────────────────────────
  pu_enabled       = False
  pu_interval      = 110.0
  pu_key           = "z"
  pu_hold_sec      = 1.5
  pu_route: list   = []
  pu_step_idx      = 0          # 현재 픽업 루트 단계
  pu_prev_fh_state = "patrol"  # 픽업 완료 후 복원할 상태
  pu_prev_fh_idx   = 0         # 픽업 완료 후 복원할 구역 인덱스
  last_pickup_time = time.time()
  pu_active        = False      # 픽업 루틴 실행 중 여부
  pu_arrived       = False      # 현재 픽업 구역 도착 여부
  ```

- [ ] **Step 2: 픽업 설정 로드**

  `if use_floor_hunt:` 블록이 끝나는 줄 바로 뒤에 추가한다.

  ```python
  # 픽업 타이머 설정 로드
  _pt = self._config.get("pickup_timer") or {}
  pu_enabled  = bool(_pt.get("enabled", False))
  pu_interval = float(_pt.get("interval_sec", 110))
  pu_key      = _pt.get("pickup_key", "z") or "z"
  pu_hold_sec = float(_pt.get("key_hold_sec", 1.5))
  pu_route    = _pt.get("route", [])   # [{to_zone, rope}, ...]
  ```

- [ ] **Step 3: 픽업 타이머 발동 체크 추가**

  메인 루프의 `while not self._stop_event.is_set():` 블록 안, 안전 감지 블록(`if now - last_safety >= SAFETY_CHECK_INTERVAL:`) 바로 아래에 추가한다.

  ```python
  # ── 픽업 타이머 발동 체크 ──────────────────────────────────
  if (use_floor_hunt and pu_enabled and not pu_active
          and pu_route and fh_state == "patrol"
          and now - last_pickup_time >= pu_interval):
      pu_active        = True
      pu_step_idx      = 0
      pu_arrived       = False
      pu_prev_fh_idx   = fh_idx
      pu_prev_fh_state = "patrol"
      # 픽업 루트 첫 번째 목적지로 이동 시작
      step    = pu_route[0]
      to_name = step.get("to_zone", "")
      rp_name = step.get("rope", "")
      ropes   = self._map_navigator.ropes
      to_zone = next((z for z in fh_zones if z.name == to_name), None)
      rp      = next((r for r in ropes if r.name == rp_name), None)
      if to_zone and rp:
          fh_rope_x    = rp.x
          fh_climb_sec = rp.climb_sec
          fh_next_idx  = fh_zones.index(to_zone)
          fh_next_dir  = 1 if to_zone.y_min < fh_zones[fh_idx].y_min else -1
          fh_state     = "to_rope"
          fh_half_count = 0
          fh_last_side  = ""
          self._map_navigator.release_direction()
          self._status(f"🎒 픽업 타이머 발동 → {to_name}")
      else:
          pu_active = False
          self._status(f"⚠ 픽업 루트 오류: '{to_name}' 또는 '{rp_name}' 미발견")
  ```

- [ ] **Step 4: 픽업 도착 처리 — climbing 상태에서 도착 시 픽업 키 입력**

  기존 `if arrived:` 블록(`fh_state = "patrol"` 으로 전환하는 곳) 안에 픽업 처리를 끼워넣는다.

  기존 코드:
  ```python
  if arrived:
      fh_idx        = fh_next_idx
      fh_state      = "patrol"
      fh_last_side  = ""
      fh_arrive_time = time.time()
      self._map_navigator.set_zones([fh_zones[fh_idx]])
      self._status(f"[층별] {fh_zones[fh_idx].name} 사냥 시작")
      _apply_zone_pattern(fh_zones[fh_idx])
  ```

  변경 후:
  ```python
  if arrived:
      fh_idx        = fh_next_idx
      fh_state      = "patrol"
      fh_last_side  = ""
      fh_arrive_time = time.time()
      self._map_navigator.set_zones([fh_zones[fh_idx]])
      _apply_zone_pattern(fh_zones[fh_idx])

      if pu_active:
          # 픽업 구역 도착 → 픽업 키 입력
          self._status(f"🎒 {fh_zones[fh_idx].name} 픽업 중...")
          self._input.press_key(pu_key, hold_sec=pu_hold_sec)
          time.sleep(0.2)
          pu_step_idx += 1

          if pu_step_idx < len(pu_route):
              # 다음 픽업 구역으로 이동
              step    = pu_route[pu_step_idx]
              to_name = step.get("to_zone", "")
              rp_name = step.get("rope", "")
              ropes   = self._map_navigator.ropes
              to_zone = next((z for z in fh_zones if z.name == to_name), None)
              rp      = next((r for r in ropes if r.name == rp_name), None)
              if to_zone and rp:
                  fh_rope_x    = rp.x
                  fh_climb_sec = rp.climb_sec
                  fh_next_idx  = fh_zones.index(to_zone)
                  fh_next_dir  = 1 if to_zone.y_min < fh_zones[fh_idx].y_min else -1
                  fh_state     = "to_rope"
                  fh_half_count = 0
                  fh_last_side  = ""
                  self._map_navigator.release_direction()
                  self._status(f"🎒 다음 픽업 구역 → {to_name}")
              else:
                  # 오류 → 픽업 종료
                  pu_active        = False
                  last_pickup_time = time.time()
                  self._status(f"⚠ 픽업 루트 오류 → 사냥 재개")
          else:
              # 모든 픽업 구역 완료 → 원래 사냥 구역 복귀
              pu_active        = False
              last_pickup_time = time.time()
              origin_zone = fh_zones[pu_prev_fh_idx]
              ropes = self._map_navigator.ropes
              rp_origin = next((r for r in ropes if r.name == pu_route[-1].get("rope", "")), None)
              if rp_origin and pu_prev_fh_idx != fh_idx:
                  fh_rope_x    = rp_origin.x
                  fh_climb_sec = rp_origin.climb_sec
                  fh_next_idx  = pu_prev_fh_idx
                  fh_next_dir  = 1 if origin_zone.y_min < fh_zones[fh_idx].y_min else -1
                  fh_state     = "to_rope"
                  fh_half_count = 0
                  fh_last_side  = ""
                  self._map_navigator.release_direction()
                  self._status(f"🎒 픽업 완료 → '{origin_zone.name}' 복귀")
              else:
                  self._map_navigator.set_zones([fh_zones[fh_idx]])
                  self._status(f"🎒 픽업 완료 — 사냥 재개")
      else:
          self._status(f"[층별] {fh_zones[fh_idx].name} 사냥 시작")
  ```

- [ ] **Step 5: 봇 실행 후 확인**

  1. 좌표 탭 → 아이템 수집 타이머 → 수집 주기 20초로 설정 (테스트용)
  2. 픽업 루트: 2층 → 3층 등록
  3. 봇 시작 → 20초 후 상태창에 "🎒 픽업 타이머 발동 → 2층" 출력 확인
  4. 2층 도착 후 Z키 누름 확인 → 3층 이동 → 픽업 → 원래 층 복귀 확인
  5. 타이머 초기화(타이머가 다시 카운트 시작) 확인

- [ ] **Step 6: 커밋**

  ```
  git add core/bot_loop.py
  git commit -m "feat: 아이템 수집 타이머 실행 로직 추가"
  ```

---

## Self-Review

**Spec coverage:**
- [x] 낙사 복귀 버그 수정 (Task 1)
- [x] Config 스키마 (Task 2)
- [x] UI (Task 3)
- [x] 실행 로직 (Task 4)

**Placeholder scan:**
- Task 4 Step 4의 "원래 사냥 구역 복귀" — 마지막 픽업 밧줄을 역방향으로 쓰는 방식. 픽업 루트가 단방향(예: 2층→3층)일 때 3층에서 사냥하던 구역으로 복귀하는 게 자연스러움. 설정에 "복귀 구역"을 따로 두지 않고 `pu_prev_fh_idx`로 원래 구역으로 돌아가는 설계는 YAGNI 원칙 준수.

**Type consistency:**
- `pu_route` 형식이 기존 `fh_route`와 동일한 `[{to_zone: str, rope: str}]` → 일관성 있음.
- `fh_zones`, `fh_rope_x`, `fh_climb_sec`, `fh_next_idx`, `fh_next_dir`, `fh_state` 변수명 모두 기존 상태머신과 동일하게 재사용 → 타입 충돌 없음.
