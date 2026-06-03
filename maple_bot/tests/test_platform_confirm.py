# 등반 완료 판정 = 발판 위에서 좌우(x) 이동 가능 확인 검증(로프 매달림이면 미완료)
from core.navigation.block_runner import BlockRunner


class _H:
    def __init__(self): self.dir = None
    def hold_dir(self, k, risk_profile=None): self.dir = k
    def release_dir(self): self.dir = None
    def hold(self, k): pass
    def release(self, k): pass
    def jitter_sec(self, b, s=None): return b


def test_confirm_true_when_x_moves_on_platform():
    # 발판: 방향키 누르면 x가 변함 → 등반 완료
    st = {"x": 100}
    h = _H()
    def pos():
        if h.dir == "left": st["x"] -= 8
        elif h.dir == "right": st["x"] += 8
        return (st["x"], 50)
    r = BlockRunner(humanizer=h, pos_fn=pos, sleep_fn=lambda s: None)
    assert r._confirm_on_platform(100, max_steps=50) is True


def test_confirm_false_when_hanging_on_rope():
    # 로프 매달림: 방향키 눌러도 x가 사다리(100) 그대로 → 미완료(재시도)
    r = BlockRunner(humanizer=_H(), pos_fn=lambda: (100, 50), sleep_fn=lambda s: None)
    assert r._confirm_on_platform(100, max_steps=50) is False
