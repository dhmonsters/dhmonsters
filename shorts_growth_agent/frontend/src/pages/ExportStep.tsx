// MP4 렌더링과 업로드 패키지를 만드는 화면이다.
import { SectionCustomizer } from "../components/SectionCustomizer";

export function ExportStep({
  customization,
  onCustomizationChange,
}: {
  customization: string;
  onCustomizationChange: (value: string) => void;
}) {
  return (
    <section className="step-panel" aria-label="출력 단계">
      <div className="step-heading">
        <p className="eyebrow">출력 준비</p>
        <h1>업로드 전 체크 기준을 정리합니다</h1>
      </div>
      <SectionCustomizer
        title="출력·분석 설정"
        value={customization}
        onChange={onCustomizationChange}
        placeholder="예: 첫 30분 CTR 우선 확인, 제목 후보 3개 저장"
      />
    </section>
  );
}
