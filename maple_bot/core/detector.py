# HP/MP 픽셀 감지 및 몬스터 템플릿 매칭 모듈
from __future__ import annotations
import os
import numpy as np
import cv2

from core.screen_reader import ScreenReader
from core.config_manager import ConfigManager


class Detector:
    def __init__(self, screen_reader: ScreenReader, config: ConfigManager):
        self._screen = screen_reader
        self._config = config
        # 템플릿 캐시 (경로 → cv2 이미지)
        self._template_cache: dict[str, np.ndarray | None] = {}

    # ── 몬스터 감지 ───────────────────────────────────────────────────
    def has_monster(
        self,
        screenshot: np.ndarray,
        template_path: str,
        threshold: float = 0.75,
    ) -> bool:
        """screenshot 안에 template_path 몬스터 이미지가 있으면 True."""
        template = self._load_template(template_path)
        if template is None:
            return False
        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        return max_val >= threshold

    def find_monsters(
        self,
        screenshot: np.ndarray,
        template_path: str,
        threshold: float = 0.75,
    ) -> list[tuple[int, int]]:
        """화면에서 몬스터 위치(중심 좌표) 목록을 반환."""
        template = self._load_template(template_path)
        if template is None:
            return []

        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        th, tw = template.shape[:2]
        locations = np.where(result >= threshold)
        positions = []
        for y, x in zip(*locations):
            positions.append((int(x + tw // 2), int(y + th // 2)))
        return positions

    # ── HP / MP 감지 ──────────────────────────────────────────────────
    def hp_ratio(self) -> float:
        """HP 바의 현재 비율(0.0~1.0)을 반환. 좌표 미설정 시 1.0."""
        return self._bar_ratio("hp")

    def mp_ratio(self) -> float:
        """MP 바의 현재 비율(0.0~1.0)을 반환. 좌표 미설정 시 1.0."""
        return self._bar_ratio("mp")

    def hp_mp_ratios(self) -> tuple[float, float]:
        """HP와 MP 영역의 합집합을 한 번 캡처해 두 비율을 함께 반환한다."""
        hp_region = self._combined_bar_region("hp")
        mp_region = self._combined_bar_region("mp")
        valid = [region for region in (hp_region, mp_region) if region is not None]
        if not valid:
            return 1.0, 1.0
        left = min(region["left"] for region in valid)
        top = min(region["top"] for region in valid)
        right = max(region["left"] + region["width"] for region in valid)
        bottom = max(region["top"] + region["height"] for region in valid)
        frame = self._screen.capture({
            "left": left,
            "top": top,
            "width": right - left,
            "height": bottom - top,
        })

        def ratio(region, bar_type: str) -> float:
            if region is None:
                return 1.0
            x1 = region["left"] - left
            y1 = region["top"] - top
            crop = frame[y1:y1 + region["height"], x1:x1 + region["width"]]
            return self._combined_bar_ratio(crop, bar_type, region["width"])

        return ratio(hp_region, "hp"), ratio(mp_region, "mp")

    def _combined_bar_region(self, bar_type: str) -> dict | None:
        coord = self._config.get("coordinate", bar_type) or {}
        try:
            import win32gui as _wg
            title = self._config.get("settings2", "game_window_title") or "MapleStory"
            hwnd = _wg.FindWindow(None, title)
            if hwnd:
                game_ox, game_oy = _wg.ClientToScreen(hwnd, (0, 0))
                left, top, right, bottom = _wg.GetClientRect(hwnd)
                game_cw, game_ch = right - left, bottom - top
            else:
                game_ox, game_oy, game_cw, game_ch = 0, 0, 0, 0
        except Exception:
            game_ox, game_oy, game_cw, game_ch = 0, 0, 0, 0
        if coord.get("x_ratio") is not None and game_cw > 0 and game_ch > 0:
            x = game_ox + int(coord["x_ratio"] * game_cw)
            y = game_oy + int(coord["y_ratio"] * game_ch)
            width = max(1, int(coord["width_ratio"] * game_cw))
        else:
            px, py, width = coord.get("x"), coord.get("y"), coord.get("width")
            if px is None or py is None or not width:
                return None
            x = game_ox + int(px)
            y = game_oy + int(py)
            width = int(width)
        return {"left": int(x), "top": int(max(0, y - 8)), "width": width, "height": 17}

    @staticmethod
    def _combined_bar_ratio(img: np.ndarray, bar_type: str, width: int) -> float:
        if img is None or img.size == 0:
            return 1.0
        f = img.astype(np.float32) / 255.0
        r, g, b = f[:, :, 2], f[:, :, 1], f[:, :, 0]
        maxc = np.maximum(r, np.maximum(g, b))
        minc = np.minimum(r, np.minimum(g, b))
        delta = maxc - minc
        v = maxc
        with np.errstate(divide="ignore", invalid="ignore"):
            s = np.where(maxc > 1e-6, delta / maxc, 0.0)
        base = (s >= 0.35) & (v >= 0.25)
        hue = np.zeros_like(r)
        d = delta + 1e-9
        mr = (delta > 1e-6) & (maxc == r)
        mg = (delta > 1e-6) & (maxc == g)
        mb = (delta > 1e-6) & (maxc == b)
        hue[mr] = ((g[mr] - b[mr]) / d[mr]) % 6
        hue[mg] = (b[mg] - r[mg]) / d[mg] + 2
        hue[mb] = (r[mb] - g[mb]) / d[mb] + 4
        hue_deg = hue * 60
        if bar_type == "hp":
            color_mask = (hue_deg <= 20) | (hue_deg >= 340)
        else:
            color_mask = (hue_deg >= 180) & (hue_deg <= 260)
        final_mask = base & color_mask
        cols = np.where(final_mask.any(axis=0))[0]
        if len(cols) == 0 or int(final_mask.sum()) < 3:
            return 1.0
        return (int(cols[-1]) + 1) / width

    def _bar_ratio(self, bar_type: str) -> float:
        """바 영역을 한 번에 캡처 후 numpy HSV로 처리 — 개별 픽셀 API 호출 없음."""
        coord = self._config.get("coordinate", bar_type) or {}

        # ── 게임 창 원점·크기 조회 (coord_mode 무관하게 항상 시도) ──────────
        try:
            import win32gui as _wg
            _title = self._config.get("settings2", "game_window_title") or "MapleStory"
            _hwnd  = _wg.FindWindow(None, _title)
            if _hwnd:
                game_ox, game_oy = _wg.ClientToScreen(_hwnd, (0, 0))
                _l, _t, _r, _b   = _wg.GetClientRect(_hwnd)
                game_cw, game_ch = _r - _l, _b - _t
            else:
                game_ox, game_oy, game_cw, game_ch = 0, 0, 0, 0
        except Exception:
            game_ox, game_oy, game_cw, game_ch = 0, 0, 0, 0

        if coord.get("x_ratio") is not None and game_cw > 0 and game_ch > 0:
            # 비율 모드 — 현재 창 크기 기준으로 재계산 (창↔전체화면 전환 자동 대응)
            x     = game_ox + int(coord["x_ratio"]     * game_cw)
            y     = game_oy + int(coord["y_ratio"]     * game_ch)
            width = max(1, int(coord["width_ratio"]    * game_cw))
        else:
            # 픽셀 fallback — 저장된 클라이언트 상대 픽셀 + 현재 창 원점
            px = coord.get("x")
            py = coord.get("y")
            width = coord.get("width")
            if px is None or py is None or not width:
                return 1.0
            x = game_ox + int(px)
            y = game_oy + int(py)
            width = int(width)

        scan_h = 17  # ±8행

        # 바 영역 한 번에 캡처 (논리 좌표 → 물리 픽셀 변환 후 mss)
        px2, py2, pw2, ph2 = int(x), int(max(0, y - 8)), int(width), int(scan_h)
        region = {"left": px2, "top": py2, "width": pw2, "height": ph2}
        img = self._screen.capture(region)   # BGR numpy (H, W, 3)

        # numpy 벡터 연산으로 HSV 마스크 계산
        f = img.astype(np.float32) / 255.0
        r, g, b = f[:, :, 2], f[:, :, 1], f[:, :, 0]

        maxc = np.maximum(r, np.maximum(g, b))
        minc = np.minimum(r, np.minimum(g, b))
        delta = maxc - minc

        v = maxc
        # maxc=0인 픽셀의 0÷0 RuntimeWarning 억제
        with np.errstate(divide='ignore', invalid='ignore'):
            s = np.where(maxc > 1e-6, delta / maxc, 0.0)

        # 채도·명도 기본 필터 (흰색 텍스트·회색 빈칸·검정 제외)
        base = (s >= 0.35) & (v >= 0.25)

        # Hue 계산
        hue = np.zeros_like(r)
        d = delta + 1e-9  # 0 나눔 방지
        mr = (delta > 1e-6) & (maxc == r)
        mg = (delta > 1e-6) & (maxc == g)
        mb = (delta > 1e-6) & (maxc == b)
        hue[mr] = ((g[mr] - b[mr]) / d[mr]) % 6
        hue[mg] = (b[mg] - r[mg]) / d[mg] + 2
        hue[mb] = (r[mb] - g[mb]) / d[mb] + 4
        hue_deg = hue * 60

        if bar_type == "hp":
            color_mask = (hue_deg <= 20) | (hue_deg >= 340)
        else:
            color_mask = (hue_deg >= 180) & (hue_deg <= 260)

        final_mask = base & color_mask   # shape (H, W)

        # 색상 픽셀이 존재하는 가장 오른쪽 열 = 채워진 비율
        col_has_match = final_mask.any(axis=0)   # shape (W,)
        cols = np.where(col_has_match)[0]

        # 색상 픽셀 미검출 = 바 캡처 실패(좌표 이탈·UI 가림 등) → 포션 오남용 방지
        # 진짜 0%라면 캐릭터가 죽으므로 실용적으로 1.0(안전값) 반환
        if len(cols) == 0:
            return 1.0

        # 유효 픽셀이 3개 미만이면 노이즈로 간주 → 안전값 반환
        total_px = int(final_mask.sum())
        if total_px < 3:
            return 1.0

        return (int(cols[-1]) + 1) / width

    # ── 템플릿 캐시 ───────────────────────────────────────────────────
    def _load_template(self, path: str) -> np.ndarray | None:
        if path not in self._template_cache:
            if os.path.exists(path):
                buf = np.fromfile(path, dtype=np.uint8)
                self._template_cache[path] = cv2.imdecode(buf, cv2.IMREAD_COLOR)
            else:
                self._template_cache[path] = None
        return self._template_cache[path]

    def clear_cache(self) -> None:
        self._template_cache.clear()

    # ── monsters/ 폴더 이미지 목록 ────────────────────────────────────
    @staticmethod
    def list_monster_templates(folder: str = "monsters") -> list[str]:
        """monsters/ 폴더(하위 구조 포함)에서 대표 이미지 목록을 반환.

        구조: monsters/몬스터이름/stand/frame_0.png  (하위 폴더 방식)
              monsters/이미지.png                    (평면 방식)

        하위 폴더 방식이면 stand → 임의 포즈 순으로 첫 프레임만 사용.
        """
        if not os.path.isdir(folder):
            return []
        exts = {".png", ".jpg", ".bmp"}
        templates = []

        for item in sorted(os.listdir(folder)):
            item_path = os.path.join(folder, item)
            if os.path.isdir(item_path):
                # 몬스터별 하위 폴더: stand 우선, 없으면 첫 포즈 폴더 사용
                _pose_dirs = ["stand", "move", "attack1", "attack"]
                picked = None
                for pose in _pose_dirs:
                    pose_path = os.path.join(item_path, pose)
                    if os.path.isdir(pose_path):
                        frames = sorted([
                            f for f in os.listdir(pose_path)
                            if os.path.splitext(f)[1].lower() in exts
                        ])
                        if frames:
                            picked = os.path.join(pose_path, frames[0])
                            break
                if picked is None:
                    # stand/move 없으면 폴더 내 첫 이미지
                    for f in sorted(os.listdir(item_path)):
                        if os.path.splitext(f)[1].lower() in exts:
                            picked = os.path.join(item_path, f)
                            break
                if picked:
                    templates.append(picked)
            elif os.path.splitext(item)[1].lower() in exts:
                # 평면 구조: 직접 이미지
                templates.append(item_path)

        return templates

