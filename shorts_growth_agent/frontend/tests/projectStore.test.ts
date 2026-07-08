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

  it("stores selected trend candidate for later script generation", () => {
    const state = createInitialProjectState();
    const next = reduceProjectState(state, {
      type: "trendSelected",
      trend: {
        video_id: "sample-game-001",
        title: "신작 게임 업데이트 보상 정리와 반응",
        category_id: "20",
        channel_title: "게임 이슈 연구소",
        view_count: 320000,
        views_per_hour: 100000,
        score: 100020,
        keyword_candidates: ["게임", "업데이트"],
        thumbnail_url: "",
      },
    });

    expect(next.selectedTrend?.video_id).toBe("sample-game-001");
  });

  it("updates section customization without changing the current step", () => {
    const state = createInitialProjectState();
    const next = reduceProjectState(state, {
      type: "customizationChanged",
      section: "script",
      value: "강한 훅, 짧은 문장, 45초",
    });

    expect(next.customization.script).toBe("강한 훅, 짧은 문장, 45초");
    expect(next.currentStep).toBe("keyword");
  });
});
