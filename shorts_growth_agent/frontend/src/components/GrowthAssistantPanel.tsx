// 성장 메모리와 AI 보조 제안을 보여주는 패널이다.
export function GrowthAssistantPanel({
  notes,
  recommendations,
}: {
  notes: string[];
  recommendations: string[];
}) {
  return (
    <aside aria-label="AI 보조와 성장 메모리" className="growth-panel">
      <h2>성장 메모리</h2>
      <ul>{notes.map((note) => <li key={note}>{note}</li>)}</ul>

      <h2>다음 제안</h2>
      <ul>{recommendations.map((item) => <li key={item}>{item}</li>)}</ul>
    </aside>
  );
}
