// 3개 영역 편집 화면을 조합해 기본 뷰를 구성합니다.
import { useReducer, useState } from "react";

import { analyzeTrendCandidate, createProject, generatePlan } from "./api/client";
import { EditorStep } from "./pages/EditorStep";
import { ExportStep } from "./pages/ExportStep";
import { GrowthAssistantPanel } from "./components/GrowthAssistantPanel";
import { KeywordStep } from "./pages/KeywordStep";
import { ShortsCanvas } from "./components/ShortsCanvas";
import { ScriptStep } from "./pages/ScriptStep";
import { Timeline } from "./components/Timeline";
import { TopStepNav } from "./components/TopStepNav";
import { VoiceSubtitleStep } from "./pages/VoiceSubtitleStep";
import { createInitialProjectState, reduceProjectState } from "./state/projectStore";
import type { StepId, TrendCandidate, TrendCategory } from "./types";
import "./styles.css";

export function App() {
  const [state, dispatch] = useReducer(reduceProjectState, createInitialProjectState());
  const [selectedSceneIndex, setSelectedSceneIndex] = useState(1);

  const scenes =
    state.scriptPlan?.scenes.map((scene, index) => ({
      ...scene,
      source_type: index === 1 ? "trend_clip_review" : "ai_image",
      motion_type: index === 0 ? "zoom-in" : index === 1 ? "shake" : "pan-right",
    })) ?? [
      { index: 1, subtitle: "오프닝", source_type: "ai_image", motion_type: "zoom-in" },
      { index: 2, subtitle: "하이라이트", source_type: "ai_image", motion_type: "fade-in" },
      { index: 3, subtitle: "콜투액션", source_type: "ai_image", motion_type: "pan-right" },
    ];

  const selectedScene = scenes.find((scene) => scene.index === selectedSceneIndex) ?? null;
  const selectedSceneExists = scenes.some((scene) => scene.index === selectedSceneIndex);

  const handleStepChange = (step: StepId) => {
    dispatch({ type: "stepChanged", step });
  };

  const handleSceneSelect = (index: number) => {
    setSelectedSceneIndex(index);
  };

  const handleCustomizationChange = (section: StepId, value: string) => {
    dispatch({ type: "customizationChanged", section, value });
  };

  const handleTrendInspect = async (trend: TrendCandidate) => {
    dispatch({ type: "trendSelected", trend });
    const analysis = await analyzeTrendCandidate(trend);
    dispatch({ type: "trendAnalyzed", analysis });
  };

  const handleTrendPicked = async (trend: TrendCandidate, category: TrendCategory) => {
    dispatch({ type: "trendSelected", trend });
    const analysis =
      state.trendAnalysis?.video_id === trend.video_id
        ? state.trendAnalysis
        : await analyzeTrendCandidate(trend);
    dispatch({ type: "trendAnalyzed", analysis });
    const planHarness = {
      ...state.harness,
      tone: analysis.recommended_harness.tone,
      hook_strength: analysis.recommended_harness.hook_strength,
      target_seconds: analysis.recommended_harness.target_seconds,
      forbidden_terms: analysis.recommended_harness.forbidden_terms,
    };
    const keyword = trend.keyword_candidates[0] ?? trend.title;
    const project = await createProject({
      title: trend.title,
      category: category.label,
      selected_keyword: keyword,
    });
    dispatch({ type: "projectCreated", project });
    const plan = await generatePlan(project.id, {
      harness: planHarness,
      trend_analysis: {
        primary_angle: analysis.production_angles[0],
        script_seed: analysis.script_seed,
      },
    });
    dispatch({ type: "planGenerated", plan });
    setSelectedSceneIndex(1);
  };

  const contentByStep: Record<StepId, JSX.Element> = {
    keyword: (
      <KeywordStep
        customization={state.customization.keyword}
        onCustomizationChange={(value) => handleCustomizationChange("keyword", value)}
        onTrendInspect={handleTrendInspect}
        onTrendPicked={handleTrendPicked}
        selectedTrend={state.selectedTrend}
        trendAnalysis={state.trendAnalysis}
      />
    ),
    script: (
      <ScriptStep
        customization={state.customization.script}
        onCustomizationChange={(value) => handleCustomizationChange("script", value)}
        harness={state.harness}
        onHarnessChange={(harness) => dispatch({ type: "harnessChanged", harness })}
        scriptPlan={state.scriptPlan}
        onSceneSubtitleChange={(index, subtitle) =>
          dispatch({ type: "sceneSubtitleChanged", index, subtitle })
        }
        onSceneRegenerate={(index) => dispatch({ type: "sceneRegenerated", index })}
        onSceneMove={(index, direction) => dispatch({ type: "sceneMoved", index, direction })}
      />
    ),
    voice: (
      <VoiceSubtitleStep
        customization={state.customization.voice}
        onCustomizationChange={(value) => handleCustomizationChange("voice", value)}
      />
    ),
    editor: (
      <EditorStep
        customization={state.customization.editor}
        onCustomizationChange={(value) => handleCustomizationChange("editor", value)}
      />
    ),
    export: (
      <ExportStep
        customization={state.customization.export}
        onCustomizationChange={(value) => handleCustomizationChange("export", value)}
      />
    ),
  };
  const showPreview = state.currentStep === "editor";
  const showAssistant = state.currentStep === "export";

  return (
    <main className="app-shell">
      <TopStepNav currentStep={state.currentStep} onStepChange={handleStepChange} />
      <section
        className={`workspace workspace-${state.currentStep}`}
        aria-label="쇼츠 제작 작업공간"
      >
        <aside className="workspace-panel workspace-primary">{contentByStep[state.currentStep]}</aside>
        {showPreview && (
          <section className="preview-stage">
            <ShortsCanvas scene={selectedSceneExists ? selectedScene : null} />
            <Timeline
              scenes={scenes}
              selectedSceneIndex={selectedSceneIndex}
              onSelectScene={handleSceneSelect}
            />
          </section>
        )}
        {showAssistant && (
          <aside className="workspace-panel">
            <GrowthAssistantPanel
              notes={["클릭률 향상을 위해 첫 3초 훅 메시지 강화", "자막 길이를 20자 이내로 간결히 정리"]}
              recommendations={["첫 화면에서 핵심 결과 제시", "콜투액션을 끝 부분에 배치"]}
            />
          </aside>
        )}
      </section>
    </main>
  );
}
