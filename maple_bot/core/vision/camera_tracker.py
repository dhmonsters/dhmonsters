# 미니맵 캐릭터 위치 기반 카메라 상태를 DeadZone 규칙으로 추적하는 모듈
from __future__ import annotations


class CameraTracker:
    """DeadZone/SoftZone 규칙으로 카메라 X/Y 위치를 프레임 간 추적한다.

    X축: camera_w_ratio로 cam_w 결정
    Y축: cam_w * (screen_h / screen_w) 로 cam_h 자동 도출 (종횡비 유지)

    deadzone_ratio = 0.0 이면 캐릭터가 항상 카메라 중앙 → 기존 동작과 동일.
    """

    def __init__(self) -> None:
        self._cam_left: float | None = None
        self._cam_top:  float | None = None

    # ── 공개 API ──────────────────────────────────────────────────────────
    def update(
        self,
        mx: int, my: int,
        mm_w: int, mm_h: int,
        cam_ratio: float,
        dz_ratio: float,
        screen_w: int = 0,
        screen_h: int = 0,
    ) -> tuple[int, int, int, int]:
        """캐릭터 미니맵 좌표로 카메라 X/Y 위치를 갱신한다.

        Args:
            mx, my:     캐릭터 미니맵 좌표 (픽셀).
            mm_w, mm_h: 미니맵 전체 크기 (픽셀).
            cam_ratio:  camera_w_ratio (미니맵 폭 대비 카메라 가시 폭 비율).
            dz_ratio:   deadzone_ratio (DeadZone 비율, 0=항상 중앙).
            screen_w/h: 오버레이(게임 화면) 크기 — cam_h 종횡비 도출에 사용.

        Returns:
            (cam_left, cam_right, cam_top, cam_bottom) in 미니맵 픽셀.
        """
        # ── X축 ──────────────────────────────────────────────────────────
        cam_w   = max(1, int(mm_w * max(0.01, min(1.0, cam_ratio))))
        dz_half = cam_w * max(0.0, min(0.5, dz_ratio)) / 2.0

        if self._cam_left is None:
            self._cam_left = float(mx) - cam_w / 2.0

        cam_cx = self._cam_left + cam_w / 2.0
        if mx > cam_cx + dz_half:
            self._cam_left = float(mx) - (cam_w / 2.0 + dz_half)
        elif mx < cam_cx - dz_half:
            self._cam_left = float(mx) - (cam_w / 2.0 - dz_half)

        self._cam_left = max(0.0, min(self._cam_left, mm_w - cam_w))

        # ── Y축 (종횡비로 cam_h 자동 도출) ─────────────────────────────
        # cam_h = cam_w × (screen_h / screen_w) × (mm_w / mm_h) 이면
        # 미니맵 픽셀 → 화면 픽셀 스케일이 X/Y 동일해진다.
        if screen_w > 0 and screen_h > 0 and mm_h > 0:
            cam_h = max(1, int(cam_w * (screen_h / screen_w) * (mm_w / mm_h)))
        else:
            cam_h = max(1, mm_h)   # 화면 크기 불명 시 미니맵 전체 높이 사용

        cam_h   = min(cam_h, mm_h)
        dz_hy   = cam_h * max(0.0, min(0.5, dz_ratio)) / 2.0

        if self._cam_top is None:
            self._cam_top = float(my) - cam_h / 2.0

        cam_cy = self._cam_top + cam_h / 2.0
        if my > cam_cy + dz_hy:
            self._cam_top = float(my) - (cam_h / 2.0 + dz_hy)
        elif my < cam_cy - dz_hy:
            self._cam_top = float(my) - (cam_h / 2.0 - dz_hy)

        self._cam_top = max(0.0, min(self._cam_top, mm_h - cam_h))

        return (
            int(self._cam_left), int(self._cam_left) + cam_w,
            int(self._cam_top),  int(self._cam_top)  + cam_h,
        )

    def reset(self) -> None:
        """추적 상태를 초기화한다. 맵 전환 또는 봇 재시작 시 호출."""
        self._cam_left = None
        self._cam_top  = None


