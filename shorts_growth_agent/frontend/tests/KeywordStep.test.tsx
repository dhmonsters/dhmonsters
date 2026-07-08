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
        onTrendInspect={vi.fn()}
        onTrendPicked={vi.fn()}
        selectedTrend={null}
        trendAnalysis={null}
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
        onTrendInspect={vi.fn()}
        onTrendPicked={onTrendPicked}
        selectedTrend={null}
        trendAnalysis={null}
      />
    );

    await user.click(screen.getByRole("button", { name: "후보 검색" }));
    await user.click(await screen.findByRole("button", { name: "이 후보로 대본 만들기" }));

    expect(onTrendPicked).toHaveBeenCalledWith(
      expect.objectContaining({ video_id: "sample-news-001" }),
      expect.objectContaining({ id: "25", label: "뉴스" })
    );
  });

  it("passes candidate to detail analysis and shows analysis panel", async () => {
    const user = userEvent.setup();
    const onTrendInspect = vi.fn();
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
        customization="게임형 쇼츠"
        onCustomizationChange={vi.fn()}
        onTrendInspect={onTrendInspect}
        onTrendPicked={vi.fn()}
        selectedTrend={null}
        trendAnalysis={{
          video_id: "sample-game-001",
          title: "신작 게임 업데이트 보상 정리와 반응",
          summary: "게임 쇼츠 소재로 분석했습니다.",
          production_angles: ["보상 비교", "반응 정리", "체크리스트"],
          risk_level: "주의",
          risk_notes: ["직접 확인한 소스만 사용"],
          script_seed: "게임 업데이트 보상",
          recommended_harness: {
            tone: "명료",
            hook_strength: "강함",
            target_seconds: 30,
            forbidden_terms: ["100%"],
          },
        }}
      />
    );

    await user.click(await screen.findByRole("button", { name: "상세 분석" }));

    expect(onTrendInspect).toHaveBeenCalledWith(
      expect.objectContaining({ video_id: "sample-game-001" })
    );
    expect(screen.getByText("후보 상세 분석")).toBeTruthy();
    expect(screen.getByText("보상 비교")).toBeTruthy();
  });
});
