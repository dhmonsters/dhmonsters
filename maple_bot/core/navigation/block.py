# Block — 동선 1스텝 데이터. C routine_runner 스키마 채택, config JSON 직렬화 호환
from __future__ import annotations

from dataclasses import dataclass, asdict, field


_VALID_TYPES = {"move", "attack", "ladder", "jump"}
_VALID_MOVE_TYPES = {"walk", "teleport"}


@dataclass
class Block:
    """동선 시퀀스의 한 스텝. type별로 사용하는 필드가 다르다.

    move:   target_x, move_type(walk|teleport), direction
    attack: skill_key, attack_mode(duration|count), attack_value, direction
    ladder: ladder_x, y_top, y_bot, exit_side
    jump:   direction
    """
    type: str
    # move
    target_x: int = 0
    move_type: str = "walk"
    direction: str = "right"
    # attack
    skill_key: str = ""
    attack_mode: str = "duration"
    attack_value: float = 0.0
    # ladder
    ladder_x: int = 0
    y_top: int = 0
    y_bot: int = 0
    exit_side: str = "left"

    def __post_init__(self) -> None:
        if self.type not in _VALID_TYPES:
            raise ValueError(f"알 수 없는 Block.type: {self.type!r} (허용: {sorted(_VALID_TYPES)})")
        if self.type == "move" and self.move_type not in _VALID_MOVE_TYPES:
            raise ValueError(f"알 수 없는 move_type: {self.move_type!r}")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Block":
        # 알 수 없는 키는 무시하고 정의된 필드만 취함(전방호환)
        fields = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in d.items() if k in fields})
