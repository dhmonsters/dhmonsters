diff --git a/shorts_growth_agent/backend/src/shorts_agent/adapters/tts.py b/shorts_growth_agent/backend/src/shorts_agent/adapters/tts.py
new file mode 100644
index 00000000..c6cc9959
--- /dev/null
+++ b/shorts_growth_agent/backend/src/shorts_agent/adapters/tts.py
@@ -0,0 +1,29 @@
+# TTS 어댑터 인터페이스와 정적 음성 합성 플레이스홀더를 제공합니다.
+from dataclasses import dataclass
+from pathlib import Path
+import wave
+
+
+@dataclass(frozen=True)
+class TtsResult:
+    audio_path: Path
+    duration_ms: int
+    voice: str
+    speed: float
+
+
+class TtsAdapter:
+    def synthesize(self, text: str, voice: str, speed: float, output_path: Path) -> TtsResult:
+        raise NotImplementedError
+
+
+class SilentTtsAdapter(TtsAdapter):
+    def synthesize(self, text: str, voice: str, speed: float, output_path: Path) -> TtsResult:
+        duration_ms = max(1000, int(len(text) * 80 / max(speed, 0.5)))
+        output_path.parent.mkdir(parents=True, exist_ok=True)
+        with wave.open(str(output_path), "w") as wav:
+            wav.setnchannels(1)
+            wav.setsampwidth(2)
+            wav.setframerate(16000)
+            wav.writeframes(b"\x00\x00" * int(16000 * duration_ms / 1000))
+        return TtsResult(audio_path=output_path, duration_ms=duration_ms, voice=voice, speed=speed)
diff --git a/shorts_growth_agent/backend/src/shorts_agent/api/projects.py b/shorts_growth_agent/backend/src/shorts_agent/api/projects.py
new file mode 100644
index 00000000..bc46b5cc
--- /dev/null
+++ b/shorts_growth_agent/backend/src/shorts_agent/api/projects.py
@@ -0,0 +1,4 @@
+# 프로젝트 관련 API 라우터를 위한 플레이스홀더입니다.
+from fastapi import APIRouter
+
+router = APIRouter()
diff --git a/shorts_growth_agent/backend/src/shorts_agent/services/subtitle_sync.py b/shorts_growth_agent/backend/src/shorts_agent/services/subtitle_sync.py
new file mode 100644
index 00000000..50e4d485
--- /dev/null
+++ b/shorts_growth_agent/backend/src/shorts_agent/services/subtitle_sync.py
@@ -0,0 +1,23 @@
+# 자막 텍스트 라인에 대한 시간 구간을 비례 분배해 동기화합니다.
+from dataclasses import dataclass
+
+
+@dataclass(frozen=True)
+class SubtitleCue:
+    text: str
+    start_ms: int
+    end_ms: int
+
+
+class SubtitleSyncService:
+    def sync(self, lines: list[str], total_duration_ms: int) -> list[SubtitleCue]:
+        if not lines:
+            return []
+
+        slot = total_duration_ms // len(lines)
+        cues = []
+        for index, line in enumerate(lines):
+            start = index * slot
+            end = total_duration_ms if index == len(lines) - 1 else (index + 1) * slot
+            cues.append(SubtitleCue(text=line, start_ms=start, end_ms=end))
+        return cues
diff --git a/shorts_growth_agent/backend/tests/test_subtitle_sync.py b/shorts_growth_agent/backend/tests/test_subtitle_sync.py
new file mode 100644
index 00000000..3c03f976
--- /dev/null
+++ b/shorts_growth_agent/backend/tests/test_subtitle_sync.py
@@ -0,0 +1,11 @@
+# 자막 동기화 서비스의 핵심 동작을 검증하는 테스트입니다.
+from shorts_agent.services.subtitle_sync import SubtitleSyncService
+
+
+def test_sync_splits_duration_across_lines():
+    cues = SubtitleSyncService().sync(["첫 번째 문장", "두 번째 문장"], total_duration_ms=4000)
+
+    assert cues[0].start_ms == 0
+    assert cues[0].end_ms == 2000
+    assert cues[1].start_ms == 2000
+    assert cues[1].end_ms == 4000
