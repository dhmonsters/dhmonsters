# 이동 루프가 스텝마다 대기해 위치 갱신 전 '거짓 멈춤'을 내지 않는지 검증
from core.navigation.block import Block
from core.navigation.block_runner import BlockRunner


class _H:
    def hold_dir(self, *a): pass
    def release_dir(self): pass
    def release_all(self): pass
    def jitter_sec(self, base, spread=None): return base


def test_exec_move_polls_so_async_position_update_is_seen():
    # 위치는 '대기(sleep)'할 때마다 전진(스캐너의 비동기 갱신 모사).
    # 루프가 스텝마다 안 쉬면 x가 안 변해 5회만에 거짓 멈춤 → 실패.
    state = {"x": 0}
    def pos():
        return (state["x"], 0)
    def slp(_t):
        state["x"] += 10   # 대기 1회당 10px 전진
    r = BlockRunner(humanizer=_H(), pos_fn=pos, sleep_fn=slp)
    ok = r.run_block(Block(type="move", target_x=30), max_steps=20)
    assert ok                      # 대기 덕분에 x가 갱신돼 30에 도달
    assert state["x"] >= 30
