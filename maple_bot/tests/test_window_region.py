# tests/test_window_region.py
# 창 원점 캐시 조회 + 상대→절대 영역 해석 검증
import core.config_manager as cm


def _reset():
    cm._origin_cache.update(title=None, ts=0.0, rect=(0, 0, 0, 0))


def test_resolve_absolute_passthrough(monkeypatch):
    _reset()
    monkeypatch.setattr(cm, "_query_window_origin", lambda t: (100, 50, 800, 600))
    assert cm.resolve_window_region("absolute", "X", 13, 136, 256, 104,
                                    anchor=(0, 0)) == (13, 136, 256, 104)


def test_resolve_relative_no_anchor_passthrough(monkeypatch):
    _reset()
    monkeypatch.setattr(cm, "_query_window_origin", lambda t: (100, 50, 800, 600))
    # 앵커 없으면 절대 그대로(안 밀림)
    assert cm.resolve_window_region("relative", "X", 13, 136, 256, 104) == (13, 136, 256, 104)


def test_resolve_relative_same_origin_no_shift(monkeypatch):
    _reset()
    monkeypatch.setattr(cm, "_query_window_origin", lambda t: (100, 50, 800, 600))
    # 현재 원점==앵커 → delta 0 → 절대 그대로(재시작해도 안 밀림)
    assert cm.resolve_window_region("relative", "X", 13, 136, 256, 104,
                                    anchor=(100, 50)) == (13, 136, 256, 104)


def test_resolve_relative_window_moved_tracks_delta(monkeypatch):
    _reset()
    monkeypatch.setattr(cm, "_query_window_origin", lambda t: (130, 70, 800, 600))
    # 창이 앵커(100,50)→(130,70) 이동 → +30,+20만큼 따라감
    assert cm.resolve_window_region("relative", "X", 13, 136, 256, 104,
                                    anchor=(100, 50)) == (43, 156, 256, 104)


def test_resolve_relative_no_window_falls_back(monkeypatch):
    _reset()
    monkeypatch.setattr(cm, "_query_window_origin", lambda t: (0, 0, 0, 0))
    assert cm.resolve_window_region("relative", "X", 13, 136, 256, 104,
                                    anchor=(100, 50)) == (13, 136, 256, 104)


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
