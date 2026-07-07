# 쇼츠 MP4 렌더링에 필요한 장면 매니페스트와 FFmpeg 명령을 만든다.
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RenderScene:
    asset_path: Path
    duration_ms: int
    subtitle: str
    motion_type: str


@dataclass(frozen=True)
class RenderManifest:
    width: int
    height: int
    scenes: list[RenderScene]
    audio_path: Path
    output_path: Path


class FfmpegCommandBuilder:
    def __init__(self, ffmpeg_path: str):
        self.ffmpeg_path = ffmpeg_path

    @staticmethod
    def _as_posix_path(path: Path) -> str:
        return path.as_posix()

    def build(self, manifest: RenderManifest) -> list[str]:
        first_scene = manifest.scenes[0]
        vf = (
            f"scale={manifest.width}:{manifest.height}:"
            f"force_original_aspect_ratio=increase,crop={manifest.width}:{manifest.height}"
        )
        return [
            self.ffmpeg_path,
            "-y",
            "-loop",
            "1",
            "-t",
            str(first_scene.duration_ms / 1000),
            "-i",
            self._as_posix_path(first_scene.asset_path),
            "-i",
            self._as_posix_path(manifest.audio_path),
            "-vf",
            vf,
            "-shortest",
            "-pix_fmt",
            "yuv420p",
            self._as_posix_path(manifest.output_path),
        ]
