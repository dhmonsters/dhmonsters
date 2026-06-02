# 미니맵↔캔버스 좌표 변환 + 화면px→미니맵px 범위 환산 + 캐릭터 추적 상태 (순수 함수)
from __future__ import annotations


def minimap_to_canvas(cx: int, cy: int, zoom: float,
                      pan: tuple[int, int] = (0, 0)) -> tuple[int, int]:
    """미니맵 픽셀(cx,cy)을 줌·팬 적용한 캔버스 픽셀로 변환."""
    return (round(cx * zoom + pan[0]), round(cy * zoom + pan[1]))


def screen_px_to_minimap_px(screen_px: float, minimap_w: int,
                            screen_w: int, camera_w_ratio: float) -> float:
    """게임 화면에서의 픽셀 거리를 미니맵 이미지에서의 픽셀 거리로 환산한다.

    공격/사냥 범위는 게임 화면(메인 뷰) 기준 픽셀로 설정돼 있지만, 캔버스는 미니맵
    이미지를 그리므로 같은 물리 거리를 미니맵 축척으로 바꿔야 노란 점 주변에 올바른
    크기로 그려진다. 미니맵 폭 중 카메라가 실제로 비추는 가시 폭이
    camera_w_ratio*minimap_w 이고, 그 가시 폭이 게임 화면 폭(screen_w)에 대응하므로
    `screen_px : screen_w = ? : camera_w_ratio*minimap_w` 비례로 환산한다.

    Args:
        screen_px: 게임 화면에서의 픽셀 거리(예: 공격박스 반폭 atk_x_max).
        minimap_w: 현재 캡처된 미니맵 이미지의 폭(px).
        screen_w: 캡처한 전체 화면(주 모니터)의 폭(px).
        camera_w_ratio: 게임 화면 폭 대비 미니맵에 보이는 카메라 가시 영역의 비율
            (기본 0.5 — config attack.camera_w_ratio).

    Returns:
        미니맵 이미지 기준 픽셀 거리(float). screen_w<=0이면 0.0(0 나눗셈 방어).
    """
    if screen_w <= 0:
        return 0.0
    return screen_px * (camera_w_ratio * minimap_w) / screen_w


def char_track_state(elapsed_sec: float,
                     lost_after: float = 1.0,
                     stale_after: float = 3.0) -> str:
    """마지막 캐릭터 검출 이후 경과시간(초)으로 추적 상태를 판정한다.

    UI가 '상황 인지'를 주도록: 정상 추적/일시적 끊김/오래 끊김을 구분한다.

    Args:
        elapsed_sec: 마지막 성공 검출 이후 흐른 시간(초).
        lost_after: 이 시간(초) 이상 미검출이면 'lost'(점 깜빡임).
        stale_after: 이 시간(초) 이상 미검출이면 'stale'(점 숨김 + 배지).

    Returns:
        "tracking" | "lost" | "stale".
    """
    if elapsed_sec < lost_after:
        return "tracking"
    if elapsed_sec < stale_after:
        return "lost"
    return "stale"


# 블록 타입 색 (단일 출처, Discord Night 네온) — 캔버스가 참조
BLOCK_COLORS = {
    "move": "#3ada85", "attack": "#ff6b81", "ladder": "#e3b341",
    "jump": "#5ab0e3", "teleport": "#b06bff",
}


def canvas_to_minimap(px: float, py: float, zoom: float,
                      pan: tuple[int, int] = (0, 0)) -> tuple[int, int]:
    """캔버스 픽셀 → 미니맵 픽셀 (minimap_to_canvas의 역변환). zoom=0이면 (0,0)."""
    if zoom == 0:
        return (0, 0)
    return (round((px - pan[0]) / zoom), round((py - pan[1]) / zoom))


def block_color(block: dict) -> str:
    """블록 표시색. move + move_type=teleport면 텔포색, 그 외 타입색."""
    t = block.get("type", "move")
    if t == "move" and block.get("move_type") == "teleport":
        return BLOCK_COLORS["teleport"]
    return BLOCK_COLORS.get(t, "#888888")


def block_anchor(block: dict) -> tuple[int, int] | None:
    """블록의 캔버스 앵커(미니맵 픽셀). ladder는 (ladder_x,y_bot), 그 외는 (pos_x,pos_y).
    미배치(ladder 좌표 0이거나 pos<0)면 None."""
    if block.get("type") == "ladder":
        lx, yb = int(block.get("ladder_x", 0)), int(block.get("y_bot", 0))
        if lx <= 0 and yb <= 0:
            return None
        return (lx, yb)
    px, py = int(block.get("pos_x", -1)), int(block.get("pos_y", -1))
    if px < 0 or py < 0:
        return None
    return (px, py)


def hit_test(blocks: list[dict], mx: int, my: int, radius: int = 10) -> int | None:
    """(mx,my)에서 radius 내 가장 가까운 블록 인덱스. 미배치(anchor None)는 제외, 없으면 None."""
    best_i, best_d = None, None
    for i, b in enumerate(blocks):
        a = block_anchor(b)
        if a is None:
            continue
        d = (a[0] - mx) ** 2 + (a[1] - my) ** 2
        if d <= radius * radius and (best_d is None or d < best_d):
            best_i, best_d = i, d
    return best_i


def seed_block_at(block_type: str, mx: int, my: int) -> dict:
    """클릭 좌표에 놓을 새 블록 dict. block_editor._DEFAULTS 재사용(지연 임포트).
    'teleport'는 move + move_type=teleport. 타입필드도 좌표로 시드."""
    from core_ui.block_editor import _DEFAULTS
    base = "move" if block_type == "teleport" else block_type
    blk = dict(_DEFAULTS[base])
    blk["pos_x"], blk["pos_y"] = mx, my
    if base == "move":
        blk["start_x"] = blk["end_x"] = mx
        if block_type == "teleport":
            blk["move_type"] = "teleport"
    elif base == "ladder":
        blk["ladder_x"] = mx
        blk["y_bot"] = my
    return blk


def translate_block(block: dict, dx: int, dy: int) -> dict:
    """블록을 (dx,dy)만큼 평행이동한 새 dict. 캔버스가 블록 내부필드를 몰라도 되게 한다.
    배치된 pos_x/y는 이동, move면 start_x/end_x, ladder면 ladder_x/y_top/y_bot도 함께."""
    b = dict(block)
    if int(b.get("pos_x", -1)) >= 0:
        b["pos_x"] = int(b["pos_x"]) + dx
    if int(b.get("pos_y", -1)) >= 0:
        b["pos_y"] = int(b["pos_y"]) + dy
    t = b.get("type")
    if t == "move":
        b["start_x"] = int(b.get("start_x", 0)) + dx
        b["end_x"] = int(b.get("end_x", 0)) + dx
    elif t == "ladder":
        b["ladder_x"] = int(b.get("ladder_x", 0)) + dx
        b["y_top"] = int(b.get("y_top", 0)) + dy
        b["y_bot"] = int(b.get("y_bot", 0)) + dy
    return b


def autoplace_unplaced(route: list[dict], mm_w: int, mm_h: int) -> int:
    """캔버스에 안 그려지는 미배치 블록(anchor None)에 좌상단 staging 좌표를 부여한다.
    리스트로만 만든 블록을 캔버스로 끌어와 맵핑할 수 있게 한다. 변경한 개수 반환.
    mm_w<=0(미니맵 미설정)이면 0(배치 불가)."""
    if mm_w <= 0:
        return 0
    cols = max(1, (mm_w - 16) // 22)
    changed = 0
    k = 0
    for b in route:
        if block_anchor(b) is not None:
            continue
        sx = 10 + (k % cols) * 22
        sy = 10 + (k // cols) * 18
        if b.get("type") == "ladder":
            b["ladder_x"] = sx
            b["y_bot"] = sy
            if int(b.get("y_top", 0)) <= 0:
                b["y_top"] = max(0, sy - 20)
        else:
            b["pos_x"] = sx
            b["pos_y"] = sy
        k += 1
        changed += 1
    return changed
