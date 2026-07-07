# AI 이미지 생성을 위한 어댑터 인터페이스입니다.
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ImageResult:
    path: Path
    prompt: str


class ImageAdapter:
    def generate(self, prompt: str, output_path: Path) -> ImageResult:
        raise NotImplementedError
