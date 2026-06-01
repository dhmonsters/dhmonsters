# Block — 동선 1스텝 데이터. C routine_runner 스키마 채택, config JSON 직렬화 호환
from __future__ import annotations

from dataclasses import dataclass, asdict, field


_VALID_TYPES = {"move", "attack", "ladder", "jump"}
_VALID_MOVE_TYPES = {"walk", "teleport"}
_VALID_MOVE_MODES = {"count", "infinite", "pass"}  # 구간왕복 횟수 / 무한왕복 / 한방향 통과
_VALID_LADDER_DIRS = {"up", "down"}                # 사다리 등반 / 하강
_VALID_GRAB_SIDES = {"auto", "left", "right", "random"}  # 밧줄 잡는 좌우 방향


@dataclass
class Block:
    """동선 시퀀스의 한 스텝. type별로 사용하는 필드가 다르다.

    move:   target_x, move_type(walk|teleport), direction
            또는 구간 왕복: start_x ~ end_x 사이를 sweeps회 왕복 (start_x<end_x 이면 구간모드)
    attack: skill_key, attack_mode(duration|count), attack_value, direction
    ladder: ladder_x, y_top, y_bot, exit_side
    jump:   direction
    """
    type: str
    # move
    target_x: int = 0
    move_type: str = "walk"
    direction: str = "right"
    # move 구간 왕복 (start_x < end_x 이면 구간 모드)
    start_x: int = 0
    end_x: int = 0
    sweeps: int = 1
    mode: str = "count"          # count=sweeps회 왕복 / infinite=무한왕복 / pass=한방향 1회 통과
    # attack
    skill_key: str = ""
    attack_mode: str = "duration"
    attack_value: float = 0.0
    # ladder
    ladder_x: int = 0
    y_top: int = 0
    y_bot: int = 0
    exit_side: str = "left"
    ladder_dir: str = "up"       # up=등반(y_top까지) / down=하강(점프 내림)
    grab_side: str = "auto"      # 밧줄 잡기 방향: auto(가까운쪽)/left/right/random(좌우 랜덤)

    def __post_init__(self) -> None:
        if self.type not in _VALID_TYPES:
            raise ValueError(f"알 수 없는 Block.type: {self.type!r} (허용: {sorted(_VALID_TYPES)})")
        if self.type == "move" and self.move_type not in _VALID_MOVE_TYPES:
            raise ValueError(f"알 수 없는 move_type: {self.move_type!r}")
        if self.type == "move" and self.mode not in _VALID_MOVE_MODES:
            raise ValueError(f"알 수 없는 move mode: {self.mode!r} (허용: {sorted(_VALID_MOVE_MODES)})")
        if self.type == "ladder" and self.ladder_dir not in _VALID_LADDER_DIRS:
            raise ValueError(f"알 수 없는 ladder_dir: {self.ladder_dir!r}")
        if self.type == "ladder" and self.grab_side not in _VALID_GRAB_SIDES:
            raise ValueError(f"알 수 없는 grab_side: {self.grab_side!r}")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Block":
        # 알 수 없는 키는 무시하고 정의된 필드만 취함(전방호환)
        fields = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in d.items() if k in fields})
