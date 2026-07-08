// 9:16 쇼츠 미리보기 캔버스 컴포넌트다.
type SceneData = {
  subtitle: string;
  motion_type?: string;
  source_type?: string;
};

export function ShortsCanvas({ scene }: { scene: SceneData | null }) {
  return (
    <section aria-label="쇼츠 미리보기" className="shorts-canvas">
      <div className="phone-frame">
        <div className="scene-source">{scene?.source_type ?? "ai_image"}</div>
        <strong className="scene-subtitle">{scene?.subtitle ?? "장면을 선택하세요"}</strong>
        {scene?.motion_type ? <p className="scene-motion">{scene.motion_type}</p> : null}
      </div>
    </section>
  );
}
