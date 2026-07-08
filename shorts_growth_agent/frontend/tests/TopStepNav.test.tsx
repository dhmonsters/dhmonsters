// 상단 단계 표시 UI가 현재 단계를 표시하는지 검증한다.
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { TopStepNav } from "../src/components/TopStepNav";

describe("TopStepNav", () => {
  it("marks the current step", () => {
    render(<TopStepNav currentStep="script" onStepChange={vi.fn()} />);

    expect(screen.getByRole("button", { name: "대본" }).getAttribute("aria-current")).toBe(
      "step"
    );
  });

  it("calls onStepChange when selecting another step", async () => {
    const user = userEvent.setup();
    const onStepChange = vi.fn();

    render(<TopStepNav currentStep="keyword" onStepChange={onStepChange} />);

    await user.click(screen.getByRole("button", { name: "대본" }));
    expect(onStepChange).toHaveBeenCalledWith("script");
  });
});
