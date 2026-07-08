// 상단 단계형 쇼츠 제작 화면의 기본 레이아웃이다.
import { useState } from "react";

import { TopStepNav } from "./components/TopStepNav";
import type { StepId } from "./types";

export function App() {
  const [currentStep, setCurrentStep] = useState<StepId>("keyword");

  return (
    <main className="app-shell">
      <TopStepNav currentStep={currentStep} onStepChange={setCurrentStep} />
      <section className="workspace" aria-label="쇼츠 제작 작업 영역">
        <aside className="workspace-panel">현재 단계 도구</aside>
        <section className="preview-stage">9:16 미리보기와 작업 영역</section>
        <aside className="workspace-panel">AI 보조와 성장 메모리</aside>
      </section>
    </main>
  );
}
