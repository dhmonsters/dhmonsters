# 캐릭터 기준 사냥 영역에서 템플릿을 찾고 쿨다운에 따라 액션을 실행하는 트리거
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

import cv2
import numpy as np

from core.navigation.world_map import ActionSpec


@dataclass(frozen=True)
class ImageTriggerSpec:
    template_path: str
    threshold: float
    check_interval_sec: float
    cooldown_sec: float
    action: ActionSpec

    def __post_init__(self) -> None:
        if not self.template_path.strip():
            raise ValueError("template_path는 비어 있을 수 없습니다")
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError("threshold는 0과 1 사이여야 합니다")
        if min(self.check_interval_sec, self.cooldown_sec) < 0:
            raise ValueError("감지 주기와 쿨다운은 음수일 수 없습니다")


@dataclass(frozen=True)
class ImageTriggerResult:
    checked: bool
    matched: bool
    executed: bool
    score: float
    location: tuple[int, int] | None


def _load_template(path: str):
    template = cv2.imread(path, cv2.IMREAD_COLOR)
    if template is None:
        raise ValueError(f"템플릿 이미지를 읽을 수 없습니다: {path}")
    return template


def _match_template(search: np.ndarray, template: np.ndarray):
    if search.shape[0] < template.shape[0] or search.shape[1] < template.shape[1]:
        return 0.0, (0, 0)
    scores = cv2.matchTemplate(search, template, cv2.TM_CCOEFF_NORMED)
    _, score, _, location = cv2.minMaxLoc(scores)
    return float(score), (int(location[0]), int(location[1]))


class ImageTrigger:
    def __init__(
        self,
        action_executor,
        template_loader: Callable = _load_template,
        match_fn: Callable = _match_template,
        clock_fn: Callable = time.monotonic,
    ):
        self._actions = action_executor
        self._load = template_loader
        self._match = match_fn
        self._clock = clock_fn
        self._templates = {}
        self._last_check = {}
        self._last_action = {}

    def check(self, frame_bgr, region, spec: ImageTriggerSpec) -> ImageTriggerResult:
        now = self._clock()
        last_check = self._last_check.get(spec.template_path)
        if last_check is not None and now - last_check < spec.check_interval_sec:
            return ImageTriggerResult(False, False, False, 0.0, None)
        self._last_check[spec.template_path] = now

        left, top, width, height = (int(value) for value in region)
        right = min(frame_bgr.shape[1], left + width)
        bottom = min(frame_bgr.shape[0], top + height)
        left = max(0, left)
        top = max(0, top)
        if right <= left or bottom <= top:
            raise ValueError("사냥 영역의 크기가 올바르지 않습니다")
        search = frame_bgr[top:bottom, left:right]
        template = self._templates.get(spec.template_path)
        if template is None:
            template = self._load(spec.template_path)
            self._templates[spec.template_path] = template
        score, local_location = self._match(search, template)
        matched = score >= spec.threshold
        location = (
            (left + local_location[0], top + local_location[1])
            if matched
            else None
        )
        executed = False
        last_action = self._last_action.get(spec.template_path)
        if matched and (
            last_action is None or now - last_action >= spec.cooldown_sec
        ):
            self._actions.execute(spec.action)
            self._last_action[spec.template_path] = now
            executed = True
        return ImageTriggerResult(True, matched, executed, score, location)
