# 닉네임 템플릿을 사냥영역에서 매칭해 캐릭터 기준점(anchor)을 추적 — 캐릭이 이동해도 따라감
from __future__ import annotations

import numpy as np

from core.sensing import monster_vision


class NameTracker:
    """캐릭터 닉네임 템플릿을 화면(사냥영역)에서 찾아 중심 좌표를 반환한다.

    내 닉네임은 항상 같은 글자라 템플릿 매칭으로 위치를 잡는다(내용을 읽지 않음).
    캐릭터가 사냥영역 안에서 랜덤 이동해도, 매 프레임 사냥영역을 훑어 닉네임 위치를
    찾으므로 그 위치가 곧 캐릭터 기준점이 된다(공격박스·투영 등에 사용)."""

    def __init__(self, template: np.ndarray | None, threshold: float = 0.7):
        self._tpl = template
        self._thr = threshold
        self._last: tuple[int, int] | None = None

    def find(self, scene: np.ndarray | None) -> tuple[int, int] | None:
        """scene(사냥영역 캡처)에서 닉네임 중심 좌표. 못 찾으면 None(마지막 위치는 유지)."""
        if self._tpl is None or scene is None:
            return None
        pos = monster_vision.find_template_pos(scene, self._tpl, threshold=self._thr)
        if pos is not None:
            self._last = pos
        return pos

    @property
    def last(self) -> tuple[int, int] | None:
        """마지막으로 찾은 닉네임 위치(없으면 None)."""
        return self._last

    def set_threshold(self, t: float) -> None:
        self._thr = t
