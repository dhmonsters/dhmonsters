// 백엔드 API 호출을 담당하는 클라이언트 유틸입니다.
import type { HarnessSettings, TrendAnalysis, TrendCandidate } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api";

export type TrendSearchParams = {
  region?: string;
  category_id?: string;
  keyword?: string;
};

export type TrendSearchResponse = {
  region: string;
  category_id: string | null;
  keyword: string | null;
  source: "youtube" | "sample" | "sample_fallback";
  items: TrendCandidate[];
};

export async function fetchTrendCandidates(
  params: TrendSearchParams,
): Promise<TrendSearchResponse> {
  const searchParams = new URLSearchParams();
  searchParams.set("region", params.region ?? "KR");
  if (params.category_id) searchParams.set("category_id", params.category_id);
  if (params.keyword) searchParams.set("keyword", params.keyword);

  const response = await fetch(`${API_BASE}/trends?${searchParams.toString()}`);
  if (!response.ok) throw new Error("트렌드 후보를 불러오지 못했습니다.");
  return response.json();
}

export async function analyzeTrendCandidate(candidate: TrendCandidate): Promise<TrendAnalysis> {
  const response = await fetch(`${API_BASE}/trends/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(candidate),
  });
  if (!response.ok) throw new Error("후보 상세 분석에 실패했습니다.");
  return response.json();
}

export async function createProject(payload: {
  title: string;
  category: string;
  selected_keyword?: string;
}) {
  const response = await fetch(`${API_BASE}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("프로젝트 생성에 실패했습니다.");
  return response.json();
}

export async function generatePlan(
  projectId: number,
  payload?: {
    harness?: HarnessSettings;
    trend_analysis?: { primary_angle?: string; script_seed?: string };
  },
) {
  const response = await fetch(`${API_BASE}/projects/${projectId}/generate-plan`, {
    method: "POST",
    headers: payload ? { "Content-Type": "application/json" } : undefined,
    body: payload ? JSON.stringify(payload) : undefined,
  });
  if (!response.ok) throw new Error("대본 계획 생성에 실패했습니다.");
  return response.json();
}
