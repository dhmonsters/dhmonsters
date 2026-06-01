# CharlieExchange — 찰리중사 이빨 교환 자동화 (구매 제외, 교환 시퀀스만). C 명세 이식
# 1루틴 = 이빨 200개 소비. 반복 = 보유 // 200. 모든 입력 Humanizer 경유(타이밍 사람화)
from __future__ import annotations

from core.humanize.intent import Intent

_TOOTH_PER_ROUTINE = 200
_DOWN_REPEAT = 15   # 대화 옵션까지 아래키 15회 (C 명세)


class CharlieExchange:
    """찰리중사와 이빨 교환. 경매장 구매는 포함하지 않는다(사용자 지정).

    1루틴 시퀀스 (C UI 명세):
      NPC키 → NPC키 → 아래키 15회 → NPC키 → 왼쪽키 1회 → NPC키 → NPC키
    키 간격(NPC 0.5s, 방향 0.1s)은 Humanizer 가 사람같이 변형한다.
    """

    def __init__(self, humanizer, npc_key: str = "u"):
        self._h = humanizer
        self._npc = npc_key

    @staticmethod
    def repeat_count(tooth_amount: int) -> int:
        """보유 이빨로 가능한 교환 루틴 횟수."""
        return tooth_amount // _TOOTH_PER_ROUTINE

    def run(self, tooth_amount: int) -> int:
        """보유량만큼 교환 반복. 실행한 루틴 수 반환."""
        n = self.repeat_count(tooth_amount)
        for _ in range(n):
            self.run_one_routine()
        return n

    def run_one_routine(self) -> None:
        """교환 1회 시퀀스."""
        self._npc_talk()                      # NPC 대화 시작
        self._npc_talk()                      # 다음 대화
        for _ in range(_DOWN_REPEAT):         # 교환 메뉴까지 아래로
            self._dir("down")
        self._npc_talk()                      # 선택
        self._dir("left")                     # 수량/확인 이동
        self._npc_talk()                      # 확인
        self._npc_talk()                      # 완료

    # ── 내부 (모든 입력 Humanizer 경유) ──────────────────────────────
    def _npc_talk(self) -> None:
        self._h.perform(Intent(action="key", key=self._npc, base_hold_sec=0.05, base_delay=0.5))

    def _dir(self, key: str) -> None:
        self._h.perform(Intent(action="key", key=key, base_hold_sec=0.05, base_delay=0.1))
