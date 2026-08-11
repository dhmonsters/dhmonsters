# Puzzle2의 Interception 전용 이동과 화면 커서 중심 보정을 검증한다.
from __future__ import annotations

import pytest

from core.puzzle2.mouse import InterceptionMouseController


class FakeInterceptionDriver:
    name = "interception"

    def __init__(self) -> None:
        self.moves: list[tuple[int, int]] = []
        self.clicks: list[tuple[int, int]] = []

    def move_to(self, x: int, y: int) -> None:
        self.moves.append((x, y))

    def click(self, x: int, y: int) -> None:
        self.clicks.append((x, y))


def test_interception_mouse_learns_then_freezes_visible_cursor_offset() -> None:
    driver = FakeInterceptionDriver()
    observations = iter([(120.0, 130.0), (999.0, 999.0)])
    controller = InterceptionMouseController(
        driver_loader=lambda: driver,
        cursor_observer=lambda: next(observations),
        offset_alpha=0.5,
    )

    controller.begin_puzzle()
    controller.move(100.0, 100.0, learn_offset=True)
    controller.move(200.0, 200.0, learn_offset=True)
    controller.move(300.0, 300.0, learn_offset=False)

    assert driver.moves == [(100, 100), (190, 185), (290, 285)]
    assert controller.offset == (-10.0, -15.0)


def test_interception_mouse_click_uses_same_corrected_kernel_driver() -> None:
    driver = FakeInterceptionDriver()
    controller = InterceptionMouseController(
        driver_loader=lambda: driver,
        cursor_observer=lambda: (110.0, 120.0),
        offset_alpha=1.0,
    )
    controller.begin_puzzle()
    controller.move(100.0, 100.0, learn_offset=True)
    controller.move(200.0, 200.0, learn_offset=True)

    controller.click(300.0, 300.0)

    assert driver.clicks == [(290, 280)]


def test_interception_mouse_rejects_non_kernel_backend() -> None:
    driver = FakeInterceptionDriver()
    driver.name = "sendinput"
    controller = InterceptionMouseController(
        driver_loader=lambda: driver,
        cursor_observer=lambda: None,
    )

    with pytest.raises(RuntimeError, match="Interception"):
        controller.move(100.0, 100.0, learn_offset=False)
