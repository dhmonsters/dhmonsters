# CaptureThread → Detectors → GameState 흐름을 조율하는 비전 파이프라인 스레드
from __future__ import annotations

import threading
import time

from .minimap_detector import MinimapDetector
from .monster_detector import MonsterDetector
from .attack_box_resolver import AttackBoxResolver
from .monster_tracker import MonsterTracker
from .screen_position_resolver import resolver_from_config, ScreenPositionResolver
from .camera_tracker import CameraTracker
from .name_tracker import NameTagTracker
from core.config_manager import get_user_templates_dir


class VisionPipeline(threading.Thread):
    """FrameBuffer에서 ROI를 읽어 감지기를 실행하고 GameState를 갱신한다.

    CaptureThread(30fps)보다 낮은 15fps로 동작해 CPU 부담을 줄인다.

    Args:
        game_state:   갱신 대상 GameState 인스턴스.
        frame_buffer: FrameBuffer 인스턴스 (ROI 이미지 소스).
        config:       ConfigManager 인스턴스.
        detector:     기존 Detector 인스턴스 (find_monsters 재사용). 선택.
        target_fps:   목표 감지 속도 (기본 15).
    """

    def __init__(self, game_state, frame_buffer, config,
                 detector=None, target_fps: int = 15) -> None:
        super().__init__(daemon=True, name="VisionPipeline")
        self._gs = game_state
        self._fb = frame_buffer
        self._config = config
        self._fps = max(1, target_fps)
        self._stop_event = threading.Event()

        # 감지기 초기화
        self._minimap_det   = MinimapDetector(config, frame_buffer)
        self._monster_det   = MonsterDetector(config, frame_buffer, detector)
        self._atk_resolver  = AttackBoxResolver()
        self._mon_tracker   = MonsterTracker()
        self._monster_tick  = 0   # 몬스터 감지 tick 카운터 (3tick마다 1회)
        self._resolver_tick = 0   # resolver 재빌드 주기 (30tick = 2초)

        # 이름표 하이브리드 추적
        self._cam_tracker_pipe = CameraTracker()
        self._name_tracker     = NameTagTracker(get_user_templates_dir())

    # ── 공개 제어 ──────────────────────────────────────────────────────
    def stop(self) -> None:
        """파이프라인 스레드를 중단 요청한다."""
        self._stop_event.set()

    # ── 스레드 본체 ────────────────────────────────────────────────────
    def run(self) -> None:
        interval = 1.0 / self._fps

        while not self._stop_event.is_set():
            t0 = time.perf_counter()

            if self._fb.has_frame():
                self._process()
                # detection_fps: 실제 처리가 있을 때만 갱신 (스파이크 방지)
                elapsed = time.perf_counter() - t0
                det_fps = 1.0 / elapsed if elapsed > 0 else 0.0
                self._gs.update(detection_fps=det_fps)

            sleep = interval - (time.perf_counter() - t0)
            if sleep > 0:
                time.sleep(sleep)

    # ── 내부 처리 ─────────────────────────────────────────────────────
    def _process(self) -> None:
        """미니맵 + 몬스터 감지 + 화면 좌표 변환 실행 후 GameState 갱신."""
        # try 블록 밖에서도 참조할 수 있도록 미리 초기화
        raw_pos    = None
        smooth_pos = None

        # ── 미니맵 감지 ───────────────────────────────────────────────
        try:
            raw_pos, smooth_pos, confidence = self._minimap_det.detect()

            updates: dict = {
                "detection_confidence": confidence,
                "char_path": self._minimap_det.get_char_path(),
            }
            if smooth_pos is not None:
                updates["char_pos_smooth"] = smooth_pos
            if raw_pos is not None:
                updates["char_pos"] = raw_pos

            # ── 화면 좌표 변환 (ScreenPositionResolver) ───────────────
            # 30tick(≈2초)마다 resolver를 재빌드해 config 변경을 반영
            self._resolver_tick += 1
            if self._resolver_tick >= 30 or not hasattr(self, "_resolver"):
                self._resolver_tick = 0
                self._resolver = resolver_from_config(self._config)

            pos_for_resolve = smooth_pos or raw_pos
            if pos_for_resolve is not None and self._resolver is not None:
                try:
                    screen_pos, cam_rect = self._resolver.resolve(pos_for_resolve)
                    updates["character_screen_pos"]   = screen_pos
                    updates["camera_rect_on_minimap"] = cam_rect
                except Exception:
                    pass

            self._gs.update(**updates)
        except Exception:
            pass

        # ── 몬스터 감지 (3tick마다 1회 — 약 5fps) ────────────────────
        self._monster_tick += 1
        if self._monster_tick >= 3:
            self._monster_tick = 0
            try:
                positions = self._monster_det.detect()
                tracked   = self._mon_tracker.update(positions)
                self._gs.update(monster_positions=positions,
                                tracked_monsters=tracked)
            except Exception:
                pass

        # ── Phase 6: 최신 미니맵 프레임 저장 (오버레이 패널용) ─────────
        try:
            mm_frame = self._fb.get_roi("minimap")
            if mm_frame is not None:
                self._gs.update(latest_minimap=mm_frame)
        except Exception:
            pass

        # ── Phase 6: 미니맵 로컬 윈도우 계산 ─────────────────────────
        try:
            pos_for_window = smooth_pos or raw_pos
            if pos_for_window is not None:
                mm_cfg   = self._config.get("minimap") or {}
                mm_w     = int(mm_cfg.get("width",  200))
                mm_h     = int(mm_cfg.get("height", 120))
                win_size = int((self._config.get("attack") or {}).get("local_window_size", 80))
                win = ScreenPositionResolver.make_local_minimap_window(
                    pos_for_window[0], pos_for_window[1], mm_w, mm_h, win_size
                )
                self._gs.update(minimap_local_window=win)
        except Exception:
            pass

        # ── Phase 6: 공격 박스 계산 ───────────────────────────────────
        try:
            screen_pos = self._gs.character_screen_pos
            if screen_pos is not None:
                lb, rb = self._atk_resolver.resolve(screen_pos, self._config)
                self._gs.update(attack_box_left=lb, attack_box_right=rb)
        except Exception:
            pass

        # ── 이름표 하이브리드 추적 ────────────────────────────────────
        try:
            pos_nt = smooth_pos or raw_pos
            if pos_nt is not None:
                game_frame = self._fb.get_frame()
                if game_frame is not None:
                    scr_h, scr_w = game_frame.shape[:2]
                    mm_cfg   = self._config.get("minimap") or {}
                    mm_w_nt  = int(mm_cfg.get("width",  200))
                    mm_h_nt  = int(mm_cfg.get("height", 120))
                    atk_nt   = self._config.get("attack") or {}
                    cam_ratio_nt = float(atk_nt.get("camera_w_ratio", 0.5))
                    dz_ratio_nt  = float(atk_nt.get("deadzone_ratio",  0.0))
                    thr_nt       = float(atk_nt.get("name_tag_threshold", 0.70))
                    self._name_tracker.set_threshold(thr_nt)

                    cl, cr, ct, cb = self._cam_tracker_pipe.update(
                        pos_nt[0], pos_nt[1],
                        mm_w_nt, mm_h_nt,
                        cam_ratio_nt, dz_ratio_nt,
                        scr_w, scr_h,
                    )
                    nt_result = self._name_tracker.update(
                        game_frame,
                        pos_nt[0], pos_nt[1],
                        cl, cr, ct, cb,
                        scr_w, scr_h,
                    )
                    self._gs.update(name_tag_result=nt_result)
        except Exception:
            pass


