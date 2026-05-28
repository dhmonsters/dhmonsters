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

SAFETY_CHECK_INTERVAL = 0.5   # 화면 캡처 기반 안전 감지 주기 (초)
POTION_CHECK_INTERVAL = 0.5   # 포션 체크 주기 (초) — 전용 스레드에서 독립 실행


class _GameState:
    """DebugOverlay / TabMonitor가 참조하는 경량 상태 컨테이너."""

    def __init__(self) -> None:
        import threading
        self._lock = threading.Lock()
        self._data: dict = {}

    def update(self, **kwargs) -> None:
        with self._lock:
            self._data.update(kwargs)

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._data)


class BotLoop:
    def __init__(self, config: ConfigManager, on_status: Callable[[str], None] | None = None):
        self._config = config
        self._on_status  = on_status or (lambda msg: None)
        self._on_stop_cb: Callable[[], None] = lambda: None
        self._on_lie_log: Callable[[str], None] = lambda msg: None
        self.game_state = _GameState()
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
        self._minimap_reader = MinimapReader(self._screen)
        self._map_navigator = MapNavigator(
            minimap_reader=self._minimap_reader,
            input_ctrl=self._input,
            detector=self._detector,
            on_status=self._status,
        )
        self._key_hunter = KeyHunter(
            input_ctrl=self._input,
            on_status=self._status,
            on_move_tick=self._map_navigator.refresh_direction,
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
        self._direction_thread: threading.Thread | None = None
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
        self._transparent_yolo  = None   # lazy init: YoloDetector (투명 도형 전용)
        self._safety_pending: str | None = None  # 백그라운드 감지 결과: "lie" | "transparent"
        self._lie_yolo      = None               # lazy init: YoloDetector (거짓말탐지기 전용)
        self._anti_mob_active   = False  # 방지몹 해제 중 재진입 방지
        self._last_buff_time:   float = 0.0  # 마지막 버프 발동 시각 (밧줄 오르기 연장 판단용)

        # 자동 판매 상태
        self._auto_sell_active:      bool  = False  # 안전지대 이동 or 판매 중
        self._auto_sell_selling:     bool  = False  # sell_junk 스레드 실행 중
        self._auto_sell_last:        float = 0.0    # 마지막 판매 완료 시각
        # 단계: "idle"|"to_departure"|"extra_to_rope"|"extra_climbing"|"walk_to_safe"|"selling"
        self._as_phase:              str   = "idle"
        self._as_extra_climb_start:  float = 0.0    # 추가 밧줄 이동 시작 시각
        self._as_walk_diag_timer:    float = 0.0    # walk_to_safe 로그 스팸 방지
        self._as_return_to_hunt:     bool  = False  # 판매 완료 후 fh_zones[0] 복귀 트리거

        # YOLO11 파이프라인 (lazy init — _init_yolo() 호출 시 생성)
        self._yolo_detector     = None  # YoloDetector | None
        self._char_tracker      = None  # CharacterTracker | None
        self._roi_manager       = None  # ROIManager | None
        self._attack_decision   = None  # AttackDecision | None
        self._yolo_frame_count: int  = 0
        self._yolo_last_result: dict | None = None  # {"direction", "can_attack"}

    def _game_window_title(self) -> str:
        """config에서 게임 창 제목을 읽는다. 미설정이면 'MapleStory' 반환."""
        return self._config.get("settings2", "game_window_title") or "MapleStory"

    def _init_yolo(self) -> None:
        """YOLO 파이프라인 초기화. 비활성이거나 모델 없으면 조용히 스킵."""
        cfg = self._config.get("yolo") or {}
        if not cfg.get("enabled", False):
            return
        model_path = (cfg.get("model_path") or "").strip()
        if not model_path:
            self._status("YOLO: 모델 경로 미설정 — 템플릿 매칭 폴백")
            return
        try:
            from core.yolo_detector import YoloDetector
            from core.character_tracker import CharacterTracker
            from core.roi_manager import ROIManager
            from core.attack_decision import AttackDecision
            self._yolo_detector = YoloDetector(
                model_path,
                confidence=float(cfg.get("confidence", 0.5)),
                iou=float(cfg.get("iou", 0.45)),
                max_det=int(cfg.get("max_det", 20)),
            )
            self._char_tracker    = CharacterTracker()
            self._roi_manager     = ROIManager()
            ar = cfg.get("attack_range") or {}
            self._attack_decision = AttackDecision(ar)
            if self._yolo_detector.is_loaded:
                self._status(f"YOLO 로드 완료: {model_path}")
            else:
                self._status("YOLO 로드 실패 — 템플릿 매칭 폴백")
                self._yolo_detector = None
        except Exception as e:
            logger.warning("_init_yolo 오류: %s", e)
            self._status(f"YOLO 초기화 오류: {e}")
            self._yolo_detector = None

    def _get_coord_origin(self) -> tuple[int, int]:
        """coord_mode == 'relative'일 때 게임 창 origin을 반환. absolute면 (0,0)."""
        from core.config_manager import get_game_window_origin
        return get_game_window_origin(self._config)

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
        self._init_yolo()
        self._stop_event.clear()
        # 메인 루프 (이동 + 스킬)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        # 포션 전용 스레드 — 스킬 블로킹과 완전히 분리
        self._potion_thread = threading.Thread(target=self._potion_loop, daemon=True)
        self._potion_thread.start()
        # 방향키 유지 전용 스레드 — 안전감지 블로킹과 무관하게 40ms마다 key_down 재전송
        self._direction_thread = threading.Thread(target=self._direction_keepalive_loop, daemon=True)
        self._direction_thread.start()
        self._status("봇 시작됨")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)
        if self._potion_thread:
            self._potion_thread.join(timeout=2)
        if self._direction_thread:
            self._direction_thread.join(timeout=1)
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

        from core.config_manager import resolve_minimap_coords
        region_x, region_y, mm_w, mm_h = resolve_minimap_coords(self._config, mm)
        cfg = MinimapConfig(
            region_x=region_x, region_y=region_y,
            width=mm_w, height=mm_h,
            char_r=mm.get("char_r", 255), char_g=mm.get("char_g", 255),
            char_b=mm.get("char_b", 255), tolerance=mm.get("tolerance", 40),
            jump_key=mm.get("jump_key", "alt"),
        )
        self._minimap_reader.set_config(cfg)

        zones = [Zone.from_dict(z, mm_w, mm_h) for z in raw_zones]
        ropes = [RopePoint.from_dict(r, mm_w)  for r in raw_ropes]
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

        # 백그라운드 스레드 시작
        import threading as _th
        _safety_th = _th.Thread(
            target=self._safety_detect_loop, daemon=True, name="safety-detect"
        )
        _safety_th.start()
        _attack_th = _th.Thread(
            target=self._attack_loop, daemon=True, name="attack"
        )
        _attack_th.start()

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
        fh_rope_x:      int   = 0        # 이동할 밧줄 X 좌표 (rope.x)
        fh_current_rope               = None  # 현재 대상 RopePoint (approach/jump_offset 참조용)
        fh_next_idx:    int   = 0        # 전환 후 목적 층 인덱스
        fh_next_dir:    int   = 1        # 전환 시 이동 방향 (+1=위, -1=아래)
        fh_climb_start: float = 0.0      # 오르기/내려가기 시작 시각
        fh_climb_sec:   float = 2.5      # 현재 밧줄의 오르기 시간 (밧줄별 설정)
        fh_arrive_time: float = 0.0      # 도착 확인 시각 (Y 감지 쿨다운 기준)
        fh_rope_escape_time: float = 0.0 # 밧줄 탈출 마지막 시각 (스팸 방지)
        fh_climb_retry:  int   = 0       # 연속 도착 실패 횟수 (무한루프 방지)
        FH_MAX_RETRY    = 3              # 이 횟수 초과 시 현재층 순찰로 강제 복귀
        FH_DESCEND_SEC  = 0.3            # 내려가기 완료 후 대기 시간 (초)
        FH_ROPE_ESCAPE_INTERVAL = 0.5    # 밧줄 탈출 시도 최소 간격 (초)
        fh_route:       list  = []       # 커스텀 루트 [{to_zone, rope}, ...]
        fh_route_idx:   int   = 0        # 현재 루트 단계
        fh_route_mode:  bool  = False    # True=커스텀 루트, False=자동 왕복
        fh_fall_timer:  float = 0.0      # B안 낙사 감지: 전체 구역 밖 진입 시각 (0=미감지)
        fh_to_rope_dir: str   = "right"  # to_rope 이동 방향 (pos 미감지 시 방향 유지용)
        FH_ROPE_EDGE    = 8              # 밧줄 도달 판정 픽셀
        FH_CLIMB_SEC    = 2.5            # UP 키 유지 시간 (초)
        FH_Y_COOLDOWN   = 4.0            # 도착 후 Y 감지 비활성 시간 (초)

        # 픽업 타이머 상태 변수
        pu_enabled       = False
        pu_interval      = 110.0
        pu_key           = "z"
        pu_hold_sec      = 1.5
        pu_route: list   = []
        pu_step_idx      = 0
        pu_prev_fh_idx   = 0
        last_pickup_time = time.time()
        pu_active        = False

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
            from core.config_manager import resolve_minimap_coords
            _fh_mm = _fh_preset.get("minimap", {}) if _fh_preset else (self._config.get("minimap") or {})
            _, _, _fh_mm_w, _fh_mm_h = resolve_minimap_coords(self._config, _fh_mm)
            all_zones = [_Zone.from_dict(z, _fh_mm_w, _fh_mm_h) for z in raw_zones]
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

        # 픽업 타이머 설정 로드
        _pt = self._config.get("pickup_timer") or {}
        pu_enabled  = bool(_pt.get("enabled", False))
        pu_interval = float(_pt.get("interval_sec", 110))
        pu_key      = _pt.get("pickup_key", "z") or "z"
        pu_hold_sec = float(_pt.get("key_hold_sec", 1.5))
        pu_route    = _pt.get("route", [])

        last_safety      = 0.0
        last_focus       = 0.0
        FOCUS_INTERVAL        = 4.0
        self._map_exit_fail = 0  # 사냥터 이탈 감지 연속 불일치 카운터

        # 봇 시작 시 즉시 판매 여부 결정
        _junk_init = self._config.get("settings2", "junk_sell") or {}
        if bool(_junk_init.get("sell_on_start", False)):
            self._auto_sell_last = 0.0   # 타이머 0 → 첫 루프에서 바로 판매 발동
        else:
            self._auto_sell_last = time.time()  # 지금부터 카운트 → 설정 주기 후 첫 판매
        try:
            while not self._stop_event.is_set():
                try:
                    now = time.time()

                    # ── 공격 스레드 pause/resume (루프 최상단 — continue 이전에 항상 실행) ──
                    _on_transit_top = (use_floor_hunt and bool(fh_zones) and fh_state == "patrol"
                                       and fh_zones[fh_idx].sweeps == 0)
                    _can_attack_now = (
                        not self._auto_sell_active
                        and (not use_floor_hunt
                             or (fh_state == "patrol" and not _on_transit_top))
                    )
                    if _can_attack_now:
                        self._key_hunter.resume()
                    else:
                        self._key_hunter.pause()

                    # 게임 창 포커스 유지
                    if self._enable_move and now - last_focus >= FOCUS_INTERVAL:
                        self._map_navigator.release_direction()
                        self._input.focus_game_window()
                        last_focus = now

                    # ── 백그라운드 감지 결과 처리 (거짓말탐지기 · 투명도형) ──
                    _pending = self._safety_pending
                    if _pending:
                        self._safety_pending = None
                        self._key_hunter.pause()   # 핸들러 실행 전 즉시 공격 중단
                        _shot = self._screen.capture()
                        _handled = False
                        if _pending == "lie":
                            _handled = self._check_lie_detector(_shot)
                            if _handled and use_floor_hunt:
                                fh_last_side = ""
                                if fh_state != "patrol":
                                    self._input.key_up("up")
                                    self._map_navigator.release_direction()
                                    fh_state = "patrol"
                        elif _pending == "transparent":
                            # 알람은 _check_transparent_shape 내부에서 재감지 후 발동
                            _handled = self._check_transparent_shape(_shot)
                            if _handled and use_floor_hunt:
                                fh_last_side = ""
                                if fh_state != "patrol":
                                    self._input.key_up("up")
                                    self._map_navigator.release_direction()
                                    fh_state = "patrol"
                        if _handled:
                            continue

                    # ── 경량 안전 감지 (죽음·레벨업·유저·맵이탈) ──────────
                    if now - last_safety >= SAFETY_CHECK_INTERVAL:
                        screenshot = self._screen.capture()
                        last_safety = now
                        if self._check_dead(screenshot):
                            continue
                        self._check_user_on_map(screenshot)
                        self._check_level_up(screenshot)
                        # 사냥터 이탈 감지 (미니맵 이름 이미지 비교 기반)
                        self._check_map_exit()
                        # 매크로방지몹 감지
                        if not self._anti_mob_active:
                            self._check_anti_mob(screenshot)

                        # ── 디버그 오버레이용 game_state 갱신 (1초마다) ──────
                        try:
                            _gs_pos = self._minimap_reader.get_character_pos()
                            _hp = self._detector.hp_ratio()
                            _mp = self._detector.mp_ratio()
                            self.game_state.update(
                                char_pos=_gs_pos,
                                char_pos_smooth=_gs_pos,
                                hp_ratio=_hp,
                                mp_ratio=_mp,
                                bot_state="running",
                                nav_state=getattr(self._map_navigator, '_direction', '-'),
                            )
                        except Exception:
                            _hp, _mp = 1.0, 1.0

                        # 긴급 마을 귀환 HP/MP % 발동 체크
                        self._check_town_scroll_trigger(_hp, _mp)

                    # ── 자동 판매 주기 체크 ────────────────────────────
                    _junk_cfg       = self._config.get("settings2", "junk_sell") or {}
                    _auto_enabled   = bool(_junk_cfg.get("auto_sell_enabled", False))
                    _auto_interval  = float(_junk_cfg.get("auto_sell_interval_min", 10)) * 60
                    _dep_zone_name  = (_junk_cfg.get("departure_zone") or "").strip()
                    _extra_rope_cfg = _junk_cfg.get("extra_rope") or {}

                    # 안전지대 좌표 — 비율 우선, 없으면 raw 픽셀 사용
                    _mm_cfg = self._minimap_reader.config
                    _mm_w   = _mm_cfg.width
                    _mm_h   = _mm_cfg.height
                    _szxr   = _junk_cfg.get("safe_zone_x_ratio")
                    _szyr   = _junk_cfg.get("safe_zone_y_ratio")
                    _safe_zone_x = (int(_szxr * _mm_w) if _szxr is not None and _mm_w > 0
                                    else int(_junk_cfg.get("safe_zone_x", -1)))
                    _safe_zone_y = (int(_szyr * _mm_h) if _szyr is not None and _mm_h > 0
                                    else int(_junk_cfg.get("safe_zone_y", -1)))

                    # 타이머 만료 → 이동 시작
                    if (_auto_enabled and _safe_zone_x >= 0
                            and not self._auto_sell_active
                            and now - self._auto_sell_last >= _auto_interval):
                        self._auto_sell_active  = True
                        self._auto_sell_selling = False
                        self._map_navigator.release_direction()
                        if use_floor_hunt and fh_state != "patrol":
                            self._input.key_up("up")
                            fh_state      = "patrol"
                            fh_half_count = 0
                        if use_floor_hunt and _dep_zone_name and fh_zones:
                            self._as_phase = "to_departure"
                            self._status(f"자동 판매: 출발지 '{_dep_zone_name}' 대기 중...")
                        else:
                            self._as_phase = "walk_to_safe"
                            self._status(f"자동 판매: 안전지대(X={_safe_zone_x})로 이동 중...")

                    if self._auto_sell_active:
                        if self._as_phase == "selling":
                            continue  # 판매 스레드 완료 대기

                        elif self._as_phase == "to_departure":
                            # floor_hunt 이 자연스럽게 층 이동 — patrol 상태에서 출발지 감지
                            if fh_state == "patrol" and fh_zones and fh_zones[fh_idx].name == _dep_zone_name:
                                if _extra_rope_cfg.get("x") is not None:
                                    self._as_phase = "extra_to_rope"
                                    self._status(f"자동 판매: 출발지 도착, 밧줄(X={_extra_rope_cfg['x']}) 이동")
                                else:
                                    self._as_phase = "walk_to_safe"
                                    self._status("자동 판매: 출발지 도착, 안전지대 걷기 중...")
                                continue  # 이번 루프 fh_state 머신 스킵
                            # else: fall-through → fh_state 머신이 층 이동 담당

                        elif self._as_phase == "extra_to_rope":
                            # 출발지에서 안전지대로 가는 전용 밧줄로 이동
                            _er_x   = int(_extra_rope_cfg.get("x", 0))
                            _er_dir = _extra_rope_cfg.get("direction", "up")
                            _as_pos = self._minimap_reader.get_character_pos()
                            if _as_pos is not None:
                                _cx = _as_pos[0]
                                if abs(_cx - _er_x) <= 8:
                                    _jump_key = self._minimap_reader.config.jump_key or "alt"
                                    if _er_dir == "up":
                                        # 걷기 방향 유지한 채 점프 → 점프 후 해제
                                        self._input.press_key(_jump_key, hold_sec=0.12)
                                        self._map_navigator.release_direction()
                                        self._input.key_down("up")
                                    else:
                                        # 아래층 — 멈춰서 down+jump
                                        self._map_navigator.release_direction()
                                        self._input.key_down("down")
                                        time.sleep(0.06)
                                        self._input.press_key(_jump_key, hold_sec=0.12)
                                        self._input.key_up("down")
                                    self._as_extra_climb_start = time.time()
                                    self._as_phase = "extra_climbing"
                                    self._status(f"자동 판매: 밧줄 점프 ({_er_dir})")
                                else:
                                    self._map_navigator.walk_toward(_er_x, _cx)
                            continue  # fh_state 머신 스킵

                        elif self._as_phase == "extra_climbing":
                            # 밧줄 이동 시간 대기
                            _er_dir = _extra_rope_cfg.get("direction", "up")
                            _er_sec = float(_extra_rope_cfg.get("climb_sec", 2.5))
                            if _er_dir == "up":
                                self._input.key_down("up")
                            if time.time() - self._as_extra_climb_start >= _er_sec:
                                self._input.key_up("up")
                                self._map_navigator.release_direction()
                                self._as_phase = "walk_to_safe"
                                self._status("자동 판매: 밧줄 이동 완료, 안전지대 도착 확인 중...")
                            continue  # fh_state 머신 스킵

                        elif self._as_phase == "walk_to_safe":
                            # X+Y 모두 도착 확인 후 판매 시작
                            if _safe_zone_y < 0:
                                # Y 미설정 — 2초마다 경고
                                if now - self._as_walk_diag_timer >= 2.0:
                                    self._status(
                                        "⚠ 자동 판매: 안전지대 Y 좌표 미설정 "
                                        "— 설정2 탭 > 📍 현재 위치로 설정을 다시 눌러주세요."
                                    )
                                    self._as_walk_diag_timer = now
                            else:
                                _as_pos = self._minimap_reader.get_character_pos()
                                if _as_pos:
                                    _cx, _cy = _as_pos
                                    _x_ok = abs(_cx - _safe_zone_x) <= 8
                                    _y_ok = abs(_cy - _safe_zone_y) <= 8
                                    if _x_ok and _y_ok:
                                        self._as_phase          = "selling"
                                        self._auto_sell_selling = True
                                        self._map_navigator.release_direction()
                                        self._status(
                                            f"자동 판매: 안전지대 도착 "
                                            f"(X={_cx} Y={_cy}), 판매 시작"
                                        )
                                        threading.Thread(
                                            target=self._auto_sell_worker, daemon=True
                                        ).start()
                                    else:
                                        # 2초마다 진단 로그 (스팸 방지)
                                        if now - self._as_walk_diag_timer >= 2.0:
                                            self._status(
                                                f"자동 판매: 이동 중 "
                                                f"현재(X={_cx} Y={_cy}) "
                                                f"목표(X={_safe_zone_x} Y={_safe_zone_y})"
                                            )
                                            self._as_walk_diag_timer = now
                                        # Y가 크게 벗어난 경우 → 밧줄 재시도
                                        _y_diff = abs(_cy - _safe_zone_y)
                                        if _y_diff > 15 and _extra_rope_cfg.get("x") is not None:
                                            self._map_navigator.release_direction()
                                            self._as_phase = "extra_to_rope"
                                            self._status(
                                                f"자동 판매: Y 불일치({_cy}→{_safe_zone_y}), "
                                                "밧줄 재시도"
                                            )
                                        else:
                                            self._map_navigator.walk_toward(_safe_zone_x, _cx)
                            continue  # fh_state 머신 스킵

                    # ── 자동 판매 완료 후 사냥 구역 복귀 ──────────────
                    if (use_floor_hunt and fh_zones
                            and self._as_return_to_hunt
                            and not self._auto_sell_active):
                        self._as_return_to_hunt = False
                        _rcv_zone  = fh_zones[0]
                        _pos_now   = self._minimap_reader.get_character_pos()
                        _cur_y_now = _pos_now[1] if _pos_now else -1
                        _ropes_rv  = self._map_navigator.ropes
                        if _rcv_zone.rope_x >= 0:
                            _rcv_rope = next(
                                (r for r in _ropes_rv if r.x == _rcv_zone.rope_x), None
                            )
                        elif _ropes_rv:
                            _rcv_rope = _ropes_rv[0]
                        else:
                            _rcv_rope = None
                        fh_rope_x       = (_rcv_rope.x if _rcv_rope
                                           else (_rcv_zone.rope_x if _rcv_zone.rope_x >= 0
                                                 else _rcv_zone.right_x))
                        fh_current_rope = _rcv_rope
                        fh_climb_sec    = (_rcv_rope.climb_sec if _rcv_rope else FH_CLIMB_SEC)
                        fh_next_idx     = 0
                        # 현재 Y 기준으로 방향 결정
                        if _cur_y_now < 0 or _cur_y_now > _rcv_zone.y_max:
                            fh_next_dir = 1   # 아래층(1F 등) → 위로 올라가기
                        else:
                            fh_next_dir = -1  # 위층(3F 등) → 아래로 내려가기
                        fh_state        = "to_rope"
                        fh_half_count   = 0
                        fh_last_side    = ""
                        fh_arrive_time  = 0.0   # Y 쿨다운 즉시 해제
                        self._map_navigator.release_direction()
                        self._status(
                            f"자동 판매 완료 → '{_rcv_zone.name}' 복귀 시작"
                            f" ({'위' if fh_next_dir > 0 else '아래'})"
                        )

                    # ── 픽업 타이머 발동 체크 ──────────────────────────
                    if (use_floor_hunt and pu_enabled and not pu_active
                            and pu_route and fh_state == "patrol"
                            and now - last_pickup_time >= pu_interval):
                        ropes = self._map_navigator.ropes
                        step    = pu_route[0]
                        to_name = step.get("to_zone", "")
                        rp_name = step.get("rope", "")
                        to_zone = next((z for z in fh_zones if z.name == to_name), None)
                        rp      = next((r for r in ropes if r.name == rp_name), None)
                        if to_zone and rp:
                            pu_active      = True
                            pu_step_idx    = 0
                            pu_prev_fh_idx = fh_idx
                            fh_rope_x      = rp.x
                            fh_current_rope = rp
                            fh_climb_sec   = rp.climb_sec
                            fh_next_idx    = fh_zones.index(to_zone)
                            fh_next_dir    = 1 if to_zone.y_min < fh_zones[fh_idx].y_min else -1
                            _pcx           = pos[0] if pos is not None else rp.x
                            fh_to_rope_dir = "right" if rp.x > _pcx else "left"
                            fh_state       = "to_rope"
                            fh_half_count  = 0
                            fh_last_side   = ""
                            # release_direction 제거 — walk_toward가 즉시 방향 설정
                            self._status(f"🎒 픽업 타이머 발동 → {to_name}")
                        else:
                            last_pickup_time = now  # 오류 시 타이머 리셋 (스팸 방지)
                            self._status(f"⚠ 픽업 루트 오류: '{to_name}' 또는 '{rp_name}' 미발견")

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
                                # 접근 목표: 밧줄 X 직접 (v1.1.6 방식)
                                # 점프 방향: approach 설정 기반 (v1.2.1 방식 유지)
                                _crp = fh_current_rope
                                if _crp is not None:
                                    # jump_offset 적용: 밧줄 옆에서 점프해 밧줄을 공중에서 잡음
                                    if _crp.approach == "left":
                                        _ax = _crp.x - _crp.jump_offset
                                        _jd = "right"
                                    elif _crp.approach == "right":
                                        _ax = _crp.x + _crp.jump_offset
                                        _jd = "left"
                                    else:  # both — 현재 위치 기준
                                        if cx <= _crp.x:
                                            _ax = _crp.x - _crp.jump_offset
                                            _jd = "right"
                                        else:
                                            _ax = _crp.x + _crp.jump_offset
                                            _jd = "left"
                                else:
                                    _ax = fh_rope_x
                                    _jd = "right" if fh_rope_x > cx else "left"
                                # 점프 전 이동 방향 저장 (pos 미감지 시 폴백용)
                                fh_to_rope_dir = "right" if _ax > cx else "left"
                                if abs(cx - _ax) <= FH_ROPE_EDGE:
                                    jump_key = self._minimap_reader.config.jump_key or "alt"
                                    if fh_next_dir > 0:        # 위층 — 방향키 꾹 누른 채 점프
                                        # _jd 방향키를 keepalive와 무관하게 직접 key_down
                                        self._map_navigator.walk_toward(
                                            1 if _jd == "right" else 0,
                                            0 if _jd == "right" else 1,
                                        )
                                        self._input.key_down(_jd)   # 방향키 확실히 누름
                                        # 방향키 유지한 채 점프키 누름/뗌
                                        self._input.key_down(jump_key)
                                        time.sleep(0.12)
                                        self._input.key_up(jump_key)
                                        # 점프 후 방향키 해제 → UP으로 전환
                                        self._map_navigator.release_direction()
                                        self._input.key_down("up")
                                    else:                       # 아래층 — 멈춰서 down+jump
                                        self._map_navigator.release_direction()
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
                                    self._map_navigator.walk_toward(_ax, cx)
                            else:
                                # pos 감지 실패 — 마지막으로 확인된 방향으로 이동 유지
                                # (전환 직후 release_direction 후 감지 실패 시에도 끊기지 않음)
                                self._map_navigator.walk_toward(
                                    1 if fh_to_rope_dir == "right" else 0,
                                    0 if fh_to_rope_dir == "right" else 1,
                                )

                        elif fh_state == "climbing":
                            # ── 오르기 / 내려가기 대기 ────────────────
                            if fh_next_dir > 0:
                                # UP만 유지 — 방향키를 누르면 옆으로 이동해 밧줄을 놓침
                                self._input.key_down("up")
                            elif (pos is not None
                                    and time.time() - fh_rope_escape_time >= FH_ROPE_ESCAPE_INTERVAL):
                                # 내려가는 중 밧줄에 걸린 경우 탈출 시도
                                # 점프 직후 0.8초는 원래 밧줄(fh_rope_x) 제외 (오감지 방지)
                                # 0.8초 이후엔 몬스터 팅김으로 재포획된 경우도 탈출 대상에 포함
                                _since_jump = time.time() - fh_climb_start
                                _jk = self._minimap_reader.config.jump_key or "alt"
                                for _rp in self._map_navigator.ropes:
                                    if _rp.x == fh_rope_x and _since_jump < 0.8:
                                        continue  # 점프 직후에는 원래 밧줄 제외
                                    if abs(pos[0] - _rp.x) <= 8:  # 3→8px (팅김 대응)
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
                            # 오르기 중 버프가 발동된 경우 UP 키 1초 추가
                            _BUFF_UP_EXTRA = 1.0
                            if (fh_next_dir > 0
                                    and self._last_buff_time > fh_climb_start
                                    and elapsed < wait_sec + _BUFF_UP_EXTRA):
                                wait_sec += _BUFF_UP_EXTRA
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
                                    # 낙사 복귀: 출발=목표(동일 층)이면 left_source 조건 불필요
                                    if src_zone is target_zone:
                                        arrived = in_target
                                    else:
                                        arrived = in_target and left_source
                                    _detected = _zone_by_y(cy)
                                    self._status(
                                        f"[층별] Y={cy} 확인 "
                                        f"목표 {target_zone.name}({target_zone.y_min}~{target_zone.y_max}) "
                                        f"출발 {src_zone.name}({src_zone.y_min}~{src_zone.y_max}) "
                                        f"이탈={'✓' if left_source else '✗'} "
                                        f"→ {'✓ 도착' if arrived else f'✗ 실패[감지:{_detected.name}]'}"
                                    )
                                if arrived:
                                    fh_climb_retry = 0            # 도착 성공 → 재시도 카운터 초기화
                                    fh_idx        = fh_next_idx
                                    fh_state      = "patrol"
                                    fh_last_side  = ""
                                    fh_arrive_time = time.time()   # Y 감지 쿨다운 시작
                                    self._map_navigator.set_zones([fh_zones[fh_idx]])
                                    _apply_zone_pattern(fh_zones[fh_idx])  # 층 도착 시 패턴 교체

                                    if pu_active:
                                        # ── 픽업 구역 도착 → 픽업 키 입력 ──
                                        self._status(f"🎒 {fh_zones[fh_idx].name} 픽업 중...")
                                        self._input.press_key(pu_key, hold_sec=pu_hold_sec)
                                        time.sleep(0.2)
                                        pu_step_idx += 1
                                        ropes = self._map_navigator.ropes

                                        if pu_step_idx < len(pu_route):
                                            # 다음 픽업 구역으로 이동
                                            nxt_step = pu_route[pu_step_idx]
                                            to_name  = nxt_step.get("to_zone", "")
                                            rp_name  = nxt_step.get("rope", "")
                                            to_zone  = next((z for z in fh_zones if z.name == to_name), None)
                                            rp       = next((r for r in ropes if r.name == rp_name), None)
                                            if to_zone and rp:
                                                fh_rope_x       = rp.x
                                                fh_current_rope = rp
                                                fh_climb_sec    = rp.climb_sec
                                                fh_next_idx     = fh_zones.index(to_zone)
                                                fh_next_dir     = 1 if to_zone.y_min < fh_zones[fh_idx].y_min else -1
                                                fh_state        = "to_rope"
                                                fh_half_count   = 0
                                                fh_last_side    = ""
                                                self._map_navigator.release_direction()
                                                self._status(f"🎒 다음 픽업 구역 → {to_name}")
                                            else:
                                                pu_active        = False
                                                last_pickup_time = time.time()
                                                self._status(f"⚠ 픽업 루트 오류 → 사냥 재개")
                                        else:
                                            # 모든 픽업 구역 완료 → 원래 사냥 구역 복귀
                                            pu_active        = False
                                            last_pickup_time = time.time()
                                            origin_zone = fh_zones[pu_prev_fh_idx]
                                            rp_back = next(
                                                (r for r in ropes if r.name == pu_route[-1].get("rope", "")),
                                                None,
                                            )
                                            if rp_back and pu_prev_fh_idx != fh_idx:
                                                fh_rope_x       = rp_back.x
                                                fh_current_rope = rp_back
                                                fh_climb_sec    = rp_back.climb_sec
                                                fh_next_idx  = pu_prev_fh_idx
                                                fh_next_dir  = 1 if origin_zone.y_min < fh_zones[fh_idx].y_min else -1
                                                fh_state     = "to_rope"
                                                fh_half_count = 0
                                                fh_last_side  = ""
                                                self._map_navigator.release_direction()
                                                self._status(f"🎒 픽업 완료 → '{origin_zone.name}' 복귀")
                                            else:
                                                self._map_navigator.set_zones([fh_zones[fh_idx]])
                                                self._status("🎒 픽업 완료 — 사냥 재개")
                                    else:
                                        self._status(f"[층별] {fh_zones[fh_idx].name} 사냥 시작")
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
                                        _y_str = f" Y={pos[1]}" if pos is not None else ""
                                        self._status(
                                            f"[층별] 낙사/이탈 감지{_y_str} → '{fh_zones[fh_idx].name}'({fh_zones[fh_idx].y_min}~{fh_zones[fh_idx].y_max}) 복귀"
                                        )
                                        _apply_zone_pattern(fh_zones[fh_idx])
                                    else:
                                        # 같은 층에서 밧줄 재시도 (재시도 한계 초과 시 현재층 순찰 복귀)
                                        fh_climb_retry += 1
                                        _y_str = f" Y={pos[1]}" if pos is not None else ""
                                        if fh_climb_retry >= FH_MAX_RETRY:
                                            fh_climb_retry = 0
                                            fh_state       = "patrol"
                                            fh_half_count  = 0
                                            fh_last_side   = ""
                                            fh_arrive_time = time.time()
                                            self._map_navigator.set_zones([fh_zones[fh_idx]])
                                            self._status(
                                                f"[층별] {target_zone.name} {FH_MAX_RETRY}회 실패{_y_str}"
                                                f" → {fh_zones[fh_idx].name} 순찰 복귀"
                                            )
                                        else:
                                            self._map_navigator.set_zones([fh_zones[fh_idx]])
                                            fh_state = "to_rope"
                                            self._status(
                                                f"[층별] {target_zone.name} 도착 실패{_y_str}"
                                                f" → 재시도 ({fh_climb_retry}/{FH_MAX_RETRY})"
                                            )

                        else:  # patrol
                            # ── 낙사/피격 감지: X 또는 Y가 현재 구역 밖이면 복귀 ──
                            # Y=0 은 미니맵 오감지(최상단 픽셀 노이즈)로 간주해 무시
                            if pos is not None and pos[1] > 0 and (
                                time.time() - fh_arrive_time >= FH_Y_COOLDOWN
                            ):
                                cur_zone  = fh_zones[fh_idx]
                                x_in_zone = (
                                    cur_zone.left_x - 5 <= pos[0] <= cur_zone.right_x + 5
                                )
                                y_in_zone = (
                                    cur_zone.y_min - 8 <= pos[1] <= cur_zone.y_max
                                )
                                if not x_in_zone or not y_in_zone:
                                    cy_now = pos[1]
                                    actual_zone = _zone_by_y(cy_now)
                                    actual_idx  = fh_zones.index(actual_zone)
                                    reason = ("X범위 이탈" if not x_in_zone else "낙사(Y 이탈)")
                                    # 현재 Y가 어떤 구역에도 속하지 않으면 → 미등록 층 낙사
                                    _y_in_any = any(
                                        z.y_min - 8 <= cy_now <= z.y_max
                                        for z in fh_zones
                                    )
                                    if actual_idx != fh_idx:
                                        fh_idx        = actual_idx
                                        fh_half_count = 0
                                        fh_last_side  = ""
                                        fh_route_idx  = 0   # 루트도 초기화
                                        fh_arrive_time = time.time()
                                        fh_fall_timer  = 0.0  # 등록 층으로 이동 → 타이머 해제
                                        self._map_navigator.set_zones([fh_zones[fh_idx]])
                                        self._status(
                                            f"[층별] {reason} Y={cy_now} "
                                            f"(현재구역 {cur_zone.name}:{cur_zone.y_min}~{cur_zone.y_max}) → "
                                            f"'{fh_zones[fh_idx].name}'({fh_zones[fh_idx].y_min}~{fh_zones[fh_idx].y_max}) 복귀"
                                        )
                                        _apply_zone_pattern(fh_zones[fh_idx])  # 복귀 층 패턴 교체
                                    elif not _y_in_any and not y_in_zone:
                                        # B안: 모든 등록 구역 밖 낙사 — 1초 지속 시 fh_zones[0]으로 복귀
                                        if fh_fall_timer <= 0.0:
                                            fh_fall_timer = time.time()
                                            self._status(
                                                f"[층별] 낙사 감지 Y={cy_now} — 1초 확인 중..."
                                            )
                                        elif time.time() - fh_fall_timer >= 1.0:
                                            fh_fall_timer   = 0.0
                                            _rcv_zone       = fh_zones[0]
                                            _ropes          = self._map_navigator.ropes
                                            if _rcv_zone.rope_x >= 0:
                                                _rcv_rope = next(
                                                    (r for r in _ropes if r.x == _rcv_zone.rope_x),
                                                    None,
                                                )
                                            elif _ropes:
                                                _rcv_rope = _ropes[0]
                                            else:
                                                _rcv_rope = None
                                            fh_rope_x       = (_rcv_rope.x if _rcv_rope
                                                                else (_rcv_zone.rope_x
                                                                      if _rcv_zone.rope_x >= 0
                                                                      else _rcv_zone.right_x))
                                            fh_current_rope = _rcv_rope
                                            fh_climb_sec    = (_rcv_rope.climb_sec if _rcv_rope
                                                                else FH_CLIMB_SEC)
                                            fh_next_idx     = 0
                                            # 현재 Y 기준으로 방향 결정
                                            # (아래층=Y큼 → 위로, 위층=Y작음 → 아래로)
                                            fh_next_dir     = (
                                                1 if cy_now > _rcv_zone.y_max else -1
                                            )
                                            fh_state        = "to_rope"
                                            fh_half_count   = 0
                                            fh_last_side    = ""
                                            self._map_navigator.release_direction()
                                            self._status(
                                                f"[층별] 낙사 확정 Y={cy_now} "
                                                f"→ '{_rcv_zone.name}'"
                                                f"({_rcv_zone.y_min}~{_rcv_zone.y_max}) 복귀 시작"
                                            )
                                else:
                                    # X·Y 모두 구역 안 → 낙사 타이머 초기화
                                    fh_fall_timer = 0.0

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
                                        fh_rope_x       = rp.x
                                        fh_current_rope = rp
                                        fh_climb_sec    = rp.climb_sec
                                        fh_next_idx     = fh_zones.index(to_zone)
                                        fh_next_dir     = 1 if to_zone.y_min < zone.y_min else -1
                                        _tcx            = pos[0] if pos is not None else rp.x
                                        fh_to_rope_dir  = "right" if rp.x > _tcx else "left"
                                        fh_state        = "to_rope"
                                        fh_half_count   = 0
                                        fh_last_side    = ""
                                        fh_route_idx   += 1
                                        # release_direction 제거 — walk_toward가 즉시 방향 설정
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
                                            fh_rope_x       = zone.rope_x
                                            matched_r       = next((r for r in ropes if r.x == zone.rope_x), None)
                                            fh_current_rope = matched_r
                                            fh_climb_sec    = matched_r.climb_sec if matched_r else 2.5
                                        elif ropes:
                                            rp_auto         = ropes[min(fh_idx, len(ropes) - 1)]
                                            fh_rope_x       = rp_auto.x
                                            fh_current_rope = rp_auto
                                            fh_climb_sec    = rp_auto.climb_sec
                                        else:
                                            fh_rope_x       = zone.right_x
                                            fh_current_rope = None
                                            fh_climb_sec    = 2.5
                                        fh_next_idx    = next_idx
                                        fh_next_dir    = fh_dir
                                        _tcx           = pos[0] if pos is not None else fh_rope_x
                                        fh_to_rope_dir = "right" if fh_rope_x > _tcx else "left"
                                        fh_state       = "to_rope"
                                        fh_half_count  = 0
                                        fh_last_side   = ""
                                        # release_direction 제거 — walk_toward가 즉시 방향 설정

                            if not _transit and pos is not None:
                                cx = pos[0]
                                EDGE = 4
                                if cx <= zone.left_x + EDGE:
                                    side = "left"
                                elif cx >= zone.right_x - EDGE:
                                    side = "right"
                                else:
                                    side = ""

                                # 경계 감지 시 map_navigator 방향 즉시 강제 보정
                                # — key_hunter 블록 중 경계를 지나쳤다가 몬스터 밀림으로
                                #   되돌아온 경우에도 올바른 방향으로 즉시 전환
                                if side == "left":
                                    self._map_navigator.force_direction("right")
                                elif side == "right":
                                    self._map_navigator.force_direction("left")

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
                                                fh_rope_x       = rp.x
                                                fh_current_rope = rp
                                                fh_climb_sec    = rp.climb_sec
                                                fh_next_idx     = fh_zones.index(to_zone)
                                                fh_next_dir     = (
                                                    1 if to_zone.y_min < zone.y_min else -1
                                                )
                                                fh_to_rope_dir  = "right" if rp.x > cx else "left"
                                                fh_state        = "to_rope"
                                                fh_half_count   = 0
                                                fh_last_side    = ""
                                                fh_route_idx   += 1
                                                # release_direction 제거 — walk_toward가 즉시 방향 설정
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
                                                    fh_rope_x       = zone.rope_x
                                                    matched_r       = next(
                                                        (r for r in ropes if r.x == zone.rope_x), None
                                                    )
                                                    fh_current_rope = matched_r
                                                    fh_climb_sec    = matched_r.climb_sec if matched_r else 2.5
                                                elif ropes:
                                                    rp_auto         = ropes[min(fh_idx, len(ropes) - 1)]
                                                    fh_rope_x       = rp_auto.x
                                                    fh_current_rope = rp_auto
                                                    fh_climb_sec    = rp_auto.climb_sec
                                                else:
                                                    fh_rope_x       = zone.right_x
                                                    fh_current_rope = None
                                                    fh_climb_sec    = 2.5
                                                fh_next_idx    = next_idx
                                                fh_next_dir    = 1 if fh_zones[next_idx].y_min < zone.y_min else -1
                                                fh_to_rope_dir = "right" if fh_rope_x > cx else "left"
                                                fh_state       = "to_rope"
                                                fh_half_count  = 0
                                                fh_last_side   = ""
                                                # release_direction 제거 — walk_toward가 즉시 방향 설정
                                                self._status(
                                                    f"[층별] {zone.name} 완료 "
                                                    f"→ {fh_zones[next_idx].name} 이동"
                                                )

                    # ── YOLO11 몬스터 감지 파이프라인 ────────────────────
                    if self._yolo_detector is not None:
                        self._yolo_frame_count += 1
                        _yolo_cfg  = self._config.get("yolo") or {}
                        _every_n   = max(1, int(_yolo_cfg.get("every_n_frame", 2)))
                        if self._yolo_frame_count % _every_n == 0:
                            try:
                                _frame = self._screen.capture()
                                if _frame is not None:
                                    _roi_ratio = _yolo_cfg.get(
                                        "roi_ratio", [0.1, 0.1, 0.9, 0.9]
                                    )
                                    _roi = self._roi_manager.get_absolute_roi(
                                        _frame.shape, _roi_ratio
                                    )
                                    _det = self._yolo_detector.detect(_frame, roi=_roi)
                                    _char_raw = (
                                        _det["character"]["center"]
                                        if _det["character"] else None
                                    )
                                    _char_center = self._char_tracker.update(_char_raw)
                                    _decision = self._attack_decision.calculate(
                                        _char_center, _det["monsters"]
                                    )
                                    self._yolo_last_result = _decision
                                    # 디버그 오버레이용 game_state 갱신
                                    try:
                                        self.game_state.update(
                                            monster_positions=[
                                                m["box"] for m in _det["monsters"]
                                            ],
                                            char_pos_smooth=_char_center,
                                        )
                                    except Exception:
                                        pass
                            except Exception as _ye:
                                logger.warning("YOLO 파이프라인 오류: %s", _ye)

                    # 이동 (층 이동 중 또는 통과 층에서는 스킵)
                    _on_transit = (use_floor_hunt and bool(fh_zones) and fh_state == "patrol"
                                   and fh_zones[fh_idx].sweeps == 0)
                    if not use_floor_hunt or (fh_state == "patrol" and not _on_transit):
                        if self._enable_move:
                            self._map_navigator.run_one_step()
                            # floor_hunt 모드: map_navigator가 자체 밧줄 점프를 하면
                            # bot_loop의 to_rope 점프 전에 extra 점프가 발생하므로 취소
                            if use_floor_hunt:
                                self._map_navigator.cancel_rope_state()

                except Exception as exc:
                    logger.exception("루프 오류: %s", exc)
                    self._status(f"오류: {exc}")
        finally:
            self._map_navigator.release_direction()
            if self._floor_hunt_thread and self._floor_hunt_thread.is_alive():
                self._floor_hunt_thread.join(timeout=3)
            self.game_state.update(bot_state="stopped", monster_positions=[], char_pos=None)
            # 내부 정지(이탈 감지 등)인 경우 UI 상태 동기화
            try:
                self._on_stop_cb()
            except Exception:
                pass
        logger.info("봇 루프 종료")

    # ── 자동 판매 스레드 ──────────────────────────────────────────────
    def _auto_sell_worker(self) -> None:
        """안전지대 도착 후 sell_junk 를 실행하는 전용 스레드."""
        try:
            from core.junk_seller import sell_junk
            sell_junk(
                self._config,
                self._screen,
                self._input,
                self._status,
                self._stop_event,
            )
        except Exception as e:
            self._status(f"자동 판매 오류: {e}")
            logger.exception("자동 판매 오류: %s", e)
        finally:
            self._auto_sell_last    = time.time()
            self._auto_sell_selling = False
            self._auto_sell_active  = False
            self._as_phase          = "idle"
            self._as_return_to_hunt = True   # 메인 루프에 사냥 구역 복귀 신호
            self._status("자동 판매 완료 — 사냥 구역 복귀 중...")

    # ── 공격 패턴 전용 루프 (별도 스레드) ───────────────────────────────
    def _attack_loop(self) -> None:
        """공격 패턴을 메인 루프와 독립적으로 실행하는 전용 스레드.

        fh_state 가 to_rope/climbing 이거나 자동 판매 중에는
        KeyHunter.pause() 로 중단 신호가 전달되어 자동으로 대기한다.
        """
        while not self._stop_event.is_set():
            try:
                if self._enable_attack and self._key_hunter.has_pattern():
                    if self._key_hunter.is_paused:
                        # 일시정지 중 타이트 스핀 방지 — GIL 양보로 방향키 스레드 우선 실행
                        self._stop_event.wait(0.05)
                    else:
                        self._key_hunter.run_one_step()
                else:
                    self._stop_event.wait(0.05)
            except Exception as exc:
                logger.warning("attack_loop 오류: %s", exc)

    # ── 방향키 유지 전용 루프 (별도 스레드) ──────────────────────────
    def _direction_keepalive_loop(self) -> None:
        """안전감지/스킬 블로킹과 무관하게 40ms마다 방향키 key_down을 재전송."""
        while not self._stop_event.is_set():
            if self._enable_move:
                self._map_navigator.refresh_direction()
            self._stop_event.wait(timeout=0.04)

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
                                self._input.press_key(key, hold_sec=0.35)
                                time.sleep(0.15)
                            self._status(f"🐾 펫먹이 급여 완료 — [{key}] {count}마리")
                            last_pet = now
                    elif pet_logged:
                        pet_logged = False  # 설정이 비활성화되면 다음 활성화 시 재출력

                # ── 버프 (동적 목록) ──────────────────────────────────
                # 여러 버프가 동시 만료될 때 스킬 모션 시간을 주어 순차 발동
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
                            self._input.press_key(buff["key"].strip(), hold_sec=0.35)
                            last_buffs[key_id] = time.time()
                            self._last_buff_time = time.time()  # 밧줄 오르기 연장 판단용
                            self._status(f"✨ {label} 사용 ({buff['key']})")
                            time.sleep(0.7)  # 스킬 모션 완료 대기 (다음 버프 캔슬 방지)

            except Exception as exc:
                logger.warning("포션 루프 오류: %s", exc)
            self._stop_event.wait(timeout=POTION_CHECK_INTERVAL)
        logger.info("포션 루프 종료")

    # ── 백그라운드 안전 감지 스레드 ──────────────────────────────────────
    def _safety_detect_loop(self) -> None:
        """거짓말탐지기·투명도형 감지 전용 백그라운드 스레드.

        무거운 YOLO 추론과 템플릿 매칭을 메인 루프 밖에서 실행해
        공격/이동 딜레이를 방지한다.
        감지 시 self._safety_pending 에 "lie" 또는 "transparent" 를 저장.
        메인 루프가 처리한 뒤 None 으로 초기화.
        """
        import glob
        from core.config_manager import resolve_region_coords, logical_to_physical_coords
        from core.transparent_shape_game import TITLE_TEMPLATE, TITLE_THRESHOLD

        while not self._stop_event.is_set():
            try:
                if self._safety_pending is None:
                    screenshot = self._screen.capture()

                    # ── 거짓말탐지기 감지 ────────────────────────────────
                    if self._enable_lie_notify or self._enable_lie_solve:
                        lie_cfg = self._config.get("settings1", "lie_detector") or {}
                        if lie_cfg.get("enabled"):
                            _lie_yolo_path = (lie_cfg.get("yolo_model_path") or "").strip()

                            if _lie_yolo_path:
                                # ── YOLO 전용 감지 (템플릿 매칭 사용 안 함) ──
                                if self._lie_yolo is None:
                                    try:
                                        from core.yolo_detector import YoloDetector
                                        self._lie_yolo = YoloDetector(
                                            _lie_yolo_path,
                                            confidence=float(lie_cfg.get("yolo_confidence", 0.25)),
                                            iou=0.45,
                                            max_det=5,
                                        )
                                        logger.info("거짓말탐지기 YOLO 로드: %s", _lie_yolo_path)
                                    except Exception as _e:
                                        logger.warning("거짓말탐지기 YOLO 로드 실패: %s", _e)
                                        self._lie_yolo = None

                                if self._lie_yolo and self._lie_yolo.is_loaded:
                                    _det = self._lie_yolo.detect(screenshot)
                                    if _det["monsters"]:
                                        self._safety_pending = "lie"
                            else:
                                # ── 템플릿 매칭 폴백 (YOLO 미설정 시) ──
                                patterns = sorted(glob.glob("templates/lie_detector_*.png"))
                                if patterns:
                                    region = lie_cfg.get("region")
                                    resolved = resolve_region_coords(self._config, region)
                                    if resolved:
                                        rx, ry, rw, rh = resolved
                                        rpx, rpy, rpw, rph = logical_to_physical_coords(
                                            rx, ry, rw, rh
                                        )
                                        target = self._screen.capture(
                                            {"left": rpx, "top": rpy,
                                             "width": rpw, "height": rph}
                                        )
                                    else:
                                        target = screenshot
                                    for tpl_path in patterns:
                                        _lie_score = self._screen.find_template_score(
                                            target, tpl_path
                                        )
                                        if _lie_score >= 0.65:
                                            self._safety_pending = "lie"
                                            break
                                        elif _lie_score >= 0.3:
                                            import os as _os
                                            self._status(
                                                f"[거탐] {_os.path.basename(tpl_path)} "
                                                f"점수={_lie_score:.3f} (기준 0.65 미달)"
                                            )

                    # ── 투명 도형 찾기 감지 ──────────────────────────────
                    if self._safety_pending is None and self._enable_transparent_shape:
                        ts_cfg = self._config.get("settings1", "transparent_shape") or {}
                        if ts_cfg.get("enabled"):
                            detected = False
                            # YOLO 감지
                            if self._transparent_yolo and self._transparent_yolo.is_loaded:
                                det = self._transparent_yolo.detect(screenshot)
                                if det["monsters"]:
                                    detected = True
                            # 템플릿 매칭 폴백
                            if not detected:
                                score = self._screen.find_template_score(
                                    screenshot, TITLE_TEMPLATE
                                )
                                if score >= TITLE_THRESHOLD:
                                    detected = True
                            if detected:
                                self._safety_pending = "transparent"

            except Exception as exc:
                logger.warning("_safety_detect_loop 오류: %s", exc)

            self._stop_event.wait(SAFETY_CHECK_INTERVAL)

    # ── 감지 핸들러 ───────────────────────────────────────────────────
    def _fire_lie_alarm(self) -> None:
        """경보음 + 텔레그램 알림 발동. 거짓말탐지기/투명도형 두 경로 공용."""
        if not self._enable_lie_notify:
            return
        cfg = self._config.get("settings1", "lie_detector") or {}
        # 1. 경보음
        if cfg.get("play_alarm"):
            import winsound
            for _ in range(3):
                winsound.Beep(1000, 300)
                time.sleep(0.1)
        # 2. 텔레그램 (백그라운드 스레드)
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

    def _check_transparent_shape(self, screenshot) -> bool:
        """투명 도형 찾기 미니게임 감지 시 폐루프 추적 루프를 실행한다.

        감지 우선순위:
          1. YOLO (settings1.transparent_shape.yolo_model_path 설정 시)
          2. 템플릿 매칭 폴백 (templates/transparent_shape_title.png)

        YOLO 감지 시 board ROI를 bbox에서 자동 계산 (수동 좌표 설정 불필요).
        """
        cfg = self._config.get("settings1", "transparent_shape") or {}
        if not cfg.get("enabled"):
            return False  # 설정1 탭에서 "투명 도형 찾기 활성화" 체크 필요

        # lazy init TransparentShapeGame
        if self._transparent_game is None:
            from core.transparent_shape_game import TransparentShapeGame
            self._transparent_game = TransparentShapeGame(
                self._screen, self._input, self._config, self._stop_event
            )
            self._transparent_game.window_title = self._game_window_title()

        # ── 1단계: YOLO 감지 시도 ─────────────────────────────────────
        detected_bbox = None  # [x1, y1, x2, y2] — 헤더 bbox
        yolo_model_path = (cfg.get("yolo_model_path") or "").strip()
        if yolo_model_path:
            # lazy init 투명 도형 전용 YOLO (신뢰도 0.25 — 소량 학습 데이터 대응)
            if self._transparent_yolo is None:
                try:
                    from core.yolo_detector import YoloDetector
                    self._transparent_yolo = YoloDetector(
                        yolo_model_path,
                        confidence=float(cfg.get("yolo_confidence", 0.25)),
                        iou=0.45,
                        max_det=5,
                    )
                    logger.info("투명 도형 YOLO 로드: %s", yolo_model_path)
                except Exception as e:
                    logger.warning("투명 도형 YOLO 로드 실패: %s", e)
                    self._transparent_yolo = None

            if self._transparent_yolo and self._transparent_yolo.is_loaded:
                det = self._transparent_yolo.detect(screenshot)
                if det["monsters"]:
                    best = max(det["monsters"], key=lambda m: m["conf"])
                    detected_bbox = best["box"]  # [x1, y1, x2, y2]

        # ── 2단계: 템플릿 매칭 폴백 ──────────────────────────────────
        if detected_bbox is None:
            title_pos = self._transparent_game.detect_title(screenshot)
            if title_pos is None:
                return False
            # 템플릿 중심 좌표로 헤더 bbox 추정 → dynamic_roi 자동 계산에 활용
            # (config board_roi의 잘못된 좌표 사용 방지)
            try:
                import cv2 as _cv2
                from core.transparent_shape_game import TITLE_TEMPLATE as _TTPL
                _tpl = _cv2.imread(_TTPL)
                if _tpl is not None:
                    _th, _tw = _tpl.shape[:2]
                    _tx, _ty = title_pos
                    detected_bbox = [_tx - _tw // 2, _ty - _th // 2,
                                     _tx + _tw // 2, _ty + _th // 2]
            except Exception:
                pass

        # ── 감지 확정 → 알람 발동 후 추적 시작 ──────────────────────────
        # 이 시점에 YOLO 또는 템플릿으로 팝업이 실제 화면에 있음을 확인한 뒤 알람 발동.
        # 유저가 이미 직접 해제해 팝업이 닫힌 경우 위 return False 로 여기까지 오지 않음.
        self._fire_lie_alarm()
        self._status("투명 도형 찾기 감지! 마우스 추적 시작...")

        # board ROI는 항상 config 비율 좌표 사용 (YOLO bbox는 팝업 전체를 감싸므로
        # y2를 board 시작점으로 쓰면 화면 밖으로 나갈 수 있음)
        dynamic_roi = None  # None → run_follow_loop 내부에서 get_board_roi() 호출

        # 게임 종료 감지 함수 — YOLO 있으면 YOLO, 없으면 템플릿 매칭
        _yolo_ref = self._transparent_yolo  # 클로저 캡처

        def _detect_end(shot) -> bool:
            """True = 게임 아직 진행 중, False = 게임 종료."""
            if _yolo_ref and _yolo_ref.is_loaded and detected_bbox is not None:
                det = _yolo_ref.detect(shot)
                return bool(det["monsters"])
            return self._transparent_game.detect_title(shot) is not None

        floor_cfg = self._config.get("floor_hunt") or {}
        if floor_cfg.get("enabled"):
            self._floor_hunter.pause()
        try:
            self._input.focus_game_window()
            self._transparent_game.run_follow_loop(
                self._status,
                board_roi=dynamic_roi,
                detect_end_fn=_detect_end,
            )
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

        # ── 감지: YOLO 우선, 템플릿 매칭 폴백 ─────────────────────────
        _lie_yolo_path = (cfg.get("yolo_model_path") or "").strip()
        matched_pos  = None
        best_score   = 0.0
        detect_mode  = ""
        region       = cfg.get("region")

        if _lie_yolo_path:
            # YOLO 전용
            # _safety_detect_loop 에서 이미 감지 확인됨 → 재감지 실패해도 알림·해제 진행
            if self._lie_yolo and self._lie_yolo.is_loaded:
                _det = self._lie_yolo.detect(screenshot)
                if _det["monsters"]:
                    _b = _det["monsters"][0]["box"]   # [x1, y1, x2, y2]
                    matched_pos = (int((_b[0] + _b[2]) / 2), int((_b[1] + _b[3]) / 2))
                    detect_mode = f"YOLO conf={_det['monsters'][0]['conf']:.2f}"
                else:
                    # 재감지 실패 — 화면이 이미 투명도형 찾기로 전환됐을 가능성 높음
                    # 알림·해제는 계속 진행 (matched_pos=None 이므로 run_follow_loop 사용)
                    detect_mode = "YOLO 감지됨 (재감지 실패 — 화면 전환 추정)"
            else:
                self._status("거짓말탐지기 YOLO: 모델 미로드 — 설정1 탭의 모델 경로를 확인하세요")
                return False
        else:
            # 템플릿 매칭 폴백
            import glob
            from core.config_manager import resolve_region_coords, logical_to_physical_coords
            patterns = sorted(glob.glob("templates/lie_detector_*.png"))
            if not patterns:
                self._status("⚠ 거짓말탐지기 템플릿 없음 — 설정1 탭에서 캡처 필요")
                return False

            resolved = resolve_region_coords(self._config, region)
            if resolved:
                rx, ry, rw, rh = resolved
                rpx, rpy, rpw, rph = logical_to_physical_coords(rx, ry, rw, rh)
                target = self._screen.capture({"left": rpx, "top": rpy, "width": rpw, "height": rph})
            else:
                target = screenshot

            for tpl_path in patterns:
                score = self._screen.find_template_score(target, tpl_path)
                if score > best_score:
                    best_score = score
                if score >= 0.65:
                    matched_pos = self._screen.find_template(target, tpl_path, threshold=0.65)
                    if matched_pos:
                        if region and matched_pos:
                            matched_pos = (matched_pos[0] + rx, matched_pos[1] + ry)
                        break

            if matched_pos is None:
                self._status(f"[탐지기 점수] {best_score:.2f}  (기준 0.65 이상이면 감지)")
                return False
            detect_mode = f"템플릿 {len(patterns)}개 중 매칭"

        self._status(f"거짓말탐지기 감지! ({detect_mode})")

        # ── 상세 로그 — ① 감지 영역 ────────────────────────────────────
        self._lie_log("━━━━━ 거짓말탐지기 감지 ━━━━━")
        if region and len(region) == 4:
            rx, ry, rw, rh = region
            self._lie_log(f"① 감지 영역  X={rx} Y={ry} W={rw} H={rh}  [설정됨]")
        else:
            self._lie_log("① 감지 영역  전체 화면 (미설정)")
        self._lie_log(f"   감지 방식={detect_mode}  위치={matched_pos}")

        # ── 알림 (거탐 알림 모듈이 켜진 경우) ────────────────────────
        self._fire_lie_alarm()

        # ── 해제 (거탐 해제 모듈이 꺼진 경우 알림만 하고 복귀) ────────
        if not self._enable_lie_solve:
            return True   # 감지는 됐으나 해제 생략 — 루프 한 번 스킵

        floor_cfg = self._config.get("floor_hunt") or {}
        if floor_cfg.get("enabled"):
            self._floor_hunter.pause()
        try:
            # ── 투명 도형 찾기 미니게임 연동 ──────────────────────────────
            ts_cfg = self._config.get("settings1", "transparent_shape") or {}
            if self._enable_transparent_shape and ts_cfg.get("enabled"):
                # lazy init
                if self._transparent_game is None:
                    from core.transparent_shape_game import TransparentShapeGame
                    self._transparent_game = TransparentShapeGame(
                        self._screen, self._input, self._config, self._stop_event
                    )
                    self._transparent_game.window_title = self._game_window_title()
                self._status("거짓말탐지기 → 투명 도형 찾기 실행 중...")
                self._input.focus_game_window()
                self._transparent_game.run_follow_loop(self._status)
                self._status("거짓말탐지기 → 투명 도형 찾기 완료")
            else:
                # 투명 도형 찾기 비활성 시 슬라이딩 퍼즐 해제 (matched_pos = YOLO bbox 중심)
                if matched_pos:
                    self._input.focus_game_window()
                    time.sleep(0.3)
                    self._solve_lie_detector(matched_pos)
                else:
                    self._status("⚠ 거짓말탐지기 위치 미확인 — YOLO 모델 설정 필요")
            time.sleep(0.8)
        finally:
            if floor_cfg.get("enabled"):
                self._floor_hunter.resume()
        return True

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
        # stat_assign 비활성화 시 템플릿 로드 자체를 건너뜀 (missing 파일 경고 방지)
        sa_cfg = self._config.get("settings1", "stat_assign") or {}
        if not sa_cfg.get("enabled"):
            return
        import os
        if not os.path.exists(TEMPLATES["level_up"]):
            return
        pos = self._screen.find_template(screenshot, TEMPLATES["level_up"])
        if pos is None:
            return
        self._status("레벨업 감지")
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
        if not name_region:
            return  # 기준 영역 미설정 → 동작 안 함
        from core.config_manager import get_user_templates_dir, resolve_region_coords, logical_to_physical_coords
        ref_path = os.path.join(get_user_templates_dir(), "map_name_ref.png")
        if not os.path.exists(ref_path):
            return  # 기준 이미지 없음 → 동작 안 함

        resolved = resolve_region_coords(self._config, name_region)
        if not resolved:
            return
        lx, ly, lw, lh = resolved
        px, py, pw, ph = logical_to_physical_coords(lx, ly, lw, lh)
        current = self._screen.capture({"left": px, "top": py, "width": pw, "height": ph})
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

    def _check_town_scroll_trigger(self, hp: float, mp: float) -> None:
        """HP 또는 MP가 설정 퍼센트 미만이면 긴급 마을 귀환 키를 발동한다."""
        ts = self._config.get("town_scroll") or {}
        if not ts.get("enabled", False):
            return
        hp_on = ts.get("hp_trigger", False)
        mp_on = ts.get("mp_trigger", False)
        if not hp_on and not mp_on:
            return

        hp_pct = int(ts.get("hp_trigger_pct", 10)) / 100.0
        mp_pct = int(ts.get("mp_trigger_pct", 10)) / 100.0

        reasons = []
        if hp_on and hp < hp_pct:
            reasons.append(f"HP {hp*100:.0f}% < {hp_pct*100:.0f}%")
        if mp_on and mp < mp_pct:
            reasons.append(f"MP {mp*100:.0f}% < {mp_pct*100:.0f}%")

        if reasons:
            self._status(f"⚠️ 긴급 마을 귀환 발동 ({' '.join(reasons)})")
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
        if region:
            from core.config_manager import resolve_region_coords, logical_to_physical_coords
            resolved_r = resolve_region_coords(self._config, region)
            if resolved_r:
                rlx, rly, rlw, rlh = resolved_r
                rpx, rpy, rpw, rph = logical_to_physical_coords(rlx, rly, rlw, rlh)
                target = self._screen.capture({"left": rpx, "top": rpy, "width": rpw, "height": rph})
            else:
                target = screenshot
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
