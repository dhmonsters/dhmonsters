diff --git a/shorts_growth_agent/backend/src/shorts_agent/api/render.py b/shorts_growth_agent/backend/src/shorts_agent/api/render.py
new file mode 100644
index 00000000..b75c7178
--- /dev/null
+++ b/shorts_growth_agent/backend/src/shorts_agent/api/render.py
@@ -0,0 +1,22 @@
+# 렌더링 요청을 받아 FFmpeg 명령 미리보기를 반환한다.
+from pathlib import Path
+
+from fastapi import APIRouter
+
+from shorts_agent.config import get_settings
+from shorts_agent.services.render_manifest import FfmpegCommandBuilder, RenderManifest, RenderScene
+
+router = APIRouter()
+
+
+@router.post("/render/preview-command")
+def preview_render_command() -> dict[str, list[str]]:
+    manifest = RenderManifest(
+        width=1080,
+        height=1920,
+        scenes=[RenderScene(Path("storage/example/scene1.png"), 2000, "첫 문장", "zoom_in")],
+        audio_path=Path("storage/example/voice.wav"),
+        output_path=Path("storage/example/out.mp4"),
+    )
+    command = FfmpegCommandBuilder(get_settings().ffmpeg_path).build(manifest)
+    return {"command": command}
\ No newline at end of file
diff --git a/shorts_growth_agent/backend/src/shorts_agent/services/render_manifest.py b/shorts_growth_agent/backend/src/shorts_agent/services/render_manifest.py
new file mode 100644
index 00000000..7a71877d
--- /dev/null
+++ b/shorts_growth_agent/backend/src/shorts_agent/services/render_manifest.py
@@ -0,0 +1,54 @@
+# 쇼츠 MP4 렌더링에 필요한 장면 매니페스트와 FFmpeg 명령을 만든다.
+from dataclasses import dataclass
+from pathlib import Path
+
+
+@dataclass(frozen=True)
+class RenderScene:
+    asset_path: Path
+    duration_ms: int
+    subtitle: str
+    motion_type: str
+
+
+@dataclass(frozen=True)
+class RenderManifest:
+    width: int
+    height: int
+    scenes: list[RenderScene]
+    audio_path: Path
+    output_path: Path
+
+
+class FfmpegCommandBuilder:
+    def __init__(self, ffmpeg_path: str):
+        self.ffmpeg_path = ffmpeg_path
+
+    @staticmethod
+    def _as_posix_path(path: Path) -> str:
+        return path.as_posix()
+
+    def build(self, manifest: RenderManifest) -> list[str]:
+        first_scene = manifest.scenes[0]
+        vf = (
+            f"scale={manifest.width}:{manifest.height}:"
+            f"force_original_aspect_ratio=increase,crop={manifest.width}:{manifest.height}"
+        )
+        return [
+            self.ffmpeg_path,
+            "-y",
+            "-loop",
+            "1",
+            "-t",
+            str(first_scene.duration_ms / 1000),
+            "-i",
+            self._as_posix_path(first_scene.asset_path),
+            "-i",
+            self._as_posix_path(manifest.audio_path),
+            "-vf",
+            vf,
+            "-shortest",
+            "-pix_fmt",
+            "yuv420p",
+            self._as_posix_path(manifest.output_path),
+        ]
diff --git a/shorts_growth_agent/backend/tests/test_render_manifest.py b/shorts_growth_agent/backend/tests/test_render_manifest.py
new file mode 100644
index 00000000..09950579
--- /dev/null
+++ b/shorts_growth_agent/backend/tests/test_render_manifest.py
@@ -0,0 +1,47 @@
+﻿# 9:16 렌더 매니페스트와 FFmpeg 명령 생성을 검증한다.
+from pathlib import Path
+
+from shorts_agent.services.render_manifest import FfmpegCommandBuilder, RenderManifest, RenderScene
+from shorts_agent.api.render import preview_render_command
+
+
+def test_ffmpeg_command_contains_vertical_output_size():
+    manifest = RenderManifest(
+        width=1080,
+        height=1920,
+        scenes=[RenderScene(asset_path=Path("scene1.png"), duration_ms=2000, subtitle="첫 문장", motion_type="zoom_in")],
+        audio_path=Path("voice.wav"),
+        output_path=Path("out.mp4"),
+    )
+    assert isinstance(manifest.audio_path, Path)
+    assert isinstance(manifest.output_path, Path)
+
+    command = FfmpegCommandBuilder(ffmpeg_path="ffmpeg").build(manifest)
+
+    assert command[0] == "ffmpeg"
+    assert "scale=1080:1920" in " ".join(command)
+    assert manifest.output_path.as_posix() in command
+
+
+def test_preview_render_command_returns_expected_default_manifest_command():
+    response = preview_render_command()
+    command = response["command"]
+
+    assert command[0] == "ffmpeg"
+    assert "scale=1080:1920" in " ".join(command)
+    assert command[-1] == "storage/example/out.mp4"
+
+
+def test_path_values_are_converted_to_posix_in_render_command():
+    manifest = RenderManifest(
+        width=1080,
+        height=1920,
+        scenes=[RenderScene(Path("storage/example/scene1.png"), 2000, "첫 문장", "zoom_in")],
+        audio_path=Path("storage/example/voice.wav"),
+        output_path=Path("storage/example/out.mp4"),
+    )
+    command = FfmpegCommandBuilder(ffmpeg_path="ffmpeg").build(manifest)
+
+    assert command[7] == "storage/example/scene1.png"
+    assert command[9] == "storage/example/voice.wav"
+    assert command[-1] == "storage/example/out.mp4"
