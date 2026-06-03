# 사다리 못 잡으면 재접근·재점프 재시도(A/B/C) — 2번째 점프에 잡혀 등반 완료 검증
from core.navigation.block import Block
from core.navigation.block_runner import BlockRunner


def test_ladder_retries_until_grabbed():
    st = {"jumps": 0, "x": 40, "y": 200, "up": False, "dir": None}

    class H:
        def perform(self, intent):
            if intent.key == "alt":      # 점프키
                st["jumps"] += 1
        def hold_dir(self, key, risk_profile=None): st["dir"] = key
        def release_dir(self): st["dir"] = None
        def held_dir(self): return st["dir"]
        def hold(self, key):
            if key == "up": st["up"] = True
        def release(self, key):
            if key == "up": st["up"] = False
        def release_all(self): st["dir"] = None; st["up"] = False
        def jitter_sec(self, base, spread=None): return base
        def random_side(self): return "left"

    def pos():
        if st["dir"] == "right": st["x"] += 8
        elif st["dir"] == "left": st["x"] -= 8
        # 2번째 점프부터만 로프를 잡아 등반(첫 점프는 미끄러짐 → 재시도 유도)
        if st["up"] and st["jumps"] >= 2:
            st["y"] = max(0, st["y"] - 8)
        return (st["x"], st["y"])

    r = BlockRunner(humanizer=H(), pos_fn=pos, sleep_fn=lambda s: None)
    ok = r.run_block(
        Block(type="ladder", ladder_x=100, y_top=10, y_bot=100, ladder_dir="up"),
        max_steps=300)
    assert ok is True          # 재시도 끝에 등반 성공
    assert st["jumps"] >= 2    # 최소 2회 점프(첫 시도 실패 → 재시도)
    assert st["y"] <= 12       # y_top 도달
