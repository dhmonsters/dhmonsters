// projectStore 상태 전이 동작을 검증하기 위한 테스트 모음.
import { describe, expect, it } from "vitest";
import { createInitialProjectState, reduceProjectState } from "../src/state/projectStore";

describe("projectStore", () => {
  it("stores generated script plan and advances to script step", () => {
    const state = createInitialProjectState();
    const next = reduceProjectState(state, {
      type: "planGenerated",
      plan: { keyword: "업데이트", scenes: [{ index: 1, subtitle: "첫 문장" }] },
    });

    expect(next.scriptPlan?.keyword).toBe("업데이트");
    expect(next.currentStep).toBe("script");
  });

  it("stores created project and advances to script step", () => {
    const state = createInitialProjectState();
    const next = reduceProjectState(state, {
      type: "projectCreated",
      project: { id: 1, title: "게임 이슈" },
    });

    expect(next.project?.title).toBe("게임 이슈");
    expect(next.currentStep).toBe("script");
  });

  it("moves to requested step", () => {
    const state = createInitialProjectState();
    const next = reduceProjectState(state, { type: "stepChanged", step: "editor" });

    expect(next.currentStep).toBe("editor");
    expect(next.project).toBeNull();
  });
});
