# 인벤토리 캐시탭 → NPC 상점 기타탭에서 잡템을 자동으로 판매하는 모듈
from __future__ import annotations
import glob
import os
import random
import time


def _tab_color_changed(cx: int, cy: int, radius: int = 20, threshold: float = 6.0) -> "callable":
    """탭 좌표(cx, cy) 주변을 캡처한 BGR 이미지를 반환하는 함수를 돌려준다.

    사용법:
        snapshot = _tab_color_changed(cx, cy)  # 클릭 전 스냅샷 함수 얻기
        before = snapshot()                     # 클릭 전 촬영
        ... double_click ...
        after  = snapshot()                     # 클릭 후 촬영
        changed = _color_diff(before, after) > threshold
    """
    import mss as _mss
    import cv2 as _cv2
    import numpy as _np

    def _snap():
        with _mss.mss() as sct:
            mon = {
                "left":   max(0, cx - radius),
                "top":    max(0, cy - radius),
                "width":  radius * 2,
                "height": radius * 2,
            }
            raw = sct.grab(mon)
            return _cv2.cvtColor(_np.array(raw), _cv2.COLOR_BGRA2BGR)

    return _snap


def _color_diff(img1, img2) -> float:
    """두 이미지의 평균 픽셀 절대 차이 (0~255)."""
    import numpy as _np
    return float(_np.abs(img1.astype(_np.int32) - img2.astype(_np.int32)).mean())


def _resolve_coords(config, cfg: dict):
    """config 기준 잡템 좌표를 현재 게임창 위치로 보정해 반환한다.

    저장 형식 우선순위:
      1. key_ratio (게임창 상대 비율) → 현재 창 위치로 절대 좌표 복원  ← 창 이동해도 OK
      2. key (절대 픽셀) → 그대로 사용  ← 창 이동 시 틀릴 수 있음
    """
    from core.config_manager import get_game_window_rect
    ox, oy, cw, ch = get_game_window_rect(config)
    has_window = cw > 0 and ch > 0

    def pt(key):
        if has_window:
            r = cfg.get(key + "_ratio")
            if r and len(r) >= 2:
                return (int(ox + r[0] * cw), int(oy + r[1] * ch))
        v = cfg.get(key)
        return (int(v[0]), int(v[1])) if v and len(v) >= 2 else None

    def region(key):
        if has_window:
            r = cfg.get(key + "_ratio")
            if r and len(r) >= 4:
                return {
                    "left":   int(ox + r[0] * cw),
                    "top":    int(oy + r[1] * ch),
                    "width":  max(1, int(r[2] * cw)),
                    "height": max(1, int(r[3] * ch)),
                }
        v = cfg.get(key)
        return (
            {"left": int(v[0]), "top": int(v[1]),
             "width": int(v[2]), "height": int(v[3])}
            if v and len(v) == 4 else None
        )

    return pt, region


def open_shop(config, screen, input_ctrl, status_cb, stop_event=None) -> bool:
    """인벤토리 감지 → 캐시탭 더블클릭 → 활성화 확인 → 첫번째 슬롯 더블클릭 → 상점 열림 확인.

    좌표 계산 원칙:
      - 캐시탭 위치  = 인벤토리 감지 위치 + (cash_tab_stored - inventory_anchor_stored)
      - 첫번째 슬롯  = 활성 캐시탭 감지 위치 + (first_slot_stored - cash_tab_active_anchor_stored)

    Returns:
        True  — 성공 (상점 열림 확인 또는 첫슬롯 클릭 완료)
        False — 중단 또는 필수 설정 누락
    """
    import mss as _mss
    import cv2 as _cv2
    import numpy as _np

    def stopped() -> bool:
        return stop_event is not None and stop_event.is_set()

    cfg = config.get("settings2", "junk_sell") or {}
    pt, _ = _resolve_coords(config, cfg)   # 비율 우선, 없으면 절대 좌표 폴백

    cash_tab_offset       = pt("cash_tab_offset")      # 인벤토리 바 중심 기준 (dx, dy)
    first_slot_offset     = pt("first_slot_offset")    # 활성 캐시탭 중심 기준 (dx, dy)
    inventory_key         = (cfg.get("inventory_key") or "i").strip() or "i"

    inventory_tpl       = "templates/junk/inventory.png"
    cash_tab_active_tpl = "templates/junk/cash_tab_active.png"
    shop_open_tpl       = "templates/junk/shop_open.png"
    has_inv_tpl         = os.path.exists(inventory_tpl)
    has_active_tpl      = os.path.exists(cash_tab_active_tpl)
    has_shop_open_tpl   = os.path.exists(shop_open_tpl)

    # ── 전체 화면 캡처 헬퍼 ──────────────────────────────────────────
    def _capture():
        with _mss.mss() as sct:
            mon = sct.monitors[0]
            raw = sct.grab(mon)
            img = _cv2.cvtColor(_np.array(raw), _cv2.COLOR_BGRA2BGR)
        return img, mon

    def _abs(pos, mon):
        return (mon["left"] + pos[0], mon["top"] + pos[1])

    # ── 게임 창 포커스 ────────────────────────────────────────────────
    status_cb("게임 창 포커스...")
    input_ctrl.focus_game_window()
    time.sleep(0.3)   # AttachThreadInput 처리 후 OS 포커스 전환 대기
    if stopped():
        return False

    # ── 1단계: 인벤토리 열림 확인 ────────────────────────────────────
    scene, mon_all = _capture()

    inv_pos = None
    if has_inv_tpl:
        score = screen.find_template_score(scene, inventory_tpl)
        status_cb(f"인벤토리 매칭 점수: {score:.2f}")
        inv_pos = screen.find_template(scene, inventory_tpl, threshold=0.70)

    # ── 2단계: 미감지 → 인벤토리 키로 열기 후 재탐색 ───────────────
    if inv_pos is None:
        status_cb(f"인벤토리 미감지 → [{inventory_key}] 키로 열기...")
        input_ctrl.press_key(inventory_key)
        time.sleep(random.uniform(0.5, 0.7))   # 인벤토리 열리는 애니메이션 대기
        if stopped():
            return False

        scene, mon_all = _capture()
        if has_inv_tpl:
            score2 = screen.find_template_score(scene, inventory_tpl)
            status_cb(f"인벤토리 재탐색 점수: {score2:.2f}")
            inv_pos = screen.find_template(scene, inventory_tpl, threshold=0.70)

    if inv_pos is None:
        status_cb("⚠ 인벤토리를 찾지 못했습니다. 인벤토리 바 이미지를 다시 캡처하세요.")
        return False

    inv_abs = _abs(inv_pos, mon_all)
    status_cb(f"인벤토리 감지: {inv_abs}")

    # ── 3단계: 캐시탭 위치 = 인벤토리 감지 위치 + 저장된 오프셋 ─────
    if not cash_tab_offset:
        status_cb("⚠ 캐시탭 오프셋 미설정 — 설정2 탭에서 '캐시탭 위치' 지정 후 재시도하세요.")
        return False

    cash_tab_actual = (inv_abs[0] + cash_tab_offset[0], inv_abs[1] + cash_tab_offset[1])
    status_cb(f"캐시탭 위치: 인벤토리{inv_abs} + 오프셋{cash_tab_offset} = {cash_tab_actual}")

    # ── 4~5단계: 캐시탭 더블클릭 → 색상 변화로 활성화 확인 (최대 3회) ─
    MAX_CASH_RETRY = 3
    active_abs = None
    snap = _tab_color_changed(*cash_tab_actual)

    for attempt in range(MAX_CASH_RETRY):
        if stopped():
            return False
        before = snap()
        status_cb(f"캐시탭 더블클릭 (시도 {attempt + 1}/{MAX_CASH_RETRY}): {cash_tab_actual}")
        input_ctrl.double_click(*cash_tab_actual)
        time.sleep(0.2)

        after = snap()
        diff = _color_diff(before, after)
        status_cb(f"캐시탭 색상 변화량: {diff:.1f}")

        if diff >= 6.0:
            active_abs = cash_tab_actual
            status_cb(f"캐시탭 활성화 확인 ✔ (색상 변화 감지)")
            break
        if attempt < MAX_CASH_RETRY - 1:
            status_cb("캐시탭 색상 미변화 → 재시도 중...")
            time.sleep(0.15)
        else:
            status_cb("⚠ 캐시탭 활성화 최종 미확인 — 계속 진행")

    if stopped():
        return False

    # ── 6단계: 첫번째 슬롯 위치 = 기준 위치 + 저장된 오프셋 ──────────
    if not first_slot_offset:
        status_cb("⚠ 첫번째 슬롯 오프셋 미설정 — 설정2 탭에서 지정하세요.")
        return False

    if active_abs:
        # 활성 캐시탭 감지 위치 기준
        first_slot_actual = (active_abs[0] + first_slot_offset[0], active_abs[1] + first_slot_offset[1])
        status_cb(f"첫번째 슬롯: 활성캐시탭{active_abs} + 오프셋{first_slot_offset} = {first_slot_actual}")
    else:
        # fallback: 캐시탭 클릭 위치 기준
        first_slot_actual = (cash_tab_actual[0] + first_slot_offset[0], cash_tab_actual[1] + first_slot_offset[1])
        status_cb(f"첫번째 슬롯: 캐시탭{cash_tab_actual} + 오프셋{first_slot_offset} = {first_slot_actual}")

    # ── 7단계: 첫번째 슬롯 더블클릭 → 상점 열림 확인 (최대 2회 재시도) ─
    MAX_SLOT_RETRY = 2
    shop_confirmed = False

    for attempt in range(MAX_SLOT_RETRY):
        if stopped():
            return False
        status_cb(f"첫번째 슬롯 더블클릭 (시도 {attempt + 1}/{MAX_SLOT_RETRY}): {first_slot_actual}")
        input_ctrl.double_click(*first_slot_actual)
        time.sleep(random.uniform(0.6, 0.8))

        if not has_shop_open_tpl:
            shop_confirmed = True
            break

        deadline = time.time() + 2.0
        first_check = True
        while time.time() < deadline and not stopped():
            chk_scene, _ = _capture()
            if first_check:
                shop_score = screen.find_template_score(chk_scene, shop_open_tpl)
                status_cb(f"상점 열림 매칭 점수: {shop_score:.2f}")
                first_check = False
            if screen.find_template(chk_scene, shop_open_tpl, threshold=0.70):
                shop_confirmed = True
                break
            time.sleep(0.1)

        if shop_confirmed:
            status_cb("상점 열림 확인 ✔")
            break
        if attempt < MAX_SLOT_RETRY - 1:
            status_cb("상점 열림 미확인 → 재시도 중...")
        else:
            status_cb("⚠ 상점 열림 최종 미확인")

    return shop_confirmed or not has_shop_open_tpl


def _exit_shop(input_ctrl, shop_exit_btn, status_cb) -> None:
    """상점 나가기 버튼 클릭 또는 ESC 2회."""
    if shop_exit_btn:
        status_cb(f"상점 나가기 클릭: {shop_exit_btn}")
        input_ctrl.click(*shop_exit_btn)
        time.sleep(0.5)
    else:
        time.sleep(0.3)
        input_ctrl.press_key("esc")
        time.sleep(0.3)
        input_ctrl.press_key("esc")


def sell_junk(config, screen, input_ctrl, status_cb, stop_event=None) -> None:
    """잡템 자동 판매. stop_event가 set 되면 즉시 중단."""
    import mss as _mss
    import cv2 as _cv2
    import numpy as _np

    def stopped() -> bool:
        return stop_event is not None and stop_event.is_set()

    cfg = config.get("settings2", "junk_sell") or {}
    pt, region = _resolve_coords(config, cfg)  # 비율 우선, 없으면 절대 좌표 폴백

    shop_exit_btn      = pt("shop_exit_btn")
    junk_sell_enabled  = bool(cfg.get("junk_sell_enabled", False))
    etc_tab            = pt("shop_etc_tab")
    shop_area          = region("shop_area")
    scroll_pos         = pt("scroll_pos")

    equip_sell_tpl      = "templates/junk/equip_sell_btn.png"
    equip_confirm_tpl   = "templates/junk/equip_sell_confirm.png"
    scroll_bottom_tpl   = "templates/junk/scroll_bottom.png"
    has_equip_sell_tpl  = os.path.exists(equip_sell_tpl)
    has_equip_conf_tpl  = os.path.exists(equip_confirm_tpl)
    has_scroll_bot_tpl  = os.path.exists(scroll_bottom_tpl)

    _system_tpls = {
        "cash_tab.png", "cash_tab_active.png", "inventory.png", "shop_open.png",
        "equip_sell_btn.png", "equip_sell_confirm.png",
        "etc_tab_active.png", "scroll_bottom.png",
    }
    item_templates = sorted(
        f for f in glob.glob("templates/junk/*.png")
        if os.path.basename(f) not in _system_tpls
    )

    has_templates  = bool(item_templates)
    has_equip_sell = has_equip_sell_tpl

    if not has_templates and not has_equip_sell:
        status_cb("잡템 판매 — 판매 템플릿도 장비 일괄 판매 템플릿도 미설정입니다.")
        return

    status_cb("잡템 판매 시작...")

    def _capture():
        with _mss.mss() as sct:
            mon = sct.monitors[0]
            raw = sct.grab(mon)
            img = _cv2.cvtColor(_np.array(raw), _cv2.COLOR_BGRA2BGR)
        return img, mon

    # ── 1. 상점 열기 ─────────────────────────────────────────────────
    if not open_shop(config, screen, input_ctrl, status_cb, stop_event):
        return
    if stopped():
        return

    # ── 2. 장비 일괄 판매 (템플릿 인식 → 더블클릭) ───────────────────
    if has_equip_sell_tpl:
        scene, mon = _capture()
        eq_score = screen.find_template_score(scene, equip_sell_tpl)
        status_cb(f"장비 일괄 판매 버튼 매칭 점수: {eq_score:.2f}")
        eq_pos = screen.find_template(scene, equip_sell_tpl, threshold=0.70)
        if eq_pos:
            abs_x = mon["left"] + eq_pos[0]
            abs_y = mon["top"]  + eq_pos[1]
            status_cb(f"장비 일괄 판매 버튼 감지 → 더블클릭: ({abs_x}, {abs_y})")
            input_ctrl.double_click(abs_x, abs_y)
            time.sleep(0.3)
            if stopped():
                return

            # 확인창 감지 → 더블클릭, 미감지 시 Enter
            confirmed = False
            if has_equip_conf_tpl:
                deadline = time.time() + 2.5
                first_check = True
                while time.time() < deadline and not stopped():
                    chk, chk_mon = _capture()
                    if first_check:
                        sc = screen.find_template_score(chk, equip_confirm_tpl)
                        status_cb(f"확인창 매칭 점수: {sc:.2f}")
                        first_check = False
                    conf_pos = screen.find_template(chk, equip_confirm_tpl, threshold=0.70)
                    if conf_pos:
                        cx = chk_mon["left"] + conf_pos[0]
                        cy = chk_mon["top"]  + conf_pos[1]
                        status_cb(f"확인창 감지 → 더블클릭: ({cx}, {cy})")
                        input_ctrl.double_click(cx, cy)
                        confirmed = True
                        break
                    time.sleep(0.15)
            if not confirmed:
                status_cb("확인창 미감지 → Enter 키")
                input_ctrl.press_key("enter")
            time.sleep(0.2)
        else:
            status_cb("⚠ 장비 일괄 판매 버튼 미감지 — 건너뜀")
        if stopped():
            return

    # ── 3. 기타템 판매 여부 ──────────────────────────────────────────
    if not junk_sell_enabled or not has_templates:
        reason = "기타템 판매 미활성" if not junk_sell_enabled else "아이템 템플릿 없음"
        status_cb(f"판매 완료 ({reason})")
        _exit_shop(input_ctrl, shop_exit_btn, status_cb)
        return

    # ── 4. 기타탭 더블클릭 → 활성화 확인 ────────────────────────────
    if etc_tab:
        status_cb(f"기타탭 더블클릭: {etc_tab}")
        input_ctrl.double_click(*etc_tab)

        etc_snap = _tab_color_changed(*etc_tab)
        before_etc = etc_snap()
        time.sleep(0.2)
        after_etc = etc_snap()
        diff_etc = _color_diff(before_etc, after_etc)
        status_cb(f"기타탭 색상 변화량: {diff_etc:.1f}")
        if diff_etc >= 6.0:
            status_cb("기타탭 활성화 확인 ✔ (색상 변화 감지)")
        else:
            status_cb("⚠ 기타탭 활성화 미확인 — 계속 진행")

    if stopped():
        return

    # ── 5. 아이템 판매 루프 ──────────────────────────────────────────
    # 기타탭 진입 시 스크롤은 항상 최상단에서 시작
    # 흐름: 현재 화면 판매 → 스크롤 다운 → 최하단 확인 → 반복
    total_sold      = 0
    no_match_streak = 0
    MAX_STREAK      = 5   # scroll_bottom 템플릿 없을 때 폴백

    while not stopped():
        # ① 현재 화면에서 아이템 판매
        sold_this = 0
        if shop_area:
            for tpl_path in item_templates:
                if stopped():
                    break
                for _ in range(20):
                    if stopped():
                        break
                    scene = screen.capture(shop_area)
                    pos   = screen.find_template(scene, tpl_path, threshold=0.75)
                    if pos is None:
                        break
                    abs_x = shop_area["left"] + pos[0]
                    abs_y = shop_area["top"]  + pos[1]
                    input_ctrl.double_click(abs_x, abs_y)
                    time.sleep(random.uniform(0.3, 0.5))
                    input_ctrl.press_key("enter")
                    time.sleep(random.uniform(0.3, 0.5))
                    sold_this  += 1
                    total_sold += 1
                    status_cb(f"잡템 판매 → {total_sold}개 판매됨")
                    time.sleep(random.uniform(0.2, 0.3))

        if stopped():
            break

        # ② 스크롤 최하단 템플릿 먼저 확인 (스크롤 전)
        if has_scroll_bot_tpl:
            chk, _ = _capture()
            if screen.find_template(chk, scroll_bottom_tpl, threshold=0.70):
                status_cb("스크롤 최하단 도달 — 판매 종료")
                break

        # ③ 스크롤 다운
        if scroll_pos:
            input_ctrl.scroll(*scroll_pos, clicks=-3)
            time.sleep(0.15)
        else:
            # 스크롤 위치 미설정 — 폴백 종료
            no_match_streak += 1
            if no_match_streak >= MAX_STREAK:
                status_cb(f"{MAX_STREAK}회 연속 미탐지 — 상점 나가기")
                break
            continue

        # ④ 스크롤 후 최하단 재확인
        if has_scroll_bot_tpl:
            chk, _ = _capture()
            if screen.find_template(chk, scroll_bottom_tpl, threshold=0.70):
                # 마지막 화면 한 번 더 판매
                if shop_area:
                    for tpl_path in item_templates:
                        if stopped():
                            break
                        for _ in range(20):
                            if stopped():
                                break
                            scene = screen.capture(shop_area)
                            pos   = screen.find_template(scene, tpl_path, threshold=0.75)
                            if pos is None:
                                break
                            abs_x = shop_area["left"] + pos[0]
                            abs_y = shop_area["top"]  + pos[1]
                            input_ctrl.double_click(abs_x, abs_y)
                            time.sleep(random.uniform(0.3, 0.5))
                            input_ctrl.press_key("enter")
                            time.sleep(random.uniform(0.3, 0.5))
                            total_sold += 1
                            status_cb(f"잡템 판매 → {total_sold}개 판매됨")
                            time.sleep(random.uniform(0.2, 0.3))
                status_cb("스크롤 최하단 도달 — 판매 종료")
                break
        else:
            # 폴백: 연속 미탐지 카운터
            if sold_this == 0:
                no_match_streak += 1
                if no_match_streak >= MAX_STREAK:
                    status_cb(f"{MAX_STREAK}회 연속 미탐지 — 상점 나가기")
                    break
            else:
                no_match_streak = 0

    status_cb(f"기타템 판매 완료 — 총 {total_sold}개 판매됨")

    # ── 7. 상점 나가기 ───────────────────────────────────────────────
    _exit_shop(input_ctrl, shop_exit_btn, status_cb)
