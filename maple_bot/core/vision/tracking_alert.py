# 추적 중 알림을 울릴 조건을 한 곳에서 판단합니다.
from __future__ import annotations


def should_emit_tracking_alert(
    auto_enabled: bool,
    tracking: bool,
    frame_index: int,
    interval: int = 30,
) -> bool:
    if interval <= 0:
        return False
    return bool(auto_enabled and tracking and frame_index % interval == 0)

