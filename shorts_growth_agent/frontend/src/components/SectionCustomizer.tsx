// 제작 단계별 커스터마이징 입력 패널입니다.
export function SectionCustomizer({
  title,
  value,
  onChange,
  placeholder,
}: {
  title: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}) {
  return (
    <details className="section-customizer" open>
      <summary>{title}</summary>
      <label className="field">
        <span>커스터마이징</span>
        <textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          rows={4}
        />
      </label>
    </details>
  );
}
