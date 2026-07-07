# Meme 라이브러리를 검색하는 어댑터 인터페이스입니다.
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MemeAsset:
    path: Path
    tags: list[str]
    source: str


class MemeAdapter:
    def search(self, query: str, limit: int = 10) -> list[MemeAsset]:
        return []
