# InputBackend 인터페이스와 자동 선택 로직을 테스트 (실제 키 송출 없이 Fake로)
import pytest
from core.humanize.backend import InputBackend, select_backend


class FakeBackend(InputBackend):
    """테스트용 — 실제 입력 대신 호출을 기록."""
    name = "fake"

    def __init__(self):
        self.calls = []

    def key_down(self, key): self.calls.append(("down", key))
    def key_up(self, key): self.calls.append(("up", key))
    def press(self, key, hold_sec=0.05): self.calls.append(("press", key, hold_sec))
    def is_available(self): return True


def test_backend_interface_contract():
    """InputBackend 구현은 key_down/up/press/is_available 를 갖는다."""
    b = FakeBackend()
    b.key_down("a"); b.key_up("a"); b.press("b", 0.1)
    assert b.calls == [("down", "a"), ("up", "a"), ("press", "b", 0.1)]
    assert b.is_available() is True


def test_select_prefers_interception_when_available():
    """Interception 가용 시 그것을, 아니면 SendInput 폴백을 고른다."""
    icept = FakeBackend(); icept.name = "interception"
    sendi = FakeBackend(); sendi.name = "sendinput"

    # interception 가용
    chosen = select_backend(candidates=[icept, sendi])
    assert chosen.name == "interception"

    # interception 불가 → sendinput 폴백
    icept.is_available = lambda: False
    chosen = select_backend(candidates=[icept, sendi])
    assert chosen.name == "sendinput"


def test_select_raises_when_none_available():
    """가용 백엔드가 하나도 없으면 에러."""
    a = FakeBackend(); a.is_available = lambda: False
    with pytest.raises(RuntimeError):
        select_backend(candidates=[a])
