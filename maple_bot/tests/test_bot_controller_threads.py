# 통합 봇 컨트롤러의 작업 스레드 생성과 반복 대기를 검증한다.
from types import SimpleNamespace

import run_integrated


class _FakeThread:
    created = []

    def __init__(self, target, daemon, name):
        self.target = target
        self.daemon = daemon
        self.name = name
        self.started = False
        self.created.append(self)

    def start(self):
        self.started = True

    def is_alive(self):
        return self.started


class _FloorRunner:
    def __init__(self):
        self.started = False

    def start(self):
        self.started = True


class _Runtime:
    def __init__(self, floor_runner=None):
        self._cfg = SimpleNamespace(game_window_title="game", minimap_region=None, char_rgb=None)
        self.floor_hunt_runner = floor_runner
        self.started_scanners = False
        self.running = False

    def set_running(self, flag):
        self.running = flag

    def start_scanners(self):
        self.started_scanners = True

    def _resolve_region(self, region):
        return (0, 0, 172, 103)


def _controller(runtime):
    controller = object.__new__(run_integrated.BotController)
    controller._rt = runtime
    controller._log = lambda *args: None
    controller._thread = None
    controller._movement_thread = None
    controller._attack_thread = None
    controller._support_thread = None
    controller._pickup_thread = None
    controller._stop = run_integrated.threading.Event()
    return controller


def test_dedicated_floor_runner_does_not_create_duplicate_movement_thread(monkeypatch):
    _FakeThread.created = []
    monkeypatch.setattr(run_integrated.threading, "Thread", _FakeThread)
    runner = _FloorRunner()
    controller = _controller(_Runtime(runner))

    controller.start()

    assert runner.started is True
    assert controller._movement_thread is None
    assert "BotMovementLoop" not in [thread.name for thread in _FakeThread.created]


def test_generic_movement_loop_waits_30ms_after_normal_tick():
    class StopProbe:
        def __init__(self):
            self.done = False
            self.waits = []

        def is_set(self):
            return self.done

        def wait(self, seconds):
            self.waits.append(seconds)
            self.done = True

    calls = []
    controller = object.__new__(run_integrated.BotController)
    controller._rt = SimpleNamespace(
        movement_tick=lambda: calls.append("tick"),
        block_runner=SimpleNamespace(
            _route_inputs=SimpleNamespace(release_direction=lambda: None),
        ),
    )
    controller._log = lambda *args: None
    controller._stop = StopProbe()

    controller._movement_loop()

    assert calls == ["tick"]
    assert controller._stop.waits == [0.03]


def test_start_request_while_running_delegates_to_safe_resume():
    resumed = []
    controller = _controller(SimpleNamespace(
        resume_lie_safety_if_clear=lambda: resumed.append(True) or True,
    ))
    controller._thread = SimpleNamespace(is_alive=lambda: True)

    controller.start()

    assert resumed == [True]
