# MVP 엔드투엔드 파이프라인 스모크 테스트입니다.
from pathlib import Path

from shorts_agent.services.performance_analysis import PerformanceAnalysisService, PerformancePoint
from shorts_agent.services.render_manifest import FfmpegCommandBuilder, RenderManifest, RenderScene
from shorts_agent.services.script_planner import HarnessConfig, ScriptPlanner
from shorts_agent.services.source_recommender import SourceRecommender
from shorts_agent.services.subtitle_sync import SubtitleSyncService


def test_mvp_pipeline_smoke():
    harness = HarnessConfig(
        name="뉴스+실험",
        tone="톤다운",
        hook_strength="강렬",
        target_seconds=45,
        forbidden_terms=["금지어", "100%"],
    )
    plan = ScriptPlanner().generate("요즘 화제", "뉴스", harness)
    subtitles = SubtitleSyncService().sync([scene.subtitle for scene in plan.scenes], 45000)
    source = SourceRecommender().recommend("뉴스", plan.scenes[1].index, plan.scenes[1].source_type)
    first_subtitle = subtitles[0]
    manifest = RenderManifest(
        width=1080,
        height=1920,
        scenes=[
            RenderScene(
                Path("scene1.png"),
                first_subtitle.end_ms - first_subtitle.start_ms,
                first_subtitle.text,
                plan.scenes[0].motion_type,
            )
        ],
        audio_path=Path("voice.wav"),
        output_path=Path("out.mp4"),
    )
    command = FfmpegCommandBuilder("ffmpeg").build(manifest)
    report = PerformanceAnalysisService().analyze(
        [
            PerformancePoint(60, views=100, impressions=3000, ctr=0.02, retention_3s=0.7),
            PerformancePoint(240, views=130, impressions=9000, ctr=0.014, retention_3s=0.68),
        ],
        {"source_type": source.source_type},
    )

    assert plan.scenes
    assert subtitles
    assert command[0] == "ffmpeg"
    assert report.cause_candidates[0].code == "title_thumbnail_mismatch"
