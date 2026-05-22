# 화면 인식 → 판단 → 입력을 반복하는 봇 메인 루프 (별도 스레드로 실행)
import os
import time
import random
import threading
import logging
from typing import Callable

from core.screen_reader import ScreenReader
from core.input_controller import InputController
from core.config_manager import ConfigManager
from core.detector import Detector
from core.hunter import Hunter
from core.key_hunter import KeyHunter
from core.minimap_reader import MinimapReader, MinimapConfig, Zone, RopePoint
from core.map_navigator import MapNavigator
from core.potion_manager import PotionManager
from core.pattern import HuntPattern, KeyPattern
from core.floor_hunter import FloorHunter

logger = logging.getLogger(__name__)

TEMPLATES = {
    "lie_detector":      "templates/lie_detector.png",
    "transparent_shape": "templates/transparent_shape_title.png",
    "player_on_map":     "templates/player_on_map.png",
    "level_up":          "templates/level_up.png",
    "dead":              "templates/dead.png",
}

SAFETY_CHECK_INTERVAL = 1.0   # 화면 캡처 기반 안전 감지 주기 (초)
POTION_CHECK_INTERVAL = 0.5   # 포션 체크 주기 (초) — 전용 스레드에서 독립 실행


class BotLoop:
    def __init__(self, config: ConfigManager, on_status: Callable[[str], None] | None = None):
        self._config = config
        self._on_status  = on_status or (lambda msg: None)
        self._on_stop_cb: Callable[[], None] = lambda: None          # 내부 정지 시 UI 알림 콜백
        self._on_lie_log: Callable[[str], None] = lambda msg: None   # 거탐 상세 로그 콜백
        self._screen = ScreenReader()
        window_title = config.get("settings2", "game_window_title") or "MapleStory"
        self._input = InputController(window_title=window_title)
        self._detector = Detector(self._screen, config)

        self._hunter = Hunter(
            input_ctrl=self._input,
            detector=self._detector,
            screen_reader=self._screen,
            on_status=self._status,
        )
        self._key_hunter = KeyHunter(
            input_ctrl=self._input,
            on_status=self._status,
        )
        self._minimap_reader = MinimapReader(self._screen)
        self._map_navigator = MapNavigator(
            minimap_reader=self._minimap_reader,
            input_ctrl=self._input,
            detector=self._detector,
            on_status=self._status,
        )
        self._potion_manager = PotionManager(
            input_ctrl=self._input,
            detector=self._detector,
            on_status=self._status,
        )

        self._floor_hunter = FloorHunter(self._input, on_status=self._status)

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._potion_thread: threading.Thread | None = None
        self._floor_hunt_thread: threading.Thread | None = None
        self._last_user_chat_time = 0.0
        self._chat_msg_index = 0

        # 모듈별 활성화 플래그
        self._enable_attack     = True
        self._enable_move       = True
        self._enable_potion     = True
        self._enable_lie_notify = True   # 거탐 알림 (경보음 + 텔레그램)
        self._enable_lie_solve  = True   # 거탐 해제 (퍼즐 자동 풀기)
        self._enable_transparent_shape = True  # 투명 도형 찾기 자동 해제
        self._transparent_game  = None   # lazy init: TransparentShapeGame
        self._anti_mob_active   = False  # 방지몹 해제 중 재진입 방지

    def _game_window_title(self) -> str:
        """config에서 게임 창 제목을 읽는다. 미설정이면 'MapleStory' 반환."""
        return self._config.get("settings2", "game_window_title") or "MapleStory"

    def set_on_stop(self, cb: Callable[[], None]) -> None:
        """봇이 내부적으로 정지될 때 UI에 알리는 콜백을 등록한다 (예: 이탈 감지 자동 정지)."""
        self._on_stop_cb = cb

    def set_lie_log(self, cb: Callable[[str], None]) -> None:
        """거짓말탐지기 상세 로그 콜백을 등록한다."""
        self._on_lie_log = cb

    def _lie_log(self, msg: str) -> None:
        """거짓말탐지기 상세 로그 전송 (일반 상태창과 별도)."""
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self._on_lie_log(f"[{ts}] {msg}")

    # ── 외부 제어 ─────────────────────────────────────────────────────
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._load_patterns()
        self._stop_event.clear()
        # 메인 루프 (이동 + 스킬)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        # 포션 전용 스레드 — 스킬 블로킹과 완전히 분리
        self._potion_thread = threading.Thread(target=self._potion_loop, daemon=True)
        self._potion_thread.start()
        self._status("봇 시작됨")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)
        if self._potion_thread:
            self._potion_thread.join(timeout=2)
        self._status("봇 정지됨")

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def set_modules(self, attack: bool = True, move: bool = True,
                    potion: bool = True,
                    lie_notify: bool = True, lie_solve: bool = True,
                    transparent_shape: bool = True) -> None:
        """모듈별 활성화 여부를 설정한다. 봇 실행 중에도 적용된다."""
        self._enable_attack            = attack
        self._enable_move              = move
        self._enable_potion            = potion
        self._enable_lie_notify        = lie_notify
        self._enable_lie_solve         = lie_solve
        self._enable_transparent_shape = transparent_shape

    def reload_pattern(self) -> None:
        self._load_patterns()

    # ── 패턴 로드 ─────────────────────────────────────────────────────
    def _load_patterns(self) -> None:
        # 게임 창 제목 동기화 (설정2에서 변경 시 바로 반영)
        self._input._window_title = self._game_window_title()
        # 활성 사냥터 프리셋 우선 로드, 없으면 레거시 키 사용
        active = self._config.get("hunt_grounds", "active") or ""
        presets = self._config.get("hunt_grounds", "presets") or {}
        preset = presets.get(active) if active else None

        # 공격 설정은 공격 탭에서 통합 관리
        atk_cfg = self._config.get("attack") or {}
        attack_key         = atk_cfg.get("key",               "ctrl")
        monster_tpl        = atk_cfg.get("monster_template",  "")
        jump_before_attack = atk_cfg.get("jump_before_attack", False)

        if preset:
            mm = preset.get("minimap", {})
            raw_zones = preset.get("zones", [])
            raw_ropes = preset.get("ropes", [])
            self._status(f"프리셋 로드: {active}")
        else:
            mm = self._config.get("minimap") or {}
            raw_zones = self._config.get("zones") or []
            raw_ropes = self._config.get("ropes") or []

        cfg = MinimapConfig(
            region_x=mm.get("region_x", 0), region_y=mm.get("region_y", 0),
            width=mm.get("width", 200), height=mm.get("height", 120),
            char_r=mm.get("char_r", 255), char_g=mm.get("char_g", 255),
            char_b=mm.get("char_b", 255), tolerance=mm.get("tolerance", 40),
            jump_key=mm.get("jump_key", "alt"),
        )
        self._minimap_reader.set_config(cfg)

        zones = [Zone.from_dict(z) for z in raw_zones]
        ropes = [RopePoint.from_dict(r) for r in raw_ropes]
        self._map_navigator.set_zones(zones)
        self._map_navigator.set_ropes(ropes)
        self._map_navigator.set_attack(
            key=attack_key,
            monster_template=monster_tpl,
            jump_before_attack=jump_before_attack,
        )

        if zones:
            self._status(f"구역 로드: {len(zones)}개  밧줄: {len(ropes)}개")

        # 포션 매니저 설정 로드
        hp_potion = self._config.get("recovery", "hp_potion") or {}
        mp_potion = self._config.get("recovery", "mp_potion") or {}
        self._potion_manager.set_config(hp_potion, mp_potion)

        # 키 반복 패턴
        raw_key = self._config.get("key_patterns", "active")
        if raw_key:
            try:
                kp = KeyPattern.from_dict(raw_key)
                self._key_hunter.set_pattern(kp)
                self._status(f"키 패턴 로드: {kp.name} ({len(kp.steps)}스텝)")
            except Exception as exc:
                logger.warning("키 패턴 로드 실패: %s", exc)

        # 이미지 인식 패턴
        raw_img = self._config.get("patterns", "active")
        if raw_img:
            try:
                hp = HuntPattern.from_dict(raw_img)
                self._hunter.set_pattern(hp)
                self._status(f"이미지 패턴 로드: {hp.name} ({len(hp.steps)}스텝)")
            except Exception as exc:
                logger.warning("이미지 패턴 로드 실패: %s", exc)

    # ── 메인 루프 (이동 + 스킬) ──────────────────────────────────────
    def _run(self) -> None:
        logger.info("봇 루프 시작")

        # 층별 핑퐁 사냥 모드 — 구역을 이름순으로 순환
        floor_cfg      = self._config.get("floor_hunt") or {}
        use_floor_hunt = bool(floor_cfg.get("enabled", False))

        # 층별 사냥 상태 변수
        fh_zones:       list  = []       # 이름순 정렬된 Zone 목록
        fh_idx:         int   = 0
        fh_dir:         int   = 1        # +1 = 위층, -1 = 아래층 (자동 모드)
        fh_half_count:  int   = 0        # 경계(left/right) 도달 횟수
        fh_last_side:   str   = ""       # 마지막 도달 경계
        fh_state:       str   = "patrol" # "patrol" | "to_rope" | "climbing"
        fh_rope_x:      int   = 0        # 이동할 밧줄 X 좌표
        fh_next_idx:    int   = 0        # 전환 후 목적 층 인덱스
        fh_next_dir:    int   = 1        # 전환 시 이동 방향 (+1=위, -1=아래)
        fh_climb_start: float = 0.0      # 오르기/내려가기 시작 시각
        fh_climb_sec:   float = 2.5      # 현재 밧줄의 오르기 시간 (밧줄별 설정)
        fh_arrive_time: float = 0.0      # 도착 확인 시각 (Y 감지 쿨다운 기준)
        fh_rope_escape_time: float = 0.0 # 밧줄 탈출 마지막 시각 (스팸 방지)
        FH_DESCEND_SEC  = 0.3            # 내려가기 완료 후 대기 시간 (초)
        FH_ROPE_ESCAPE_INTERVAL = 0.5    # 밧줄 탈출 시도 최소 간격 (초)
        fh_route:       list  = []       # 커스텀 루트 [{to_zone, rope}, ...]
        fh_route_idx:   int   = 0        # 현재 루트 단계
        fh_route_mode:  bool  = False    # True=커스텀 루트, False=자동 왕복
        FH_ROPE_EDGE    = 8              # 밧줄 도달 판정 픽셀
        FH_CLIMB_SEC    = 2.5            # UP 키 유지 시간 (초)
        FH_Y_COOLDOWN   = 4.0            # 도착 후 Y 감지 비활성 시간 (초)

        # 층별 패턴 프리셋 (key_patterns.presets)
        kp_presets: dict = self._config.get("key_patterns", "presets") or {}
        # 기본 패턴 (층별 패턴 미설정 시 복원용)
        kp_default_raw = self._config.get("key_patterns", "active")

        def _apply_zone_pattern(zone) -> None:
            """구역의 key_pattern 프리셋을 KeyHunter에 적용. 빈 문자열이면 기본 패턴 복원."""
            from core.pattern import KeyPattern as _KP
            pname = zone.key_pattern if zone else ""
            if pname and pname in kp_presets:
                try:
                    kp = _KP.from_dict(kp_presets[pname])
                    self._key_hunter.set_pattern(kp)
                    self._status(f"[층별] 공격 패턴 → {pname}")
                    return
                except Exception as exc:
                    logger.warning("층별 패턴 로드 실패 (%s): %s", pname, exc)
            # 기본 패턴 복원
            if kp_default_raw:
                try:
                    kp = _KP.from_dict(kp_default_raw)
                    self._key_hunter.set_pattern(kp)
                    if pname:
                        self._status(f"[층별] 패턴 '{pname}' 미발견 → 기본 패턴 사용")
                except Exception:
                    pass

        if use_floor_hunt:
            # 프리셋 우선, 없으면 레거시 키 사용 (_load_patterns와 동일 로직)
            _fh_active  = self._config.get("hunt_grounds", "active") or ""
            _fh_presets = self._config.get("hunt_grounds", "presets") or {}
            _fh_preset  = _fh_presets.get(_fh_active) if _fh_active else None
            raw_zones = _fh_preset.get("zones", []) if _fh_preset else (self._config.get("zones") or [])
            from core.minimap_reader import Zone as _Zone
            all_zones = [_Zone.from_dict(z) for z in raw_zones]
            fh_zones = sorted(all_zones, key=lambda z: z.name)
            fh_cfg = self._config.get("floor_hunt") or {}
            fh_route_mode = bool(fh_cfg.get("route_mode", False))
            fh_route = fh_cfg.get("route", [])
            if fh_zones:
                self._map_navigator.set_zones([fh_zones[0]])
                mode_str = "커스텀 루트" if fh_route_mode else "자동 왕복"
                self._status(f"[층별] {fh_zones[0].name} 사냥 시작 [{mode_str}]")
                _apply_zone_pattern(fh_zones[0])  # 시작 층 패턴 적용
            else:
                self._status("⚠ [층별] 구역이 없습니다 — 좌표 탭에서 구역을 먼저 추가하세요.")

        last_safety      = 0.0
        last_focus       = 0.0
        last_potion_cnt  = 0.0
        FOCUS_INTERVAL        = 4.0
        POTION_CNT_INTERVAL   = 30.0   # 포션 수량 체크 주기 (초)
        self._map_exit_fail = 0  # 사냥터 이탈 감지 연속 불일치 카운터
        try:
            while not self._stop_event.is_set():
                try:
                    now = time.time()

                    # 게임 창 포커스 유지
                    if self._enable_move and now - last_focus >= FOCUS_INTERVAL:
                        self._map_navigator.release_direction()
                        self._input.focus_game_window()
                        last_focus = now

                    # 안전 감지 (화면 캡처)
                    if now - last_safety >= SAFETY_CHECK_INTERVAL:
                        screenshot = self._screen.capture()
                        last_safety = now
                        if (self._enable_lie_notify or self._enable_lie_solve) and self._check_lie_detector(screenshot):
                            if use_floor_hunt:
                                fh_last_side = ""   # 거탐 해제 후 직전 방향 무효화
                                if fh_state != "patrol":  # 층 이동 중이었다면 순찰로 복귀
                                    self._input.key_up("up")
                                    self._map_navigator.release_direction()
                                    fh_state = "patrol"
                            continue
                        if self._enable_transparent_shape and self._check_transparent_shape(screenshot):
                            if use_floor_hunt:
                                fh_last_side = ""
                                if fh_state != "patrol":
                                    self._input.key_up("up")
                                    self._map_navigator.release_direction()
                                    fh_state = "patrol"
                            continue
                        if self._check_dead(screenshot):
                            continue
                        self._check_user_on_map(screenshot)
                        self._check_level_up(screenshot)
                        # 사냥터 이탈 감지 (미니맵 이름 이미지 비교 기반)
                        self._check_map_exit()
                        # 매크로방지몹 감지
                        if not self._anti_mob_active:
                            self._check_anti_mob(screenshot)

                    # 포션 수량 체크 (30초마다)
                    if now - last_potion_cnt >= POTION_CNT_INTERVAL:
                        last_potion_cnt = now
                        self._check_potion_count()

                    # 층별 핑퐁 상태머신
                    if use_floor_hunt and fh_zones:
                        # Y 좌표로 현재 층을 판별하는 헬퍼 — 항상 먼저 정의
                        def _zone_by_y(y: int):
                            for z in fh_zones:
                                if z.y_min <= y <= z.y_max:
                                    return z
                            return min(
                                fh_zones,
                                key=lambda z: min(
                                    abs(y - z.y_min), abs(y - z.y_max)
                                ),
                            )

                        pos = self._minimap_reader.get_character_pos()

                        if fh_state == "to_rope":
                            # ── 밧줄로 이동 중 ─────────────────────────
                            if pos is not None:
                                cx = pos[0]
                                if abs(cx - fh_rope_x) <= FH_ROPE_EDGE:
                                    # 밧줄 도달 → 점프/내려가기 실행
                                    jump_key = self._minimap_reader.config.jump_key or "alt"
                                    self._map_navigator.release_direction()
                                    if fh_next_dir > 0:        # 위층으로
                                        # 방향키 없이 점프+UP — 방향키를 누르면
                                        # 옆으로 점프해 밧줄을 놓침
                                        self._input.press_key(jump_key, hold_sec=0.12)
                                        time.sleep(0.10)
                                        self._input.key_down("up")
                                    else:                       # 아래층으로
                                        self._input.key_down("down")
                                        time.sleep(0.06)
                                        self._input.press_key(jump_key, hold_sec=0.12)
                                        self._input.key_up("down")
                                    fh_climb_start = time.time()
                                    fh_state = "climbing"
                                    # fh_idx는 Y 확인 후 업데이트 (미도착 시 재시도 대비)
                                    self._map_navigator.set_zones([fh_zones[fh_next_idx]])
                                    self._status(f"[층별] → {fh_zones[fh_next_idx].name} 이동 중")
                                else:
                                    self._map_navigator.walk_toward(fh_rope_x, cx)

                        elif fh_state == "climbing":
                            # ── 오르기 / 내려가기 대기 ────────────────
                            if fh_next_dir > 0:
                                # UP만 유지 — 방향키를 누르면 옆으로 이동해 밧줄을 놓침
                                self._input.key_down("up")
                            elif (pos is not None
                                    and time.time() - fh_rope_escape_time >= FH_ROPE_ESCAPE_INTERVAL):
                                # 내려가는 중 밧줄에 걸린 경우 탈출 시도
                                # fh_rope_x 는 방금 뛰어내린 밧줄이므로 제외 (to_rope 상태에서 처리)
                                _jk = self._minimap_reader.config.jump_key or "alt"
                                for _rp in self._map_navigator.ropes:
                                    if _rp.x != fh_rope_x and abs(pos[0] - _rp.x) <= 3:
                                        _esc = _rp.approach if _rp.approach in ("left", "right") else "left"
                                        self._map_navigator.release_direction()
                                        self._input.key_down(_esc)
                                        self._input.press_key(_jk, hold_sec=0.12)
                                        self._input.key_up(_esc)
                                        fh_rope_escape_time = time.time()
                                        self._status(
                                            f"[층별] 하강 중 밧줄 X={_rp.x} 감지 "
                                            f"→ {_esc}+점프 탈출"
                                        )
                                        break
                            elapsed = time.time() - fh_climb_start
                            wait_sec = fh_climb_sec if fh_next_dir > 0 else FH_DESCEND_SEC
                            if elapsed >= wait_sec:
                                self._input.key_up("up")
                                self._map_navigator.release_direction()

                                # Y 좌표로 실제 도착 여부 확인
                                target_zone = fh_zones[fh_next_idx]
                                src_zone    = fh_zones[fh_idx]
                                Y_TOL = 12   # 허용 오차 (px)
                                arrived = False
                                if pos is not None:
                                    cy = pos[1]
                                    # 내려가기(Y 증가): 목표보다 더 아래로 떨어지면 오인식 방지
                                    # 올라가기(Y 감소): 목표보다 더 위로 올라가면 오인식 방지
                                    if fh_next_dir < 0:
                                        in_target = (target_zone.y_min - Y_TOL <= cy <= target_zone.y_max)
                                    else:
                                        in_target = (target_zone.y_min <= cy <= target_zone.y_max + Y_TOL)
                                    left_source = not (src_zone.y_min - 5 <= cy <= src_zone.y_max + 5)
                                    arrived = in_target and left_source
                                    self._status(
                                        f"[층별] Y={cy} 확인 "
                                        f"목표 {target_zone.y_min}~{target_zone.y_max} "
                                        f"출발층 이탈={'✓' if left_source else '✗'} "
                                        f"→ {'✓ 도착' if arrived else '✗ 실패'}"
                                    )
                                if arrived:
                                    fh_idx        = fh_next_idx
                                    fh_state      = "patrol"
                                    fh_last_side  = ""
                                    fh_arrive_time = time.time()   # Y 감지 쿨다운 시작
                                    self._map_navigator.set_zones([fh_zones[fh_idx]])
                                    self._status(f"[층별] {fh_zones[fh_idx].name} 사냥 시작")
                                    _apply_zone_pattern(fh_zones[fh_idx])  # 층 도착 시 패턴 교체
                                else:
                                    # 도착 실패 → 실제 Y 위치로 현재 층 재판별
                                    if pos is not None:
                                        actual_zone = _zone_by_y(pos[1])
                                        actual_idx  = fh_zones.index(actual_zone)
                                    else:
                                        actual_idx  = fh_idx
                                    if actual_idx != fh_idx:
                                        # 낙사/피격으로 다른 층에 있음 → 실제 층 순찰 복귀
                                        fh_idx         = actual_idx
                                        fh_state       = "patrol"
                                        fh_arrive_time = time.time()
                                        fh_half_count  = 0
                                        fh_last_side   = ""
                                        fh_route_idx   = 0
                                        self._map_navigator.set_zones([fh_zones[fh_idx]])
                                        self._status(
                                            f"[층별] 낙사/이탈 감지 → '{fh_zones[fh_idx].name}' 복귀"
                                        )
                                        _apply_zone_pattern(fh_zones[fh_idx])
                                    else:
                                        # 같은 층에서 밧줄 재시도
                                        self._map_navigator.set_zones([fh_zones[fh_idx]])
                                        fh_state = "to_rope"
                                        self._status(
                                            f"[층별] {target_zone.name} 도착 실패 → 재시도"
                                        )

                        else:  # patrol
                            # ── 낙사/피격 감지: X 또는 Y가 현재 구역 밖이면 복귀 ──
                            if pos is not None and (
                                time.time() - fh_arrive_time >= FH_Y_COOLDOWN
                            ):
                                cur_zone  = fh_zones[fh_idx]
                                x_in_zone = (
                                    cur_zone.left_x - 5 <= pos[0] <= cur_zone.right_x + 5
                                )
                                y_in_zone = (
                                    cur_zone.y_min - 8 <= pos[1] <= cur_zone.y_max + 8
                                )
                                if not x_in_zone or not y_in_zone:
                                    cy_now = pos[1]
                                    actual_zone = _zone_by_y(cy_now)
                                    actual_idx  = fh_zones.index(actual_zone)
                                    reason = ("X범위 이탈" if not x_in_zone else "낙사(Y 이탈)")
                                    if actual_idx != fh_idx:
                                        fh_idx        = actual_idx
                                        fh_half_count = 0
                                        fh_last_side  = ""
                                        fh_route_idx  = 0   # 루트도 초기화
                                        fh_arrive_time = time.time()
                                        self._map_navigator.set_zones([fh_zones[fh_idx]])
                                        self._status(
                                            f"[층별] {reason} Y={cy_now} → "
                                            f"'{fh_zones[fh_idx].name}' 복귀"
                                        )
                                        _apply_zone_pattern(fh_zones[fh_idx])  # 복귀 층 패턴 교체

                            # ── 왕복 횟수 카운트 ──────────────────────
                            zone = fh_zones[fh_idx]

                            # sweeps=0: 통과 모드 — 도착 0.5초 후 즉시 밧줄로 이동 (순찰/공격 없음)
                            _transit = zone.sweeps == 0
                            if _transit and time.time() - fh_arrive_time >= 0.5:
                                self._status(f"[층별] {zone.name} 통과 → 다음 층으로")
                                ropes = self._map_navigator.ropes
                                _transit_moved = False
                                if fh_route_mode and fh_route:
                                    step    = fh_route[fh_route_idx % len(fh_route)]
                                    to_name = step.get("to_zone", "")
                                    rp_name = step.get("rope", "")
                                    to_zone = next((z for z in fh_zones if z.name == to_name), None)
                                    rp      = next((r for r in ropes if r.name == rp_name), None)
                                    if to_zone and rp:
                                        fh_rope_x    = rp.x
                                        fh_climb_sec = rp.climb_sec
                                        fh_next_idx  = fh_zones.index(to_zone)
                                        fh_next_dir  = 1 if to_zone.y_min < zone.y_min else -1
                                        fh_state     = "to_rope"
                                        fh_half_count = 0
                                        fh_last_side  = ""
                                        fh_route_idx += 1
                                        self._map_navigator.release_direction()
                                        _transit_moved = True
                                if not _transit_moved:
                                    n        = len(fh_zones)
                                    # 통과 구역에서 낙사 복귀: 가장 가까운 사냥 구역(sweeps>0) 방향 강제
                                    hunt_indices = [i for i, z in enumerate(fh_zones) if z.sweeps > 0]
                                    if hunt_indices:
                                        nearest_hunt = min(hunt_indices, key=lambda i: abs(i - fh_idx))
                                        if nearest_hunt != fh_idx:
                                            fh_dir = 1 if nearest_hunt > fh_idx else -1
                                    next_idx = fh_idx + fh_dir
                                    if next_idx >= n:
                                        fh_dir   = -1
                                        next_idx = fh_idx - 1
                                    elif next_idx < 0:
                                        fh_dir   = 1
                                        next_idx = fh_idx + 1
                                    if 0 <= next_idx < n and next_idx != fh_idx:
                                        if zone.rope_x >= 0:
                                            fh_rope_x    = zone.rope_x
                                            matched_r    = next((r for r in ropes if r.x == zone.rope_x), None)
                                            fh_climb_sec = matched_r.climb_sec if matched_r else 2.5
                                        elif ropes:
                                            rp_auto      = ropes[min(fh_idx, len(ropes) - 1)]
                                            fh_rope_x    = rp_auto.x
                                            fh_climb_sec = rp_auto.climb_sec
                                        else:
                                            fh_rope_x    = zone.right_x
                                            fh_climb_sec = 2.5
                                        fh_next_idx   = next_idx
                                        fh_next_dir   = fh_dir
                                        fh_state      = "to_rope"
                                        fh_half_count = 0
                                        fh_last_side  = ""
                                        self._map_navigator.release_direction()

                            if not _transit and pos is not None:
                                cx = pos[0]
                                EDGE = 4
                                if cx <= zone.left_x + EDGE:
                                    side = "left"
                                elif cx >= zone.right_x - EDGE:
                                    side = "right"
                                else:
                                    side = ""

                                if side and side != fh_last_side:
                                    fh_last_side   = side
                                    fh_half_count += 1
                                    target     = int(zone.sweeps * 2)
                                    self._status(
                                        f"[층별] {zone.name} 경계({side}) "
                                        f"{fh_half_count}/{target}회"
                                    )
                                    if fh_half_count >= target:
                                        ropes = self._map_navigator.ropes

                                        if fh_route_mode and fh_route:
                                            # ── 커스텀 루트 ──────────────
                                            step = fh_route[fh_route_idx % len(fh_route)]
                                            to_name  = step.get("to_zone", "")
                                            rp_name  = step.get("rope", "")
                                            to_zone  = next(
                                                (z for z in fh_zones if z.name == to_name), None
                                            )
                                            rp = next(
                                                (r for r in ropes if r.name == rp_name), None
                                            )
                                            if to_zone and rp:
                                                fh_rope_x    = rp.x
                                                fh_climb_sec = rp.climb_sec
                                                fh_next_idx  = fh_zones.index(to_zone)
                                                fh_next_dir  = (
                                                    1 if to_zone.y_min < zone.y_min else -1
                                                )
                                                fh_state      = "to_rope"
                                                fh_half_count = 0
                                                fh_last_side  = ""
                                                fh_route_idx += 1
                                                self._map_navigator.release_direction()
                                                self._status(
                                                    f"[층별] {zone.name} 완료 "
                                                    f"→ {to_name} (밧줄: {rp_name})"
                                                )
                                            else:
                                                self._status(
                                                    f"⚠ [층별] 루트 오류: "
                                                    f"'{to_name}' 또는 '{rp_name}' 미발견"
                                                )
                                        else:
                                            # ── 자동 왕복 ────────────────
                                            # 사냥 구역(sweeps>0)끼리만 왕복 — 통과 구역은 낙사 복귀 전용
                                            n = len(fh_zones)
                                            hunt_up   = [i for i in range(fh_idx + 1, n)
                                                         if fh_zones[i].sweeps > 0]
                                            hunt_down = [i for i in range(fh_idx - 1, -1, -1)
                                                         if fh_zones[i].sweeps > 0]
                                            if fh_dir > 0:
                                                if hunt_up:
                                                    next_idx = hunt_up[0]
                                                elif hunt_down:
                                                    fh_dir   = -1
                                                    next_idx = hunt_down[0]
                                                else:
                                                    next_idx = fh_idx
                                            else:
                                                if hunt_down:
                                                    next_idx = hunt_down[0]
                                                elif hunt_up:
                                                    fh_dir   = 1
                                                    next_idx = hunt_up[0]
                                                else:
                                                    next_idx = fh_idx

                                            if next_idx != fh_idx:
                                                if zone.rope_x >= 0:
                                                    fh_rope_x = zone.rope_x
                                                    matched_r = next(
                                                        (r for r in ropes if r.x == zone.rope_x), None
                                                    )
                                                    fh_climb_sec = matched_r.climb_sec if matched_r else 2.5
                                                elif ropes:
                                                    rp_auto = ropes[min(fh_idx, len(ropes) - 1)]
                                                    fh_rope_x    = rp_auto.x
                                                    fh_climb_sec = rp_auto.climb_sec
                                                else:
                                                    fh_rope_x    = zone.right_x
                                                    fh_climb_sec = 2.5
                                                fh_next_idx = next_idx
                                                fh_next_dir = 1 if fh_zones[next_idx].y_min < zone.y_min else -1
                                                fh_state    = "to_rope"
                                                fh_half_count = 0
                                                fh_last_side  = ""
                                                self._map_navigator.release_direction()
                                                self._status(
                                                    f"[층별] {zone.name} 완료 "
                                                    f"→ {fh_zones[next_idx].name} 이동"
                                                )

                    # 이동 + 스킬 (층 이동 중 또는 통과 층에서는 스킵)
                    _on_transit = (use_floor_hunt and fh_state == "patrol"
                                   and fh_zones[fh_idx].sweeps == 0)
                    if not use_floor_hunt or (fh_state == "patrol" and not _on_transit):
                        if self._enable_move:
                            self._map_navigator.run_one_step()
                        if self._enable_attack:
                            self._key_hunter.run_one_step()

                except Exception as exc:
                    logger.exception("루프 오류: %s", exc)
                    self._status(f"오류: {exc}")
        finally:
            self._map_navigator.release_direction()
            if self._floor_hunt_thread and self._floor_hunt_thread.is_alive():
                self._floor_hunt_thread.join(timeout=3)
            # 내부 정지(이탈 감지 등)인 경우 UI 상태 동기화
            try:
                self._on_stop_cb()
            except Exception:
                pass
        logger.info("봇 루프 종료")

    # ── 포션 전용 루프 (별도 스레드) ─────────────────────────────────
    def _potion_loop(self) -> None:
        """포션 · 펫먹이 · 버프를 주기적으로 처리하는 전용 스레드."""
        logger.info("포션 루프 시작")
        last_pet  = 0.0   # 0으로 초기화 → 봇 시작 즉시 첫 급여 (인터벌 경과로 간주)
        last_buffs: dict[tuple, float] = {}  # {("normal"|"toggle", idx): timestamp}
        pet_logged = False  # 펫먹이 설정 알림 출력 여부

        while not self._stop_event.is_set():
            now = time.time()
            try:
                # ── HP/MP 포션 ────────────────────────────────────────
                if self._enable_potion:
                    self._potion_manager.check_and_use()

                # ── 펫먹이 ───────────────────────────────────────────
                if self._enable_potion:
                    pet = self._config.get("recovery", "pet_food") or {}
                    if pet.get("enabled") and pet.get("key", "").strip():
                        interval_sec = float(pet.get("interval_min", 20)) * 60
                        key   = pet["key"].strip()
                        count = max(1, int(pet.get("pet_count", 1)))
                        # 최초 1회: 설정 확인 로그 (다음 급여까지 남은 시간 표시)
                        if not pet_logged:
                            remaining = max(0.0, interval_sec - (now - last_pet))
                            if remaining < 1:
                                self._status(
                                    f"🐾 펫먹이 설정됨 — 키=[{key}] {count}마리 "
                                    f"{int(interval_sec//60)}분 간격 (즉시 첫 급여)"
                                )
                            else:
                                self._status(
                                    f"🐾 펫먹이 설정됨 — 키=[{key}] {count}마리 "
                                    f"{int(interval_sec//60)}분 간격 "
                                    f"(첫 급여까지 {remaining/60:.0f}분)"
                                )
                            pet_logged = True
                        if now - last_pet >= interval_sec:
                            for _ in range(count):
                                self._input.press_key(key)
                                time.sleep(0.15)
                            self._status(f"🐾 펫먹이 급여 완료 — [{key}] {count}마리")
                            last_pet = now
                    elif pet_logged:
                        pet_logged = False  # 설정이 비활성화되면 다음 활성화 시 재출력

                # ── 버프 (동적 목록) ──────────────────────────────────
                for btype, cfg_key, label in [
                    ("normal", "normal_buffs", "일반버프"),
                    ("toggle", "toggle_buffs", "온오프버프"),
                ]:
                    buffs = self._config.get("attack", cfg_key) or []
                    for i, buff in enumerate(buffs):
                        if not buff.get("enabled") or not buff.get("key", "").strip():
                            continue
                        key_id   = (btype, i)
                        interval = float(buff.get("interval_sec", 180))
                        if now - last_buffs.get(key_id, 0.0) >= interval:
                            self._input.press_key(buff["key"].strip())
                            self._status(f"✨ {label} 사용 ({buff['key']})")
                            last_buffs[key_id] = now

            except Exception as exc:
                logger.warning("포션 루프 오류: %s", exc)
            self._stop_event.wait(timeout=POTION_CHECK_INTERVAL)
        logger.info("포션 루프 종료")

    # ── 감지 핸들러 ───────────────────────────────────────────────────
    def _check_transparent_shape(self, screenshot) -> bool:
        """투명 도형 찾기 미니게임 감지 시 폐루프 추적 루프를 실행한다."""
        cfg = self._config.get("settings1", "transparent_shape") or {}
        if not cfg.get("enabled"):
            return False

        # lazy init
        if self._transparent_game is None:
            from core.transparent_shape_game import TransparentShapeGame
            self._transparent_game = TransparentShapeGame(
                self._screen, self._input, self._config, self._stop_event
            )
            self._transparent_game.window_title = self._game_window_title()

        title_pos = self._transparent_game.detect_title(screenshot)
        if title_pos is None:
            return False

        self._status("투명 도형 찾기 감지! 마우스 추적 시작...")
        floor_cfg = self._config.get("floor_hunt") or {}
        if floor_cfg.get("enabled"):
            self._floor_hunter.pause()
        try:
            self._input.focus_game_window()
            self._transparent_game.run_follow_loop(self._status)
        finally:
            if floor_cfg.get("enabled"):
                self._floor_hunter.resume()
            if cfg.get("debug_overlay"):
                import cv2
                try:
                    cv2.destroyWindow("transparent_shape_debug")
                except Exception:
                    pass
            self._status("투명 도형 찾기: 완료, 사냥 재개")
        return True

    def _check_lie_detector(self, screenshot) -> bool:
        cfg = self._config.get("settings1", "lie_detector") or {}
        if not cfg.get("enabled"):
            return False

        # templates/lie_detector_*.png 파일을 모두 검사 — 하나라도 매칭되면 감지
        import glob
        patterns = sorted(glob.glob("templates/lie_detector_*.png"))
        if not patterns:
            self._status("⚠ 거짓말탐지기 템플릿 없음 — 설정1 탭에서 캡처 필요")
            return False

        # 감지 영역이 설정돼 있으면 해당 영역만 캡처해서 검사
        region = cfg.get("region")
        if region and len(region) == 4:
            rx, ry, rw, rh = region
            # 상대좌표인 경우 절대좌표로 변환
            if cfg.get("coord_mode") == "relative":
                origin = self._screen.get_window_client_origin(self._game_window_title())
                if origin:
                    rx += origin[0]
                    ry += origin[1]
            target = self._screen.capture({"left": rx, "top": ry, "width": rw, "height": rh})
        else:
            target = screenshot

        matched_pos = None
        best_score = 0.0
        for tpl_path in patterns:
            score = self._screen.find_template_score(target, tpl_path)
            if score > best_score:
                best_score = score
            if score >= 0.65:
                matched_pos = self._screen.find_template(target, tpl_path, threshold=0.65)
                if matched_pos:
                    # 영역이 설정된 경우 절대 좌표로 변환
                    if region and matched_pos:
                        matched_pos = (matched_pos[0] + rx, matched_pos[1] + ry)
                    break

        if matched_pos is None:
            self._status(f"[탐지기 점수] {best_score:.2f}  (기준 0.65 이상이면 감지)")
            return False

        self._status(f"거짓말탐지기 감지! (템플릿 {len(patterns)}개 중 매칭)")

        # ── 상세 로그 — ① 감지 영역 ────────────────────────────────────
        self._lie_log("━━━━━ 거짓말탐지기 감지 ━━━━━")
        if region and len(region) == 4:
            rx, ry, rw, rh = region
            self._lie_log(f"① 감지 영역  X={rx} Y={ry} W={rw} H={rh}  [설정됨]")
        else:
            self._lie_log("① 감지 영역  전체 화면 (미설정)")
        self._lie_log(f"   템플릿 {len(patterns)}개 검사  최고 점수={best_score:.3f}  위치={matched_pos}")

        # ── 알림 (거탐 알림 모듈이 켜진 경우) ────────────────────────
        if self._enable_lie_notify:
            # 1. 경보음
            if cfg.get("play_alarm"):
                import winsound
                for _ in range(3):
                    winsound.Beep(1000, 300)
                    time.sleep(0.1)

            # 2. 텔레그램 알림 (백그라운드 스레드 — 봇 루프 차단 없음)
            if cfg.get("tg_enabled"):
                _token   = cfg.get("tg_token", "")
                _chat_id = cfg.get("tg_chat_id", "")
                if _token and _chat_id:
                    _prefix = cfg.get("tg_prefix", "").strip()
                    _msg = (f"{_prefix} 거짓말 탐지기 발견!" if _prefix
                            else "⚠️ [MapleBot] 거짓말탐지기 발견!")
                    import threading as _t
                    def _send_tg(_tok=_token, _cid=_chat_id, _m=_msg):
                        try:
                            from ui.tab_settings1 import _send_telegram
                            _send_telegram(_tok, _cid, _m)
                        except Exception:
                            pass
                    _t.Thread(target=_send_tg, daemon=True).start()

        # ── 해제 (거탐 해제 모듈이 꺼진 경우 알림만 하고 복귀) ────────
        if not self._enable_lie_solve:
            return True   # 감지는 됐으나 해제 생략 — 루프 한 번 스킵

        # 3. 종료 옵션 처리
        import subprocess
        if cfg.get("close_maple"):
            self._stop_event.set()
            subprocess.Popen("taskkill /F /IM MapleStory.exe", shell=True)
            return True
        if cfg.get("shutdown_pc"):
            self._stop_event.set()
            subprocess.Popen("shutdown /s /t 10", shell=True)
            return True

        # 3. 퍼즐 해제 — 수동 좌표 설정 시 우선 사용
        # 층별 사냥 중이면 일시정지
        floor_cfg = self._config.get("floor_hunt") or {}
        if floor_cfg.get("enabled"):
            self._floor_hunter.pause()
        try:
            has_manual = all(cfg.get(k) for k in ("puzzle_area", "piece_area", "next_btn", "confirm_btn"))
            if has_manual:
                self._solve_lie_detector_manual()
            else:
                self._input.focus_game_window()
                time.sleep(0.3)
                self._solve_lie_detector(matched_pos)
            time.sleep(0.8)
        finally:
            if floor_cfg.get("enabled"):
                self._floor_hunter.resume()
        return True

    def _solve_lie_detector_manual(self) -> None:
        """설정된 좌표(②~⑤)로 거짓말탐지기 퍼즐을 사람처럼 해제한다.
        흐름: ② 빈칸 X 감지 → ④ >> 클릭 → ③ 바를 빈칸 X에 맞춰 드래그 → ⑤ 확인"""
        import cv2
        import numpy as np

        cfg = self._config.get("settings1", "lie_detector") or {}

        # ── 상대좌표 → 절대좌표 변환 ──────────────────────────────────
        coord_mode = cfg.get("coord_mode", "absolute")
        if coord_mode == "relative":
            origin = self._screen.get_window_client_origin(self._game_window_title())
            if origin is None:
                self._status("⚠ MapleStory 창을 찾을 수 없음 — 상대좌표 변환 실패")
                return
            ox, oy = origin
            def _to_abs(rect):
                if not rect or len(rect) < 4:
                    return rect
                x, y, w, h = rect
                return [x + ox, y + oy, w, h]
        else:
            def _to_abs(rect):
                return rect

        puzzle_area = _to_abs(cfg.get("puzzle_area"))  # ② 빈칸 탐색 영역
        bar_area    = _to_abs(cfg.get("piece_area"))   # ③ 드래그 바 범위
        next_btn    = _to_abs(cfg.get("next_btn"))     # ④ >> 버튼
        confirm_btn = _to_abs(cfg.get("confirm_btn"))  # ⑤ 확인 버튼
        done_btn    = _to_abs(cfg.get("done_btn"))     # 완료 팝업 확인 버튼

        if not all([puzzle_area, bar_area, next_btn, confirm_btn]):
            self._status("⚠ 거짓말탐지기 해제 좌표 미설정 — 설정1 탭에서 ②~⑤ 영역 설정 필요")
            return

        def rand_pt(region, x_ratio=None):
            """영역 안 랜덤 float 좌표. x_ratio를 주면 X만 해당 비율로 고정."""
            x, y, w, h = region
            rx = x + (w * x_ratio if x_ratio is not None
                       else random.uniform(w * 0.2, w * 0.8))
            ry = y + random.uniform(h * 0.2, h * 0.8)
            return rx, ry

        self._input.focus_game_window()
        time.sleep(random.uniform(0.2, 0.35))

        # ── 상세 로그 — 좌표 설정값 출력 ──────────────────────────────
        self._lie_log("━━━━━ 거짓말탐지기 해제 시작 ━━━━━")
        self._lie_log(f"② 퍼즐 영역   X={puzzle_area[0]} Y={puzzle_area[1]} W={puzzle_area[2]} H={puzzle_area[3]}")
        self._lie_log(f"③ 바 영역     X={bar_area[0]} Y={bar_area[1]} W={bar_area[2]} H={bar_area[3]}")
        self._lie_log(f"④ >> 버튼    X={next_btn[0]} Y={next_btn[1]} W={next_btn[2]} H={next_btn[3]}")
        self._lie_log(f"⑤ 확인 버튼  X={confirm_btn[0]} Y={confirm_btn[1]} W={confirm_btn[2]} H={confirm_btn[3]}")

        # ── ② 퍼즐 영역에서 빈칸 감지 (HSV 채도 → Laplacian 폴백) ────
        px, py, pw, ph = puzzle_area
        bx, by, bw, bh = bar_area
        scene = self._screen.capture({"left": px, "top": py, "width": pw, "height": ph})

        def _find_blank_hsv(img: np.ndarray) -> tuple[int, int, int, int] | None:
            """HSV 채도 마스크로 회색 단색 사각형(빈칸)을 찾는다.
            반환: (cx, cy, w, h) 퍼즐 내 좌표. 실패 시 None."""
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            s = hsv[:, :, 1]
            # 채도 25 이하 = 회색/흰색 (하늘색 배경은 채도가 더 높음)
            _, mask = cv2.threshold(s, 25, 255, cv2.THRESH_BINARY_INV)
            k = np.ones((3, 3), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  k)  # 점 노이즈 제거
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)  # 내부 빈틈 채우기
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return None
            best = max(contours, key=cv2.contourArea)
            if cv2.contourArea(best) < 50:
                return None
            x, y, w, h = cv2.boundingRect(best)
            return x + w // 2, y + h // 2, w, h

        def _find_blank_laplacian(img: np.ndarray, step: int = 20) -> int:
            """Laplacian 분산 스캔으로 텍스처가 가장 없는 X 중심을 반환 (폴백)."""
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            lap  = cv2.Laplacian(gray, cv2.CV_64F)
            _, w = gray.shape
            min_var, best_x = float("inf"), w // 2
            half = step // 2
            for x in range(0, w - step, half):
                v = float(lap[:, x:x + step].var())
                if v < min_var:
                    min_var = v
                    best_x  = x + half
            return best_x

        # 1차: HSV 채도 방식
        blank_result = _find_blank_hsv(scene)
        strip_region: dict | None  = None
        blank_color:  np.ndarray | None = None

        if blank_result is not None:
            blank_cx, blank_cy, blank_w, blank_h = blank_result
            blank_abs_x  = float(px + blank_cx)
            strip_top    = py + blank_cy - blank_h // 2
            strip_region = {"left": px, "top": max(0, strip_top), "width": pw, "height": max(1, blank_h)}
            blank_color  = scene[blank_cy, blank_cx].astype(np.int32)   # 실제 화면 샘플
            self._status(f"거짓말탐지기 → 빈칸 감지(HSV) X={blank_cx} → 절대X={blank_abs_x:.1f}")
            self._lie_log(f"② 빈칸 감지(HSV)  퍼즐내 cx={blank_cx} cy={blank_cy}  크기={blank_w}×{blank_h}  절대X={blank_abs_x:.1f}")
            self._lie_log(f"   빈칸 색 샘플  B={blank_color[0]} G={blank_color[1]} R={blank_color[2]}")
        else:
            # 2차 폴백: Laplacian 분산 스캔
            lap_cx      = _find_blank_laplacian(scene)
            blank_abs_x = float(px + lap_cx)
            # strip 높이를 바 높이로 근사
            strip_region = {"left": px, "top": py, "width": pw, "height": ph}
            blank_color  = scene[ph // 2, lap_cx].astype(np.int32)
            self._status(f"거짓말탐지기 → 빈칸 감지(Laplacian폴백) X={lap_cx} → 절대X={blank_abs_x:.1f}")
            self._lie_log(f"② 빈칸 감지(Laplacian폴백)  퍼즐내 cx={lap_cx}  절대X={blank_abs_x:.1f}")
            self._lie_log(f"   빈칸 색 샘플  B={blank_color[0]} G={blank_color[1]} R={blank_color[2]}")

        # ── ④ >> 버튼 랜덤 클릭 → 오프셋 보정으로 버튼 중심이 빈칸에 정확히 맞춤 ──
        nx, ny, nw, nh = next_btn
        btn_cx = nx + nw / 2
        btn_cy = ny + nh / 2
        from_x, from_y = rand_pt(next_btn)
        dx = from_x - btn_cx          # 중심 대비 클릭 오프셋 (목적지에 동일 적용 → 버튼 중심이 blank_abs_x에 정확히 착지)
        dy = from_y - btn_cy
        to_x = blank_abs_x + dx       # human_offset 제거 → 정중앙 착지
        to_y = float(by + bh / 2) + dy
        drag_dur = random.uniform(1.0, 1.5)
        self._status(f"거짓말탐지기 → >> 드래그 ({from_x:.1f},{from_y:.1f}) → ({to_x:.1f},{to_y:.1f})")
        self._lie_log(f"④ >> 버튼 드래그  시작=({from_x:.1f},{from_y:.1f})  끝=({to_x:.1f},{to_y:.1f})"
                      f"  오프셋 dx={dx:+.1f} dy={dy:+.1f}  소요={drag_dur:.2f}s")
        self._input.drag_slider((from_x, from_y), (to_x, to_y),
                                duration=drag_dur)

        # 드래그 후 피스 중심 위치 추적 (미세 조정 기준점)
        piece_cx = blank_abs_x   # 버튼 중심이 정확히 blank_abs_x에 착지
        piece_cy = by + bh / 2

        # ── 빈칸 커버 확인 및 미세 조정 (최대 2회) ──────────────────────
        # 빈칸 Y strip 전체 색상 소실 방식 — piece_cx 추정 오차 없이 빈칸 직접 관찰

        def _blank_remaining() -> tuple[float, float | None]:
            """빈칸 색 픽셀이 Y strip에 남은 비율과 남은 X 무게중심(퍼즐 내 절대px) 반환.
            strip_region 또는 blank_color 미설정이면 (1.0, None) 반환."""
            if strip_region is None or blank_color is None:
                return 1.0, None
            strip = self._screen.capture(strip_region)   # (th, pw, 3) BGR
            diff = np.abs(strip.astype(np.int32) - blank_color)
            mask = np.all(diff <= 30, axis=2)            # tolerance 30
            ratio = float(mask.sum()) / max(mask.size, 1)
            if mask.any():
                xs = np.where(mask)[1]                   # 열 인덱스 (퍼즐 내 X)
                return ratio, float(np.mean(xs))
            return ratio, None

        self._lie_log("── 커버 확인 루프 시작 (최대 3회) ──")
        for attempt in range(3):
            time.sleep(random.uniform(0.4, 0.6))
            ratio, remaining_x = _blank_remaining()
            covered = ratio < 0.10   # 빈칸 색 10% 미만 = 조각이 덮음
            status_str = f"거짓말탐지기 → 빈칸색 잔여 {ratio:.2f} ({'✓ 커버됨' if covered else '✗ 미완'})"
            self._status(status_str)
            rx_str = f"{remaining_x:.1f}" if remaining_x is not None else "None"
            self._lie_log(
                f"   [{attempt+1}차] 잔여비율={ratio:.3f}  남은X={rx_str}  "
                f"→ {'✓ 커버됨' if covered else '✗ 미완'}"
            )
            if covered or attempt >= 2:
                break
            if remaining_x is None:
                break
            # 남은 빈칸 X 무게중심 → 피스를 그곳으로 이동
            remaining_abs_x = px + remaining_x
            adj_x = remaining_abs_x - piece_cx
            adj_from_x = piece_cx + random.uniform(-1, 1)
            adj_from_y = piece_cy + random.uniform(-1, 1)
            adj_to_x   = adj_from_x + adj_x
            adj_dur    = random.uniform(1.0, 1.8)
            self._status(f"거짓말탐지기 → 미세 조정 {adj_x:+.1f}px")
            self._lie_log(
                f"   미세 조정  adj_x={adj_x:+.1f}px  "
                f"({adj_from_x:.1f},{adj_from_y:.1f}) → ({adj_to_x:.1f},{adj_from_y:.1f})  "
                f"소요={adj_dur:.2f}s"
            )
            self._input.drag_slider(
                (adj_from_x, adj_from_y), (adj_to_x, adj_from_y),
                duration=adj_dur,
            )
            piece_cx += adj_x

        # ── ⑤ 확인 버튼 클릭 ─────────────────────────────────────────
        cx, cy = rand_pt(confirm_btn)
        self._status(f"거짓말탐지기 → 확인 클릭 ({cx:.1f}, {cy:.1f})")
        self._lie_log(f"⑤ 확인 버튼 클릭  ({cx:.1f},{cy:.1f})")
        self._input.click(int(cx), int(cy))

        # ── 완료 팝업 확인 클릭 ───────────────────────────────────────
        if done_btn:
            time.sleep(random.uniform(0.5, 0.9))  # 팝업 뜨는 시간 대기
            dx, dy = rand_pt(done_btn)
            self._status(f"거짓말탐지기 → 완료 팝업 확인 클릭 ({dx:.1f}, {dy:.1f})")
            self._input.click(int(dx), int(dy))

        self._lie_log("━━━━━ 거짓말탐지기 해제 종료 ━━━━━")
        self._status("거짓말탐지기 해제 완료")

    def _solve_lie_detector(self, title_pos: tuple) -> None:
        """
        거짓말탐지기 퍼즐 자동 해제.
        title_pos: 템플릿 매칭으로 찾은 제목 중심의 화면 절대 좌표.
        전략: 파란 테두리 조각 → 흰색 빈칸으로 드래그.
        """
        import numpy as np
        import cv2

        tx, ty = title_pos

        # 퍼즐 창 추정 영역 (제목 기준 ±210px 가로, 아래로 350px)
        px = max(0, tx - 210)
        py = max(0, ty - 10)
        pw, ph = 420, 350
        region = {"left": px, "top": py, "width": pw, "height": ph}
        scene = self._screen.capture(region)

        # ── 파란 테두리 조각 찾기 ──────────────────────────────────────
        hsv = cv2.cvtColor(scene, cv2.COLOR_BGR2HSV)
        blue_mask = cv2.inRange(hsv,
                                np.array([95, 60, 60]),
                                np.array([135, 255, 255]))
        piece_rel = self._largest_contour_center(blue_mask, min_area=150, max_area=25000)

        # ── 흰색 빈칸 찾기 ────────────────────────────────────────────
        gray = cv2.cvtColor(scene, cv2.COLOR_BGR2GRAY)
        _, white_mask = cv2.threshold(gray, 228, 255, cv2.THRESH_BINARY)
        # 창 테두리/버튼 등 가장자리 30px 제외
        white_mask[:30, :] = 0
        white_mask[-30:, :] = 0
        white_mask[:, :30] = 0
        white_mask[:, -30:] = 0
        blank_rel = self._largest_contour_center(white_mask, min_area=400, max_area=20000)

        if piece_rel is None:
            self._status("거짓말탐지기 → 조각 감지 실패 (템플릿 재캡처 필요)")
            return
        if blank_rel is None:
            self._status("거짓말탐지기 → 빈칸 감지 실패")
            return

        # 화면 절대 좌표로 변환
        piece_abs = (piece_rel[0] + px, piece_rel[1] + py)
        blank_abs = (blank_rel[0] + px, blank_rel[1] + py)

        self._status(f"거짓말탐지기 자동해제: 조각{piece_abs} → 빈칸{blank_abs}")
        self._input.drag(piece_abs, blank_abs)

    def _largest_contour_center(
        self, mask, min_area: int = 100, max_area: int = 50000
    ) -> tuple | None:
        """마스크에서 가장 큰 윤곽의 중심 좌표를 반환."""
        import cv2
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        best, best_area = None, 0
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if min_area < area < max_area and area > best_area:
                best_area = area
                best = cnt
        if best is None:
            return None
        M = cv2.moments(best)
        if M["m00"] == 0:
            return None
        return (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))

    def _check_user_on_map(self, screenshot) -> None:
        cfg = self._config.get("settings1", "user_detected") or {}
        if not cfg.get("enabled"):
            return
        pos = self._screen.find_template(screenshot, TEMPLATES["player_on_map"])
        if pos is None:
            return

        interval_sec = cfg.get("interval_minutes", 5) * 60
        now = time.time()
        if now - self._last_user_chat_time < interval_sec:
            return

        messages = cfg.get("messages", [])
        msg = messages[self._chat_msg_index % len(messages)] if messages else ""
        if msg:
            self._input.focus_game_window()
            self._input.send_chat(msg)
            self._status(f"유저 발견 → 채팅: {msg}")
        self._chat_msg_index += 1
        self._last_user_chat_time = now

    def _check_level_up(self, screenshot) -> None:
        pos = self._screen.find_template(screenshot, TEMPLATES["level_up"])
        if pos is None:
            return
        self._status("레벨업 감지")
        sa_cfg = self._config.get("settings1", "stat_assign") or {}
        if sa_cfg.get("enabled"):
            self._assign_stats(sa_cfg)

    def _check_dead(self, screenshot) -> bool:
        cfg = self._config.get("settings2", "shutdown") or {}
        if not cfg.get("on_death"):
            return False
        pos = self._screen.find_template(screenshot, TEMPLATES["dead"])
        if pos is None:
            return False
        self._status("사망 감지 → 컴퓨터 종료")
        self._stop_event.set()
        import subprocess
        subprocess.Popen("shutdown /s /t 10", shell=True)
        return True

    def _assign_stats(self, cfg: dict) -> None:
        self._input.focus_game_window()
        self._input.press_key("s")
        time.sleep(0.3)
        for stat in ["STR", "DEX", "INT", "LUK"]:
            for _ in range(cfg.get(stat, 0)):
                logger.debug("스텟 배분: %s", stat)
        self._input.press_key("s")

    def _check_map_exit(self) -> None:
        """미니맵 이름 영역 이미지 비교로 사냥터 이탈을 감지한다.
        저장된 기준 이미지(map_name_ref.png)와 현재 화면을 매 1초마다 비교.
        연속 N회 유사도 < threshold 이면 이탈 판정."""
        cfg = self._config.get("map_exit") or {}
        if not cfg.get("enabled"):
            return
        name_region = cfg.get("name_region")
        if not name_region or len(name_region) < 4:
            return  # 기준 영역 미설정 → 동작 안 함
        from core.config_manager import get_user_templates_dir
        ref_path = os.path.join(get_user_templates_dir(), "map_name_ref.png")
        if not os.path.exists(ref_path):
            return  # 기준 이미지 없음 → 동작 안 함

        x, y, w, h = name_region
        current = self._screen.capture({"left": int(x), "top": int(y), "width": int(w), "height": int(h)})
        score = self._screen.find_template_score(current, ref_path)

        threshold = float(cfg.get("threshold", 0.75))
        if score >= threshold:
            self._map_exit_fail = 0   # 일치 → 카운터 초기화
            return

        self._map_exit_fail += 1
        grace = int(cfg.get("grace_count", 3))
        self._status(f"[이탈감지] 유사도={score:.2f} ({self._map_exit_fail}/{grace}회)")
        if self._map_exit_fail < grace:
            return

        # 이탈 판정 (중복 실행 방지)
        self._map_exit_fail = -9999
        action = cfg.get("action", "stop")
        self._status(f"⚠️ 사냥터 이탈 감지 (유사도={score:.2f}) — 맵이 바뀌었습니다")
        if action in ("telegram", "both"):
            self._send_map_exit_telegram()
        if action in ("stop", "both"):
            self._stop_event.set()

    def _check_potion_count(self) -> None:
        """포션 슬롯 영역을 OCR로 읽어 수량 0이면 마을 귀환을 실행한다."""
        pc = self._config.get("recovery", "potion_count") or {}
        if not pc.get("zero_return", False):
            return

        ts = self._config.get("town_scroll") or {}
        if not ts.get("enabled", False):
            return

        hp_region = pc.get("hp_region")
        mp_region = pc.get("mp_region")
        if not hp_region and not mp_region:
            return

        from core.ocr_detector import read_number

        def _is_zero(region) -> bool | None:
            """수량 숫자 영역을 OCR로 읽어 0이면 True, 수량 있으면 False, 실패면 None 반환."""
            if not region or len(region) < 4:
                return None
            x, y, w, h = int(region[0]), int(region[1]), int(region[2]), int(region[3])
            try:
                img = self._screen.capture({"left": x, "top": y, "width": w, "height": h})
                n = read_number(img)
                if n is None:
                    return None  # 읽기 실패 — 오탐 방지를 위해 무시
                self._status(f"[포션수량] {n}개")
                return n == 0
            except Exception:
                return None

        hp_zero = _is_zero(hp_region) if hp_region else None
        mp_zero = _is_zero(mp_region) if mp_region else None

        # 읽기 실패(None)는 무시, 명확히 0인 경우만 귀환
        if hp_zero is not True and mp_zero is not True:
            return

        kind = "HP" if hp_zero else "MP"
        if hp_zero and mp_zero:
            kind = "HP+MP"
        self._status(f"⚠️ {kind} 포션 수량 0 감지 — 마을 귀환 실행")
        self._use_town_scroll()

    def _use_town_scroll(self) -> None:
        """마을 귀환 주문서 키를 눌러 귀환하고 봇을 정지한다."""
        ts = self._config.get("town_scroll") or {}
        key = ts.get("key", "")
        if key:
            self._input.press_key(key)
        time.sleep(1.0)
        self._stop_event.set()

    def _send_map_exit_telegram(self) -> None:
        """사냥터 이탈 시 텔레그램 알림 발송 (기존 거탐 설정 공유)."""
        ld = self._config.get("settings1", "lie_detector") or {}
        token   = ld.get("tg_token", "")
        chat_id = ld.get("tg_chat_id", "")
        if not token or not chat_id:
            return
        prefix = ld.get("tg_prefix", "").strip()
        msg = (f"{prefix} 사냥터 이탈 감지!" if prefix
               else "⚠️ [MapleBot] 사냥터 이탈 감지!")
        import threading as _t
        def _send(_tok=token, _cid=chat_id, _m=msg):
            try:
                from ui.tab_settings1 import _send_telegram
                _send_telegram(_tok, _cid, _m)
            except Exception:
                pass
        _t.Thread(target=_send, daemon=True).start()

    # ── 매크로방지몹 감지 및 해제 ─────────────────────────────────────
    def _check_anti_mob(self, screenshot) -> None:
        """화면 템플릿 매칭으로 방지몹을 감지하고 해제 절차를 실행한다."""
        cfg = self._config.get("anti_mob") or {}
        if not cfg.get("enabled"):
            return

        import glob
        patterns = sorted(glob.glob("templates/anti_mob_*.png"))
        if not patterns:
            return

        region = cfg.get("detect_region")
        if region and len(region) == 4:
            rx, ry, rw, rh = region
            target = self._screen.capture({"left": int(rx), "top": int(ry),
                                           "width": int(rw), "height": int(rh)})
        else:
            target = screenshot

        detected = False
        for tpl_path in patterns:
            if self._screen.find_template_score(target, tpl_path) >= 0.65:
                detected = True
                break

        if not detected:
            return

        self._status("⚠️ 매크로방지몹 감지! 공격 정지 후 해제 시작...")
        self._anti_mob_active = True
        prev_attack = self._enable_attack
        self._enable_attack = False
        try:
            self._handle_anti_mob(cfg)
        except Exception as exc:
            self._status(f"매크로방지몹 해제 오류: {exc}")
        finally:
            self._enable_attack = prev_attack
            self._anti_mob_active = False
            self._status("매크로방지몹 해제 완료 — 공격 재개")

    def _handle_anti_mob(self, cfg: dict) -> None:
        """방지몹 해제 절차: 이동 → 타입별 동작."""
        mob_type = cfg.get("type", "click")
        target_x = int(cfg.get("target_x", 100))
        self._move_to_minimap_x(target_x)
        if mob_type == "click":
            self._anti_mob_click(cfg)
        elif mob_type == "item":
            self._anti_mob_item(cfg)
        elif mob_type == "basic":
            self._anti_mob_basic(cfg)

    def _move_to_minimap_x(self, target_x: int, timeout: float = 6.0) -> None:
        """미니맵 X 좌표로 방향키로 이동한다. timeout 초 안에 못 도달하면 반환."""
        self._map_navigator.release_direction()
        start = time.time()
        while not self._stop_event.is_set():
            if time.time() - start > timeout:
                break
            pos = self._minimap_reader.get_character_pos()
            if pos is None:
                time.sleep(0.1)
                continue
            diff = target_x - pos[0]
            if abs(diff) <= 4:
                break
            if diff > 0:
                self._input.key_up("left")
                self._input.key_down("right")
            else:
                self._input.key_up("right")
                self._input.key_down("left")
            time.sleep(0.08)
        self._map_navigator.release_direction()
        time.sleep(0.2)

    def _anti_mob_click(self, cfg: dict) -> None:
        """클릭형: 설정된 키 시퀀스를 순서대로 누른다."""
        keys_str = cfg.get("click_keys", "space,enter")
        keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        for key in keys:
            self._input.press_key(key)
            time.sleep(random.uniform(0.15, 0.3))

    def _anti_mob_item(self, cfg: dict) -> None:
        """아이템 뿌리기형: 인벤토리 열기 → 기타탭 클릭 → Ctrl+클릭으로 버리기."""
        inv_tab   = cfg.get("item_inv_tab")
        item_slot = cfg.get("item_slot")
        if not inv_tab or not item_slot:
            self._status("⚠ 아이템 뿌리기형: 인벤토리 탭 또는 슬롯 좌표 미설정")
            return
        # 인벤토리 열기
        self._input.press_key("i")
        time.sleep(random.uniform(0.4, 0.6))
        # 기타탭 클릭
        tx, ty, tw, th = inv_tab
        self._input.click(tx + tw // 2, ty + th // 2)
        time.sleep(random.uniform(0.3, 0.5))
        # 아이템 슬롯 Ctrl+클릭 (1개 버리기)
        sx, sy, sw, sh = item_slot
        scx, scy = sx + sw // 2, sy + sh // 2
        self._input.key_down("ctrl")
        time.sleep(0.05)
        self._input.click(scx, scy)
        time.sleep(0.1)
        self._input.key_up("ctrl")
        time.sleep(random.uniform(0.3, 0.5))
        # 수량 확인 팝업 Enter
        self._input.press_key("enter")
        time.sleep(0.3)
        # 인벤토리 닫기
        self._input.press_key("i")
        time.sleep(0.3)

    def _anti_mob_basic(self, cfg: dict) -> None:
        """기본 공격형: 공격 키를 N회 누른다."""
        count = max(1, int(cfg.get("basic_count", 5)))
        attack_key = (self._config.get("attack") or {}).get("key", "ctrl")
        for _ in range(count):
            self._input.press_key(attack_key)
            time.sleep(random.uniform(0.1, 0.2))

    def _status(self, msg: str) -> None:
        logger.info(msg)
        self._on_status(msg)
