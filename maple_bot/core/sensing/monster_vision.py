# 몬스터 감지(OpenCV) — B 메커니즘: 닉네임 위치 → atk 오프셋 박스 → 박스 안 몬스터 매칭
# A detector.py(cv2.matchTemplate TM_CCOEFF_NORMED) 로직 베이스 + B 다중템플릿(monster1~9)
from __future__ import annotations

import os

import cv2
import numpy as np


def load_template(path: str) -> np.ndarray | None:
    """한글 경로 대응 템플릿 로드 (A 방식: fromfile+imdecode)."""
    if not os.path.exists(path):
        return None
    buf = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def find_template_pos(scene: np.ndarray, template: np.ndarray,
                      threshold: float = 0.7) -> tuple[int, int] | None:
    """scene에서 template 최고 매칭 위치의 중심좌표. 임계 미달이면 None (닉네임 찾기용)."""
    if template is None or template.size == 0:
        return None
    if template.shape[0] > scene.shape[0] or template.shape[1] > scene.shape[1]:
        return None
    res = cv2.matchTemplate(scene, template, cv2.TM_CCOEFF_NORMED)
    _, mx, _, loc = cv2.minMaxLoc(res)
    if mx < threshold:
        return None
    th, tw = template.shape[:2]
    return (int(loc[0] + tw // 2), int(loc[1] + th // 2))


def attack_box(name_pos: tuple[int, int],
               x_min: int, x_max: int, y_min: int, y_max: int) -> tuple:
    """닉네임 위치 기준 공격 박스 (B atk_x/y_min/max 오프셋). → (left, top, w, h)."""
    cx, cy = name_pos
    left = cx + x_min
    top = cy + y_min
    return (left, top, x_max - x_min, y_max - y_min)


def monsters_in_box(scene: np.ndarray, templates: dict[str, np.ndarray],
                    box: tuple, threshold: float = 0.9) -> int:
    """공격 박스 영역만 잘라, 다중 몬스터 템플릿 중 임계 이상 매칭 개수 반환.

    B 방식: 박스 안에서만 monster1~9 매칭 → 전체화면 대비 빠름.
    """
    bx, by, bw, bh = box
    h, w = scene.shape[:2]
    # 박스를 화면 안으로 클램프
    x1 = max(0, bx); y1 = max(0, by)
    x2 = min(w, bx + bw); y2 = min(h, by + bh)
    if x2 <= x1 or y2 <= y1:
        return 0
    roi = scene[y1:y2, x1:x2]

    count = 0
    for tpl in templates.values():
        if tpl is None or tpl.size == 0:
            continue
        if tpl.shape[0] > roi.shape[0] or tpl.shape[1] > roi.shape[1]:
            continue
        res = cv2.matchTemplate(roi, tpl, cv2.TM_CCOEFF_NORMED)
        _, mx, _, _ = cv2.minMaxLoc(res)
        if mx >= threshold:
            count += 1
    return count


def monster_boxes_in_box(scene: np.ndarray, templates: dict[str, np.ndarray],
                         box: tuple, threshold: float = 0.9) -> list[tuple]:
    """박스 안 몬스터들의 원본좌표 박스 [(x,y,w,h), ...] 반환 (오버레이 표시용).
    같은 위치 중복은 간단 거리필터로 제거."""
    bx, by, bw, bh = box
    h, w = scene.shape[:2]
    x1 = max(0, bx); y1 = max(0, by)
    x2 = min(w, bx + bw); y2 = min(h, by + bh)
    if x2 <= x1 or y2 <= y1:
        return []
    roi = scene[y1:y2, x1:x2]

    found: list[tuple] = []
    for tpl in templates.values():
        if tpl is None or tpl.size == 0:
            continue
        th, tw = tpl.shape[:2]
        if th > roi.shape[0] or tw > roi.shape[1]:
            continue
        res = cv2.matchTemplate(roi, tpl, cv2.TM_CCOEFF_NORMED)
        local_max = cv2.dilate(res, np.ones((3, 3), dtype=np.uint8))
        ys, xs = np.where((res >= threshold) & (res >= local_max))
        if len(xs) > 200:
            scores = res[ys, xs]
            keep = np.argpartition(scores, -200)[-200:]
            keep = keep[np.argsort(scores[keep])[::-1]]
            ys, xs = ys[keep], xs[keep]
        for ry, rx in zip(ys, xs):
            ox, oy = x1 + int(rx), y1 + int(ry)   # 원본좌표
            # 근접 중복 제거 (이미 가까운 박스 있으면 skip)
            if any(abs(ox - fx) < tw // 2 and abs(oy - fy) < th // 2
                   for fx, fy, _, _ in found):
                continue
            found.append((ox, oy, tw, th))
            if len(found) >= 100:
                return found
    return found
