# tests/test_window_region.py
# 창 원점 캐시 조회 + 상대→절대 영역 해석 검증
import core.config_manager as cm


def _reset():
    cm._origin_cache.update(title=None, ts=0.0, rect=(0, 0, 0, 0))


def test_resolve_absolute_passthrough(monkeypatch):
    _reset()
    monkeypatch.setattr(cm, "_query_window_origin", lambda t: (100, 50, 800, 600))
    assert cm.resolve_window_region("absolute", "X", 13, 136, 256, 104) == (13, 136, 256, 104)


def test_resolve_relative_adds_origin(monkeypatch):
    _reset()
    monkeypatch.setattr(cm, "_query_window_origin", lambda t: (100, 50, 800, 600))
    assert cm.resolve_window_region("relative", "X", 13, 136, 256, 104) == (113, 186, 256, 104)


def test_resolve_relative_no_window_falls_back(monkeypatch):
    _reset()
    monkeypatch.setattr(cm, "_query_window_origin", lambda t: (0, 0, 0, 0))
    assert cm.resolve_window_region("relative", "X", 13, 136, 256, 104) == (13, 136, 256, 104)


def test_cached_within_ttl_queries_once(monkeypatch):
    _reset()
    calls = {"n": 0}
    def q(t):
        calls["n"] += 1
        return (10, 20, 800, 600)
    monkeypatch.setattr(cm, "_query_window_origin", q)
    clock = {"t": 1000.0}
    now = lambda: clock["t"]
    cm.cached_window_origin("X", ttl=0.2, _now=now)
    cm.cached_window_origin("X", ttl=0.2, _now=now)
    assert calls["n"] == 1
    clock["t"] += 0.5
    cm.cached_window_origin("X", ttl=0.2, _now=now)
    assert calls["n"] == 2
