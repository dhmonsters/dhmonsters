# 9:16 렌더 매니페스트와 FFmpeg 명령 생성을 검증한다.
from pathlib import Path

from shorts_agent.services.render_manifest import FfmpegCommandBuilder, RenderManifest, RenderScene
from shorts_agent.api.render import preview_render_command


def test_ffmpeg_command_contains_vertical_output_size():
    manifest = RenderManifest(
        width=1080,
        height=1920,
        scenes=[RenderScene(asset_path=Path("scene1.png"), duration_ms=2000, subtitle="첫 문장", motion_type="zoom_in")],
        audio_path=Path("voice.wav"),
        output_path=Path("out.mp4"),
    )
    assert isinstance(manifest.audio_path, Path)
    assert isinstance(manifest.output_path, Path)

    command = FfmpegCommandBuilder(ffmpeg_path="ffmpeg").build(manifest)

    assert command[0] == "ffmpeg"
    assert "scale=1080:1920" in " ".join(command)
    assert manifest.output_path.as_posix() in command


def test_preview_render_command_returns_expected_default_manifest_command():
    response = preview_render_command()
    command = response["command"]

    assert command[0] == "ffmpeg"
    assert "scale=1080:1920" in " ".join(command)
    assert command[-1] == "storage/example/out.mp4"


def test_path_values_are_converted_to_posix_in_render_command():
    manifest = RenderManifest(
        width=1080,
        height=1920,
        scenes=[RenderScene(Path("storage/example/scene1.png"), 2000, "첫 문장", "zoom_in")],
        audio_path=Path("storage/example/voice.wav"),
        output_path=Path("storage/example/out.mp4"),
    )
    command = FfmpegCommandBuilder(ffmpeg_path="ffmpeg").build(manifest)

    assert command[7] == "storage/example/scene1.png"
    assert command[9] == "storage/example/voice.wav"
    assert command[-1] == "storage/example/out.mp4"
