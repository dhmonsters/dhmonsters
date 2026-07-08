// 편집 미리보기 컴포넌트의 기본 렌더링과 타임라인 선택을 검증한다.
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { GrowthAssistantPanel } from "../src/components/GrowthAssistantPanel";
import { GrowthReportPage } from "../src/pages/GrowthReportPage";
import { ShortsCanvas } from "../src/components/ShortsCanvas";
import { Timeline } from "../src/components/Timeline";

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
          { index: 1, subtitle: "첫 장면", motion_type: "zoom" },
          { index: 2, subtitle: "둘째 장면", motion_type: "fade" },
        ]}
        selectedSceneIndex={1}
        onSelectScene={onSelectScene}
      />,
    );

    await user.click(screen.getByRole("button", { name: "장면 2" }));
    expect(onSelectScene).toHaveBeenCalledWith(2);
  });

  it("renders growth assistant notes and recommendations", () => {
    render(
      <GrowthAssistantPanel notes={["CTR 개선"]} recommendations={["추천 문구를 앞부분으로 이동"]} />,
    );

    expect(screen.getByText("CTR 개선")).toBeTruthy();
    expect(screen.getByText("추천 문구를 앞부분으로 이동")).toBeTruthy();
  });

  it("shows the growth report copy", () => {
    render(<GrowthReportPage />);

    expect(
      screen.getByText("10분, 30분, 1시간, 24시간, 7일 단위 성과를 비교해 원인 후보를 좁힙니다."),
    ).toBeTruthy();
  });
});
