diff --git a/shorts_growth_agent/frontend/src/App.tsx b/shorts_growth_agent/frontend/src/App.tsx
index 9ec1b998..3852fa06 100644
--- a/shorts_growth_agent/frontend/src/App.tsx
+++ b/shorts_growth_agent/frontend/src/App.tsx
@@ -1,39 +1,68 @@
-// 쇼츠 제작 워크플로우를 전환하는 최상위 앱 화면입니다.
-import { useReducer } from "react";
+// 3개 영역 편집 화면을 조합해 기본 뷰를 구성합니다.
+import { useReducer, useState } from "react";
 
 import { EditorStep } from "./pages/EditorStep";
 import { ExportStep } from "./pages/ExportStep";
+import { GrowthAssistantPanel } from "./components/GrowthAssistantPanel";
 import { KeywordStep } from "./pages/KeywordStep";
+import { ShortsCanvas } from "./components/ShortsCanvas";
 import { ScriptStep } from "./pages/ScriptStep";
+import { Timeline } from "./components/Timeline";
 import { TopStepNav } from "./components/TopStepNav";
 import { VoiceSubtitleStep } from "./pages/VoiceSubtitleStep";
 import { createInitialProjectState, reduceProjectState } from "./state/projectStore";
 import type { StepId } from "./types";
 import "./styles.css";
 
 export function App() {
   const [state, dispatch] = useReducer(reduceProjectState, createInitialProjectState());
+  const [selectedSceneIndex, setSelectedSceneIndex] = useState(1);
+
+  const scenes = [
+    { index: 1, subtitle: "오프닝", source_type: "ai_image", motion_type: "zoom-in" },
+    { index: 2, subtitle: "하이라이트", source_type: "ai_image", motion_type: "fade-in" },
+    { index: 3, subtitle: "콜투액션", source_type: "ai_image", motion_type: "pan-right" },
+  ];
+
+  const selectedScene = scenes.find((scene) => scene.index === selectedSceneIndex) ?? null;
+  const selectedSceneExists = scenes.some((scene) => scene.index === selectedSceneIndex);
 
   const handleStepChange = (step: StepId) => {
     dispatch({ type: "stepChanged", step });
   };
 
+  const handleSceneSelect = (index: number) => {
+    setSelectedSceneIndex(index);
+  };
+
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
-      <section className="workspace" aria-label="쇼츠 제작 작업 공간">
+      <section className="workspace" aria-label="쇼츠 편집 작업공간">
         <aside className="workspace-panel">{contentByStep[state.currentStep]}</aside>
-        <section className="preview-stage">9:16 미리보기와 작업 영역</section>
-        <aside className="workspace-panel">AI 보조와 성장 메모리</aside>
+        <section className="preview-stage">
+          <ShortsCanvas scene={selectedSceneExists ? selectedScene : null} />
+          <Timeline
+            scenes={scenes}
+            selectedSceneIndex={selectedSceneIndex}
+            onSelectScene={handleSceneSelect}
+          />
+        </section>
+        <aside className="workspace-panel">
+          <GrowthAssistantPanel
+            notes={["클릭률 향상을 위해 첫 3초 훅 메시지 강화", "자막 길이를 20자 이내로 간결히 정리"]}
+            recommendations={["첫 화면에서 핵심 결과 제시", "콜투액션을 끝 부분에 배치"]}
+          />
+        </aside>
       </section>
     </main>
   );
 }
diff --git a/shorts_growth_agent/frontend/src/components/GrowthAssistantPanel.tsx b/shorts_growth_agent/frontend/src/components/GrowthAssistantPanel.tsx
new file mode 100644
index 00000000..b6baf6a0
--- /dev/null
+++ b/shorts_growth_agent/frontend/src/components/GrowthAssistantPanel.tsx
@@ -0,0 +1,18 @@
+// 성장 메모리와 AI 보조 제안을 보여주는 패널이다.
+export function GrowthAssistantPanel({
+  notes,
+  recommendations,
+}: {
+  notes: string[];
+  recommendations: string[];
+}) {
+  return (
+    <aside aria-label="AI 보조와 성장 메모리" className="growth-panel">
+      <h2>성장 메모리</h2>
+      <ul>{notes.map((note) => <li key={note}>{note}</li>)}</ul>
+
+      <h2>다음 제안</h2>
+      <ul>{recommendations.map((item) => <li key={item}>{item}</li>)}</ul>
+    </aside>
+  );
+}
diff --git a/shorts_growth_agent/frontend/src/components/ShortsCanvas.tsx b/shorts_growth_agent/frontend/src/components/ShortsCanvas.tsx
new file mode 100644
index 00000000..7a91ebf3
--- /dev/null
+++ b/shorts_growth_agent/frontend/src/components/ShortsCanvas.tsx
@@ -0,0 +1,18 @@
+// 9:16 쇼츠 미리보기 캔버스 컴포넌트다.
+type SceneData = {
+  subtitle: string;
+  motion_type?: string;
+  source_type?: string;
+};
+
+export function ShortsCanvas({ scene }: { scene: SceneData | null }) {
+  return (
+    <section aria-label="쇼츠 미리보기" className="shorts-canvas">
+      <div className="phone-frame">
+        <div className="scene-source">{scene?.source_type ?? "ai_image"}</div>
+        <strong className="scene-subtitle">{scene?.subtitle ?? "장면을 선택하세요"}</strong>
+        {scene?.motion_type ? <p className="scene-motion">{scene.motion_type}</p> : null}
+      </div>
+    </section>
+  );
+}
diff --git a/shorts_growth_agent/frontend/src/components/Timeline.tsx b/shorts_growth_agent/frontend/src/components/Timeline.tsx
new file mode 100644
index 00000000..1c145220
--- /dev/null
+++ b/shorts_growth_agent/frontend/src/components/Timeline.tsx
@@ -0,0 +1,33 @@
+// 장면별 타임라인 선택 컴포넌트다.
+type SceneMeta = {
+  index: number;
+  subtitle: string;
+  duration_ms?: number;
+  motion_type?: string;
+};
+
+export function Timeline({
+  scenes,
+  selectedSceneIndex,
+  onSelectScene,
+}: {
+  scenes: SceneMeta[];
+  selectedSceneIndex: number;
+  onSelectScene: (index: number) => void;
+}) {
+  return (
+    <section aria-label="장면 타임라인" className="timeline">
+      {scenes.map((scene) => (
+        <button
+          key={scene.index}
+          type="button"
+          className="timeline-item"
+          aria-current={scene.index === selectedSceneIndex ? "true" : undefined}
+          onClick={() => onSelectScene(scene.index)}
+        >
+          장면 {scene.index}
+        </button>
+      ))}
+    </section>
+  );
+}
diff --git a/shorts_growth_agent/frontend/src/pages/GrowthReportPage.tsx b/shorts_growth_agent/frontend/src/pages/GrowthReportPage.tsx
new file mode 100644
index 00000000..2be5c6f6
--- /dev/null
+++ b/shorts_growth_agent/frontend/src/pages/GrowthReportPage.tsx
@@ -0,0 +1,9 @@
+// 시간별 성과 분석 리포트 화면이다.
+export function GrowthReportPage() {
+  return (
+    <section aria-label="성장 리포트">
+      <h1>시간별 성과 분석</h1>
+      <p>10분, 30분, 1시간, 24시간, 7일 단위 성과를 비교해 원인 후보를 좁힙니다.</p>
+    </section>
+  );
+}
diff --git a/shorts_growth_agent/frontend/src/styles.css b/shorts_growth_agent/frontend/src/styles.css
index 991ae3d1..0b0cda85 100644
--- a/shorts_growth_agent/frontend/src/styles.css
+++ b/shorts_growth_agent/frontend/src/styles.css
@@ -61,22 +61,93 @@ button {
 .preview-stage {
   border: 1px solid #d9dfeb;
   border-radius: 8px;
   background: #ffffff;
   padding: 16px;
   box-sizing: border-box;
 }
 
 .preview-stage {
   display: grid;
-  place-items: center;
+  gap: 10px;
   min-width: 0;
+  padding: 12px;
+}
+
+.shorts-canvas {
+  display: grid;
+  place-items: center;
+}
+
+.phone-frame {
+  width: min(360px, 100%);
+  aspect-ratio: 9 / 16;
+  border: 2px solid #d9dfeb;
+  border-radius: 20px;
+  background: #f3f6fb;
+  display: grid;
+  align-content: start;
+  gap: 8px;
+  padding: 12px;
+  box-sizing: border-box;
+  color: #17202f;
+}
+
+.scene-source {
+  color: #526071;
+  font-size: 12px;
+}
+
+.scene-subtitle {
+  font-size: 22px;
+  line-height: 1.4;
+}
+
+.scene-motion {
+  color: #526071;
+  font-size: 12px;
+  margin: 0;
+}
+
+.timeline {
+  display: grid;
+  gap: 6px;
+}
+
+.timeline-item {
+  justify-self: stretch;
+  padding: 8px 10px;
+  border: 1px solid #d9dfeb;
+  border-radius: 8px;
+  background: #ffffff;
+  cursor: pointer;
+  min-height: 34px;
+  text-align: left;
+}
+
+.timeline-item[aria-current="true"] {
+  border-color: #2557d6;
+  background: #eef3ff;
+}
+
+.growth-panel h2 {
+  margin: 0 0 8px 0;
+  font-size: 16px;
+}
+
+.growth-panel ul {
+  margin: 0 0 12px 0;
+  padding-left: 18px;
+}
+
+.growth-panel li {
+  margin-bottom: 4px;
 }
 
 @media (max-width: 860px) {
   .top-step-nav {
     overflow-x: auto;
   }
 
   .workspace {
     grid-template-columns: 1fr;
   }
diff --git a/shorts_growth_agent/frontend/tests/editorComponents.test.tsx b/shorts_growth_agent/frontend/tests/editorComponents.test.tsx
new file mode 100644
index 00000000..885943de
--- /dev/null
+++ b/shorts_growth_agent/frontend/tests/editorComponents.test.tsx
@@ -0,0 +1,52 @@
+// 편집 미리보기 컴포넌트의 기본 렌더링과 타임라인 선택을 검증한다.
+import { render, screen } from "@testing-library/react";
+import userEvent from "@testing-library/user-event";
+import { describe, expect, it, vi } from "vitest";
+import { GrowthAssistantPanel } from "../src/components/GrowthAssistantPanel";
+import { GrowthReportPage } from "../src/pages/GrowthReportPage";
+import { ShortsCanvas } from "../src/components/ShortsCanvas";
+import { Timeline } from "../src/components/Timeline";
+
+describe("editor components", () => {
+  it("shows placeholder text when no scene is selected", () => {
+    render(<ShortsCanvas scene={null} />);
+
+    expect(screen.getByText("장면을 선택하세요")).toBeTruthy();
+  });
+
+  it("selects a scene from the timeline", async () => {
+    const user = userEvent.setup();
+    const onSelectScene = vi.fn();
+
+    render(
+      <Timeline
+        scenes={[
+          { index: 1, subtitle: "첫 장면", motion_type: "zoom" },
+          { index: 2, subtitle: "둘째 장면", motion_type: "fade" },
+        ]}
+        selectedSceneIndex={1}
+        onSelectScene={onSelectScene}
+      />,
+    );
+
+    await user.click(screen.getByRole("button", { name: "장면 2" }));
+    expect(onSelectScene).toHaveBeenCalledWith(2);
+  });
+
+  it("renders growth assistant notes and recommendations", () => {
+    render(
+      <GrowthAssistantPanel notes={["CTR 개선"]} recommendations={["추천 문구를 앞부분으로 이동"]} />,
+    );
+
+    expect(screen.getByText("CTR 개선")).toBeTruthy();
+    expect(screen.getByText("추천 문구를 앞부분으로 이동")).toBeTruthy();
+  });
+
+  it("shows the growth report copy", () => {
+    render(<GrowthReportPage />);
+
+    expect(
+      screen.getByText("10분, 30분, 1시간, 24시간, 7일 단위 성과를 비교해 원인 후보를 좁힙니다."),
+    ).toBeTruthy();
+  });
+});
