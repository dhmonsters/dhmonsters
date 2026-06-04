# BotRuntime — 7개 모듈을 조립해 한 틱이 도는 봇 런타임. 게임/드라이버는 주입식(테스트 가능)
from __future__ import annotations

import queue
import time
from dataclasses import dataclass, field

from core.humanize.humanizer import Humanizer
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
from core.acting.buff import BuffManager, Buff
from core.acting.pet import PetFeeder
from core.sensing.user_scanner import UserScanner
from core.sensing import monster_vision
from core.notify.telegram import TelegramNotifier
from core.humanize.intent import Intent
from core.minigame.registry import SolverRegistry
from core.minigame.self_transparent_engine import SelfTransparentEngine
from core.minigame.sidecar import InMemoryChannel, SidecarChannel


@dataclass
class RuntimeConfig:
    """런타임 조립에 필요한 설정 (config.json 에서 매핑)."""
    minimap_region: dict
    floors: list[Floor] = field(default_factory=list)
    route: list[Block] = field(default_factory=list)
    route_mode: bool = False     # True면 route를 floor-hunt 루트 실행기로 반복 실행(사다리/모드)
    attack_key: str = ""
    hp_rule: PotionRule | None = None
    mp_rule: PotionRule | None = None
    buffs: list[Buff] = field(default_factory=list)
    antimob_templates: dict = field(default_factory=dict)
    antimob_enabled: dict = field(default_factory=dict)
    minigame_type: str = "planet"
    # 거탐 (자체 ncnn 엔진)
    transparent_models_dir: str = "models/transparent"
    board_region: dict | None = None          # 거탐 게임판 화면영역 (None=board_roi 비율 사용)
    board_roi: dict | None = None              # A 고정 상대좌표 {x_ratio,y_ratio,w_ratio,h_ratio}
    transparent_use_gpu: bool = False
    transparent_enabled: bool = True           # 투명도형 자동풀이 on/off (체크박스 게이팅)
    # 거탐 감지 (LieScanner)
    lie_enabled: bool = True
    lie_alert: bool = False                     # 거탐 알림(소리+텔레그램) 통합 토글
    lie_title_template: str = "templates/transparent_shape_title.png"
    lie_threshold: float = 0.65
    lie_detect_region: dict | None = None      # 타이틀 탐색 영역 (None=전체화면)
    # 순찰 (Patrol) — 첫 구역 좌우 경계
    patrol_left_x: int = 0
    patrol_right_x: int = 0
    patrol_margin: int = 0
    # 잡템 판매 — ConfigManager(get 인터페이스) 주입 시 활성. 없으면 비활성
    junk_config: object = None
    # 펫 먹이
    pet_key: str = ""
    pet_interval: float = 600.0
    pet_count: int = 1
    attack_interval: float = 0.4   # 공격(스킬) 최소 발동 간격(초) — 매 틱 도배 방지
    # 밀집 사냥(시간당 처치 최적화): 사냥영역 몹 개수로 멈춰사냥↔이동 결정
    hunt_stay_threshold: int = 3    # 이 마리수 이상이면 멈춰 사냥(밀집)
    hunt_leave_threshold: int = 1   # 이 마리수 이하로 줄면 이동(희소)
    hunt_max_dwell_sec: float = 8.0 # 한 자리 최대 체류(밀집이어도 초과 시 강제 이동)
    # 픽업 타이머 — 주기적으로 줍기 키 입력(바닥 아이템 자동 줍기)
    pickup_key: str = ""
    pickup_interval: float = 60.0
    # 텔레그램 알림
    tg_enabled: bool = False
    tg_token: str = ""
    tg_chat_id: str = ""
    # 다른 유저 감지 + 자동응답
    user_detect_enabled: bool = False
    user_min_red: int = 15
    auto_reply_messages: list = field(default_factory=list)
    # 사냥 영역 (B training: 이 영역 안에서만 몬스터/닉네임 감지)
    hunt_area_region: dict | None = None
    # 좌표 기준 — relative면 영역을 게임창 이동량(현재원점-앵커)만큼 보정(창 따라감)
    coord_mode: str = "absolute"
    game_window_title: str = ""
    coord_anchor: list | None = None      # 영역 지정 시점 창 원점 [ox, oy]
    char_rgb: tuple | None = None          # 미니맵 캐릭터 점 색(RGB). None이면 기본 노랑
    # 몬스터 감지(image 모드, B 메커니즘: 닉네임 박스 안 몬스터)
    hunt_mode: str = "key"
    name_template: str = ""        # 닉네임 템플릿 경로
    monster_templates: list = field(default_factory=list)  # 몬스터 템플릿 경로들
    monster_accuracy: float = 0.9
    atk_x_min: int = -35
    atk_x_max: int = 35
    atk_y_min: int = -70
    atk_y_max: int = 70
    name_threshold: float = 0.7


class BotRuntime:
    """7모듈 조립 + 틱 실행. 의존성(화면캡처/입력백엔드/채널)은 주입 — 실기/테스트 공용.

    실기: screen_capture=실제 mss, input_backend=InterceptionBackend
    테스트: Fake capture + RecordingBackend
    """

    def __init__(self, screen_capture, input_backend, config: RuntimeConfig,
                 sidecar_channel: SidecarChannel | None = None,
                 hp_mp_reader=None):
        self._capture = screen_capture
        self._cfg = config
        self._sidecar = sidecar_channel or InMemoryChannel()
        # HP/MP 비율을 읽어 (hp, mp) 반환하는 콜백(run_integrated가 Detector로 주입).
        # 통합 포팅 때 포션 배선이 빠져 있었음 — 이 리더 + check_potions로 복구.
        self._hp_mp_reader = hp_mp_reader

        # 입력 계층
        self.humanizer = Humanizer(backend=input_backend)

        # 감지 계층 → 이벤트큐
        self.event_queue: queue.Queue = queue.Queue()
        self.char_scanner = CharScanner(
            screen_capture, lambda: self._resolve_region(config.minimap_region),
            log_fn=lambda m: self.log(m, "감지"))
        self.antimob_scanner = None
        if config.antimob_templates:
            self.antimob_scanner = AntiMobScanner(
                screen_capture, config.antimob_templates,
                config.antimob_enabled,
                region=lambda: self._resolve_region(config.minimap_region),
            )
        # 거탐 감지 — 타이틀 출현 → "lie" 이벤트 → Orchestrator가 safety 모드 전환
        self.lie_scanner = None
        if config.lie_enabled:
            import os as _os
            if _os.path.exists(config.lie_title_template):
                self.lie_scanner = LieScanner(
                    screen_capture, config.lie_title_template,
                    threshold=config.lie_threshold,
                    region=config.lie_detect_region,
                )
        # 다른 유저 감지 (빨강 픽셀)
        self.user_scanner = None
        if config.user_detect_enabled:
            self.user_scanner = UserScanner(
                screen_capture, min_red=config.user_min_red,
                region=lambda: self._resolve_region(config.minimap_region),
            )
        # 텔레그램 알림 — 토큰·챗ID 있으면 활성(거탐 알림 통합 토글이 발동 시점 결정)
        self.telegram = TelegramNotifier(
            token=config.tg_token, chat_id=config.tg_chat_id,
            enabled=bool(config.tg_token and config.tg_chat_id),
        )

        # 조율 계층
        self.orchestrator = Orchestrator(
            self.event_queue,
            on_pause=self._on_safety_pause,
            on_resume=lambda: None,
        )

        # 행동/동선 계층
        self._bot_running = False    # 컨트롤러 start/stop로 토글 (루트 실행 활성 조건)
        self._route_hunt_active = False   # 현재 루트 블록이 사냥 구간이면 True(공격 게이팅)
        self.log = lambda m, cat="시스템": None  # UI 로그 콜백(run_integrated 주입). (msg, 카테고리)
        # 층: 명시적 zones가 있으면 우선, 없으면 루트 블록 Y에서 자동 추출(복귀용)
        _floors = config.floors
        if not _floors and config.route:
            from core.navigation.floor_extract import floors_from_route
            _floors = floors_from_route([b.to_dict() for b in config.route])
        self.floor_judge = FloorJudge(_floors) if _floors else None
        # 층 이탈 복귀 그래프 — route의 사다리에서 자동 구성
        _recovery_graph = None
        if self.floor_judge is not None and config.route:
            from core.navigation.map_graph import build_graph
            _recovery_graph = build_graph(
                _floors, [b.to_dict() for b in config.route], self.floor_judge)
        # 밀집 사냥 디렉터 — 사냥영역 몹 개수로 멈춰사냥(DWELL)↔이동(MOVING) 결정
        from core.acting.hunt_director import HuntDirector
        self.hunt_director = HuntDirector(
            config.hunt_stay_threshold, config.hunt_leave_threshold,
            config.hunt_max_dwell_sec)
        self._area_count = 0
        self._area_count_ts = -1e9
        self.block_runner = BlockRunner(
            humanizer=self.humanizer,
            pos_fn=lambda: self.orchestrator.state.get_position() or (0, 0),
            stop_fn=lambda: not self._route_can_run(),   # 안전모드·정지 시 루트 폴링루프 즉시 이탈
            dwell_fn=lambda: self.hunt_director.is_dwelling(),  # 밀집 시 이동 park
            floor_judge=self.floor_judge, recovery_graph=_recovery_graph,
            on_segment_enter=self._on_route_segment_enter,
            on_segment_exit=self._on_route_segment_exit,
            log_fn=lambda m: self.log(m, "이동"),
        )
        # 설정된 캐릭터색(char_r/g/b)을 느슨한 HSV로 감지에 반영(미니맵 노란점 인식률↑)
        if config.char_rgb:
            from core.sensing.char_scanner import hsv_range_from_rgb
            lo, hi = hsv_range_from_rgb(*config.char_rgb)
            self.char_scanner.set_hsv(lo, hi)
        self.combat = Combat(self.humanizer, hp_rule=config.hp_rule, mp_rule=config.mp_rule,
                             log_fn=lambda m, c: self.log(m, c))
        self.buffs = BuffManager(self.humanizer, config.buffs,
                                 log_fn=lambda m: self.log(m, "버프"))
        self.pet = PetFeeder(self.humanizer, key=config.pet_key, interval=config.pet_interval,
                             log_fn=lambda m: self.log(m, "펫·줍기"), label="펫 먹이",
                             count=config.pet_count)
        # 픽업 타이머 — PetFeeder 패턴 재사용(주기 줍기 키)
        self.pickup = PetFeeder(self.humanizer, key=config.pickup_key,
                                interval=config.pickup_interval,
                                log_fn=lambda m: self.log(m, "펫·줍기"), label="줍기")
        # 몬스터 감지(image 모드) — 닉네임/몬스터 템플릿 로드 (B 메커니즘)
        self._name_tpl = None
        self._monster_tpls = {}
        if config.hunt_mode == "image" or config.route_mode:
            if config.name_template:
                self._name_tpl = monster_vision.load_template(config.name_template)
            for i, p in enumerate(config.monster_templates):
                t = monster_vision.load_template(p)
                if t is not None:
                    self._monster_tpls[f"m{i}"] = t
        # 닉네임 템플릿 추적기 — 사냥영역에서 닉네임 위치(=캐릭 기준점)를 찾아 따라감
        from core.sensing.name_tracker import NameTracker
        self.name_tracker = NameTracker(self._name_tpl, config.name_threshold)
        # 잡템 자동판매 (A sell_junk 래핑 + B 보호목록). 실판매는 게임 필요 → 인스턴스만 준비
        self.junk_seller = None
        if config.junk_config is not None:
            from core.acting.junk_seller import JunkSeller
            self.junk_seller = JunkSeller(
                config.junk_config, screen_capture, input_backend,
            )
        # 순찰 — 구역 좌우 왕복 (경계 도달시 방향전환, 랜덤마진)
        self.patrol = None
        if config.patrol_right_x > config.patrol_left_x:
            self.patrol = Patrol(
                PatrolZone(config.patrol_left_x, config.patrol_right_x),
                margin=config.patrol_margin,
            )

        # 층별 반복 사냥 루트 실행기 — route_mode + route 있으면 별도 스레드로 반복 실행
        self.floor_hunt_runner = None
        if config.route_mode and config.route:
            from core.navigation.floor_hunt_runner import FloorHuntRunner
            self.floor_hunt_runner = FloorHuntRunner(
                self.block_runner,
                get_blocks=lambda: self._cfg.route,
                is_active=self._route_can_run,
            )

        # 거탐 계층 (격리) — 자체 ncnn 엔진 (secure_loader/서버 의존 없음)
        self.registry = SolverRegistry()
        self.registry.register(SelfTransparentEngine(
            models_dir=config.transparent_models_dir,
            board_capture_fn=self._capture_board,
            move_cursor_fn=self._move_cursor,
            use_gpu=config.transparent_use_gpu,
        ))

        self._frame_id = 0
        self._reply_idx = 0

        # 다른 유저 감지 → 자동응답(채팅) + 텔레그램 알림
        self.orchestrator.on("user_detected", self._handle_user_detected)
        # 거탐 감지 → 알림(소리+텔레그램) 통합. 자동풀이는 safety_tick이 담당
        self.orchestrator.on("lie", self._handle_lie)

    # ── 감지 펌프 (테스트: 수동 / 실기: 스레드) ──────────────────────
    def pump_scanners_once(self) -> None:
        """스캐너 scan_once 를 직접 1회 호출해 이벤트큐를 채운다(테스트용)."""
        for sc in (self.char_scanner, self.antimob_scanner, self.lie_scanner, self.user_scanner):
            if sc is None:
                continue
            ev = sc.scan_once()
            if ev is not None:
                self.event_queue.put(ev)

    def start_scanners(self) -> None:
        """실기: 스캐너 스레드 시작."""
        for sc in (self.char_scanner, self.antimob_scanner, self.lie_scanner, self.user_scanner):
            if sc is not None:
                sc.start(self.event_queue)

    def stop_scanners(self) -> None:
        for sc in (self.char_scanner, self.antimob_scanner, self.lie_scanner, self.user_scanner):
            if sc is not None:
                sc.stop()

    # ── 루트 실행 활성 조건 ───────────────────────────────────────────
    def set_running(self, flag: bool) -> None:
        """컨트롤러 start/stop가 호출 — 루트 실행기 활성/정지 토글."""
        self._bot_running = flag

    def _route_can_run(self) -> bool:
        """봇이 켜져 있고 사냥 모드일 때만 루트 실행(안전모드·정지 시 즉시 이탈)."""
        return self._bot_running and self.orchestrator.mode == "hunting"

    # ── 틱 ────────────────────────────────────────────────────────────
    def hunting_tick(self, now: float | None = None) -> None:
        """정상 사냥 1틱: 구역 좌우 왕복 순찰 + 공격 + 버프."""
        now = now if now is not None else time.time()
        if self.orchestrator.mode != "hunting":
            return

        # HP/MP 물약 — 매 사냥 틱 확인(임계 미만이면 Combat이 키 입력). 어느 분기든 먼저 실행.
        self._check_potions(now)

        # 밀집 판단 — 몬스터 템플릿이 있을 때만(image/route). 사냥영역 전체 몹 개수로
        # 멈춰사냥(dwelling)↔이동 결정. 희소(≤이탈임계)면 안 멈추고 이동, 밀집(≥진입임계)이면 멈춰 처치.
        density_on = (getattr(self, "_name_tpl", None) is not None
                      and bool(getattr(self, "_monster_tpls", None))
                      and getattr(self, "hunt_director", None) is not None)
        dwelling = False
        if density_on:
            dwelling = self.hunt_director.update(self._count_monsters_in_area(now), now)

        # 루트 실행기 모드: 이동·공격은 루트 스레드가 수행 → 여기선 버프/펫만
        if self.floor_hunt_runner is not None:
            self.buffs.tick(now)
            self.pet.tick(now)
            self.pickup.tick(now)
            # 사냥 구간에서, 밀집(dwelling)일 때만 멈춰 공격(이동 park는 dwell_fn이 처리).
            # 템플릿 없으면 기존 공격박스 판정으로 폴백.
            if self._route_hunt_active and self._cfg.attack_key:
                if dwelling if density_on else self._monster_in_range():
                    self.combat.attack(self._cfg.attack_key, mode="duration",
                                       now=now, interval=self._cfg.attack_interval)
            return

        # 공격할지 판정: 밀집 사용 시 dwelling, 아니면 image=공격박스/key=항상
        attacking = False
        if self._cfg.attack_key:
            if density_on:
                attacking = dwelling
            elif self._cfg.hunt_mode == "image":
                attacking = self._monster_in_range()
            else:
                attacking = True

        # 이동 XOR 제자리공격 — 좌우 이동키는 누른 채 유지하고, 공격할 땐 뗀다.
        if attacking:
            self.humanizer.release_dir()   # 제자리 공격: 유지 중인 이동키 해제
            self.combat.attack(self._cfg.attack_key, mode="duration",
                               now=now, interval=self._cfg.attack_interval)
        else:
            # 순찰: 현재 위치로 방향 결정 → 목표 경계로 이동(hold_dir로 키 유지)
            if self.patrol is not None:
                pos = self.orchestrator.state.get_position()
                if pos is not None:
                    self.patrol.next_direction(pos[0])
                    target = self.patrol.target_x()
                    self.block_runner.run_block(
                        Block(type="move", target_x=target, move_type="walk"),
                        max_steps=1,
                    )
            elif self._cfg.route:
                self.block_runner.run_block(self._cfg.route[0], max_steps=1)

        self.buffs.tick(now)
        self.pet.tick(now)
        self.pickup.tick(now)

    def _check_potions(self, now: float) -> None:
        """HP/MP 비율을 읽어 임계 미만이면 물약 사용(Combat.check_potions).
        리더 미주입(테스트 등)이면 아무것도 안 함."""
        reader = getattr(self, "_hp_mp_reader", None)
        if reader is None:
            return
        try:
            hp, mp = reader()
        except Exception:
            return
        self.combat.check_potions(hp, mp, now)

    def _on_route_segment_enter(self, block) -> None:
        """루트 러너가 블록 진입 시 호출 — 사냥 구간(move·pass아님)이면 공격 허용."""
        self._route_hunt_active = (
            getattr(block, "type", None) == "move"
            and getattr(block, "mode", "count") != "pass")

    def _on_route_segment_exit(self, block) -> None:
        """블록 이탈(finally) 시 호출 — 공격 플래그를 항상 끈다(블록 사이 비공격)."""
        self._route_hunt_active = False

    def _resolve_region(self, region: dict | None) -> dict | None:
        """상대 영역 dict를 현재 게임창 원점으로 해석(absolute면 그대로, None이면 None)."""
        if not region:
            return region
        from core.config_manager import resolve_window_region
        a = self._cfg.coord_anchor
        anchor = (int(a[0]), int(a[1])) if a else None
        x, y, w, h = resolve_window_region(
            self._cfg.coord_mode, self._cfg.game_window_title,
            int(region["left"]), int(region["top"]),
            int(region["width"]), int(region["height"]), anchor)
        return {"left": x, "top": y, "width": w, "height": h}

    def _monster_in_range(self) -> bool:
        """B 메커니즘: 사냥영역 캡처 → 닉네임 위치 → atk 박스 → 박스 안 몬스터 매칭."""
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
        """사냥영역 '전체'의 몹 개수(공격박스가 아님). 밀집 판단용. ≈0.3s throttle 캐시."""
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

    def detect_monsters_rel(self) -> list[tuple[int, int]]:
        """사냥영역 몬스터 탐지 → 캐릭(닉네임) 기준 화면px 오프셋 [(dx,dy), ...].
        미니맵 캔버스의 몬스터 점 표시용(헌트모드 무관). 템플릿/닉네임 없으면 []."""
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
        """안전 모드 1틱: (자동풀이 켜졌을 때만) 거탐 풀이 시도 → 성공 시 사냥 재개."""
        if self.orchestrator.mode != "safety":
            return
        if not self._cfg.transparent_enabled:
            return   # 투명도형 자동풀이 꺼짐 → 일시정지 유지(사용자 수동 처리)
        self._frame_id += 1
        # SelfTransparentEngine.solve 가 게임판을 추적해 도형 사라질때까지 푼다(블로킹)
        result = self.registry.solve(
            self._cfg.minigame_type, screenshot=None,
            ctx={"frame_id": self._frame_id},
        )
        if result is not None and result.success:
            self.orchestrator.clear_safety()

    # ── 내부 ──────────────────────────────────────────────────────────
    def _handle_lie(self, ev) -> None:
        """거탐 감지 → 알림(소리+텔레그램) 통합 발동. lie_alert 켜졌을 때만."""
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
            self.telegram.send("거탐 감지됨 — 봇 일시정지")
        except Exception:
            pass

    def _capture_board(self):
        """거탐 게임판 영역 캡처. board_region 우선, 없으면 board_roi 비율(A 고정값)로 환산, 둘 다 없으면 전체."""
        region = self._cfg.board_region
        if region is None and self._cfg.board_roi:
            region = self._board_roi_to_region(self._cfg.board_roi)
        return self._capture(region) if region else self._capture()

    def _board_roi_to_region(self, roi: dict):
        """A 고정 상대좌표(x/y/w/h_ratio)를 주모니터 기준 픽셀 영역으로 환산."""
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
        """거탐 도형 추적용 커서 이동. 백엔드에 move_to 있으면 사용(실기 Interception)."""
        bk = self.humanizer._backend
        if hasattr(bk, "move_to"):
            bk.move_to(cx, cy)

    def _on_safety_pause(self) -> None:
        """안전 진입 시 유지 중인 이동 방향키 해제(행동 정지)."""
        self.humanizer.release_dir()           # 좌우 유지키 해제(상태 동기화)
        self.humanizer._backend.key_up("up")   # 위(사다리 등) 키도 안전 해제

    def _handle_user_detected(self, ev) -> None:
        """다른 유저 감지 → 텔레그램 알림 + 자동응답 채팅(메시지 순환)."""
        self.telegram.send("다른 유저 감지됨")
        msgs = self._cfg.auto_reply_messages
        if not msgs:
            return
        msg = msgs[self._reply_idx % len(msgs)]
        self._reply_idx += 1
        # 채팅: enter → 메시지 입력 → enter (실기 입력은 백엔드 통해)
        self.humanizer.perform(Intent(action="key", key="enter", base_hold_sec=0.05))
