// 대본 하네스와 장면 대본을 편집하는 화면이다.
import { SectionCustomizer } from "../components/SectionCustomizer";
import type { ScriptPlan } from "../state/projectStore";

export function ScriptStep({
  customization,
  onCustomizationChange,
  scriptPlan,
}: {
  customization: string;
  onCustomizationChange: (value: string) => void;
  scriptPlan: ScriptPlan | null;
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
      <div className="script-scenes">
        {(scriptPlan?.scenes ?? []).map((scene) => (
          <article key={scene.index} className="script-scene">
            <strong>장면 {scene.index}</strong>
            <p>{scene.subtitle}</p>
          </article>
        ))}
        {!scriptPlan && <p className="empty-text">트렌드 후보를 선택하면 대본 초안이 표시됩니다.</p>}
      </div>
    </section>
  );
}
