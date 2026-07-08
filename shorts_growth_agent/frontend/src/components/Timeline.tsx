// 장면별 타임라인 선택 컴포넌트다.
type SceneMeta = {
  index: number;
  subtitle: string;
  duration_ms?: number;
  motion_type?: string;
};

export function Timeline({
  scenes,
  selectedSceneIndex,
  onSelectScene,
}: {
  scenes: SceneMeta[];
  selectedSceneIndex: number;
  onSelectScene: (index: number) => void;
}) {
  return (
    <section aria-label="장면 타임라인" className="timeline">
      {scenes.map((scene) => (
        <button
          key={scene.index}
          type="button"
          className="timeline-item"
          aria-current={scene.index === selectedSceneIndex ? "true" : undefined}
          onClick={() => onSelectScene(scene.index)}
        >
          장면 {scene.index}
        </button>
      ))}
    </section>
  );
}
