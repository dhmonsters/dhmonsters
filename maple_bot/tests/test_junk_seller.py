# JunkSeller — A sell_junk 래핑 + B 보호목록(화이트리스트). 위임/필터 로직 검증(게임불필요)
import pytest
from core.acting.junk_seller import JunkSeller


class FakeConfig:
    def __init__(self, data): self._d = data
    def get(self, *keys, default=None):
        node = self._d
        for k in keys:
            if not isinstance(node, dict) or k not in node: return default
            node = node[k]
        return node


def test_protect_list_filters():
    """보호목록에 있는 아이템은 판매 제외."""
    js = JunkSeller(config=None, screen=None, input_ctrl=None,
                    protect_items=["순백의 주문서", "파워 엘릭서"])
    assert js.is_protected("순백의 주문서") is True
    assert js.is_protected("파워 엘릭서") is True
    assert js.is_protected("쓸모없는 잡템") is False


def test_protect_list_partial_match():
    """부분 문자열 매칭(아이템명 일부만 등록해도 보호)."""
    js = JunkSeller(config=None, screen=None, input_ctrl=None,
                    protect_items=["주문서"])
    assert js.is_protected("순백의 주문서") is True   # '주문서' 포함
    assert js.is_protected("10% 공격력 주문서") is True


def test_empty_protect_list():
    js = JunkSeller(config=None, screen=None, input_ctrl=None, protect_items=[])
    assert js.is_protected("아무거나") is False


def test_protect_from_config():
    """config의 보호목록 키에서 로드."""
    cfg = FakeConfig({"settings2": {"junk_sell": {"protect_items": ["메소", "쿠폰"]}}})
    js = JunkSeller(config=cfg, screen=None, input_ctrl=None)
    assert js.is_protected("이벤트 쿠폰") is True
    assert js.is_protected("메소 주머니") is True
    assert js.is_protected("잡템") is False


def test_sell_delegates_to_sell_junk(monkeypatch):
    """sell()은 기존 A sell_junk 에 위임한다."""
    called = {}
    def fake_sell_junk(config, screen, input_ctrl, status_cb, stop_event=None):
        called["yes"] = True
        status_cb("판매 시작")
    monkeypatch.setattr("core.acting.junk_seller.sell_junk", fake_sell_junk)
    logs = []
    js = JunkSeller(config=None, screen=None, input_ctrl=None, status_cb=logs.append)
    js.sell()
    assert called.get("yes") is True
    assert "판매 시작" in logs
