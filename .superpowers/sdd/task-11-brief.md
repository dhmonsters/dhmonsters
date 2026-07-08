# Task 11 Brief: Frontend Project Store And Step Pages

## Goal

Add the frontend state layer and simple step pages that sit behind the top-step shell.

## Scope

Create or modify only these files unless a test/build failure proves a directly related fix is required.

- `shorts_growth_agent/frontend/src/api/client.ts`
- `shorts_growth_agent/frontend/src/state/projectStore.ts`
- `shorts_growth_agent/frontend/src/pages/KeywordStep.tsx`
- `shorts_growth_agent/frontend/src/pages/ScriptStep.tsx`
- `shorts_growth_agent/frontend/src/pages/VoiceSubtitleStep.tsx`
- `shorts_growth_agent/frontend/src/pages/EditorStep.tsx`
- `shorts_growth_agent/frontend/src/pages/ExportStep.tsx`
- `shorts_growth_agent/frontend/src/App.tsx`
- `shorts_growth_agent/frontend/tests/projectStore.test.ts`
- `.superpowers/sdd/task-11-report.md`

Do not implement Task 12 preview canvas, timeline, or growth report components yet.

## Required Behavior

- `createProject(payload)` calls `POST /api/projects`.
- `generatePlan(projectId)` calls `POST /api/projects/{projectId}/generate-plan`.
- `createInitialProjectState()` returns `{ currentStep: "keyword", project: null, scriptPlan: null }`.
- `reduceProjectState()` handles `projectCreated`, `planGenerated`, and `stepChanged`.
- Generated plan moves `currentStep` to `script`.
- App shell renders the correct simple page for the current top step.

## Test First

Create `shorts_growth_agent/frontend/tests/projectStore.test.ts`.

```ts
// 프로젝트 상태 저장소가 생성 결과와 대본 계획을 보관하는지 검증한다.
import { describe, expect, it } from "vitest";
import { createInitialProjectState, reduceProjectState } from "../src/state/projectStore";

describe("projectStore", () => {
  it("stores generated script plan", () => {
    const state = createInitialProjectState();
    const next = reduceProjectState(state, {
      type: "planGenerated",
      plan: { keyword: "업데이트", scenes: [{ index: 1, subtitle: "첫 문장" }] },
    });

    expect(next.scriptPlan?.keyword).toBe("업데이트");
    expect(next.currentStep).toBe("script");
  });
});
```

Add a small step change test if it stays simple.

Run it before implementation.

Use the same subst pattern as Task 10 because the local sandbox blocks Vitest's parent-directory scan.

```powershell
cmd /c "subst X: C:\Users\PC\Desktop\02_work\05_AI\shorts_growth_agent\frontend && X: && npm.cmd test -- projectStore.test.ts"
```

Expected first failure: missing `projectStore`.

## Implementation Notes

`src/api/client.ts`.

```ts
// 백엔드 API 호출을 담당한다.
const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api";

export async function createProject(payload: {
  title: string;
  category: string;
  selected_keyword?: string;
}) {
  const response = await fetch(`${API_BASE}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("프로젝트 생성에 실패했습니다.");
  return response.json();
}

export async function generatePlan(projectId: number) {
  const response = await fetch(`${API_BASE}/projects/${projectId}/generate-plan`, {
    method: "POST",
  });
  if (!response.ok) throw new Error("대본 계획 생성에 실패했습니다.");
  return response.json();
}
```

`src/state/projectStore.ts`.

```ts
// 쇼츠 프로젝트 화면 상태를 관리한다.
import type { StepId } from "../types";

export type ScriptPlan = {
  keyword: string;
  scenes: Array<{ index: number; subtitle: string }>;
};

export type ProjectState = {
  currentStep: StepId;
  project: { id: number; title: string } | null;
  scriptPlan: ScriptPlan | null;
};

export type ProjectAction =
  | { type: "projectCreated"; project: { id: number; title: string } }
  | { type: "planGenerated"; plan: ScriptPlan }
  | { type: "stepChanged"; step: StepId };

export function createInitialProjectState(): ProjectState {
  return { currentStep: "keyword", project: null, scriptPlan: null };
}

export function reduceProjectState(state: ProjectState, action: ProjectAction): ProjectState {
  if (action.type === "projectCreated") {
    return { ...state, project: action.project, currentStep: "script" };
  }
  if (action.type === "planGenerated") {
    return { ...state, scriptPlan: action.plan, currentStep: "script" };
  }
  if (action.type === "stepChanged") {
    return { ...state, currentStep: action.step };
  }
  return state;
}
```

Step page files:

- `KeywordStep`: `aria-label="키워드 단계"` and text `한국 인기 영상과 키워드 추천`.
- `ScriptStep`: `aria-label="대본 단계"` and text `대본 하네스와 장면 대본`.
- `VoiceSubtitleStep`: `aria-label="음성 자막 단계"` and text `TTS와 자막 자동 싱크`.
- `EditorStep`: `aria-label="편집 단계"` and text `9:16 캔버스와 타임라인`.
- `ExportStep`: `aria-label="출력 단계"` and text `MP4 렌더링과 업로드 패키지`.

Update `App.tsx` to render the selected page inside the main work area. Keep the shell simple and do not add real form submission yet.

## Verification

Run these from the workspace root.

```powershell
cmd /c "subst X: C:\Users\PC\Desktop\02_work\05_AI\shorts_growth_agent\frontend && X: && npm.cmd test -- projectStore.test.ts"
cmd /c "subst X: C:\Users\PC\Desktop\02_work\05_AI\shorts_growth_agent\frontend && X: && npm.cmd test -- TopStepNav.test.tsx projectStore.test.ts"
cmd /c "subst X: C:\Users\PC\Desktop\02_work\05_AI\shorts_growth_agent\frontend && X: && npm.cmd run build"
```

Report red test output, green test/build output, and changed files in `.superpowers/sdd/task-11-report.md`.
