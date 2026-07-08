# Task 12 Brief: Preview Canvas, Timeline, And Growth Panel

## Goal

Add the first visible editing-surface components for a Shorts workspace: 9:16 preview, scene timeline, and growth assistant panel.

## Scope

Create or modify only these files unless a test/build failure proves a directly related fix is required.

- `shorts_growth_agent/frontend/src/components/ShortsCanvas.tsx`
- `shorts_growth_agent/frontend/src/components/Timeline.tsx`
- `shorts_growth_agent/frontend/src/components/GrowthAssistantPanel.tsx`
- `shorts_growth_agent/frontend/src/pages/GrowthReportPage.tsx`
- `shorts_growth_agent/frontend/src/App.tsx`
- `shorts_growth_agent/frontend/src/styles.css`
- `shorts_growth_agent/frontend/tests/editorComponents.test.tsx`
- `.superpowers/sdd/task-12-report.md`

Do not implement backend calls, drag editing, real media upload, render execution, or Task 13 smoke tests.

## Required Behavior

- `ShortsCanvas({ scene })` renders a 9:16 preview region.
- When no scene is selected, `ShortsCanvas` displays `장면을 선택하세요`.
- `Timeline({ scenes, selectedSceneIndex, onSelectScene })` renders one button per scene.
- The selected timeline button uses `aria-current="true"`.
- Clicking a timeline button calls `onSelectScene(scene.index)`.
- `GrowthAssistantPanel({ notes, recommendations })` renders notes and recommendations.
- `GrowthReportPage` renders the time-based performance report copy.
- `App` keeps the 3-zone shell and replaces placeholder middle/right zones with the new preview/timeline and growth assistant components using simple sample data.

## Test First

Create `shorts_growth_agent/frontend/tests/editorComponents.test.tsx`.

Recommended tests:

```tsx
// 편집 미리보기 컴포넌트의 기본 렌더링과 타임라인 선택을 검증한다.
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ShortsCanvas } from "../src/components/ShortsCanvas";
import { Timeline } from "../src/components/Timeline";
import { GrowthAssistantPanel } from "../src/components/GrowthAssistantPanel";

describe("editor components", () => {
  it("shows placeholder text when no scene is selected", () => {
    render(<ShortsCanvas scene={null} />);

    expect(screen.getByText("장면을 선택하세요")).toBeTruthy();
  });

  it("selects a scene from the timeline", async () => {
    const user = userEvent.setup();
    const onSelectScene = vi.fn();

    render(
      <Timeline
        scenes={[
          { index: 1, subtitle: "첫 장면" },
          { index: 2, subtitle: "둘째 장면" },
        ]}
        selectedSceneIndex={1}
        onSelectScene={onSelectScene}
      />,
    );

    await user.click(screen.getByRole("button", { name: "장면 2" }));
    expect(onSelectScene).toHaveBeenCalledWith(2);
  });

  it("renders growth assistant notes and recommendations", () => {
    render(<GrowthAssistantPanel notes={["CTR 하락"]} recommendations={["첫 3초 보강"]} />);

    expect(screen.getByText("CTR 하락")).toBeTruthy();
    expect(screen.getByText("첫 3초 보강")).toBeTruthy();
  });
});
```

Run it before implementation.

```powershell
cmd /c "subst X: C:\Users\PC\Desktop\02_work\05_AI\shorts_growth_agent\frontend && X: && npm.cmd test -- editorComponents.test.tsx"
```

Expected first failure: missing editor components.

## Implementation Notes

`ShortsCanvas.tsx`.

```tsx
// 9:16 쇼츠 미리보기 캔버스 컴포넌트다.
export function ShortsCanvas({
  scene,
}: {
  scene: { subtitle: string; motion_type?: string; source_type?: string } | null;
}) {
  return (
    <section aria-label="쇼츠 미리보기" className="shorts-canvas">
      <div className="phone-frame">
        <div className="scene-source">{scene?.source_type ?? "ai_image"}</div>
        <strong className="scene-subtitle">{scene?.subtitle ?? "장면을 선택하세요"}</strong>
      </div>
    </section>
  );
}
```

`Timeline.tsx`.

```tsx
// 장면별 타임라인 선택 컴포넌트다.
export function Timeline({
  scenes,
  selectedSceneIndex,
  onSelectScene,
}: {
  scenes: Array<{ index: number; subtitle: string; duration_ms?: number }>;
  selectedSceneIndex: number;
  onSelectScene: (index: number) => void;
}) {
  return (
    <section aria-label="장면 타임라인" className="timeline">
      {scenes.map((scene) => (
        <button
          key={scene.index}
          type="button"
          aria-current={scene.index === selectedSceneIndex ? "true" : undefined}
          onClick={() => onSelectScene(scene.index)}
        >
          장면 {scene.index}
        </button>
      ))}
    </section>
  );
}
```

`GrowthAssistantPanel.tsx`.

```tsx
// 성장 메모리와 AI 보조 제안을 보여주는 패널이다.
export function GrowthAssistantPanel({
  notes,
  recommendations,
}: {
  notes: string[];
  recommendations: string[];
}) {
  return (
    <aside aria-label="AI 보조와 성장 메모리">
      <h2>성장 메모리</h2>
      <ul>{notes.map((note) => <li key={note}>{note}</li>)}</ul>
      <h2>다음 제안</h2>
      <ul>{recommendations.map((item) => <li key={item}>{item}</li>)}</ul>
    </aside>
  );
}
```

`GrowthReportPage.tsx`.

```tsx
// 시간별 성과 분석 리포트 화면이다.
export function GrowthReportPage() {
  return (
    <section aria-label="성장 리포트">
      <h1>시간별 성과 분석</h1>
      <p>10분, 30분, 1시간, 24시간, 7일 단위 성과를 비교해 원인 후보를 좁힙니다.</p>
    </section>
  );
}
```

Keep visual styling restrained and work-focused. Preserve stable dimensions for the 9:16 preview, timeline buttons, and panel layout.

## Verification

Run these from the workspace root.

```powershell
cmd /c "subst X: C:\Users\PC\Desktop\02_work\05_AI\shorts_growth_agent\frontend && X: && npm.cmd test -- editorComponents.test.tsx"
cmd /c "subst X: C:\Users\PC\Desktop\02_work\05_AI\shorts_growth_agent\frontend && X: && npm.cmd test -- TopStepNav.test.tsx projectStore.test.ts editorComponents.test.tsx"
cmd /c "subst X: C:\Users\PC\Desktop\02_work\05_AI\shorts_growth_agent\frontend && X: && npm.cmd run build"
```

Report red test output, green test/build output, and changed files in `.superpowers/sdd/task-12-report.md`.
