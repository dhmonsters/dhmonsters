# BotRuntime ??7媛?紐⑤뱢??議곕┰?????깆씠 ?꾨뒗 遊??고??? 寃뚯엫/?쒕씪?대쾭??二쇱엯???뚯뒪??媛??
from __future__ import annotations

import queue
import threading
import time
import sys
from dataclasses import dataclass, field
from pathlib import Path

from core.sensing.char_scanner import CharScanner
from core.sensing.antimob_scanner import AntiMobScanner
from core.sensing.lie_scanner import LieScanner
from core.sensing.event import Event
from core.orchestrator.orchestrator import Orchestrator
from core.navigation.block import Block
from core.navigation.block_runner import BlockRunner
from core.navigation.floor_judge import Floor, FloorJudge
from core.navigation.patrol import Patrol, PatrolZone
from core.acting.combat import Combat, PotionRule
from core.acting.attack_sequence import AttackSequence, AttackSequenceRunner
from core.acting.buff import BuffManager, Buff
from core.acting.pet import PetFeeder
from core.humanize.timing import down_5
from core.sensing.user_scanner import UserScanner
from core.sensing import monster_vision
from core.notify.telegram import TelegramNotifier
from core.minigame.registry import SolverRegistry


def _app_path(path: str) -> str:
    """상대 리소스 경로를 프로젝트/EXE 기준 절대경로로 변환한다."""
    if not path:
        return path
    candidate = Path(path)
    if candidate.is_absolute():
        return str(candidate)
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return str(base / candidate)
from core.minigame.self_transparent_engine import SelfTransparentEngine
from core.minigame.sidecar import InMemoryChannel, SidecarChannel
from core.navigation.viewport_tracker import ViewportTracker
from core.navigation.image_trigger import ImageTrigger
from core.navigation.world_map import WorldMapModel
from core.navigation.world_runner import ActionExecutor, WorldRouteRunner
from core.sensing.world_position_scanner import WorldPositionScanner
from core.navigation.route_state import RouteStep
from core.navigation.route_position import LatestPositionStore
from core.navigation.route_input_owner import RouteInputOwner
from core.navigation.route_state_runner import RouteStateRunner
from core.navigation.floor_hunt_runner import FloorHuntRunner
from core.navigation.rednose2_runner import RedNose2RouteRunner
from core.navigation.rednose3_runner import RedNose3RouteRunner
from core.auto_seller import AutoSeller


@dataclass
class RuntimeConfig:
    """?고???議곕┰???꾩슂???ㅼ젙 (config.json ?먯꽌 留ㅽ븨)."""
    minimap_region: dict
    floors: list[Floor] = field(default_factory=list)
    route: list[Block] = field(default_factory=list)
    route_steps: list[RouteStep] = field(default_factory=list)
    route_mode: bool = False     # True硫?route瑜?floor-hunt 猷⑦듃 ?ㅽ뻾湲곕줈 諛섎났 ?ㅽ뻾(?щ떎由?紐⑤뱶)
    hunt_ground_active: str = ""
    rednose2_v5: dict = field(default_factory=dict)
    rednose3: dict = field(default_factory=dict)
    attack_key: str = ""
    attack_sequences: list[AttackSequence] = field(default_factory=list)
    hp_rule: PotionRule | None = None
    mp_rule: PotionRule | None = None
    buffs: list[Buff] = field(default_factory=list)
    antimob_templates: dict = field(default_factory=dict)
    antimob_enabled: dict = field(default_factory=dict)
    anti_mob_profile: dict = field(default_factory=dict)
    minigame_type: str = "planet"
    # 嫄고깘 (?먯껜 ncnn ?붿쭊)
    transparent_models_dir: str = "models/transparent"
    board_region: dict | None = None          # 嫄고깘 寃뚯엫???붾㈃?곸뿭 (None=board_roi 鍮꾩쑉 ?ъ슜)
    board_roi: dict | None = None              # A 怨좎젙 ?곷?醫뚰몴 {x_ratio,y_ratio,w_ratio,h_ratio}
    transparent_use_gpu: bool = False
    transparent_enabled: bool = True           # ?щ챸?꾪삎 ?먮룞???on/off (泥댄겕諛뺤뒪 寃뚯씠??
    # 嫄고깘 媛먯? (LieScanner)
    lie_enabled: bool = True
    lie_alert: bool = False                     # 嫄고깘 ?뚮┝(?뚮━+?붾젅洹몃옩) ?듯빀 ?좉?
    lie_title_template: str = "templates/lie_detector/title.png"
    lie_threshold: float = 0.65
    lie_detect_region: dict | None = None      # ??댄? ?먯깋 ?곸뿭 (None=?꾩껜?붾㈃)
    # ?쒖같 (Patrol) ??泥?援ъ뿭 醫뚯슦 寃쎄퀎
    patrol_left_x: int = 0
    patrol_right_x: int = 0
    patrol_margin: int = 0
    # ?≫뀥 ?먮ℓ ??ConfigManager(get ?명꽣?섏씠?? 二쇱엯 ???쒖꽦. ?놁쑝硫?鍮꾪솢??
    junk_config: object = None
    auto_sell_enabled: bool = False
    auto_sell_interval_min: float = 10.0
    auto_sell_on_start: bool = False
    # ??癒뱀씠
    pet_key: str = ""
    pet_interval: float = 600.0
    pet_count: int = 1
    attack_interval: float = 0.4   # 怨듦꺽???щ늻由?理쒖냼 媛꾧꺽(珥? ??留????꾨같 諛⑹?(?ㅽ궗 ?쒕젅??
    # ?대룞 ?먰봽 ??醫뚯슦 嫄룰린 ?숈븞 ?먰봽?ㅻ? ?꾨Ⅸ 梨??좎?(諛붾땲??. ?щ떎由?룻뀛?덊룷???대룞??誘몄쟻??
    jump_key: str = "alt"
    jump_while_move: bool = False
    ladder_launch_distance: float = 5.0
    ladder_launch_distance_right: float = 7.0
    ladder_launch_distance_left: float = 2.0
    ladder_jump_hold_sec: float = 0.10
    ladder_up_delay_sec: float = 0.125
    ladder_direction_hold_sec: float = 0.08
    ladder_stable_tolerance: int = 2
    ladder_stable_samples: int = 3
    ladder_position_max_age_sec: float = 0.15
    ladder_grab_confirm_sec: float = 1.00
    # ???= 紐⑺몴 諛⑹닔 횞 ?ㅽ궗1???쒓컙 (紐뱀씠 紐?諛⑹뿉 二쎈뒗吏??留욎떠 洹몃쭔??湲멸쾶 ?꾨쫫)
    hits_to_kill: int = 1          # 紐?泥섏튂???꾩슂???寃???
    skill_cast_sec: float = 0.6    # ?ㅽ궗 1???쒖쟾 ?쒓컙(珥? ??1諛??섍????쒓컙
    # 諛吏??щ깷(?쒓컙??泥섏튂 理쒖쟻??: ?щ깷?곸뿭 紐?媛쒖닔濡?硫덉떠?щ깷?붿씠??寃곗젙
    hunt_stay_threshold: int = 3    # ??留덈━???댁긽?대㈃ 硫덉떠 ?щ깷(諛吏?
    hunt_leave_threshold: int = 1   # ??留덈━???댄븯濡?以꾨㈃ ?대룞(?ъ냼)
    hunt_max_dwell_sec: float = 8.0 # ???먮━ 理쒕? 泥대쪟(諛吏묒씠?대룄 珥덇낵 ??媛뺤젣 ?대룞)
    # ?쎌뾽 ??대㉧ ??二쇨린?곸쑝濡?以띻린 ???낅젰(諛붾떏 ?꾩씠???먮룞 以띻린)
    pickup_key: str = ""
    pickup_interval: float = 60.0
    pickup_always: bool = False
    # ?붾젅洹몃옩 ?뚮┝
    tg_enabled: bool = False
    tg_token: str = ""
    tg_chat_id: str = ""
    # ?ㅻⅨ ?좎? 媛먯? + ?먮룞?묐떟
    user_detect_enabled: bool = False
    user_min_red: int = 15
    auto_reply_messages: list = field(default_factory=list)
    # ?щ깷 ?곸뿭 (B training: ???곸뿭 ?덉뿉?쒕쭔 紐ъ뒪???됰꽕??媛먯?)
    hunt_area_region: dict | None = None
    world_map: "WorldMapModel | None" = None
    image_trigger_spec: object = None
    # 醫뚰몴 湲곗? ??relative硫??곸뿭??寃뚯엫李??대룞???꾩옱?먯젏-?듭빱)留뚰겮 蹂댁젙(李??곕씪媛?
    coord_mode: str = "absolute"
    game_window_title: str = ""
    coord_anchor: list | None = None      # ?곸뿭 吏???쒖젏 李??먯젏 [ox, oy]
    char_rgb: tuple | None = None          # 誘몃땲留?罹먮┃??????RGB). None?대㈃ 湲곕낯 ?몃옉
    char_h_low: int | None = None
    char_h_high: int | None = None
    char_h_tol: int = 10
    char_s_min: int = 100
    char_v_min: int = 200
    char_area_min: float = 3.0
    char_area_max: float = 160.0
    char_position_offset_x: int = 0
    char_position_offset_y: int = 0
    # 紐ъ뒪??媛먯?(image 紐⑤뱶, B 硫붿빱?덉쬁: ?됰꽕??諛뺤뒪 ??紐ъ뒪??
    hunt_mode: str = "key"
    name_template: str = ""        # ?됰꽕???쒗뵆由?寃쎈줈
    monster_templates: list = field(default_factory=list)  # 紐ъ뒪???쒗뵆由?寃쎈줈??
    monster_accuracy: float = 0.9
    atk_x_min: int = -35
    atk_x_max: int = 35
    atk_y_min: int = -70
    atk_y_max: int = 70
    name_threshold: float = 0.7


class BotRuntime:
    """7紐⑤뱢 議곕┰ + ???ㅽ뻾. ?섏〈???붾㈃罹≪쿂/?낅젰諛깆뿏??梨꾨꼸)? 二쇱엯 ???ㅺ린/?뚯뒪??怨듭슜.

    ?ㅺ린: screen_capture=?ㅼ젣 mss, input_backend=InterceptionBackend
    ?뚯뒪?? Fake capture + RecordingBackend
    """

    def __init__(self, screen_capture, input_backend, config: RuntimeConfig,
                 sidecar_channel: SidecarChannel | None = None,
                 hp_mp_reader=None):
        self._capture = screen_capture
        self._cfg = config
        self._anti_mob_busy = False
        self._anti_mob_moving = False
        self._anti_mob_failed = False
        self._anti_mob_last = -1e9
        self._anti_mob_last_diag = -1e9
        self._sidecar = sidecar_channel or InMemoryChannel()
        # HP/MP 鍮꾩쑉???쎌뼱 (hp, mp) 諛섑솚?섎뒗 肄쒕갚(run_integrated媛 Detector濡?二쇱엯).
        # ?듯빀 ?ы똿 ???ъ뀡 諛곗꽑??鍮좎졇 ?덉뿀??????由щ뜑 + check_potions濡?蹂듦뎄.
        self._hp_mp_reader = hp_mp_reader

        # ?낅젰 怨꾩링
        self.input_backend = input_backend
        self.route_position_store = LatestPositionStore()

        # 媛먯? 怨꾩링 ???대깽?명걧
        self.event_queue: queue.Queue = queue.Queue()
        self._lie_template_missing = None
        marker_exclusions = (
            (
                (66, 62, 68, 64),
        (66, 37, 68, 39),
        (22, 51, 24, 53),
        (83, 62, 85, 64),
                (114, 63, 116, 65),
                (131, 62, 133, 64),
            )
            if config.hunt_ground_active.strip() == "\ube68\ucf542"
            else ()
        )
        self.char_scanner = CharScanner(
            screen_capture, lambda: self._resolve_region(config.minimap_region),
            log_fn=lambda m: self.log(m, "감지"),
            position_store=self.route_position_store,
            hsv_lower=(
                int(config.char_h_low) if config.char_h_low is not None else 20,
                int(config.char_s_min),
                int(config.char_v_min),
            ),
            hsv_upper=(
                int(config.char_h_high) if config.char_h_high is not None else 40,
                255,
                255,
            ),
            min_area=float(config.char_area_min),
            max_area=float(config.char_area_max),
            marker_exclusions=marker_exclusions,
            position_offset=(
                int(config.char_position_offset_x),
                int(config.char_position_offset_y),
            ),
        )
        self.antimob_scanner = None
        if config.antimob_templates:
            self.antimob_scanner = AntiMobScanner(
                screen_capture, config.antimob_templates,
                config.antimob_enabled,
                region=lambda: self._resolve_region(config.minimap_region),
            )
        # 嫄고깘 媛먯? ????댄? 異쒗쁽 ??"lie" ?대깽????Orchestrator媛 safety 紐⑤뱶 ?꾪솚
        self.lie_scanner = None
        if config.lie_enabled:
            import os as _os
            lie_title_template = _app_path(config.lie_title_template)
            self._cfg.lie_title_template = lie_title_template
            if _os.path.exists(lie_title_template):
                self.lie_scanner = LieScanner(
                    screen_capture, lie_title_template,
                    threshold=config.lie_threshold,
                    region=lambda: self._resolve_region(config.lie_detect_region),
                    debug_log_fn=self._log_lie_scan,
                    debug_dir=self._lie_debug_dir(),
                )
            else:
                self._lie_template_missing = lie_title_template
        # ?ㅻⅨ ?좎? 媛먯? (鍮④컯 ?쎌?)
        self.user_scanner = None
        if config.user_detect_enabled:
            self.user_scanner = UserScanner(
                screen_capture, min_red=config.user_min_red,
                region=lambda: self._resolve_region(config.minimap_region),
            )
        # ?붾젅洹몃옩 ?뚮┝ ???좏겙쨌梨뾋D ?덉쑝硫??쒖꽦(嫄고깘 ?뚮┝ ?듯빀 ?좉???諛쒕룞 ?쒖젏 寃곗젙)
        self.telegram = TelegramNotifier(
            token=config.tg_token, chat_id=config.tg_chat_id,
            enabled=bool(config.tg_token and config.tg_chat_id),
        )

        # 議곗쑉 怨꾩링
        self.orchestrator = Orchestrator(
            self.event_queue,
            on_pause=self._on_safety_pause,
            on_resume=lambda: None,
        )
        self._lie_safety_active = False

        # ?됰룞/?숈꽑 怨꾩링
        self._bot_running = False    # 而⑦듃濡ㅻ윭 start/stop濡??좉? (猷⑦듃 ?ㅽ뻾 ?쒖꽦 議곌굔)
        self._route_move_fault = False  # ?대룞 ?ㅽ뙣 ??媛숈? 諛⑺뼢 ?ъ떆??諛⑹?
        self._route_hunt_active = False   # ?꾩옱 猷⑦듃 釉붾줉???щ깷 援ш컙?대㈃ True(怨듦꺽 寃뚯씠??
        self._junk_selling = False
        self._junk_sell_lock = threading.Lock()
        self._junk_sell_stop = threading.Event()
        self._junk_sell_thread: threading.Thread | None = None
        self._auto_sell_on_start_done = False
        self.log = lambda m, cat="시스템": None  # UI 로그 콜백(run_integrated 주입). (msg, 카테고리)
        # 痢??뺤쓽:
        #   - route_mode硫?route???ㅼ링 援ъ“(?щ떎由?釉붾줉 Y)?먯꽌 異붿텧 ???⑥씪 zone蹂대떎 ?곗꽑.
        #     (?⑥씪 zone "1痢? ?섎굹留??곕㈃ 紐⑤뱺 Y瑜?1痢듭쑝濡??ㅽ뙋 ???ㅻⅨ 痢듭뿉??1痢?醫뚰몴濡??吏곸엫)
        #   - 洹??몄뿏 紐낆떆??zones, ?놁쑝硫?route?먯꽌 蹂댁“ 異붿텧.
        _floors = config.floors
        if config.route:
            from core.navigation.floor_extract import floors_from_route
            _rf = floors_from_route([b.to_dict() for b in config.route])
            if _rf and (config.route_mode or not _floors):
                _floors = _rf
        self.floor_judge = FloorJudge(_floors) if _floors else None
        # 痢??댄깉 蹂듦? 洹몃옒????route???щ떎由ъ뿉???먮룞 援ъ꽦
        _recovery_graph = None
        if self.floor_judge is not None and config.route:
            from core.navigation.map_graph import build_graph
            _recovery_graph = build_graph(
                _floors, [b.to_dict() for b in config.route], self.floor_judge)
        # 諛吏??щ깷 ?붾젆?????щ깷?곸뿭 紐?媛쒖닔濡?硫덉떠?щ깷(DWELL)?붿씠??MOVING) 寃곗젙
        from core.acting.hunt_director import HuntDirector
        self.hunt_director = HuntDirector(
            config.hunt_stay_threshold, config.hunt_leave_threshold,
            config.hunt_max_dwell_sec,
            jitter_fn=down_5)
        self._area_count = 0
        self._area_count_ts = -1e9
        self._movement_lock = threading.RLock()
        self._ladder_motion_active = False
        self._ladder_monster_waiting = False
        self._ladder_monster_cache = False
        self._ladder_monster_cache_at = -1e9
        self.block_runner = BlockRunner(
            input_backend=self.input_backend,
            # ?대룞 以묒뿉???대깽????吏???놁씠 ?ㅼ틦?덉쓽 理쒖떊 醫뚰몴瑜?吏곸젒 ?ъ슜?쒕떎.
            pos_fn=lambda: self.char_scanner.position()
                                or self.orchestrator.state.get_position()
                                or (0, 0),
            jump_key=config.jump_key or "alt",
            jump_while_move=config.jump_while_move,
            position_sample_fn=self.char_scanner.sample,
            monster_present_fn=self._ladder_monster_present,
            ladder_motion_fn=self._set_ladder_motion,
            minimap_size_fn=lambda: self._resolve_region(config.minimap_region)[2:4],
            ladder_profile={
                "launch_distance": config.ladder_launch_distance,
                "launch_distance_right": config.ladder_launch_distance_right,
                "launch_distance_left": config.ladder_launch_distance_left,
                "jump_hold_sec": config.ladder_jump_hold_sec,
                "up_delay_sec": config.ladder_up_delay_sec,
                "direction_hold_sec": config.ladder_direction_hold_sec,
                "stable_tolerance": config.ladder_stable_tolerance,
                "stable_samples": config.ladder_stable_samples,
                "position_max_age_sec": config.ladder_position_max_age_sec,
                "grab_confirm_sec": config.ladder_grab_confirm_sec,
            },
            stop_fn=lambda: (
                not self._route_can_run()
                or (self._anti_mob_busy and not self._anti_mob_moving)
            ),   # 諛⑹?紐??쒖옉 ???쇰컲 ?숈꽑 ?대룞??利됱떆 ?댄깉
            dwell_fn=lambda: self.hunt_director.is_dwelling(),  # 諛吏????대룞 park
            floor_judge=self.floor_judge, recovery_graph=_recovery_graph,
            on_segment_enter=self._on_route_segment_enter,
            on_segment_exit=self._on_route_segment_exit,
            log_fn=lambda m: self.log(m, "이동"),
        )
        self._world_scanner = None
        self._world_runner = None
        self._world_thread = None
        self._world_lock = threading.Lock()
        self._world_navigation_active = False
        if config.world_map is not None:
            import cv2

            world_image = cv2.imread(config.world_map.image_path, cv2.IMREAD_GRAYSCALE)
            if world_image is not None and config.world_map.calibration is not None:
                tracker = ViewportTracker(
                    world_image,
                    config.world_map.calibration,
                )
                self._world_scanner = WorldPositionScanner(
                    capture_fn=self._capture,
                    region_fn=lambda: self._resolve_region(config.minimap_region),
                    local_position_fn=lambda: self.orchestrator.state.get_position(),
                    tracker=tracker,
                )
                world_blocks = BlockRunner(
                    input_backend=self.input_backend,
                    pos_fn=lambda: self.world_position() or (0, 0),
                    jump_key=config.jump_key or "alt",
                    jump_while_move=config.jump_while_move,
                    stop_fn=lambda: not self._world_can_run(),
                    log_fn=lambda m: self.log(m, "전역이동"),
                )
                self._world_runner = WorldRouteRunner(
                    config.world_map,
                    world_blocks,
                    ActionExecutor(self.input_backend, click_fn=getattr(input_backend, "click", None)),
                )
        self._image_trigger = (
            ImageTrigger(ActionExecutor(self.input_backend, click_fn=getattr(input_backend, "click", None)))
            if config.image_trigger_spec is not None
            else None
        )
        self.reload_character_filter(config)
        self.combat = Combat(
            self.input_backend,
            hp_rule=config.hp_rule,
            mp_rule=config.mp_rule,
            log_fn=lambda m, c: self.log(m, c),
        )
        self.attack_sequence_runner = AttackSequenceRunner(
            config.attack_sequences,
            lambda key, hold: self.combat.attack(
                key, mode="duration", hold=hold or self._attack_hold()
            ),
        )
        self.buffs = BuffManager(self.input_backend, config.buffs,
                                 log_fn=lambda m: self.log(m, "버프"))
        self.pet = PetFeeder(self.input_backend, key=config.pet_key, interval=config.pet_interval,
                             log_fn=lambda m: self.log(m, "펫먹이"), label="펫먹이",
                             count=config.pet_count)
        # ?쎌뾽 ??대㉧ ??PetFeeder ?⑦꽩 ?ъ궗??二쇨린 以띻린 ??
        self.pickup = None
        self._pickup_held_key: str | None = None
        self._pickup_always_last = -1e9
        self._pickup_always_interval = 2.0
        # 紐ъ뒪??媛먯?(image 紐⑤뱶) ???됰꽕??紐ъ뒪???쒗뵆由?濡쒕뱶 (B 硫붿빱?덉쬁)
        self._name_tpl = None
        self._monster_tpls = {}
        if config.hunt_mode == "image" or (
                config.route_mode and any(b.type == "ladder" for b in config.route)):
            if config.name_template:
                self._name_tpl = monster_vision.load_template(config.name_template)
            for i, p in enumerate(config.monster_templates):
                t = monster_vision.load_template(p)
                if t is not None:
                    self._monster_tpls[f"m{i}"] = t
                    import cv2
                    self._monster_tpls[f"m{i}_flip"] = cv2.flip(t, 1)
        # ?됰꽕???쒗뵆由?異붿쟻湲????щ깷?곸뿭?먯꽌 ?됰꽕???꾩튂(=罹먮┃ 湲곗???瑜?李얠븘 ?곕씪媛?
        from core.sensing.name_tracker import NameTracker
        self.name_tracker = NameTracker(self._name_tpl, config.name_threshold)
        # ?≫뀥 ?먮룞?먮ℓ (A sell_junk ?섑븨 + B 蹂댄샇紐⑸줉). ?ㅽ뙋留ㅻ뒗 寃뚯엫 ?꾩슂 ???몄뒪?댁뒪留?以鍮?
        self.junk_seller = None
        self.auto_seller = None
        if config.junk_config is not None:
            from core.acting.junk_seller import JunkSeller
            self.junk_seller = JunkSeller(
                config.junk_config, screen_capture, input_backend,
            )
            self.auto_seller = AutoSeller(self.junk_seller)
        # ?쒖같 ??援ъ뿭 醫뚯슦 ?뺣났 (寃쎄퀎 ?꾨떖??諛⑺뼢?꾪솚, ?쒕뜡留덉쭊)
        self.patrol = None
        if config.patrol_right_x > config.patrol_left_x:
            self.patrol = Patrol(
                PatrolZone(config.patrol_left_x, config.patrol_right_x),
                margin=config.patrol_margin,
            )

        # 痢듬퀎 諛섎났 ?щ깷 猷⑦듃 ?ㅽ뻾湲???route_mode + route ?덉쑝硫?蹂꾨룄 ?ㅻ젅?쒕줈 諛섎났 ?ㅽ뻾
        self.floor_hunt_runner = None
        is_rednose2_route = (
            bool(config.rednose2_v5.get("enabled", True))
            and config.hunt_ground_active.strip() == "\ube68\ucf542"
        )
        is_rednose3_route = (
            bool(config.rednose3.get("enabled", True))
            and config.hunt_ground_active.strip() == "\ube68\ucf543"
        )
        if is_rednose3_route:
            self.floor_hunt_runner = RedNose3RouteRunner(
                self.block_runner,
                is_active=self._floor_route_can_run,
                profile=config.rednose3,
                log_fn=lambda m: self.log(m, "이동"),
                minimap_region_fn=lambda: self._resolve_region(config.minimap_region),
            )
        elif is_rednose2_route:
            self.floor_hunt_runner = RedNose2RouteRunner(
                self.block_runner,
                get_blocks=lambda: self._cfg.route,
                is_active=self._floor_route_can_run,
                profile=config.rednose2_v5,
                log_fn=lambda m: self.log(m, "이동"),
                minimap_region_fn=lambda: self._resolve_region(config.minimap_region),
            )
        elif config.route_steps:
            self.route_input_owner = self.block_runner._route_inputs
            self.floor_hunt_runner = RouteStateRunner(
                get_steps=lambda: self._cfg.route_steps,
                is_active=self._route_can_run,
                position_store=self.route_position_store,
                input_owner=self.route_input_owner,
                block_runner=self.block_runner,
                log_fn=lambda m: self.log(m, "이동"),
            )
        elif config.route:
            self.floor_hunt_runner = FloorHuntRunner(
                self.block_runner,
                get_blocks=lambda: self._cfg.route,
                is_active=self._route_can_run,
            )

        # 嫄고깘 怨꾩링 (寃⑸━) ???먯껜 ncnn ?붿쭊 (secure_loader/?쒕쾭 ?섏〈 ?놁쓬)
        self.registry = SolverRegistry()
        self.registry.register(SelfTransparentEngine(
            models_dir=config.transparent_models_dir,
            board_capture_fn=self._capture_board,
            move_cursor_fn=self._move_cursor,
            use_gpu=config.transparent_use_gpu,
        ))

        self._frame_id = 0
        self._reply_idx = 0

        # ?ㅻⅨ ?좎? 媛먯? ???먮룞?묐떟(梨꾪똿) + ?붾젅洹몃옩 ?뚮┝
        self.orchestrator.on("user_detected", self._handle_user_detected)
        # 嫄고깘 媛먯? ???뚮┝(?뚮━+?붾젅洹몃옩) ?듯빀. ?먮룞??대뒗 safety_tick???대떦
        self.orchestrator.on("lie", self._handle_lie)

    def _release_runtime_inputs(self) -> None:
        """런타임이 소유한 지속 입력을 즉시 해제한다."""
        if hasattr(self, "block_runner"):
            self.block_runner.release_inputs()
        self.release_pickup_key()
        keys = {
            "left", "right", "up", "down",
            str(self._cfg.jump_key or "alt"),
            str(getattr(self._cfg, "attack_key", "") or ""),
        }
        for profile_name in ("rednose2_v5", "rednose3"):
            profile = getattr(self._cfg, profile_name, {}) or {}
            keys.add(str(profile.get("teleport_key") or ""))
            keys.add(str(profile.get("attack_key") or ""))
        for key in keys:
            if key:
                self.input_backend.key_up(key)
    def reload_character_filter(self, config) -> None:
        self.char_scanner.reload_marker_templates()
        self._cfg.char_rgb = getattr(config, "char_rgb", None)
        self._cfg.char_h_low = getattr(config, "char_h_low", None)
        self._cfg.char_h_high = getattr(config, "char_h_high", None)
        self._cfg.char_h_tol = int(getattr(config, "char_h_tol", 10))
        self._cfg.char_s_min = int(getattr(config, "char_s_min", 100))
        self._cfg.char_v_min = int(getattr(config, "char_v_min", 200))
        self._cfg.char_area_min = float(getattr(config, "char_area_min", 3.0))
        self._cfg.char_area_max = float(getattr(config, "char_area_max", 100.0))
        self._cfg.char_position_offset_x = int(getattr(config, "char_position_offset_x", 0))
        self._cfg.char_position_offset_y = int(getattr(config, "char_position_offset_y", 0))
        set_position_offset = getattr(self.char_scanner, "set_position_offset", None)
        if callable(set_position_offset):
            set_position_offset(
                self._cfg.char_position_offset_x,
                self._cfg.char_position_offset_y,
            )

        h_low = getattr(config, "char_h_low", None)
        h_high = getattr(config, "char_h_high", None)
        s_min = int(getattr(config, "char_s_min", 100))
        v_min = int(getattr(config, "char_v_min", 200))
        min_area = float(getattr(config, "char_area_min", 3.0))
        max_area = float(getattr(config, "char_area_max", 100.0))

        if h_low is not None and h_high is not None:
            lo = (max(0, min(179, int(h_low))), s_min, v_min)
            hi = (max(0, min(179, int(h_high))), 255, 255)
            if lo[0] > hi[0]:
                lo = (hi[0], lo[1], lo[2])
            self.char_scanner.set_filters(lo, hi, min_area=min_area, max_area=max_area)
            return

        if getattr(config, "char_rgb", None):
            from core.sensing.char_scanner import auto_hsv_range_from_rgb
            lo, hi = auto_hsv_range_from_rgb(
                *config.char_rgb,
                h_tol=int(getattr(config, "char_h_tol", 10)),
            )
            self.char_scanner.set_filters(lo, hi, min_area=min_area, max_area=max_area)

    # ?? 媛먯? ?뚰봽 (?뚯뒪?? ?섎룞 / ?ㅺ린: ?ㅻ젅?? ??????????????????????
    def pump_scanners_once(self) -> None:
        """?ㅼ틦??scan_once 瑜?吏곸젒 1???몄텧???대깽?명걧瑜?梨꾩슫???뚯뒪?몄슜)."""
        for sc in (self.char_scanner, self.antimob_scanner, self.lie_scanner, self.user_scanner):
            if sc is None:
                continue
            ev = sc.scan_once()
            if ev is not None:
                self.event_queue.put(ev)

    def start_scanners(self) -> None:
        """?ㅺ린: ?ㅼ틦???ㅻ젅???쒖옉."""
        for sc in (self.char_scanner, self.antimob_scanner, self.lie_scanner, self.user_scanner):
            if sc is not None:
                sc.start(self.event_queue)
        self.log_lie_scanner_status()
        if self._world_scanner is not None:
            self._world_scanner.start()

    def stop_scanners(self) -> None:
        for sc in (self.char_scanner, self.antimob_scanner, self.lie_scanner, self.user_scanner):
            if sc is not None:
                sc.stop()
        if self._world_scanner is not None:
            self._world_scanner.stop()

    def world_position(self):
        return self._world_scanner.position() if self._world_scanner else None

    def world_tracking_state(self):
        return self._world_scanner.state() if self._world_scanner else "unavailable"

    def world_viewport(self):
        return self._world_scanner.viewport() if self._world_scanner else None

    def _start_world_job(self, fn) -> bool:
        import threading

        if self._world_runner is None:
            return False
        with self._world_lock:
            if self._world_thread and self._world_thread.is_alive():
                return False
            self._world_navigation_active = True

            def guarded():
                try:
                    fn()
                finally:
                    with self._world_lock:
                        self._world_navigation_active = False

            self._world_thread = threading.Thread(
                target=guarded,
                daemon=True,
                name="WorldNavigation",
            )
            self._world_thread.start()
        return True

    def start_world_route(self, route_id: str) -> bool:
        if self._world_runner is None or self._cfg.world_map is None:
            return False
        route = self._cfg.world_map.routes.get(route_id)
        if route is None:
            return False

        def run():
            while self._world_can_run():
                if not self._world_runner.run_node_path(route.node_ids):
                    return
                if not route.loop:
                    return

        return self._start_world_job(run)

    def navigate_world_to(self, node_id: str) -> bool:
        if self._world_runner is None or self._cfg.world_map is None:
            return False
        if node_id not in self._cfg.world_map.nodes:
            return False
        position = self.world_position()
        if position is None:
            return False
        px, py = position
        start = min(
            self._cfg.world_map.nodes.values(),
            key=lambda node: (node.x - px) ** 2 + (node.y - py) ** 2,
        )
        return self._start_world_job(
            lambda: self._world_runner.navigate_to(start.id, node_id)
        )

    # ?? 猷⑦듃 ?ㅽ뻾 ?쒖꽦 議곌굔 ???????????????????????????????????????????
    def set_running(self, flag: bool) -> None:
        """而⑦듃濡ㅻ윭 start/stop媛 ?몄텧 ??猷⑦듃 ?ㅽ뻾湲??쒖꽦/?뺤? ?좉?."""
        self._bot_running = flag
        if flag:
            self._refresh_auto_sell_config()
            # ???ㅽ뻾?먯꽌???댁쟾 ?대룞 ?ㅽ뙣 ?곹깭瑜?珥덇린?뷀븳??
            self._route_move_fault = False
            self._anti_mob_failed = False
            if self._cfg.auto_sell_on_start and not self._auto_sell_on_start_done:
                self._auto_sell_on_start_done = True
                self.start_junk_sell(reason="start")
        else:
            self._auto_sell_on_start_done = False

    def _route_can_run(self) -> bool:
        """일반 동선은 사냥 모드일 때만 실행한다."""
        return (self._bot_running and self.orchestrator.mode == "hunting"
                and not self._world_navigation_active
                and not self._junk_selling)

    def _floor_route_can_run(self) -> bool:
        """빨코 전용 동선은 시작 상태면 즉시 실행한다."""
        return (self._bot_running and self.orchestrator.mode == "hunting"
                and not self._world_navigation_active
                and not self._junk_selling)

    def monitor_tick(self) -> None:
        """硫붿씤 ?ㅻ젅?쒖뿉??泥섎━?섎뒗 ?붾㈃ 湲곕컲 媛먯떆 ?묒뾽."""
        if self._junk_selling:
            return
        if self._ladder_motion_active:
            return
        if self.orchestrator.mode == "hunting":
            self._check_anti_mob_profile()
            self._check_image_trigger()

    def movement_tick(self) -> None:
        """?대룞 ?ㅻ젅???꾩슜 ?? 怨듦꺽쨌踰꾪봽? ?낅┰?곸쑝濡?route瑜??ㅽ뻾?쒕떎."""
        if self._junk_selling:
            self.block_runner._route_inputs.release_direction()
            return
        if self.orchestrator.mode != "hunting":
            return
        if self._anti_mob_busy or self._anti_mob_failed:
            self.block_runner._route_inputs.release_direction()
            return
        if self.floor_hunt_runner is not None:
            return  # 痢듬퀎 route???꾩슜 FloorHuntRunner媛 ?대떦?쒕떎.
        if not self._cfg.route:
            return
        with self._movement_lock:
            moved = self.block_runner.run_block(self._cfg.route[0], max_steps=200)
        if not moved:
            self.block_runner._route_inputs.release_direction()
            self.log(
                "이동 실패: 방향키를 해제하고 다음 틱에 같은 이동 블록을 다시 시도합니다.",
                "이동",
            )

    def attack_tick(self, now: float | None = None) -> None:
        """怨듦꺽 ?ㅻ젅???꾩슜 ?? ?대룞 以묒뿉??怨듦꺽??怨꾩냽 ?ㅽ뻾?쒕떎."""
        if self._junk_selling:
            return
        if self.orchestrator.mode != "hunting":
            return
        if self._anti_mob_busy or self._anti_mob_failed:
            return
        now = now if now is not None else time.time()
        if self._ladder_motion_active:
            return
        if getattr(self.floor_hunt_runner, "controls_attack", False):
            return
        if self.floor_hunt_runner is not None:
            allowed = self._floor_runner_attack_allowed(False, False)
        elif self._cfg.hunt_mode == "image":
            allowed = self._monster_in_range()
        else:
            allowed = True
        self._run_attacks(now, allowed)

    def support_tick(self, now: float | None = None) -> None:
        """?ъ뀡 ?ㅻ젅???꾩슜 ?? ?ъ뀡쨌踰꾪봽쨌?レ쓣 泥섎━?쒕떎."""
        if self._junk_selling:
            return
        if self.orchestrator.mode != "hunting":
            return
        if self._anti_mob_busy:
            return
        now = now if now is not None else time.time()
        self._auto_sell_tick(now)
        if self._junk_selling:
            return
        self._check_potions(now)
        self.buffs.tick(now)
        if not self._ladder_motion_active:
            self.pet.tick(now)

    def pickup_tick(self, now: float | None = None) -> None:
        """?쎌뾽 ?꾩슜 ?ㅻ젅?? 二쇨린 ?쎌뾽 ?먮뒗 2珥?二쇨린 ??떆 ?쎌뾽??泥섎━?쒕떎."""
        now = now if now is not None else time.time()
        if self._junk_selling:
            self.release_pickup_key()
            self._pickup_always_last = -1e9
            return
        if self._ladder_motion_active:
            self.release_pickup_key()
            self._pickup_always_last = -1e9
            return
        if self._anti_mob_busy:
            return
        key = (self._cfg.pickup_key or "").strip()
        active = self._bot_running and self.orchestrator.mode == "hunting" and bool(key)
        if not active:
            self.release_pickup_key()
            self._pickup_always_last = -1e9
            return
        if self._cfg.pickup_always:
            if self._pickup_held_key is None:
                self.input_backend.key_down(key)
                self._pickup_held_key = key
                self._pickup_always_last = now
                self._pickup_always_interval = 2.0
            elif now - self._pickup_always_last >= self._pickup_always_interval:
                self.input_backend.key_up(key)
                self.input_backend.key_down(key)
                self._pickup_always_last = now
                self._pickup_always_interval = 2.0
        else:
            self.release_pickup_key()
            self._pickup_always_last = -1e9

    def release_pickup_key(self) -> None:
        """??떆 ?쎌뾽??吏곸젒 ?꾨Ⅸ ?ㅻ? 利됱떆 ?댁젣?쒕떎."""
        key = self._pickup_held_key
        if key is None:
            return
        try:
            self.input_backend.key_up(key)
        finally:
            self._pickup_held_key = None

    def _world_can_run(self) -> bool:
        return (self._bot_running and self.orchestrator.mode == "hunting"
                and self._world_navigation_active
                and not self._junk_selling)


    def is_junk_selling(self) -> bool:
        """?먮룞?먮ℓ ?ㅽ뻾 以묒씤吏 諛섑솚?쒕떎."""
        return self._junk_selling

    def auto_sell_status_text(self) -> str:
        """?먮룞?먮ℓ ?곹깭瑜?UI ?쒖떆??臾몄옣?쇰줈 諛섑솚?쒕떎."""
        if self.auto_seller is None:
            return "자동판매 연결 없음"
        return self.auto_seller.text()

    def _auto_sell_tick(self, now: float | None = None) -> None:
        """二쇨린 ?먮룞?먮ℓ媛 耳쒖졇 ?덉쑝硫??먮ℓ ?쒖젏??媛蹂띻쾶 ?뺤씤?쒕떎."""
        if not self._bot_running or self.auto_seller is None:
            return
        self._refresh_auto_sell_config()
        now = time.time() if now is None else now
        if self.auto_seller.should_run(
            self._cfg.auto_sell_enabled,
            self._cfg.auto_sell_interval_min,
            now,
        ):
            self.start_junk_sell(reason="scheduled")

    def _refresh_auto_sell_config(self) -> None:
        """UI가 저장한 최신 자동판매 설정을 실행 중 런타임에 반영한다."""
        source = getattr(self._cfg, "junk_config", None)
        if source is None:
            return
        settings = source.get("settings2", "junk_sell", default={}) or {}
        self._cfg.auto_sell_enabled = bool(settings.get("auto_sell_enabled", False))
        self._cfg.auto_sell_interval_min = float(settings.get("auto_sell_interval_min", 10))
        self._cfg.auto_sell_on_start = bool(settings.get("sell_on_start", False))

    def start_junk_sell(self, reason: str = "manual") -> bool:
        """?먮룞?먮ℓ瑜?蹂꾨룄 ?ㅻ젅?쒕줈 1???ㅽ뻾?쒕떎."""
        self._refresh_auto_sell_config()
        if self.junk_seller is None or self.auto_seller is None:
            self.log("자동판매 설정 또는 템플릿 연결이 없습니다.", "자동판매")
            return False
        with self._junk_sell_lock:
            if self._junk_sell_thread and self._junk_sell_thread.is_alive():
                self.log("자동판매가 이미 실행 중입니다.", "자동판매")
                return False
            self._junk_sell_stop.clear()
            if reason == "scheduled":
                self.log("주기 자동판매 실행 시점입니다.", "자동판매")
            self._junk_sell_thread = threading.Thread(
                target=self._run_junk_sell_once,
                daemon=True,
                name="JunkSellWorker",
            )
            self._junk_sell_thread.start()
        return True

    def stop_junk_sell(self) -> None:
        """吏꾪뻾 以묒씤 ?먮룞?먮ℓ??以묐떒 ?좏샇瑜?蹂대궦??"""
        if self.auto_seller is not None:
            self.auto_seller.request_stop()
        self._junk_sell_stop.set()

    def _run_junk_sell_once(self) -> None:
        """자동판매 실행 중 다른 행동 입력을 멈추고 판매를 수행한다."""
        rednose_prepared = False
        sale_succeeded = False
        self._junk_selling = True
        try:
            self.release_pickup_key()
            self._release_runtime_inputs()
            runner = self.floor_hunt_runner
            if isinstance(runner, RedNose2RouteRunner):
                self.log("빨코2 자동판매 진입: 2층 X=123~136 정렬 후 윗텔포합니다.", "자동판매")
                rednose_prepared = runner.prepare_auto_sell_from_floor2()
                if not rednose_prepared:
                    self.log("빨코2 자동판매 진입 실패: 판매를 시작하지 않습니다.", "자동판매")
                    return
            self.log("자동판매 시작: 이동·공격·픽업 입력을 일시정지합니다.", "자동판매")
            self.release_pickup_key()
            self._release_runtime_inputs()
            sale_started_at = time.perf_counter()
            try:
                sale_succeeded = self.auto_seller.run_once(
                    lambda msg: self.log(msg, "자동판매"),
                    self._junk_sell_stop,
                )
            finally:
                elapsed = time.perf_counter() - sale_started_at
                self.log(f"판매 위치 도착 후 자동판매 소요={elapsed:.3f}초", "자동판매")
        except Exception as exc:
            self.log(f"자동판매 오류: {exc}", "자동판매")
        finally:
            try:
                self.release_pickup_key()
                self._release_runtime_inputs()
                if rednose_prepared and isinstance(self.floor_hunt_runner, RedNose2RouteRunner):
                    self.floor_hunt_runner.return_floor2_after_auto_sell()
            finally:
                self._junk_selling = False
                self._junk_sell_stop.clear()
                if self.auto_seller is not None:
                    if sale_succeeded:
                        self.auto_seller.schedule_after_minutes(self._cfg.auto_sell_interval_min)
                    else:
                        self.auto_seller.schedule_after_seconds(5.0)
                        self.log("자동판매 미완료: 5초 후 다시 시도합니다.", "자동판매")
                self.log("자동판매 종료: 사냥 입력을 다시 허용합니다.", "자동판매")

    def reload_lie_scanner(self, config) -> None:
        """嫄고깘 媛먯? ?ㅼ젙??理쒖떊 config濡??ㅼ떆 ?곸슜?쒕떎."""
        was_running = self.lie_scanner is not None and self.lie_scanner.is_running()
        if self.lie_scanner is not None:
            self.lie_scanner.stop()
        self._cfg.lie_enabled = config.lie_enabled
        self._cfg.lie_alert = config.lie_alert
        self._cfg.lie_title_template = config.lie_title_template
        self._cfg.lie_threshold = config.lie_threshold
        self._cfg.lie_detect_region = config.lie_detect_region
        self._cfg.tg_token = config.tg_token
        self._cfg.tg_chat_id = config.tg_chat_id
        self.telegram._enabled = bool(config.tg_token and config.tg_chat_id)
        self.telegram._token = config.tg_token
        self.telegram._chat_id = config.tg_chat_id
        self.lie_scanner = None
        if config.lie_enabled:
            import os as _os
            lie_title_template = _app_path(config.lie_title_template)
            self._cfg.lie_title_template = lie_title_template
            if _os.path.exists(lie_title_template):
                self.lie_scanner = LieScanner(
                    self._capture,
                    lie_title_template,
                    threshold=config.lie_threshold,
                    region=lambda: self._resolve_region(config.lie_detect_region),
                    debug_log_fn=self._log_lie_scan,
                    debug_dir=self._lie_debug_dir(),
                )
            else:
                self.log(f"거탐 템플릿 없음: {lie_title_template}", "감지")
        if was_running and self.lie_scanner is not None:
            self.lie_scanner.start(self.event_queue)
        self.log_lie_scanner_status()

    def log_lie_scanner_status(self) -> None:
        """현재 거탐 감지 상태를 로그에 표시한다."""
        if not self._cfg.lie_enabled:
            self.log("거탐 감지: 꺼짐", "감지")
            return
        if self.lie_scanner is None:
            if getattr(self, "_lie_template_missing", None):
                self.log(f"거탐 템플릿 없음: {self._lie_template_missing}", "감지")
            self.log(
                f"거탐 감지: 스캐너 없음, template={self._cfg.lie_title_template}",
                "감지",
            )
            return
        running = "실행중" if self.lie_scanner.is_running() else "대기중"
        resolved_region = self._resolve_region(self._cfg.lie_detect_region)
        self.log(
            f"거탐 감지: {running}, threshold={self._cfg.lie_threshold:.3f}, "
            f"region={resolved_region or '전체화면'}, "
            f"template={self._cfg.lie_title_template}, alert={self._cfg.lie_alert}",
            "감지",
        )

    def reload_floor_hunt_runner(self, config) -> None:
        """현재 사냥터 이름에 맞는 전용 동선 러너를 다시 구성한다."""
        if self.floor_hunt_runner is not None:
            self.floor_hunt_runner.stop()
        self.floor_hunt_runner = None
        self._cfg.minimap_region = config.minimap_region
        self._cfg.route = config.route
        self._cfg.route_steps = config.route_steps
        self._cfg.route_mode = config.route_mode
        self._cfg.hunt_ground_active = config.hunt_ground_active
        self._cfg.rednose2_v5 = config.rednose2_v5
        self._cfg.rednose3 = config.rednose3

        is_rednose3_route = (
            bool(config.rednose3.get("enabled", True))
            and config.hunt_ground_active.strip() == "\ube68\ucf543"
        )
        is_rednose2_route = (
            bool(config.rednose2_v5.get("enabled", True))
            and config.hunt_ground_active.strip() == "\ube68\ucf542"
        )
        if is_rednose3_route:
            self.floor_hunt_runner = RedNose3RouteRunner(
                self.block_runner,
                is_active=self._floor_route_can_run,
                profile=config.rednose3,
                log_fn=lambda m: self.log(m, "이동"),
                minimap_region_fn=lambda: self._resolve_region(config.minimap_region),
            )
        elif is_rednose2_route:
            self.floor_hunt_runner = RedNose2RouteRunner(
                self.block_runner,
                get_blocks=lambda: self._cfg.route,
                is_active=self._floor_route_can_run,
                profile=config.rednose2_v5,
                log_fn=lambda m: self.log(m, "이동"),
                minimap_region_fn=lambda: self._resolve_region(config.minimap_region),
            )
        elif config.route_steps:
            self.route_input_owner = self.block_runner._route_inputs
            self.floor_hunt_runner = RouteStateRunner(
                get_steps=lambda: self._cfg.route_steps,
                is_active=self._route_can_run,
                position_store=self.route_position_store,
                input_owner=self.route_input_owner,
                block_runner=self.block_runner,
                log_fn=lambda m: self.log(m, "이동"),
            )
        elif config.route:
            self.floor_hunt_runner = FloorHuntRunner(
                self.block_runner,
                get_blocks=lambda: self._cfg.route,
                is_active=self._route_can_run,
            )

    def _check_anti_mob_profile(self) -> None:
        """珥덇툒 ?섎젴??諛⑹?紐??대?吏瑜?李얠븘 怨좎젙 ?댁젣 ?쒖꽌瑜??ㅽ뻾?쒕떎."""
        import cv2
        import os
        import random
        import sys
        from pathlib import Path

        profile = getattr(self._cfg, "anti_mob_profile", {}) or {}
        def diag(message: str, interval_sec: float = 2.0) -> None:
            now_diag = time.monotonic()
            if now_diag - self._anti_mob_last_diag >= interval_sec:
                self._anti_mob_last_diag = now_diag
                self.log(message, "안티밴")

        if (
            not profile.get("enabled")
            or profile.get("profile") != "beginner_training"
            or self._anti_mob_busy
            or self._anti_mob_failed
        ):
            return
        now = time.monotonic()
        cooldown_sec = max(60.0, float(profile.get("cooldown_sec", 60.0)))
        if now - self._anti_mob_last < cooldown_sec:
            return

        app_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
        template_dir = app_root / "templates" / "anti_mob" / "beginner_training"

        def fixed_templates(kind: str) -> list[str]:
            return [str(path) for path in sorted(template_dir.glob(f"{kind}_*.png")) if path.is_file()]

        paths1 = fixed_templates("image1")
        paths2 = fixed_templates("image2")
        paths3 = fixed_templates("image3")
        if not paths1 or not paths2 or not paths3:
            diag(
                f"방지몹 감시 대기: 템플릿 부족 "
                f"(image1={len(paths1)}, image2={len(paths2)}, image3={len(paths3)})"
            )
            return
        region = self._resolve_region(self._cfg.hunt_area_region)
        if not region:
            diag("방지몹 감시 대기: 사냥영역이 설정되지 않았습니다.")
            return
        scene = self._capture(region)
        if scene is None:
            diag("방지몹 감시 대기: 사냥영역 캡처 실패")
            return

        def best_match(paths):
            best = (0.0, None, (0, 0), (0, 0))
            for path in paths:
                template = monster_vision.load_template(path)
                if template is None:
                    continue
                for candidate in (template, cv2.flip(template, 1)):
                    th, tw = candidate.shape[:2]
                    if th > scene.shape[0] or tw > scene.shape[1]:
                        continue
                    result = cv2.matchTemplate(scene, candidate, cv2.TM_CCOEFF_NORMED)
                    _, score, _, loc = cv2.minMaxLoc(result)
                    if float(score) > best[0]:
                        best = (float(score), path, (int(loc[0]), int(loc[1])), (tw, th))
            return best

        threshold = float(profile.get("threshold", 1.0))
        first = best_match(paths1)
        if first[0] < threshold:
            name = os.path.basename(str(first[1])) if first[1] else "없음"
            diag(
                f"방지몹 감시중: image1 score={first[0]:.3f}, "
                f"threshold={threshold:.3f}, template={name}"
            )
            return

        self._anti_mob_busy = True
        self._release_runtime_inputs()
        try:
            self.log(
                f"사냥영역 방지몹 이미지1 감지: score={first[0]:.3f} / "
                f"template={os.path.basename(str(first[1]))}",
                "안티밴",
            )
            self.log("공격·이동 입력 정지, 왼쪽 이동하며 이미지2 검색 시작", "안티밴")

            second = None
            with self._movement_lock:
                self._anti_mob_moving = True
                try:
                    self.input_backend.key_down("left")
                    deadline = time.monotonic() + 1.0
                    while self._bot_running and time.monotonic() < deadline:
                        current_scene = self._capture(region)
                        if current_scene is not None:
                            scene = current_scene
                            candidate = best_match(paths2)
                            if candidate[0] >= threshold:
                                second = candidate
                                break
                        time.sleep(0.05)
                finally:
                    self.input_backend.key_up("left")
                    self._anti_mob_moving = False

            if not self._bot_running:
                self.log("봇 정지로 이미지2 검색을 중단하고 왼쪽 이동을 해제했습니다.", "안티밴")
                return

            if second is None:
                self._anti_mob_failed = True
                self._release_runtime_inputs()
                message = "방지몹 이미지2를 1초 동안 찾지 못해 왼쪽 이동을 해제하고 공격을 중지합니다."
                self.log(message, "안티밴")
                try:
                    self.telegram.send(message)
                except Exception:
                    pass
                return

            self.log(
                f"사냥영역 이미지2 감지: score={second[0]:.3f} / "
                f"template={os.path.basename(str(second[1]))}",
                "안티밴",
            )
            click = getattr(self.input_backend, "click", None)
            if click is None:
                raise RuntimeError("마우스 클릭 백엔드를 사용할 수 없습니다.")

            def double_click_twice(match, label):
                match_x, match_y = match[2]
                match_w, match_h = match[3]
                point_x = int(region["left"]) + random.randint(match_x, match_x + match_w - 1)
                point_y = int(region["top"]) + random.randint(match_y, match_y + match_h - 1)
                self.log(
                    f"{label} 매칭 영역 안에서 랜덤 더블클릭 2회: x={point_x}, y={point_y} "
                    f"(영역={match_w}x{match_h})",
                    "안티밴",
                )
                for double_index in range(2):
                    click(point_x, point_y)
                    time.sleep(0.08)
                    click(point_x, point_y)
                    if double_index == 0:
                        time.sleep(0.08)

            double_click_twice(second, "이미지2")
            time.sleep(0.5)

            def wait_for_match(paths, label):
                nonlocal scene
                deadline = time.monotonic() + float(profile.get("image2_wait_sec", 3.0))
                while time.monotonic() < deadline:
                    current_scene = self._capture(region)
                    if current_scene is not None:
                        scene = current_scene
                        candidate = best_match(paths)
                        if candidate[0] >= threshold:
                            return candidate
                    time.sleep(0.05)
                self.log(f"{label}을 찾지 못해 방지몹 해제를 취소하고 공격을 재개합니다.", "안티밴")
                return None

            third = wait_for_match(paths3, "이미지3")
            if third is None:
                return
            double_click_twice(third, "이미지3")
            self._anti_mob_last = time.monotonic()
            time.sleep(0.5)

            self.log("방지몹 해제 완료, 공격 스레드 재개", "안티밴")
        except Exception as exc:
            self.log(f"방지몹 해제 오류: {exc}", "안티밴")
        finally:
            self._anti_mob_busy = False

    def _check_image_trigger(self):
        spec = getattr(self._cfg, "image_trigger_spec", None)
        image_trigger = getattr(self, "_image_trigger", None)
        if image_trigger is None or spec is None:
            return None
        try:
            hunt_region = self._resolve_region(self._cfg.hunt_area_region)
            if not hunt_region:
                return None
            frame = self._capture(hunt_region)
            if frame is None or not getattr(frame, "size", 0):
                return None
            height, width = frame.shape[:2]
            return image_trigger.check(
                frame,
                (0, 0, width, height),
                spec,
            )
        except Exception as exc:
            self.log(f"이미지 트리거 오류: {exc}", "감지")
            return None

    # ?? ??????????????????????????????????????????????????????????????
    def hunting_tick(self, now: float | None = None) -> None:
        """?뺤긽 ?щ깷 1?? 援ъ뿭 醫뚯슦 ?뺣났 ?쒖같 + 怨듦꺽 + 踰꾪봽."""
        now = now if now is not None else time.time()
        if self.orchestrator.mode != "hunting":
            return

        self._check_image_trigger()

        # HP/MP 臾쇱빟 ??留??щ깷 ???뺤씤(?꾧퀎 誘몃쭔?대㈃ Combat?????낅젰). ?대뒓 遺꾧린??癒쇱? ?ㅽ뻾.
        self._check_potions(now)

        # 諛吏??먮떒 ??紐ъ뒪???쒗뵆由우씠 ?덉쓣 ?뚮쭔(image/route). ?щ깷?곸뿭 ?꾩껜 紐?媛쒖닔濡?
        # 硫덉떠?щ깷(dwelling)?붿씠??寃곗젙. ?ъ냼(?ㅼ씠?덉엫怨?硫???硫덉텛怨??대룞, 諛吏??μ쭊?낆엫怨??대㈃ 硫덉떠 泥섏튂.
        density_on = (getattr(self, "_name_tpl", None) is not None
                      and bool(getattr(self, "_monster_tpls", None))
                      and getattr(self, "hunt_director", None) is not None)
        dwelling = False
        if density_on:
            dwelling = self.hunt_director.update(self._count_monsters_in_area(now), now)

        # 猷⑦듃 ?ㅽ뻾湲?紐⑤뱶: ?대룞쨌怨듦꺽? 猷⑦듃 ?ㅻ젅?쒓? ?섑뻾 ???ш린??踰꾪봽/?ル쭔
        if self.floor_hunt_runner is not None:
            self.buffs.tick(now)
            self.pet.tick(now)
            self.pickup.tick(now)
            if getattr(self.floor_hunt_runner, "controls_attack", False):
                return
            allowed = self._floor_runner_attack_allowed(density_on, dwelling)
            self._run_attacks(now, allowed)
            return

        # 怨듦꺽?좎? ?먯젙: 諛吏??ъ슜 ??dwelling, ?꾨땲硫?image=怨듦꺽諛뺤뒪/key=??긽
        attacking = False
        if self._cfg.attack_key or self.attack_sequence_runner.active:
            if density_on:
                attacking = dwelling
            elif self._cfg.hunt_mode == "image":
                attacking = self._monster_in_range()
            else:
                attacking = True

        # ?ㅼ엯??紐⑤뱶??怨듦꺽?섎㈃???щ깷?곸뿭???쒖같?쒕떎.
        # ?대?吏 紐⑤뱶?먯꽌留?紐ъ뒪?곌? 怨듦꺽踰붿쐞???ㅼ뼱?ㅻ㈃ ?쒖옄由?怨듦꺽?쒕떎.
        if self._cfg.hunt_mode == "key":
            self._run_attacks(now, True)
            attacking = False

        # ?대룞 XOR ?쒖옄由ш났寃???醫뚯슦 ?대룞?ㅻ뒗 ?꾨Ⅸ 梨??좎??섍퀬, 怨듦꺽???????
        if attacking:
            self.block_runner._route_inputs.release_direction()   # ?쒖옄由?怨듦꺽: ?좎? 以묒씤 ?대룞???댁젣
            self._run_attacks(now, True)
        else:
            if self._cfg.hunt_mode != "key":
                self._run_attacks(now, False)
            # ?숈꽑 醫뚰몴媛 ?덉쑝硫?誘몃땲留듭뿉 吏?뺥븳 ?숈꽑???곗꽑 ?ъ슜?쒕떎.
            # ?щ깷?곸뿭 醫뚯슦 寃쎄퀎??紐ъ뒪???몄떇 ?곸뿭?대ŉ ?대룞 紐⑺몴濡??ъ슜?섏? ?딅뒗??
            if self._cfg.route:
                moved = self.block_runner.run_block(self._cfg.route[0], max_steps=200)
                if not moved:
                    self.block_runner._route_inputs.release_direction()
                    self.log(
                        "이동 실패: 방향키를 해제하고 다음 틱에 같은 이동 블록을 다시 시도합니다.",
                        "이동",
                    )
            # ?숈꽑 醫뚰몴媛 ?놁쓣 ?뚮쭔 湲곗〈 ?쒖같 寃쎄퀎瑜?蹂댁“ ?ъ슜?쒕떎.
            elif self.patrol is not None:
                pos = self.orchestrator.state.get_position()
                if pos is not None:
                    self.patrol.next_direction(pos[0])
                    target = self.patrol.target_x()
                    self.block_runner.run_block(
                        Block(type="move", target_x=target, move_type="walk"),
                        max_steps=1,
                    )

        self.buffs.tick(now)
        self.pet.tick(now)

    def _attack_hold(self) -> float:
        """공격 유지시간을 반환한다. 기능별 입력 시점에 한 번만 시간 보정을 적용한다."""
        return max(1, int(self._cfg.hits_to_kill)) * float(self._cfg.skill_cast_sec)

    def _run_attacks(self, now: float, allowed: bool) -> None:
        if self.attack_sequence_runner.active:
            self.attack_sequence_runner.tick(now, allowed)
        elif allowed and self._cfg.attack_key:
            self.combat.attack(
                self._cfg.attack_key,
                mode="duration",
                now=now,
                interval=self._cfg.attack_interval,
                hold=self._attack_hold(),
            )

    def _floor_runner_attack_allowed(self, density_on: bool, dwelling: bool) -> bool:
        """일반 동선 러너는 이동 중에도 기존 전투 설정으로 공격한다."""
        if isinstance(self.floor_hunt_runner, RouteStateRunner):
            if density_on:
                return bool(dwelling)
            if self._cfg.hunt_mode == "image":
                return self._monster_in_range()
            return True
        return bool(self._route_hunt_active or self._ladder_monster_waiting)

    def _check_potions(self, now: float) -> None:
        """HP/MP 鍮꾩쑉???쎌뼱 ?꾧퀎 誘몃쭔?대㈃ 臾쇱빟 ?ъ슜(Combat.check_potions).
        由щ뜑 誘몄＜???뚯뒪?????대㈃ ?꾨Т寃껊룄 ????"""
        reader = getattr(self, "_hp_mp_reader", None)
        if reader is None:
            return
        try:
            hp, mp = reader()
        except Exception:
            return
        self.combat.check_potions(hp, mp, now)

    def _on_route_segment_enter(self, block) -> None:
        """猷⑦듃 ?щ꼫媛 釉붾줉 吏꾩엯 ???몄텧 ???щ깷 援ш컙(move쨌pass?꾨떂)?대㈃ 怨듦꺽 ?덉슜."""
        self._route_hunt_active = (
            getattr(block, "type", None) == "move"
            and getattr(block, "mode", "count") != "pass")

    def _on_route_segment_exit(self, block) -> None:
        """釉붾줉 ?댄깉(finally) ???몄텧 ??怨듦꺽 ?뚮옒洹몃? ??긽 ?덈떎(釉붾줉 ?ъ씠 鍮꾧났寃?."""
        self._route_hunt_active = False

    def _set_ladder_motion(self, active: bool) -> None:
        self._ladder_motion_active = bool(active)
        if active:
            self._ladder_monster_waiting = False
            self.release_pickup_key()

    def _ladder_monster_present(self) -> bool:
        now = time.monotonic()
        if now - self._ladder_monster_cache_at >= 0.2:
            self._ladder_monster_cache_at = now
            self._ladder_monster_cache = self._monster_in_range()
        self._ladder_monster_waiting = bool(self._ladder_monster_cache)
        return self._ladder_monster_waiting

    def ladder_debug_state(self):
        return self.block_runner.ladder_debug_state()

    def update_minimap_region(self, minimap: dict) -> None:
        """UI에서 새로 지정한 미니맵 영역을 실행 중 스캐너들에 즉시 반영한다."""
        region = {
            "left": int(minimap.get("region_x", 0)),
            "top": int(minimap.get("region_y", 0)),
            "width": max(1, int(minimap.get("width", 1))),
            "height": max(1, int(minimap.get("height", 1))),
        }
        ratio_keys = ("region_x_ratio", "region_y_ratio", "width_ratio", "height_ratio")
        if all(minimap.get(key) is not None for key in ratio_keys):
            region.update({
                "x_ratio": float(minimap["region_x_ratio"]),
                "y_ratio": float(minimap["region_y_ratio"]),
                "w_ratio": float(minimap["width_ratio"]),
                "h_ratio": float(minimap["height_ratio"]),
                "base_region": [
                    region["left"], region["top"], region["width"], region["height"],
                ],
            })
        self._cfg.minimap_region = region

    def _resolve_region(self, region: dict | None) -> dict | None:
        """?곷? ?곸뿭 dict瑜??꾩옱 寃뚯엫李??먯젏?쇰줈 ?댁꽍(absolute硫?洹몃?濡? None?대㈃ None)."""
        if not region:
            return region
        if region.get("x_ratio") is not None:
            try:
                from core.game_window import (
                    find_game_hwnd,
                    find_window_hwnd_by_title,
                    get_game_client_rect_screen,
                )
                hwnd = None
                if self._cfg.game_window_title:
                    hwnd = find_window_hwnd_by_title(self._cfg.game_window_title)
                if hwnd is None:
                    hwnd = find_game_hwnd()
                if hwnd:
                    left, top, width, height = get_game_client_rect_screen(hwnd)
                    return {
                        "left": left + int(float(region["x_ratio"]) * width),
                        "top": top + int(float(region["y_ratio"]) * height),
                        "width": max(1, int(float(region["w_ratio"]) * width)),
                        "height": max(1, int(float(region["h_ratio"]) * height)),
                    }
            except Exception:
                return None
        from core.config_manager import resolve_window_region
        a = self._cfg.coord_anchor
        anchor = (int(a[0]), int(a[1])) if a else None
        x, y, w, h = resolve_window_region(
            self._cfg.coord_mode, self._cfg.game_window_title,
            int(region["left"]), int(region["top"]),
            int(region["width"]), int(region["height"]), anchor)
        return {"left": x, "top": y, "width": w, "height": h}

    def _monster_in_range(self) -> bool:
        """B 硫붿빱?덉쬁: ?щ깷?곸뿭 罹≪쿂 ???됰꽕???꾩튂 ??atk 諛뺤뒪 ??諛뺤뒪 ??紐ъ뒪??留ㅼ묶."""
        if self._name_tpl is None or not self._monster_tpls:
            return False
        region = self._resolve_region(self._cfg.hunt_area_region)
        scene = self._capture(region) if region else self._capture()
        if scene is None:
            return False
        name_pos = self.name_tracker.find(scene)
        if name_pos is None:
            return False
        box = monster_vision.attack_box(
            name_pos, self._cfg.atk_x_min, self._cfg.atk_x_max,
            self._cfg.atk_y_min, self._cfg.atk_y_max)
        return monster_vision.monsters_in_box(
            scene, self._monster_tpls, box, threshold=self._cfg.monster_accuracy) > 0

    def _count_monsters_in_area(self, now: float) -> int:
        """?щ깷?곸뿭 '?꾩껜'??紐?媛쒖닔(怨듦꺽諛뺤뒪媛 ?꾨떂). 諛吏??먮떒?? ??.3s throttle 罹먯떆."""
        if now - self._area_count_ts < 0.3:
            return self._area_count
        self._area_count_ts = now
        if self._name_tpl is None or not self._monster_tpls:
            self._area_count = 0
            return 0
        region = self._resolve_region(self._cfg.hunt_area_region)
        scene = self._capture(region) if region else self._capture()
        if scene is None:
            self._area_count = 0
            return 0
        h, w = scene.shape[:2]
        boxes = monster_vision.monster_boxes_in_box(
            scene, self._monster_tpls, (0, 0, w, h),
            threshold=self._cfg.monster_accuracy)
        self._area_count = len(boxes)
        return self._area_count

    def reload_monster_templates(self, config) -> None:
        """?꾩옱 ?щ깷???ㅼ젙??紐ъ뒪???쒗뵆由용쭔 ?ㅼ떆 ?곸옱?쒕떎."""
        self._name_tpl = None
        self._monster_tpls = {}
        if config.hunt_mode == "image" or (
                config.route_mode and any(b.type == "ladder" for b in config.route)):
            if config.name_template:
                self._name_tpl = monster_vision.load_template(config.name_template)
            import cv2
            for i, path in enumerate(config.monster_templates):
                template = monster_vision.load_template(path)
                if template is None:
                    continue
                self._monster_tpls[f"m{i}"] = template
                self._monster_tpls[f"m{i}_flip"] = cv2.flip(template, 1)
        from core.sensing.name_tracker import NameTracker
        self.name_tracker = NameTracker(self._name_tpl, config.name_threshold)
        self._cfg.hunt_mode = config.hunt_mode
        self._cfg.name_template = config.name_template
        self._cfg.monster_templates = list(config.monster_templates)
        self._cfg.name_threshold = config.name_threshold

    def detect_monsters_rel(self) -> list[tuple[int, int]]:
        """?щ깷?곸뿭 紐ъ뒪???먯? ??罹먮┃(?됰꽕?? 湲곗? ?붾㈃px ?ㅽ봽??[(dx,dy), ...].
        誘몃땲留?罹붾쾭?ㅼ쓽 紐ъ뒪?????쒖떆???뚰듃紐⑤뱶 臾닿?). ?쒗뵆由??됰꽕???놁쑝硫?[]."""
        if self._name_tpl is None or not self._monster_tpls:
            return []
        region = self._resolve_region(self._cfg.hunt_area_region)
        scene = self._capture(region) if region else self._capture()
        if scene is None:
            return []
        name_pos = self.name_tracker.find(scene)
        if name_pos is None:
            return []
        box = monster_vision.attack_box(
            name_pos, self._cfg.atk_x_min, self._cfg.atk_x_max,
            self._cfg.atk_y_min, self._cfg.atk_y_max)
        boxes = monster_vision.monster_boxes_in_box(
            scene, self._monster_tpls, box, threshold=self._cfg.monster_accuracy)
        nx, ny = name_pos
        return [(x + w // 2 - nx, y + h // 2 - ny) for (x, y, w, h) in boxes]

    def safety_tick(self, now: float | None = None) -> None:
        """?덉쟾 紐⑤뱶 1?? (?먮룞???耳쒖죱???뚮쭔) 嫄고깘 ????쒕룄 ???깃났 ???щ깷 ?ш컻."""
        if self.orchestrator.mode != "safety":
            return
        if not self._cfg.transparent_enabled:
            return   # ?щ챸?꾪삎 ?먮룞???爰쇱쭚 ???쇱떆?뺤? ?좎?(?ъ슜???섎룞 泥섎━)
        self._frame_id += 1
        # SelfTransparentEngine.solve 媛 寃뚯엫?먯쓣 異붿쟻???꾪삎 ?щ씪吏덈븣源뚯? ?쇰떎(釉붾줈??
        result = self.registry.solve(
            self._cfg.minigame_type, screenshot=None,
            ctx={"frame_id": self._frame_id},
        )
        if result is not None and result.success:
            self._clear_lie_safety()

    def _clear_lie_safety(self) -> None:
        """거탐 안전 상태를 해제하고 수동 재개 상태도 초기화한다."""
        self.orchestrator.clear_safety()
        self._lie_safety_active = False

    def resume_lie_safety_if_clear(self) -> bool:
        """F1 재요청 시 거탐 창이 사라졌을 때만 사냥을 재개한다."""
        if self.orchestrator.mode != "safety":
            return False
        if not self._lie_safety_active:
            self.log("F1 재개 보류: 현재 안전 상태는 거탐 감지로 시작되지 않았습니다.", "시스템")
            return False
        scanner = self.lie_scanner
        if scanner is None or scanner.is_present():
            self.log("F1 재개 보류: 거탐 창이 아직 화면에 남아 있습니다.", "감지")
            return False
        self._clear_lie_safety()
        self.log("F1 재개: 거탐 창이 사라져 사냥을 다시 시작합니다.", "감지")
        return True

    # ?? ?대? ??????????????????????????????????????????????????????????
    def _lie_debug_dir(self) -> str:
        """거탐 감지 실패 시 확인용 이미지를 저장할 폴더를 반환한다."""
        try:
            import sys
            from pathlib import Path
            if getattr(sys, "frozen", False):
                base = Path(sys.executable).resolve().parent
            else:
                base = Path(__file__).resolve().parent.parent
            return str(base / "03_output" / "lie_debug")
        except Exception:
            return "03_output/lie_debug"

    def _log_lie_scan(self, message: str) -> None:
        """거탐 감시 상태를 시스템과 감지 로그 양쪽에 표시한다."""
        self.log(message, "시스템")
        self.log(message, "감지")
    def _handle_lie(self, ev) -> None:
        """거탐 감지 시 알림을 처리한다."""
        self._lie_safety_active = True
        data = getattr(ev, "data", {}) or {}
        score = data.get("score")
        scale = data.get("scale", 1.0)
        self.log(
            f"거탐 템플릿 감지: score={float(score):.3f}, scale={float(scale):.3f}"
            if score is not None else "거탐 템플릿 감지",
            "감지",
        )
        if self._junk_selling:
            self.stop_junk_sell()
            self.log("거탐 감지로 자동판매 중단을 요청했습니다.", "자동판매")
            try:
                self.telegram.send("거탐 감지: 자동판매 중단")
            except Exception:
                pass
        if not self._cfg.lie_alert:
            return
        import threading as _th

        def _beep():
            try:
                import winsound
                for _ in range(3):
                    winsound.Beep(1000, 300)
            except Exception:
                pass
        _th.Thread(target=_beep, daemon=True).start()
        try:
            self.telegram.send("거탐 감지: 즉시 확인이 필요합니다.")
        except Exception:
            pass

    def _capture_board(self):
        """嫄고깘 寃뚯엫???곸뿭 罹≪쿂. board_region ?곗꽑, ?놁쑝硫?board_roi 鍮꾩쑉(A 怨좎젙媛?濡??섏궛, ?????놁쑝硫??꾩껜."""
        region = self._cfg.board_region
        if region is None and self._cfg.board_roi:
            region = self._board_roi_to_region(self._cfg.board_roi)
        return self._capture(region) if region else self._capture()

    def _board_roi_to_region(self, roi: dict):
        """A 怨좎젙 ?곷?醫뚰몴(x/y/w/h_ratio)瑜?二쇰え?덊꽣 湲곗? ?쎌? ?곸뿭?쇰줈 ?섏궛."""
        try:
            import mss as _mss
            with _mss.mss() as sct:
                mon = sct.monitors[1]
            return {
                "left": mon["left"] + int(roi["x_ratio"] * mon["width"]),
                "top": mon["top"] + int(roi["y_ratio"] * mon["height"]),
                "width": max(1, int(roi["w_ratio"] * mon["width"])),
                "height": max(1, int(roi["h_ratio"] * mon["height"])),
            }
        except Exception:
            return None

    def _move_cursor(self, cx: int, cy: int) -> None:
        """嫄고깘 ?꾪삎 異붿쟻??而ㅼ꽌 ?대룞. planet_live_solver? ?숈씪?섍쾶 SetCursorPos ?ъ슜."""
        try:
            import win32api
            win32api.SetCursorPos((int(cx), int(cy)))
        except Exception:
            pass

    def _on_safety_pause(self) -> None:
        """안전 모드 진입 시 런타임이 소유한 지속 입력을 모두 해제한다."""
        self._release_runtime_inputs()

    def _handle_user_detected(self, ev) -> None:
        """?ㅻⅨ ?좎? 媛먯? ???붾젅洹몃옩 ?뚮┝ + ?먮룞?묐떟 梨꾪똿(硫붿떆吏 ?쒗솚)."""
        self.telegram.send("다른 유저 감지")
        msgs = self._cfg.auto_reply_messages
        if not msgs:
            return
        msg = msgs[self._reply_idx % len(msgs)]
        self._reply_idx += 1
        # 梨꾪똿: enter ??硫붿떆吏 ?낅젰 ??enter (?ㅺ린 ?낅젰? 諛깆뿏???듯빐)
        self.input_backend.press("enter", 0.05)


