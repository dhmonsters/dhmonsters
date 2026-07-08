// 단계별 집중 레이아웃의 노출 규칙을 검증합니다.
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../src/App";

function stubTrendFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        source: "sample",
        items: [
          {
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
        ],
      }),
    }),
  );
}

describe("App focused layout", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("keeps keyword step focused on trend search", async () => {
    stubTrendFetch();

    render(<App />);

    expect(screen.getByLabelText("키워드 단계")).toBeTruthy();
    expect(screen.queryByLabelText("쇼츠 미리보기")).toBeNull();
    expect(screen.queryByLabelText("장면 타임라인")).toBeNull();
    expect(screen.queryByLabelText("AI 보조와 성장 메모리")).toBeNull();
    expect(await screen.findByText("신작 게임 업데이트 보상 정리와 반응")).toBeTruthy();
  });

  it("shows preview and timeline only on editor step", async () => {
    const user = userEvent.setup();
    stubTrendFetch();

    render(<App />);
    await user.click(screen.getByRole("button", { name: "편집" }));

    expect(screen.getByLabelText("쇼츠 미리보기")).toBeTruthy();
    expect(screen.getByLabelText("장면 타임라인")).toBeTruthy();
  });
});
