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

export type HarnessSettings = {
  name: string;
  tone: string;
  hook_strength: string;
  target_seconds: number;
  forbidden_terms: string[];
  custom_prompt: string;
};

export type TrendAnalysis = {
  video_id: string;
  title: string;
  summary: string;
  production_angles: string[];
  risk_level: "낮음" | "주의" | "높음";
  risk_notes: string[];
  script_seed: string;
  recommended_harness: Omit<HarnessSettings, "name" | "custom_prompt">;
};

export type SectionCustomization = Record<StepId, string>;
