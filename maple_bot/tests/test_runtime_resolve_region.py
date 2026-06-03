# 런타임 _resolve_region이 coord_mode/창제목으로 영역을 해석하는지 검증
from core import runtime as rt_mod


def _rt(coord_mode, title, anchor=None):
    rt = rt_mod.BotRuntime.__new__(rt_mod.BotRuntime)
    class _Cfg:
        pass
    rt._cfg = _Cfg()
    rt._cfg.coord_mode = coord_mode
    rt._cfg.game_window_title = title
    rt._cfg.coord_anchor = anchor
    return rt


def test_resolve_none_is_none():
    rt = _rt("relative", "X")
    assert rt._resolve_region(None) is None


def test_resolve_absolute_passthrough(monkeypatch):
    import core.config_manager as cm
    cm._origin_cache.update(title=None, ts=0.0, rect=(0, 0, 0, 0))
    monkeypatch.setattr(cm, "_query_window_origin", lambda t: (100, 50, 800, 600))
    rt = _rt("absolute", "X")
    assert rt._resolve_region({"left": 13, "top": 136, "width": 256, "height": 104}) == \
        {"left": 13, "top": 136, "width": 256, "height": 104}


def test_resolve_relative_tracks_window_move(monkeypatch):
    import core.config_manager as cm
    cm._origin_cache.update(title=None, ts=0.0, rect=(0, 0, 0, 0))
    monkeypatch.setattr(cm, "_query_window_origin", lambda t: (100, 50, 800, 600))
    # 앵커(0,0) → 현재(100,50) 이동 → +100,+50 보정
    rt = _rt("relative", "X", anchor=[0, 0])
    assert rt._resolve_region({"left": 13, "top": 136, "width": 256, "height": 104}) == \
        {"left": 113, "top": 186, "width": 256, "height": 104}


def test_resolve_relative_no_anchor_no_shift(monkeypatch):
    import core.config_manager as cm
    cm._origin_cache.update(title=None, ts=0.0, rect=(0, 0, 0, 0))
    monkeypatch.setattr(cm, "_query_window_origin", lambda t: (100, 50, 800, 600))
    rt = _rt("relative", "X", anchor=None)   # 앵커 없음 → 절대 그대로
    assert rt._resolve_region({"left": 13, "top": 136, "width": 256, "height": 104}) == \
        {"left": 13, "top": 136, "width": 256, "height": 104}
