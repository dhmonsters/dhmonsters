# TelegramNotifier — 거탐/이탈 등 이벤트를 텔레그램으로 통지 (B·C 방식, requests 단순호출)
from __future__ import annotations


class TelegramNotifier:
    """텔레그램 봇 알림. 전송 실패가 봇을 멈추지 않게 예외를 삼킨다.

    post_fn: HTTP POST 함수 주입(테스트용). 기본은 requests.post.
    """

    def __init__(self, token: str = "", chat_id: str = "",
                 enabled: bool = False, post_fn=None):
        self._token = token
        self._chat_id = chat_id
        self._enabled = enabled
        self._post = post_fn

    def _http_post(self, url, data):
        if self._post is not None:
            return self._post(url, data=data)
        import requests
        return requests.post(url, data=data, timeout=5)

    def send(self, text: str) -> bool:
        """메시지 전송. 비활성/토큰없음/실패 시 False (예외 안 던짐)."""
        if not self._enabled or not self._token or not self._chat_id:
            return False
        try:
            url = f"https://api.telegram.org/bot{self._token}/sendMessage"
            self._http_post(url, {"chat_id": self._chat_id, "text": text})
            return True
        except Exception:
            return False
