// 쇼츠 제작 단계와 트렌드 후보 타입을 정의한다.
export type StepId = "keyword" | "script" | "voice" | "editor" | "export";

export type TrendCandidate = {
  video_id: string;
  title: string;
  category_id: string;
  channel_title: string;
  view_count: number;
  views_per_hour: number;
  score: number;
  keyword_candidates: string[];
  thumbnail_url: string;
};

export type TrendCategory = {
  id: string;
  label: string;
};

export type SectionCustomization = Record<StepId, string>;
