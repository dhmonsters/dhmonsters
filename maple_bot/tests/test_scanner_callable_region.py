# 스캐너가 callable region을 매 스캔 호출해 해석하는지 검증
import numpy as np
from core.sensing.char_scanner import CharScanner


def test_callable_region_is_invoked_each_scan():
    seen = []
    def region_fn():
        r = {"left": 1, "top": 2, "width": 3, "height": 4}
        seen.append(r)
        return r
    def cap(region):
        assert region == {"left": 1, "top": 2, "width": 3, "height": 4}
        return np.zeros((4, 3, 3), np.uint8)
    sc = CharScanner(cap, region_fn)
    sc.scan_once()
    sc.scan_once()
    assert len(seen) == 2


def test_dict_region_still_works():
    def cap(region):
        assert region == {"left": 5, "top": 6, "width": 7, "height": 8}
        return None
    sc = CharScanner(cap, {"left": 5, "top": 6, "width": 7, "height": 8})
    sc.scan_once()
