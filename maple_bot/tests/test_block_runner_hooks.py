# tests/test_block_runner_hooks.py
# BlockRunner가 블록 실행을 enter/exit로 감싸 통지하는지(예외에도 exit 보장) 검증
from core.navigation.block import Block
from core.navigation.block_runner import BlockRunner


def _runner(events, fail=False):
    h = type("H", (), {"hold_dir": lambda *a: None, "release_dir": lambda *a: None,
                       "release_all": lambda *a: None, "release": lambda *a, **k: None,
                       "hold": lambda *a, **k: None, "perform": lambda *a, **k: None,
                       "jitter_sec": lambda s, b: 0.0, "random_side": lambda s: "left"})()
    # 도착 즉시(pos가 target과 같다고 보고) 끝나도록 pos_fn 고정
    return BlockRunner(
        humanizer=h, pos_fn=lambda: (0, 0), sleep_fn=lambda s: None,
        on_segment_enter=lambda b: events.append(("enter", b.type, b.mode)),
        on_segment_exit=lambda b: events.append(("exit", b.type, b.mode)))


def test_enter_then_exit_wraps_block():
    events = []
    r = _runner(events)
    r.run_block(Block(type="move", target_x=0, move_type="walk"))  # pos=0=target → 즉시 도착
    assert events[0][0] == "enter"
    assert events[-1][0] == "exit"


def test_exit_called_even_on_exception():
    events = []
    r = _runner(events)
    # _recover_if_needed가 터지게 만들어 예외 경로에서도 exit 보장 확인
    r._recover_if_needed = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    try:
        r.run_block(Block(type="move", target_x=0, move_type="walk"))
    except RuntimeError:
        pass
    assert ("exit", "move", "count") in events
