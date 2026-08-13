# ?낅젰 諛깆뿏????Interception(?ㅽ뀛?? ?곗꽑, SendInput ?대갚. 怨듯넻 ?명꽣?섏씠???ㅻ줈 寃⑸━
from __future__ import annotations

from abc import ABC, abstractmethod

from core.humanize.timing import down_5


class InputBackend(ABC):
    """?낅젰 ?≪텧 諛깆뿏??怨꾩빟. 援ы쁽泥대뒗 援먯껜 媛??肄섏꽱??."""
    name: str = "abstract"

    @abstractmethod
    def key_down(self, key: str) -> None: ...

    @abstractmethod
    def key_up(self, key: str) -> None: ...

    @abstractmethod
    def press(self, key: str, hold_sec: float = 0.05) -> None: ...

    @abstractmethod
    def click(self, x: int, y: int) -> None: ...

    @abstractmethod
    def is_available(self) -> bool:
        """??諛깆뿏?쒓? ?꾩옱 ?섍꼍?먯꽌 ?ъ슜 媛?ν븳媛."""
        ...

    def begin_priority(self) -> None:
        """以묒슂 ?낅젰 援ш컙 ?쒖옉. 吏?먰븯吏 ?딅뒗 諛깆뿏?쒕뒗 洹몃?濡??ㅽ뻾?쒕떎."""

    def end_priority(self) -> None:
        """以묒슂 ?낅젰 援ш컙 醫낅즺. 吏?먰븯吏 ?딅뒗 諛깆뿏?쒕뒗 洹몃?濡??ㅽ뻾?쒕떎."""


class InterceptionBackend(InputBackend):
    """而ㅻ꼸 ?쒕씪?대쾭 湲곕컲 ?ㅽ뀛???낅젰 (core/interception_backend.py ?섑븨)."""
    name = "interception"

    def __init__(self):
        from core import interception_backend as _ic
        self._ic = _ic
        self._enabled = False

    def is_available(self) -> bool:
        if not self._enabled:
            # enable()? ?쒕씪?대쾭 罹≪쿂瑜?1???쒕룄?섍퀬 ?깃났 ?щ?瑜?諛섑솚
            self._enabled = self._ic.enable()
        return self._ic.is_active()

    def key_down(self, key: str) -> None:
        self._ic.key_down(key)

    def key_up(self, key: str) -> None:
        self._ic.key_up(key)

    def press(self, key: str, hold_sec: float = 0.05) -> None:
        self._ic.press(key, hold_sec)

    def click(self, x: int, y: int) -> None:
        self._ic.click(int(x), int(y))

    def begin_priority(self) -> None:
        self._ic.begin_priority()

    def end_priority(self) -> None:
        self._ic.end_priority()


class SendInputBackend(InputBackend):
    """Win32 SendInput ?대갚 (core/input_controller.py ?꾨━誘명떚釉??ъ궗??."""
    name = "sendinput"

    def __init__(self):
        from core import input_controller as _src
        self._src = _src

    def is_available(self) -> bool:
        return True  # Win32????긽 媛??
    def key_down(self, key: str) -> None:
        vk = self._src._vk(key)
        if vk:
            self._src._send_key(vk, 0)

    def key_up(self, key: str) -> None:
        vk = self._src._vk(key)
        if vk:
            self._src._send_key(vk, self._src.KEYEVENTF_KEYUP)

    def press(self, key: str, hold_sec: float = 0.05) -> None:
        import time
        self.key_down(key)
        time.sleep(down_5(hold_sec))
        self.key_up(key)

    def click(self, x: int, y: int) -> None:
        import time
        self._src._move_mouse(int(x), int(y))
        time.sleep(0.03)
        self._src._click_mouse(True)
        time.sleep(0.05)
        self._src._click_mouse(False)


def select_backend(candidates: list[InputBackend] | None = None) -> InputBackend:
    """Interception 입력 백엔드만 선택합니다. 실패 시 fallback 없이 중단합니다."""
    if candidates is None:
        candidates = [InterceptionBackend()]
    last_error: Exception | None = None
    for b in candidates:
        try:
            if b.is_available():
                return b
        except Exception as exc:
            last_error = exc
    detail = f" ({last_error})" if last_error else ""
    raise RuntimeError("Interception 입력 백엔드 활성화에 실패했습니다. 드라이버 설치와 관리자 권한 실행을 확인해 주세요." + detail)
