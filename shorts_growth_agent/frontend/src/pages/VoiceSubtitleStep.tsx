// TTS와 자막 싱크를 조정하는 화면이다.
import { SectionCustomizer } from "../components/SectionCustomizer";

export function VoiceSubtitleStep({
  customization,
  onCustomizationChange,
}: {
  customization: string;
  onCustomizationChange: (value: string) => void;
}) {
  return (
    <section className="step-panel" aria-label="음성 자막 단계">
      <div className="step-heading">
        <p className="eyebrow">TTS와 자막</p>
        <h1>목소리 속도와 자막 스타일을 맞춥니다</h1>
      </div>
      <SectionCustomizer
        title="음성·자막 설정"
        value={customization}
        onChange={onCustomizationChange}
        placeholder="예: 빠른 여성 목소리, 자막 하단 중앙, 글꼴 크게"
      />
    </section>
  );
}
