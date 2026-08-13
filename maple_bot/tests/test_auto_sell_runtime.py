# 자동판매의 최신 설정 반영과 실패 재시도 상태를 검증한다.
from types import SimpleNamespace
import threading

from core.auto_seller import AutoSeller
from core.runtime import BotRuntime


class DictConfig:
    def __init__(self, data):
        self.data = data

    def get(self, *keys, default=None):
        node = self.data
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node


def test_auto_sell_tick_uses_latest_saved_settings():
    observed = []
    runtime = BotRuntime.__new__(BotRuntime)
    runtime._bot_running = True
    runtime._cfg = SimpleNamespace(
        junk_config=DictConfig({
            "settings2": {
                "junk_sell": {
                    "auto_sell_enabled": True,
                    "auto_sell_interval_min": 3,
                    "sell_on_start": True,
                }
            }
        }),
        auto_sell_enabled=False,
        auto_sell_interval_min=10.0,
        auto_sell_on_start=False,
    )
    runtime.auto_seller = SimpleNamespace(
        should_run=lambda enabled, interval, now: observed.append((enabled, interval, now)) or False,
    )

    runtime._auto_sell_tick(123.0)

    assert observed == [(True, 3.0, 123.0)]
    assert runtime._cfg.auto_sell_on_start is True


def test_failed_sale_is_reported_by_state_machine():
    seller = SimpleNamespace(sell=lambda **_kwargs: False)
    auto_seller = AutoSeller(seller)

    result = auto_seller.run_once(lambda _message: None, SimpleNamespace(is_set=lambda: False))

    assert result is False
    assert auto_seller.state == "failed"
    assert auto_seller.status.last_error == "판매 단계 미완료"


def test_failed_runtime_sale_is_retried_after_five_seconds():
    schedules = []
    runtime = BotRuntime.__new__(BotRuntime)
    runtime._junk_selling = False
    runtime._junk_sell_stop = threading.Event()
    runtime._cfg = SimpleNamespace(auto_sell_interval_min=10.0)
    runtime.floor_hunt_runner = None
    runtime.release_pickup_key = lambda: None
    runtime._release_runtime_inputs = lambda: None
    runtime.log = lambda *_args: None
    runtime.auto_seller = SimpleNamespace(
        run_once=lambda _status, _stop: False,
        schedule_after_minutes=lambda minutes: schedules.append(("minutes", minutes)),
        schedule_after_seconds=lambda seconds: schedules.append(("seconds", seconds)),
    )

    runtime._run_junk_sell_once()

    assert schedules == [("seconds", 5.0)]
    assert runtime._junk_selling is False
