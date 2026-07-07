# TTS 어댑터 인터페이스와 정적 음성 합성 플레이스홀더를 제공합니다.
from dataclasses import dataclass
from pathlib import Path
import wave


@dataclass(frozen=True)
class TtsResult:
    audio_path: Path
    duration_ms: int
    voice: str
    speed: float


class TtsAdapter:
    def synthesize(self, text: str, voice: str, speed: float, output_path: Path) -> TtsResult:
        raise NotImplementedError


class SilentTtsAdapter(TtsAdapter):
    def synthesize(self, text: str, voice: str, speed: float, output_path: Path) -> TtsResult:
        duration_ms = max(1000, int(len(text) * 80 / max(speed, 0.5)))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "w") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(b"\x00\x00" * int(16000 * duration_ms / 1000))
        return TtsResult(audio_path=output_path, duration_ms=duration_ms, voice=voice, speed=speed)
