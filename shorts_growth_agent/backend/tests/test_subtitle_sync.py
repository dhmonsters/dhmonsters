# 자막 동기화 서비스의 핵심 동작을 검증하는 테스트입니다.
from shorts_agent.services.subtitle_sync import SubtitleSyncService


def test_sync_splits_duration_across_lines():
    cues = SubtitleSyncService().sync(["첫 번째 문장", "두 번째 문장"], total_duration_ms=4000)

    assert cues[0].start_ms == 0
    assert cues[0].end_ms == 2000
    assert cues[1].start_ms == 2000
    assert cues[1].end_ms == 4000
