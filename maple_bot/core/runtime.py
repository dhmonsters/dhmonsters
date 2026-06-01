# BotRuntime — 7개 모듈을 조립해 한 틱이 도는 봇 런타임. 게임/드라이버는 주입식(테스트 가능)
from __future__ import annotations

import queue
import time
from dataclasses import dataclass, field

from core.humanize.humanizer import Humanizer
from core.sensing.char_scanner import CharScanner
from core.sensing.antimob_scanner import AntiMobScanner
from core.sensing.event import Event
from core.orchestrator.orchestrator import Orchestrator
from core.navigation.block import Block
from core.navigation.block_runner import BlockRunner
from core.navigation.floor_judge import Floor, FloorJudge
from core.acting.combat import Combat, PotionRule
from core.acting.buff import BuffManager, Buff
from core.minigame.registry import SolverRegistry
from core.minigame.self_transparent_engine import SelfTransparentEngine
from core.minigame.sidecar import InMemoryChannel, SidecarChannel


@dataclass
class RuntimeConfig:
    """런타임 조립에 필요한 설정 (config.json 에서 매핑)."""
    minimap_region: dict
    floors: list[Floor] = field(default_factory=list)
    route: list[Block] = field(default_factory=list)
    attack_key: str = ""
    hp_rule: PotionRule | None = None
    mp_rule: PotionRule | None = None
    buffs: list[Buff] = field(default_factory=list)
    antimob_templates: dict = field(default_factory=dict)
    antimob_enabled: dict = field(default_factory=dict)
    minigame_type: str = "planet"
    # 거탐 (자체 ncnn 엔진)
    transparent_models_dir: str = "models/transparent"
    board_region: dict | None = None          # 거탐 게임판 화면영역 (None=minimap_region 대용 아님; 실기 설정)
    transparent_use_gpu: bool = False


class BotRuntime:
    """7모듈 조립 + 틱 실행. 의존성(화면캡처/입력백엔드/채널)은 주입 — 실기/테스트 공용.

    실기: screen_capture=실제 mss, input_backend=InterceptionBackend
    테스트: Fake capture + RecordingBackend
    """

    def __init__(self, screen_capture, input_backend, config: RuntimeConfig,
                 sidecar_channel: SidecarChannel | None = None):
        self._capture = screen_capture
        self._cfg = config
        self._sidecar = sidecar_channel or InMemoryChannel()

        # 입력 계층
        self.humanizer = Humanizer(backend=input_backend)

        # 감지 계층 → 이벤트큐
        self.event_queue: queue.Queue = queue.Queue()
        self.char_scanner = CharScanner(screen_capture, config.minimap_region)
        self.antimob_scanner = None
        if config.antimob_templates:
            self.antimob_scanner = AntiMobScanner(
                screen_capture, config.antimob_templates,
                config.antimob_enabled, region=config.minimap_region,
            )

        # 조율 계층
        self.orchestrator = Orchestrator(
            self.event_queue,
            on_pause=self._on_safety_pause,
            on_resume=lambda: None,
        )

        # 행동/동선 계층
        self.block_runner = BlockRunner(
            humanizer=self.humanizer,
            pos_fn=lambda: self.orchestrator.state.get_position() or (0, 0),
        )
        self.floor_judge = FloorJudge(config.floors) if config.floors else None
        self.combat = Combat(self.humanizer, hp_rule=config.hp_rule, mp_rule=config.mp_rule)
        self.buffs = BuffManager(self.humanizer, config.buffs)

        # 거탐 계층 (격리) — 자체 ncnn 엔진 (secure_loader/서버 의존 없음)
        self.registry = SolverRegistry()
        self.registry.register(SelfTransparentEngine(
            models_dir=config.transparent_models_dir,
            board_capture_fn=self._capture_board,
            move_cursor_fn=self._move_cursor,
            use_gpu=config.transparent_use_gpu,
        ))

        self._frame_id = 0

    # ── 감지 펌프 (테스트: 수동 / 실기: 스레드) ──────────────────────
    def pump_scanners_once(self) -> None:
        """스캐너 scan_once 를 직접 1회 호출해 이벤트큐를 채운다(테스트용)."""
        for sc in (self.char_scanner, self.antimob_scanner):
            if sc is None:
                continue
            ev = sc.scan_once()
            if ev is not None:
                self.event_queue.put(ev)

    def start_scanners(self) -> None:
        """실기: 스캐너 스레드 시작."""
        self.char_scanner.start(self.event_queue)
        if self.antimob_scanner:
            self.antimob_scanner.start(self.event_queue)

    def stop_scanners(self) -> None:
        self.char_scanner.stop()
        if self.antimob_scanner:
            self.antimob_scanner.stop()

    # ── 틱 ────────────────────────────────────────────────────────────
    def hunting_tick(self, now: float | None = None) -> None:
        """정상 사냥 1틱: 순찰 이동 + 공격 + 버프."""
        now = now if now is not None else time.time()
        if self.orchestrator.mode != "hunting":
            return
        if self._cfg.route:
            # 라우트 첫 블록을 한 스텝 진행(실기는 전체 순찰, 여기선 1블록 1회)
            self.block_runner.run_block(self._cfg.route[0], max_steps=1)
        if self._cfg.attack_key:
            self.combat.attack(self._cfg.attack_key, mode="duration")
        self.buffs.tick(now)

    def safety_tick(self, now: float | None = None) -> None:
        """안전 모드 1틱: 거탐 풀이 시도 → 성공 시 사냥 재개."""
        if self.orchestrator.mode != "safety":
            return
        self._frame_id += 1
        # SelfTransparentEngine.solve 가 게임판을 추적해 도형 사라질때까지 푼다(블로킹)
        result = self.registry.solve(
            self._cfg.minigame_type, screenshot=None,
            ctx={"frame_id": self._frame_id},
        )
        if result is not None and result.success:
            self.orchestrator.clear_safety()

    # ── 내부 ──────────────────────────────────────────────────────────
    def _capture_board(self):
        """거탐 게임판 영역 캡처 (board_region 설정 시 그 영역, 없으면 전체)."""
        region = self._cfg.board_region
        return self._capture(region) if region else self._capture()

    def _move_cursor(self, cx: int, cy: int) -> None:
        """거탐 도형 추적용 커서 이동. 백엔드에 move_to 있으면 사용(실기 Interception)."""
        bk = self.humanizer._backend
        if hasattr(bk, "move_to"):
            bk.move_to(cx, cy)

    def _on_safety_pause(self) -> None:
        """안전 진입 시 진행 중인 이동 방향키 해제(행동 정지)."""
        self.humanizer._backend.key_up("left")
        self.humanizer._backend.key_up("right")
        self.humanizer._backend.key_up("up")
