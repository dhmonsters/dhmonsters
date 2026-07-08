// 3개 영역 편집 화면을 조합해 기본 뷰를 구성합니다.
import { useReducer, useState } from "react";

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
import type { StepId } from "./types";
import "./styles.css";

export function App() {
  const [state, dispatch] = useReducer(reduceProjectState, createInitialProjectState());
  const [selectedSceneIndex, setSelectedSceneIndex] = useState(1);

  const scenes = [
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

  const contentByStep: Record<StepId, JSX.Element> = {
    keyword: <KeywordStep />,
    script: <ScriptStep />,
    voice: <VoiceSubtitleStep />,
    editor: <EditorStep />,
    export: <ExportStep />,
  };

  return (
    <main className="app-shell">
      <TopStepNav currentStep={state.currentStep} onStepChange={handleStepChange} />
      <section className="workspace" aria-label="쇼츠 편집 작업공간">
        <aside className="workspace-panel">{contentByStep[state.currentStep]}</aside>
        <section className="preview-stage">
          <ShortsCanvas scene={selectedSceneExists ? selectedScene : null} />
          <Timeline
            scenes={scenes}
            selectedSceneIndex={selectedSceneIndex}
            onSelectScene={handleSceneSelect}
          />
        </section>
        <aside className="workspace-panel">
          <GrowthAssistantPanel
            notes={["클릭률 향상을 위해 첫 3초 훅 메시지 강화", "자막 길이를 20자 이내로 간결히 정리"]}
            recommendations={["첫 화면에서 핵심 결과 제시", "콜투액션을 끝 부분에 배치"]}
          />
        </aside>
      </section>
    </main>
  );
}
