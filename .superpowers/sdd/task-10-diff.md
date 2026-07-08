diff --git a/shorts_growth_agent/frontend/.gitignore b/shorts_growth_agent/frontend/.gitignore
new file mode 100644
index 00000000..8370e904
--- /dev/null
+++ b/shorts_growth_agent/frontend/.gitignore
@@ -0,0 +1,6 @@
+node_modules/
+.npm-cache/
+dist/
+*.tsbuildinfo
+vite.config.js
+vite.config.d.ts
diff --git a/shorts_growth_agent/frontend/index.html b/shorts_growth_agent/frontend/index.html
new file mode 100644
index 00000000..38557a87
--- /dev/null
+++ b/shorts_growth_agent/frontend/index.html
@@ -0,0 +1,12 @@
+<!doctype html>
+<html lang="en">
+  <head>
+    <meta charset="UTF-8" />
+    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
+    <title>Shorts Growth Agent</title>
+  </head>
+  <body>
+    <div id="root"></div>
+    <script type="module" src="/src/main.tsx"></script>
+  </body>
+</html>
diff --git a/shorts_growth_agent/frontend/package.json b/shorts_growth_agent/frontend/package.json
new file mode 100644
index 00000000..64e385e3
--- /dev/null
+++ b/shorts_growth_agent/frontend/package.json
@@ -0,0 +1,28 @@
+{
+  "name": "shorts-growth-agent-frontend",
+  "private": true,
+  "version": "0.0.0",
+  "type": "module",
+  "scripts": {
+    "dev": "vite",
+    "build": "tsc -b && vite build",
+    "test": "vitest run"
+  },
+  "dependencies": {
+    "@vitejs/plugin-react": "^4.3.0",
+    "react": "^18.3.1",
+    "react-dom": "^18.3.1",
+    "vite": "^5.4.0"
+  },
+  "devDependencies": {
+    "@testing-library/jest-dom": "^6.4.0",
+    "@testing-library/react": "^16.0.0",
+    "@testing-library/user-event": "^14.5.0",
+    "@types/node": "^26.1.0",
+    "@types/react": "^18.3.0",
+    "@types/react-dom": "^18.3.0",
+    "jsdom": "^24.1.0",
+    "typescript": "^5.5.0",
+    "vitest": "^2.0.0"
+  }
+}
diff --git a/shorts_growth_agent/frontend/src/App.tsx b/shorts_growth_agent/frontend/src/App.tsx
new file mode 100644
index 00000000..9a1f29c6
--- /dev/null
+++ b/shorts_growth_agent/frontend/src/App.tsx
@@ -0,0 +1,20 @@
+// 상단 단계형 쇼츠 제작 화면의 기본 레이아웃이다.
+import { useState } from "react";
+
+import { TopStepNav } from "./components/TopStepNav";
+import type { StepId } from "./types";
+
+export function App() {
+  const [currentStep, setCurrentStep] = useState<StepId>("keyword");
+
+  return (
+    <main className="app-shell">
+      <TopStepNav currentStep={currentStep} onStepChange={setCurrentStep} />
+      <section className="workspace" aria-label="쇼츠 제작 작업 영역">
+        <aside className="workspace-panel">현재 단계 도구</aside>
+        <section className="preview-stage">9:16 미리보기와 작업 영역</section>
+        <aside className="workspace-panel">AI 보조와 성장 메모리</aside>
+      </section>
+    </main>
+  );
+}
diff --git a/shorts_growth_agent/frontend/src/components/TopStepNav.tsx b/shorts_growth_agent/frontend/src/components/TopStepNav.tsx
new file mode 100644
index 00000000..d0088979
--- /dev/null
+++ b/shorts_growth_agent/frontend/src/components/TopStepNav.tsx
@@ -0,0 +1,33 @@
+// 상단의 작은 제작 단계 표시 컴포넌트다.
+import type { StepId } from "../types";
+
+const STEPS: Array<{ id: StepId; label: string }> = [
+  { id: "keyword", label: "키워드" },
+  { id: "script", label: "대본" },
+  { id: "voice", label: "음성/자막" },
+  { id: "editor", label: "편집" },
+  { id: "export", label: "출력" },
+];
+
+export function TopStepNav({
+  currentStep,
+  onStepChange,
+}: {
+  currentStep: StepId;
+  onStepChange: (step: StepId) => void;
+}) {
+  return (
+    <nav className="top-step-nav" aria-label="쇼츠 제작 단계">
+      {STEPS.map((step) => (
+        <button
+          key={step.id}
+          type="button"
+          aria-current={currentStep === step.id ? "step" : undefined}
+          onClick={() => onStepChange(step.id)}
+        >
+          {step.label}
+        </button>
+      ))}
+    </nav>
+  );
+}
diff --git a/shorts_growth_agent/frontend/src/main.tsx b/shorts_growth_agent/frontend/src/main.tsx
new file mode 100644
index 00000000..81643d19
--- /dev/null
+++ b/shorts_growth_agent/frontend/src/main.tsx
@@ -0,0 +1,12 @@
+// React 앱을 브라우저 루트에 마운트한다.
+import React from "react";
+import ReactDOM from "react-dom/client";
+
+import { App } from "./App";
+import "./styles.css";
+
+ReactDOM.createRoot(document.getElementById("root")!).render(
+  <React.StrictMode>
+    <App />
+  </React.StrictMode>,
+);
diff --git a/shorts_growth_agent/frontend/src/styles.css b/shorts_growth_agent/frontend/src/styles.css
new file mode 100644
index 00000000..991ae3d1
--- /dev/null
+++ b/shorts_growth_agent/frontend/src/styles.css
@@ -0,0 +1,83 @@
+/* 쇼츠 제작 앱의 기본 화면 밀도와 단계형 작업 레이아웃을 정의한다. */
+:root {
+  color-scheme: light;
+  background: #f7f8fb;
+  color: #17202f;
+  font-family:
+    Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
+}
+
+body {
+  margin: 0;
+}
+
+button {
+  font: inherit;
+}
+
+.app-shell {
+  min-height: 100vh;
+  padding: 16px;
+  box-sizing: border-box;
+}
+
+.top-step-nav {
+  display: flex;
+  align-items: center;
+  gap: 6px;
+  padding: 6px;
+  border: 1px solid #d9dfeb;
+  border-radius: 8px;
+  background: #ffffff;
+}
+
+.top-step-nav button {
+  min-height: 34px;
+  padding: 0 12px;
+  border: 1px solid transparent;
+  border-radius: 6px;
+  background: transparent;
+  color: #526071;
+  cursor: pointer;
+  white-space: nowrap;
+}
+
+.top-step-nav button[aria-current="step"] {
+  border-color: #2557d6;
+  background: #eef3ff;
+  color: #163f9f;
+  font-weight: 700;
+}
+
+.workspace {
+  display: grid;
+  grid-template-columns: minmax(180px, 260px) minmax(320px, 1fr) minmax(200px, 280px);
+  gap: 12px;
+  margin-top: 12px;
+  min-height: calc(100vh - 84px);
+}
+
+.workspace-panel,
+.preview-stage {
+  border: 1px solid #d9dfeb;
+  border-radius: 8px;
+  background: #ffffff;
+  padding: 16px;
+  box-sizing: border-box;
+}
+
+.preview-stage {
+  display: grid;
+  place-items: center;
+  min-width: 0;
+}
+
+@media (max-width: 860px) {
+  .top-step-nav {
+    overflow-x: auto;
+  }
+
+  .workspace {
+    grid-template-columns: 1fr;
+  }
+}
diff --git a/shorts_growth_agent/frontend/src/types.ts b/shorts_growth_agent/frontend/src/types.ts
new file mode 100644
index 00000000..88b5fbcb
--- /dev/null
+++ b/shorts_growth_agent/frontend/src/types.ts
@@ -0,0 +1,2 @@
+// 쇼츠 제작 단계 타입을 정의한다.
+export type StepId = "keyword" | "script" | "voice" | "editor" | "export";
diff --git a/shorts_growth_agent/frontend/src/vite-env.d.ts b/shorts_growth_agent/frontend/src/vite-env.d.ts
new file mode 100644
index 00000000..11f02fe2
--- /dev/null
+++ b/shorts_growth_agent/frontend/src/vite-env.d.ts
@@ -0,0 +1 @@
+/// <reference types="vite/client" />
diff --git a/shorts_growth_agent/frontend/tests/TopStepNav.test.tsx b/shorts_growth_agent/frontend/tests/TopStepNav.test.tsx
new file mode 100644
index 00000000..74502006
--- /dev/null
+++ b/shorts_growth_agent/frontend/tests/TopStepNav.test.tsx
@@ -0,0 +1,25 @@
+// 상단 단계 표시 UI가 현재 단계를 표시하는지 검증한다.
+import { render, screen } from "@testing-library/react";
+import userEvent from "@testing-library/user-event";
+import { describe, expect, it, vi } from "vitest";
+import { TopStepNav } from "../src/components/TopStepNav";
+
+describe("TopStepNav", () => {
+  it("marks the current step", () => {
+    render(<TopStepNav currentStep="script" onStepChange={vi.fn()} />);
+
+    expect(screen.getByRole("button", { name: "대본" }).getAttribute("aria-current")).toBe(
+      "step"
+    );
+  });
+
+  it("calls onStepChange when selecting another step", async () => {
+    const user = userEvent.setup();
+    const onStepChange = vi.fn();
+
+    render(<TopStepNav currentStep="keyword" onStepChange={onStepChange} />);
+
+    await user.click(screen.getByRole("button", { name: "대본" }));
+    expect(onStepChange).toHaveBeenCalledWith("script");
+  });
+});
diff --git a/shorts_growth_agent/frontend/tsconfig.json b/shorts_growth_agent/frontend/tsconfig.json
new file mode 100644
index 00000000..3eafddc9
--- /dev/null
+++ b/shorts_growth_agent/frontend/tsconfig.json
@@ -0,0 +1,17 @@
+{
+  "compilerOptions": {
+    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.tsbuildinfo",
+    "target": "ES2022",
+    "module": "ESNext",
+    "moduleResolution": "Bundler",
+    "allowImportingTsExtensions": true,
+    "moduleDetection": "force",
+    "noEmit": true,
+    "jsx": "react-jsx",
+    "strict": true,
+    "skipLibCheck": true,
+    "isolatedModules": true,
+    "types": ["vite/client", "node"]
+  },
+  "include": ["src", "tests", "vite.config.ts"]
+}
diff --git a/shorts_growth_agent/frontend/tsconfig.node.json b/shorts_growth_agent/frontend/tsconfig.node.json
new file mode 100644
index 00000000..4a14b5a5
--- /dev/null
+++ b/shorts_growth_agent/frontend/tsconfig.node.json
@@ -0,0 +1,14 @@
+{
+  "compilerOptions": {
+    "composite": true,
+    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.node.tsbuildinfo",
+    "target": "ES2022",
+    "module": "ESNext",
+    "moduleResolution": "Bundler",
+    "allowSyntheticDefaultImports": true,
+    "strict": true,
+    "skipLibCheck": true,
+    "types": ["node"]
+  },
+  "include": ["vite.config.ts"]
+}
diff --git a/shorts_growth_agent/frontend/vite.config.ts b/shorts_growth_agent/frontend/vite.config.ts
new file mode 100644
index 00000000..fb671769
--- /dev/null
+++ b/shorts_growth_agent/frontend/vite.config.ts
@@ -0,0 +1,21 @@
+import { dirname } from "node:path";
+import { realpathSync } from "node:fs";
+import { fileURLToPath } from "node:url";
+import react from "@vitejs/plugin-react";
+import { defineConfig } from "vitest/config";
+
+const projectRoot = dirname(fileURLToPath(import.meta.url));
+const realProjectRoot = realpathSync.native(projectRoot);
+
+export default defineConfig({
+  plugins: [react()],
+  server: {
+    fs: {
+      allow: [projectRoot, realProjectRoot],
+    },
+  },
+  test: {
+    environment: "jsdom",
+    globals: true,
+  },
+});
