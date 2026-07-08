// 쇼츠 제작 워크플로우를 전환하는 최상위 앱 화면입니다.
import { useReducer } from "react";

import { EditorStep } from "./pages/EditorStep";
import { ExportStep } from "./pages/ExportStep";
import { KeywordStep } from "./pages/KeywordStep";
import { ScriptStep } from "./pages/ScriptStep";
import { TopStepNav } from "./components/TopStepNav";
import { VoiceSubtitleStep } from "./pages/VoiceSubtitleStep";
import { createInitialProjectState, reduceProjectState } from "./state/projectStore";
import type { StepId } from "./types";
import "./styles.css";

export function App() {
  const [state, dispatch] = useReducer(reduceProjectState, createInitialProjectState());

  const handleStepChange = (step: StepId) => {
    dispatch({ type: "stepChanged", step });
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
      <section className="workspace" aria-label="쇼츠 제작 작업 공간">
        <aside className="workspace-panel">{contentByStep[state.currentStep]}</aside>
        <section className="preview-stage">9:16 미리보기와 작업 영역</section>
        <aside className="workspace-panel">AI 보조와 성장 메모리</aside>
      </section>
    </main>
  );
}
