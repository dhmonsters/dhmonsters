// 대본 하네스와 장면 대본을 편집하는 화면이다.
import { SectionCustomizer } from "../components/SectionCustomizer";
import type { ScriptPlan } from "../state/projectStore";
import type { HarnessSettings } from "../types";

export function ScriptStep({
  customization,
  onCustomizationChange,
  harness,
  onHarnessChange,
  scriptPlan,
  onSceneSubtitleChange,
  onSceneRegenerate,
  onSceneMove,
}: {
  customization: string;
  onCustomizationChange: (value: string) => void;
  harness: HarnessSettings;
  onHarnessChange: (harness: Partial<HarnessSettings>) => void;
  scriptPlan: ScriptPlan | null;
  onSceneSubtitleChange: (index: number, subtitle: string) => void;
  onSceneRegenerate: (index: number) => void;
  onSceneMove: (index: number, direction: "up" | "down") => void;
}) {
  return (
    <section className="step-panel" aria-label="대본 단계">
      <div className="step-heading">
        <p className="eyebrow">대본 하네스</p>
        <h1>장면별 대본을 고정된 방향으로 만듭니다</h1>
      </div>
      <SectionCustomizer
        title="대본 방향 설정"
        value={customization}
        onChange={onCustomizationChange}
        placeholder="예: 첫 2초 질문형 훅, 문장 짧게, 과장 표현 제외"
      />
      <section className="harness-panel" aria-label="대본 하네스 상세 설정">
        <label className="field">
          <span>하네스 이름</span>
          <input
            value={harness.name}
            onChange={(event) => onHarnessChange({ name: event.target.value })}
          />
        </label>
        <label className="field">
          <span>말투</span>
          <select
            value={harness.tone}
            onChange={(event) => onHarnessChange({ tone: event.target.value })}
          >
            <option value="명료">명료</option>
            <option value="친근">친근</option>
            <option value="긴박">긴박</option>
            <option value="차분">차분</option>
          </select>
        </label>
        <label className="field">
          <span>훅 강도</span>
          <select
            value={harness.hook_strength}
            onChange={(event) => onHarnessChange({ hook_strength: event.target.value })}
          >
            <option value="강함">강함</option>
            <option value="중간">중간</option>
            <option value="낮음">낮음</option>
          </select>
        </label>
        <label className="field">
          <span>목표 길이</span>
          <input
            type="number"
            min="15"
            max="60"
            value={harness.target_seconds}
            onChange={(event) => onHarnessChange({ target_seconds: Number(event.target.value) })}
          />
        </label>
        <label className="field">
          <span>금지어</span>
          <input
            value={harness.forbidden_terms.join(", ")}
            onChange={(event) =>
              onHarnessChange({
                forbidden_terms: event.target.value
                  .split(",")
                  .map((term) => term.trim())
                  .filter(Boolean),
              })
            }
          />
        </label>
        <label className="field">
          <span>추가 지시</span>
          <textarea
            value={harness.custom_prompt}
            onChange={(event) => onHarnessChange({ custom_prompt: event.target.value })}
            rows={3}
            placeholder="예: 첫 장면은 보상부터 말하기"
          />
        </label>
      </section>
      <div className="script-scenes">
        {(scriptPlan?.scenes ?? []).map((scene) => (
          <article key={scene.index} className="script-scene">
            <strong>장면 {scene.index}</strong>
            <label className="field">
              <span>장면 {scene.index} 대본</span>
              <textarea
                value={scene.subtitle}
                onChange={(event) => onSceneSubtitleChange(scene.index, event.target.value)}
                rows={3}
              />
            </label>
            <p className="scene-asset-note">
              소스 {scene.source_type ?? "ai_image"} · 모션 {scene.motion_type ?? "none"}
            </p>
            <div className="button-row">
              <button
                type="button"
                className="secondary-button"
                onClick={() => onSceneRegenerate(scene.index)}
              >
                다시 생성
              </button>
              <button
                type="button"
                className="secondary-button"
                onClick={() => onSceneMove(scene.index, "up")}
              >
                위로
              </button>
              <button
                type="button"
                className="secondary-button"
                onClick={() => onSceneMove(scene.index, "down")}
              >
                아래로
              </button>
            </div>
          </article>
        ))}
        {!scriptPlan && <p className="empty-text">트렌드 후보를 선택하면 대본 초안이 표시됩니다.</p>}
      </div>
    </section>
  );
}
