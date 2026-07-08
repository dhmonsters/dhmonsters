// 쇼츠 장면과 레이어를 편집하는 화면이다.
import { SectionCustomizer } from "../components/SectionCustomizer";

export function EditorStep({
  customization,
  onCustomizationChange,
}: {
  customization: string;
  onCustomizationChange: (value: string) => void;
}) {
  return (
    <section className="step-panel" aria-label="편집 단계">
      <div className="step-heading">
        <p className="eyebrow">화면 편집</p>
        <h1>9:16 화면과 장면 움직임을 조정합니다</h1>
      </div>
      <SectionCustomizer
        title="화면·모션 설정"
        value={customization}
        onChange={onCustomizationChange}
        placeholder="예: 이미지 흔들림, 손 모양 포인트, 빠른 컷 전환"
      />
    </section>
  );
}
