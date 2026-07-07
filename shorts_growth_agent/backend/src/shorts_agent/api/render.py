# 렌더링 요청을 받아 FFmpeg 명령 미리보기를 반환한다.
from pathlib import Path

from fastapi import APIRouter

from shorts_agent.config import get_settings
from shorts_agent.services.render_manifest import FfmpegCommandBuilder, RenderManifest, RenderScene

router = APIRouter()


@router.post("/render/preview-command")
def preview_render_command() -> dict[str, list[str]]:
    manifest = RenderManifest(
        width=1080,
        height=1920,
        scenes=[RenderScene(Path("storage/example/scene1.png"), 2000, "첫 문장", "zoom_in")],
        audio_path=Path("storage/example/voice.wav"),
        output_path=Path("storage/example/out.mp4"),
    )
    command = FfmpegCommandBuilder(get_settings().ffmpeg_path).build(manifest)
    return {"command": command}