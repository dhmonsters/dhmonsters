// 키워드 단계에서 트렌드 후보 검색과 선택 동작을 검증합니다.
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { KeywordStep } from "../src/pages/KeywordStep";

describe("KeywordStep", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows trend candidates after searching", async () => {
    const user = userEvent.setup();
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
      })
    );

    render(
      <KeywordStep
        customization="한국 게임 쇼츠 중심"
        onCustomizationChange={vi.fn()}
        onTrendPicked={vi.fn()}
        selectedTrend={null}
      />
    );

    await user.type(screen.getByLabelText("키워드"), "게임");
    await user.click(screen.getByRole("button", { name: "후보 검색" }));

    expect(await screen.findByText("신작 게임 업데이트 보상 정리와 반응")).toBeTruthy();
  });

  it("passes selected trend to the parent flow", async () => {
    const user = userEvent.setup();
    const onTrendPicked = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          source: "sample",
          items: [
            {
              video_id: "sample-news-001",
              title: "오늘 한국에서 화제 된 생활 뉴스 세 가지",
              category_id: "25",
              channel_title: "요약 뉴스룸",
              view_count: 480000,
              views_per_hour: 240000,
              score: 240020,
              keyword_candidates: ["한국", "뉴스"],
              thumbnail_url: "",
            },
          ],
        }),
      })
    );

    render(
      <KeywordStep
        customization="뉴스형 쇼츠"
        onCustomizationChange={vi.fn()}
        onTrendPicked={onTrendPicked}
        selectedTrend={null}
      />
    );

    await user.click(screen.getByRole("button", { name: "후보 검색" }));
    await user.click(await screen.findByRole("button", { name: "이 후보로 대본 만들기" }));

    expect(onTrendPicked).toHaveBeenCalledWith(
      expect.objectContaining({ video_id: "sample-news-001" }),
      expect.objectContaining({ id: "25", label: "뉴스" })
    );
  });
});
