# JunkSeller — A core/junk_seller.sell_junk 래핑 + B 보호목록(화이트리스트). 신구조 Acting 모듈
from __future__ import annotations

from core.junk_seller import sell_junk   # A 기존 판매 로직 재사용(템플릿 인벤→상점)


class JunkSeller:
    """잡템 자동판매. 실판매는 검증된 A sell_junk 에 위임하고,
    B 방식 보호목록(화이트리스트)으로 특정 아이템 판매를 막는다.

    protect_items: 명시 리스트 우선, 없으면 config settings2.junk_sell.protect_items.
    """

    def __init__(self, config, screen, input_ctrl,
                 status_cb=None, stop_event=None, protect_items=None):
        self._config = config
        self._screen = screen
        self._input = input_ctrl
        self._status = status_cb or (lambda m: None)
        self._stop_event = stop_event
        if protect_items is not None:
            self._protect = list(protect_items)
        else:
            self._protect = self._load_protect()

    def _load_protect(self) -> list[str]:
        if self._config is None:
            return []
        items = self._config.get("settings2", "junk_sell", "protect_items", default=[])
        return list(items) if items else []

    def is_protected(self, item_name: str) -> bool:
        """아이템명이 보호목록에 (부분)매칭되면 판매 제외."""
        return any(p and p in item_name for p in self._protect)

    def sell(self) -> None:
        """잡템 판매 실행 — A sell_junk 위임 (보호목록은 향후 슬롯별 판매에 적용).

        주의: A sell_junk 는 '기타탭 일괄판매'라 아이템명 단위 필터가 없다.
        보호목록은 슬롯 단위 판매로 확장될 때 is_protected 로 거른다(실기 확장 지점).
        """
        sell_junk(self._config, self._screen, self._input, self._status, self._stop_event)
