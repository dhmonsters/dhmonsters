diff --git a/shorts_growth_agent/frontend/src/App.tsx b/shorts_growth_agent/frontend/src/App.tsx
index 9a1f29c6..9ec1b998 100644
--- a/shorts_growth_agent/frontend/src/App.tsx
+++ b/shorts_growth_agent/frontend/src/App.tsx
@@ -1,20 +1,39 @@
-// 상단 단계형 쇼츠 제작 화면의 기본 레이아웃이다.
-import { useState } from "react";
+// 쇼츠 제작 워크플로우를 전환하는 최상위 앱 화면입니다.
+import { useReducer } from "react";
 
+import { EditorStep } from "./pages/EditorStep";
+import { ExportStep } from "./pages/ExportStep";
+import { KeywordStep } from "./pages/KeywordStep";
+import { ScriptStep } from "./pages/ScriptStep";
 import { TopStepNav } from "./components/TopStepNav";
+import { VoiceSubtitleStep } from "./pages/VoiceSubtitleStep";
+import { createInitialProjectState, reduceProjectState } from "./state/projectStore";
 import type { StepId } from "./types";
+import "./styles.css";
 
 export function App() {
-  const [currentStep, setCurrentStep] = useState<StepId>("keyword");
+  const [state, dispatch] = useReducer(reduceProjectState, createInitialProjectState());
+
+  const handleStepChange = (step: StepId) => {
+    dispatch({ type: "stepChanged", step });
+  };
+
+  const contentByStep: Record<StepId, JSX.Element> = {
+    keyword: <KeywordStep />,
+    script: <ScriptStep />,
+    voice: <VoiceSubtitleStep />,
+    editor: <EditorStep />,
+    export: <ExportStep />,
+  };
 
   return (
     <main className="app-shell">
-      <TopStepNav currentStep={currentStep} onStepChange={setCurrentStep} />
-      <section className="workspace" aria-label="쇼츠 제작 작업 영역">
-        <aside className="workspace-panel">현재 단계 도구</aside>
+      <TopStepNav currentStep={state.currentStep} onStepChange={handleStepChange} />
+      <section className="workspace" aria-label="쇼츠 제작 작업 공간">
+        <aside className="workspace-panel">{contentByStep[state.currentStep]}</aside>
         <section className="preview-stage">9:16 미리보기와 작업 영역</section>
         <aside className="workspace-panel">AI 보조와 성장 메모리</aside>
       </section>
     </main>
   );
 }
diff --git a/shorts_growth_agent/frontend/src/api/client.ts b/shorts_growth_agent/frontend/src/api/client.ts
new file mode 100644
index 00000000..d046a67e
--- /dev/null
+++ b/shorts_growth_agent/frontend/src/api/client.ts
@@ -0,0 +1,24 @@
+// 백엔드 API 호출을 담당하는 클라이언트 유틸입니다.
+const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api";
+
+export async function createProject(payload: {
+  title: string;
+  category: string;
+  selected_keyword?: string;
+}) {
+  const response = await fetch(`${API_BASE}/projects`, {
+    method: "POST",
+    headers: { "Content-Type": "application/json" },
+    body: JSON.stringify(payload),
+  });
+  if (!response.ok) throw new Error("프로젝트 생성에 실패했습니다.");
+  return response.json();
+}
+
+export async function generatePlan(projectId: number) {
+  const response = await fetch(`${API_BASE}/projects/${projectId}/generate-plan`, {
+    method: "POST",
+  });
+  if (!response.ok) throw new Error("대본 계획 생성에 실패했습니다.");
+  return response.json();
+}
diff --git a/shorts_growth_agent/frontend/src/pages/EditorStep.tsx b/shorts_growth_agent/frontend/src/pages/EditorStep.tsx
new file mode 100644
index 00000000..2cdba88a
--- /dev/null
+++ b/shorts_growth_agent/frontend/src/pages/EditorStep.tsx
@@ -0,0 +1,4 @@
+// 쇼츠 장면과 레이어를 편집하는 화면이다.
+export function EditorStep() {
+  return <section aria-label="편집 단계">9:16 캔버스와 타임라인</section>;
+}
diff --git a/shorts_growth_agent/frontend/src/pages/ExportStep.tsx b/shorts_growth_agent/frontend/src/pages/ExportStep.tsx
new file mode 100644
index 00000000..3a105029
--- /dev/null
+++ b/shorts_growth_agent/frontend/src/pages/ExportStep.tsx
@@ -0,0 +1,4 @@
+// MP4 렌더링과 업로드 패키지를 만드는 화면이다.
+export function ExportStep() {
+  return <section aria-label="출력 단계">MP4 렌더링과 업로드 패키지</section>;
+}
diff --git a/shorts_growth_agent/frontend/src/pages/KeywordStep.tsx b/shorts_growth_agent/frontend/src/pages/KeywordStep.tsx
new file mode 100644
index 00000000..fe31c5fb
--- /dev/null
+++ b/shorts_growth_agent/frontend/src/pages/KeywordStep.tsx
@@ -0,0 +1,4 @@
+// 키워드와 카테고리 기반 소재 발굴 화면이다.
+export function KeywordStep() {
+  return <section aria-label="키워드 단계">한국 인기 영상과 키워드 추천</section>;
+}
diff --git a/shorts_growth_agent/frontend/src/pages/ScriptStep.tsx b/shorts_growth_agent/frontend/src/pages/ScriptStep.tsx
new file mode 100644
index 00000000..d4ec5dc3
--- /dev/null
+++ b/shorts_growth_agent/frontend/src/pages/ScriptStep.tsx
@@ -0,0 +1,4 @@
+// 대본 하네스와 장면 대본을 편집하는 화면이다.
+export function ScriptStep() {
+  return <section aria-label="대본 단계">대본 하네스와 장면 대본</section>;
+}
diff --git a/shorts_growth_agent/frontend/src/pages/VoiceSubtitleStep.tsx b/shorts_growth_agent/frontend/src/pages/VoiceSubtitleStep.tsx
new file mode 100644
index 00000000..7daa1807
--- /dev/null
+++ b/shorts_growth_agent/frontend/src/pages/VoiceSubtitleStep.tsx
@@ -0,0 +1,4 @@
+// TTS와 자막 싱크를 조정하는 화면이다.
+export function VoiceSubtitleStep() {
+  return <section aria-label="음성 자막 단계">TTS와 자막 자동 싱크</section>;
+}
diff --git a/shorts_growth_agent/frontend/src/state/projectStore.ts b/shorts_growth_agent/frontend/src/state/projectStore.ts
new file mode 100644
index 00000000..e3030c8b
--- /dev/null
+++ b/shorts_growth_agent/frontend/src/state/projectStore.ts
@@ -0,0 +1,35 @@
+// 쇼츠 제작 프로젝트 상태 전이와 초기 상태를 관리합니다.
+import type { StepId } from "../types";
+
+export type ScriptPlan = {
+  keyword: string;
+  scenes: Array<{ index: number; subtitle: string }>;
+};
+
+export type ProjectState = {
+  currentStep: StepId;
+  project: { id: number; title: string } | null;
+  scriptPlan: ScriptPlan | null;
+};
+
+export type ProjectAction =
+  | { type: "projectCreated"; project: { id: number; title: string } }
+  | { type: "planGenerated"; plan: ScriptPlan }
+  | { type: "stepChanged"; step: StepId };
+
+export function createInitialProjectState(): ProjectState {
+  return { currentStep: "keyword", project: null, scriptPlan: null };
+}
+
+export function reduceProjectState(state: ProjectState, action: ProjectAction): ProjectState {
+  if (action.type === "projectCreated") {
+    return { ...state, project: action.project, currentStep: "script" };
+  }
+  if (action.type === "planGenerated") {
+    return { ...state, scriptPlan: action.plan, currentStep: "script" };
+  }
+  if (action.type === "stepChanged") {
+    return { ...state, currentStep: action.step };
+  }
+  return state;
+}
diff --git a/shorts_growth_agent/frontend/tests/projectStore.test.ts b/shorts_growth_agent/frontend/tests/projectStore.test.ts
new file mode 100644
index 00000000..ab6beeb4
--- /dev/null
+++ b/shorts_growth_agent/frontend/tests/projectStore.test.ts
@@ -0,0 +1,35 @@
+// projectStore 상태 전이 동작을 검증하기 위한 테스트 모음.
+import { describe, expect, it } from "vitest";
+import { createInitialProjectState, reduceProjectState } from "../src/state/projectStore";
+
+describe("projectStore", () => {
+  it("stores generated script plan and advances to script step", () => {
+    const state = createInitialProjectState();
+    const next = reduceProjectState(state, {
+      type: "planGenerated",
+      plan: { keyword: "업데이트", scenes: [{ index: 1, subtitle: "첫 문장" }] },
+    });
+
+    expect(next.scriptPlan?.keyword).toBe("업데이트");
+    expect(next.currentStep).toBe("script");
+  });
+
+  it("stores created project and advances to script step", () => {
+    const state = createInitialProjectState();
+    const next = reduceProjectState(state, {
+      type: "projectCreated",
+      project: { id: 1, title: "게임 이슈" },
+    });
+
+    expect(next.project?.title).toBe("게임 이슈");
+    expect(next.currentStep).toBe("script");
+  });
+
+  it("moves to requested step", () => {
+    const state = createInitialProjectState();
+    const next = reduceProjectState(state, { type: "stepChanged", step: "editor" });
+
+    expect(next.currentStep).toBe("editor");
+    expect(next.project).toBeNull();
+  });
+});
