# PetFeeder(주기 펫먹이) + TelegramNotifier(알림) 검증
import pytest
from core.acting.pet import PetFeeder
from core.notify.telegram import TelegramNotifier


class FakeHumanizer:
    def __init__(self): self.intents = []
    def perform(self, i): self.intents.append(i)


# ── PetFeeder ─────────────────────────────────────────────────
def test_pet_feeds_on_interval():
    h = FakeHumanizer()
    pet = PetFeeder(h, key="=", interval=600)   # 10분
    pet.tick(now=1000.0)                          # 최초
    assert any(i.key == "=" for i in h.intents)


def test_pet_respects_interval():
    h = FakeHumanizer()
    pet = PetFeeder(h, key="=", interval=600)
    pet.tick(1000.0); n = len(h.intents)
    pet.tick(1300.0)                              # 5분 → 아직
    assert len(h.intents) == n
    pet.tick(1601.0)                              # 10분 경과
    assert len(h.intents) > n


def test_pet_disabled_when_no_key():
    h = FakeHumanizer()
    pet = PetFeeder(h, key="", interval=600)
    pet.tick(1000.0)
    assert len(h.intents) == 0


# ── TelegramNotifier ──────────────────────────────────────────
def test_telegram_sends_when_enabled():
    sent = []
    def fake_post(url, data=None, **kw):
        sent.append((url, data)); return type("R", (), {"status_code": 200})()
    n = TelegramNotifier(token="T", chat_id="C", enabled=True, post_fn=fake_post)
    n.send("거탐 감지!")
    assert len(sent) == 1
    assert "T" in sent[0][0]              # URL에 토큰
    assert sent[0][1]["chat_id"] == "C"
    assert "거탐" in sent[0][1]["text"]


def test_telegram_silent_when_disabled():
    sent = []
    n = TelegramNotifier(token="T", chat_id="C", enabled=False,
                         post_fn=lambda *a, **k: sent.append(1))
    n.send("x")
    assert sent == []


def test_telegram_no_token_no_send():
    sent = []
    n = TelegramNotifier(token="", chat_id="C", enabled=True,
                         post_fn=lambda *a, **k: sent.append(1))
    n.send("x")
    assert sent == []


def test_telegram_exception_safe():
    """전송 실패해도 예외 안 터짐(봇 안 멈춤)."""
    def boom(*a, **k): raise RuntimeError("network")
    n = TelegramNotifier(token="T", chat_id="C", enabled=True, post_fn=boom)
    n.send("x")   # 예외 없이 통과
