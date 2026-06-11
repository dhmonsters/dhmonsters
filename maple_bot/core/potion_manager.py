# HP/MP 비율 감지 후 포션 키를 자동으로 입력하는 포션 관리자
import time
import random
import logging
from typing import Callable

from core.detector import Detector
from core.input_controller import InputController

logger = logging.getLogger(__name__)


class PotionManager:
    def __init__(
        self,
        input_ctrl: InputController,
        detector: Detector,
        on_status: Callable[[str], None] | None = None,
        on_before_use: Callable[[], None] | None = None,
    ):
        self._input = input_ctrl
        self._detector = detector
        self._on_status = on_status or (lambda msg: None)
        # 실제 포션 키를 누르기 직전 호출 — 이동 점프 홀드 일시 해제용(공중 씹힘 방지)
        self._on_before_use = on_before_use or (lambda: None)

        self._hp_cfg: dict = {}
        self._mp_cfg: dict = {}
        self._hp_last_used: float = 0.0
        self._mp_last_used: float = 0.0
        # 진단 로그(실측 비율) 출력 throttle — 포션이 왜 안 나가는지 눈으로 보기 위함
        self._diag_last: dict[str, float] = {}
        self._diag_interval: float = 5.0

    def set_config(self, hp_cfg: dict, mp_cfg: dict) -> None:
        """회복 설정(recovery.hp_potion, recovery.mp_potion)을 주입."""
        self._hp_cfg = hp_cfg
        self._mp_cfg = mp_cfg

    def check_and_use(self) -> None:
        """HP/MP 비율을 확인하고 임계값 이하이면 포션 키를 입력한다.
        HP 오류가 발생해도 MP 체크는 독립적으로 실행된다."""
        now = time.time()
        try:
            self._check_potion(now, "hp", self._hp_cfg)
        except Exception as exc:
            logger.warning("HP 포션 체크 오류: %s", exc)
            self._on_status(f"HP 포션 오류: {exc}")
        try:
            self._check_potion(now, "mp", self._mp_cfg)
        except Exception as exc:
            logger.warning("MP 포션 체크 오류: %s", exc)
            self._on_status(f"MP 포션 오류: {exc}")

    # ── 내부 ──────────────────────────────────────────────────────────
    def _check_potion(self, now: float, bar_type: str, cfg: dict) -> None:
        if not cfg.get("enabled"):
            return

        threshold = cfg.get("threshold", 70) / 100.0
        cooldown  = cfg.get("cooldown_sec", 3.0)
        key       = cfg.get("key", "9" if bar_type == "hp" else "0")
        label     = "HP" if bar_type == "hp" else "MP"

        # 실측 비율을 먼저 읽어 진단 로그를 throttle 출력(쿨다운과 무관하게 항상 가시화).
        # ratio가 계속 100%면 바 좌표/창 인식 문제, 임계 미만인데 안 나가면 키/쿨다운 문제.
        ratio = self._detector.hp_ratio() if bar_type == "hp" else self._detector.mp_ratio()
        if now - self._diag_last.get(bar_type, 0.0) >= self._diag_interval:
            self._on_status(f"💊 {label} {ratio * 100:.0f}% (임계 {threshold * 100:.0f}%, 키 [{key}])")
            self._diag_last[bar_type] = now

        last_used = self._hp_last_used if bar_type == "hp" else self._mp_last_used
        if now - last_used < cooldown:
            return  # 쿨다운 중

        if ratio < threshold:
            hold = random.uniform(0.03, 0.20)
            self._on_before_use()   # 이동 점프 잠깐 해제 → 포션이 공중에서 씹히지 않게
            self._input.press_key(key, hold_sec=hold)
            self._on_status(f"{label} 포션 사용 [{key}] ({ratio * 100:.0f}%)")
            logger.info("%s 포션: ratio=%.2f key=%s", label, ratio, key)

            if bar_type == "hp":
                self._hp_last_used = now
            else:
                self._mp_last_used = now
