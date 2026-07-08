# Task 10 Brief: Frontend Scaffold And Top-Step Layout

## Goal

Create the first frontend shell for the Shorts Growth Agent with a compact top step navigation.

## Scope

Create only the frontend scaffold needed for a working test and a basic app shell.

Required files:

- `shorts_growth_agent/frontend/package.json`
- `shorts_growth_agent/frontend/index.html`
- `shorts_growth_agent/frontend/src/main.tsx`
- `shorts_growth_agent/frontend/src/App.tsx`
- `shorts_growth_agent/frontend/src/types.ts`
- `shorts_growth_agent/frontend/src/components/TopStepNav.tsx`
- `shorts_growth_agent/frontend/tests/TopStepNav.test.tsx`
- `.superpowers/sdd/task-10-report.md`

Allowed minimal support files if needed for tests/build:

- `shorts_growth_agent/frontend/tsconfig.json`
- `shorts_growth_agent/frontend/tsconfig.node.json`
- `shorts_growth_agent/frontend/vite.config.ts`
- `shorts_growth_agent/frontend/src/styles.css`
- `shorts_growth_agent/frontend/src/vite-env.d.ts`

Do not implement Task 11 page/store behavior yet.

## Required Behavior

- Step ids are exactly `keyword`, `script`, `voice`, `editor`, `export`.
- `TopStepNav({ currentStep, onStepChange })` renders compact top navigation buttons.
- The current step button has `aria-current="step"`.
- Clicking another step calls `onStepChange(stepId)`.
- `App` renders the top step nav and a three-zone workspace shell for tools, 9:16 preview/work area, and AI/growth memory.

## Test First

Create `shorts_growth_agent/frontend/tests/TopStepNav.test.tsx`.

```tsx
// 상단 단계 표시 UI가 현재 단계를 표시하는지 검증한다.
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TopStepNav } from "../src/components/TopStepNav";

describe("TopStepNav", () => {
  it("marks the current step", () => {
    render(<TopStepNav currentStep="script" onStepChange={vi.fn()} />);

    expect(screen.getByRole("button", { name: "대본" })).toHaveAttribute("aria-current", "step");
  });
});
```

Add a small click test if it stays simple.

Run it before implementation.

Use `npm.cmd`, not `npm`, because PowerShell blocks `npm.ps1` on this machine.

```powershell
npm.cmd test -- TopStepNav.test.tsx
```

Expected first failure: missing package setup or missing `TopStepNav`.

## Package Setup

Use Vite, React, TypeScript, Vitest, Testing Library, and jsdom.

Minimum package requirements:

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "test": "vitest run"
  },
  "dependencies": {
    "@vitejs/plugin-react": "^4.3.0",
    "vite": "^5.4.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.4.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/user-event": "^14.5.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "jsdom": "^24.1.0",
    "typescript": "^5.5.0",
    "vitest": "^2.0.0"
  }
}
```

Run `npm.cmd install` after writing `package.json`.

## Implementation Notes

`src/types.ts`.

```ts
// 쇼츠 제작 단계 타입을 정의한다.
export type StepId = "keyword" | "script" | "voice" | "editor" | "export";
```

`src/components/TopStepNav.tsx`.

```tsx
// 상단의 작은 제작 단계 표시 컴포넌트다.
import type { StepId } from "../types";

const STEPS: Array<{ id: StepId; label: string }> = [
  { id: "keyword", label: "키워드" },
  { id: "script", label: "대본" },
  { id: "voice", label: "음성/자막" },
  { id: "editor", label: "편집" },
  { id: "export", label: "출력" },
];

export function TopStepNav({
  currentStep,
  onStepChange,
}: {
  currentStep: StepId;
  onStepChange: (step: StepId) => void;
}) {
  return (
    <nav className="top-step-nav" aria-label="쇼츠 제작 단계">
      {STEPS.map((step) => (
        <button
          key={step.id}
          type="button"
          aria-current={currentStep === step.id ? "step" : undefined}
          onClick={() => onStepChange(step.id)}
        >
          {step.label}
        </button>
      ))}
    </nav>
  );
}
```

`src/App.tsx`.

```tsx
// 상단 단계형 쇼츠 제작 화면의 기본 레이아웃이다.
import { useState } from "react";
import { TopStepNav } from "./components/TopStepNav";
import type { StepId } from "./types";

export function App() {
  const [currentStep, setCurrentStep] = useState<StepId>("keyword");

  return (
    <main>
      <TopStepNav currentStep={currentStep} onStepChange={setCurrentStep} />
      <section className="workspace">
        <aside>현재 단계 도구</aside>
        <section>9:16 미리보기와 작업 영역</section>
        <aside>AI 보조와 성장 메모리</aside>
      </section>
    </main>
  );
}
```

Keep styling restrained and work-focused. Use a compact top step bar, stable workspace columns, and avoid card-heavy landing page styling.

## Verification

Run these from `shorts_growth_agent/frontend`.

```powershell
npm.cmd test -- TopStepNav.test.tsx
npm.cmd run build
```

Report red test output, install/build/test results, and changed files in `.superpowers/sdd/task-10-report.md`.
