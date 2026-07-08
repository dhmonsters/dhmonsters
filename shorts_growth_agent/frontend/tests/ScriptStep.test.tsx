// 대본 단계의 하네스 편집과 장면 편집 동작을 검증합니다.
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { ScriptStep } from "../src/pages/ScriptStep";
import type { ScriptPlan } from "../src/state/projectStore";
import type { HarnessSettings } from "../src/types";

describe("ScriptStep", () => {
  it("edits harness fields and script scenes", async () => {
    const user = userEvent.setup();
    const onHarnessChange = vi.fn();
    const onSceneSubtitleChange = vi.fn();
    const onSceneRegenerate = vi.fn();
    const onSceneMove = vi.fn();

    function ScriptStepHarness() {
      const [harness, setHarness] = useState<HarnessSettings>({
          name: "게임 반응형",
          tone: "명료",
          hook_strength: "강함",
          target_seconds: 30,
          forbidden_terms: ["100%"],
          custom_prompt: "",
        });
      const [scriptPlan, setScriptPlan] = useState<ScriptPlan>({
        keyword: "게임",
        scenes: [
          { index: 1, subtitle: "첫 장면" },
          { index: 2, subtitle: "둘째 장면" },
        ],
      });
      return (
        <ScriptStep
          customization="강한 훅"
          onCustomizationChange={vi.fn()}
          harness={harness}
          onHarnessChange={(next) => {
            onHarnessChange(next);
            setHarness((current) => ({ ...current, ...next }));
          }}
          scriptPlan={scriptPlan}
          onSceneSubtitleChange={(index, subtitle) => {
            onSceneSubtitleChange(index, subtitle);
            setScriptPlan((current) => ({
              ...current,
              scenes: current.scenes.map((scene) =>
                scene.index === index ? { ...scene, subtitle } : scene,
              ),
            }));
          }}
          onSceneRegenerate={onSceneRegenerate}
          onSceneMove={onSceneMove}
        />
      );
    }

    render(<ScriptStepHarness />);

    await user.selectOptions(screen.getByLabelText("말투"), "친근");
    await user.clear(screen.getByLabelText("장면 1 대본"));
    await user.type(screen.getByLabelText("장면 1 대본"), "수정한 첫 장면");
    await user.click(screen.getAllByRole("button", { name: "다시 생성" })[0]);
    await user.click(screen.getAllByRole("button", { name: "아래로" })[0]);

    expect(onHarnessChange).toHaveBeenCalledWith({ tone: "친근" });
    expect(onSceneSubtitleChange).toHaveBeenCalledWith(1, "수정한 첫 장면");
    expect(onSceneRegenerate).toHaveBeenCalledWith(1);
    expect(onSceneMove).toHaveBeenCalledWith(1, "down");
  });
});
